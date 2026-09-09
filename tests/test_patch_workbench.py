"""Unit tests for container/patch-workbench.py's guard rails.

The point of that script is that it FAILS LOUDLY rather than producing an image
whose iOS keyboard suppressor is silently missing, so the failure modes are the
thing worth testing — not the happy path.

These DO run in CI: release.yml calls tekflox/aw-marketplace's shared
app-release.yml, whose "Run app tests" step does `python3 -m pytest tests/ -q`
on every push to master, before any version bump or marketplace sync. They use
nothing outside the stdlib + pytest, which is all that step installs.

The second, independent guard is the image build itself: container/Dockerfile
runs patch-workbench.py, so any of the failures below also breaks the build.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "container" / "patch-workbench.py"

# Trimmed to the parts the patcher actually asserts on.
GOOD_HTML = """<!DOCTYPE html>
<html>
\t<head><meta charset="utf-8" /></head>
\t<body aria-label=""></body>
\t<script type="module" src="{{WORKBENCH_WEB_BASE_URL}}/out/vs/code/browser/workbench/workbench.js"></script>
</html>
"""

GOOD_JS = "(function () { 'use strict'; })();\n"


def load_patcher(monkeypatch, workbench: Path, script: Path):
    """Import the hyphenated script by path and point it at a temp workbench."""
    spec = importlib.util.spec_from_file_location("patch_workbench", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["patch_workbench"] = mod
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "WORKBENCH", workbench)
    monkeypatch.setattr(mod, "SCRIPT", script)
    return mod


@pytest.fixture
def env(tmp_path, monkeypatch):
    workbench = tmp_path / "workbench.html"
    workbench.write_text(GOOD_HTML, encoding="utf-8")
    script = tmp_path / "ios-kbd-suppressor.js"
    script.write_text(GOOD_JS, encoding="utf-8")
    mod = load_patcher(monkeypatch, workbench, script)
    return mod, workbench, script


def test_injects_before_closing_html(env):
    mod, workbench, _ = env
    mod.main()
    out = workbench.read_text(encoding="utf-8")
    assert mod.MARKER in out
    assert GOOD_JS.strip() in out
    # After every startup script tag, so upstream's "do not modify order of
    # script tags!" still holds.
    assert out.index("workbench.js") < out.index(mod.MARKER)
    assert out.index(mod.MARKER) < out.index("</html>")


def test_double_patch_is_a_failure(env):
    mod, _, _ = env
    mod.main()
    with pytest.raises(SystemExit) as e:
        mod.main()
    assert e.value.code == 1


def test_missing_workbench_is_a_failure(env):
    mod, workbench, _ = env
    workbench.unlink()
    with pytest.raises(SystemExit):
        mod.main()


def test_missing_suppressor_is_a_failure(env):
    mod, _, script = env
    script.unlink()
    with pytest.raises(SystemExit):
        mod.main()


def test_unrecognised_workbench_is_a_failure(env):
    """An upstream reshuffle that leaves a different document at this path."""
    mod, workbench, _ = env
    workbench.write_text("<html><body>not the workbench</body></html>", encoding="utf-8")
    with pytest.raises(SystemExit):
        mod.main()


def test_a_new_csp_is_a_failure(env):
    """The whole design rests on there being no CSP; an inline script would
    otherwise be blocked at runtime with nothing to notice it."""
    mod, workbench, _ = env
    workbench.write_text(
        GOOD_HTML.replace(
            "<head>",
            '<head><meta http-equiv="Content-Security-Policy" content="script-src \'self\'">',
        ),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit):
        mod.main()


@pytest.mark.parametrize(
    "payload",
    [
        "var a = {{BASE}};",          # collides with code-server's templating
        "var s = '</script>';",       # closes the tag early
    ],
)
def test_unsafe_payload_is_a_failure(env, payload):
    mod, _, script = env
    script.write_text(payload, encoding="utf-8")
    with pytest.raises(SystemExit):
        mod.main()


def test_nothing_is_written_when_it_fails(env):
    mod, workbench, script = env
    script.write_text("var a = {{BASE}};", encoding="utf-8")
    before = workbench.read_text(encoding="utf-8")
    with pytest.raises(SystemExit):
        mod.main()
    assert workbench.read_text(encoding="utf-8") == before


def test_the_real_suppressor_passes_the_payload_guards(env):
    """Guards the shipped file, not a fixture — a future edit that sneaks in a
    '{{' or a literal closing script tag fails here as well as in the build."""
    mod, workbench, _ = env
    real = REPO / "container" / "ios-kbd-suppressor.js"
    mod.SCRIPT = real
    mod.main()
    assert mod.MARKER in workbench.read_text(encoding="utf-8")
