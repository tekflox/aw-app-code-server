#!/usr/bin/env python3
"""Bake container/ios-kbd-suppressor.js into code-server's workbench.html.

Run at IMAGE BUILD TIME (see container/Dockerfile). The iframe that hosts
code-server in the workspace shell is cross-origin, so the shell cannot inject
anything into this document at runtime — the suppressor has to already be in
the page that code-server serves.

THIS SCRIPT EXITS NON-ZERO ON ANY SURPRISE, ON PURPOSE.

The thing being patched is a vendored upstream file that a
`codercom/code-server:latest` bump can move, rename or CSP-harden at any time.
Every one of those changes would leave the suppressor absent or blocked with no
error at runtime: the editor would simply keep raising the iOS keyboard, months
later, with nobody able to tell why. A failed image build is loud; a silently
dead feature is not. So a no-match is a build failure, never a warning.
"""

import sys
from pathlib import Path

WORKBENCH = Path(
    "/usr/lib/code-server/lib/vscode/out/vs/code/browser/workbench/workbench.html"
)
SCRIPT = Path(__file__).with_name("ios-kbd-suppressor.js")

# Injected right before </html>, i.e. after every startup script tag, so the
# "do not modify order of script tags!" comment upstream carries is respected.
# The suppressor is a CLASSIC inline script while workbench.js is a module, so
# it still executes first (modules are deferred) — which is what lets it remove
# globalThis.EditContext before VS Code probes for it.
ANCHOR = "</html>"
MARKER = "aw-ios-kbd-suppressor"

# Proof we are patching the file we think we are, not some other workbench.html
# that happens to exist at this path after an upstream reshuffle.
EXPECT = "out/vs/code/browser/workbench/workbench.js"


def fail(msg: str) -> "NoReturn":  # noqa: F821
    print(f"patch-workbench: FAILED: {msg}", file=sys.stderr)
    print(
        "patch-workbench: refusing to produce an image whose iOS keyboard "
        "suppressor is silently absent.",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    if not WORKBENCH.is_file():
        fail(f"{WORKBENCH} does not exist (upstream moved it?)")
    if not SCRIPT.is_file():
        fail(f"{SCRIPT} is missing from the build context")

    html = WORKBENCH.read_text(encoding="utf-8")
    js = SCRIPT.read_text(encoding="utf-8")

    if MARKER in html:
        fail("workbench.html already carries the suppressor — double patch")
    if EXPECT not in html:
        fail(
            f"{WORKBENCH} does not reference {EXPECT!r}; this is not the "
            "workbench document this patch was written against"
        )
    if html.count(ANCHOR) != 1:
        fail(f"expected exactly one {ANCHOR!r} anchor, found {html.count(ANCHOR)}")

    # A CSP would block an inline script without raising anything the build or
    # the runtime could notice — the feature would just be gone. Verified absent
    # in code-server 4.135.0 (no meta tag here, and no CSP response header on
    # `/`); assert it so a future hardening release fails here instead.
    lowered = html.lower()
    if "content-security-policy" in lowered:
        fail(
            "workbench.html now carries a Content-Security-Policy; an inline "
            "script would be blocked at runtime with no error. Serve the "
            "suppressor as a file and add its hash/nonce instead."
        )

    # The document is templated by code-server with {{TOKEN}} placeholders, so
    # the payload must not smuggle a brace pair of its own, and must not close
    # the script element early.
    if "{{" in js or "}}" in js:
        fail("suppressor contains '{{' or '}}' — would collide with templating")
    if "</script" in js.lower():
        fail("suppressor contains a literal '</script' — would close the tag early")

    block = (
        f"\t<!-- {MARKER}: keeps the iOS on-screen keyboard down while a "
        "Bluetooth keyboard is in use. Injected at image build time by "
        "container/patch-workbench.py. -->\n"
        f"\t<script>\n{js}\n\t</script>\n"
    )
    patched = html.replace(ANCHOR, block + ANCHOR)

    if MARKER not in patched or len(patched) <= len(html):
        fail("post-patch verification failed — nothing was written")

    WORKBENCH.write_text(patched, encoding="utf-8")
    print(
        f"patch-workbench: injected {len(js)} bytes of suppressor into "
        f"{WORKBENCH}"
    )


if __name__ == "__main__":
    main()
