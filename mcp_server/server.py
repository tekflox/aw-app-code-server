"""Stdio MCP server for the decoupled aw-app-code-server app.

Builds a deep-link URL into this app's own browser-based VS Code
(code-server) container, pointed at a specific file or folder. Ported from
agentic-workspace's ``src/mcp/vscode.py`` + ``src/api/routes/code_server.py``
onto this app's own tree, following the aw-app-presentations /
aw-app-whiteboard concept: the gateway that federates a session's tools
(``aw-app-mcp-gateway``) scans each installed app's own root ``mcp.json``
and spawns whatever it declares.

Dropped in the port (monolith-only concepts that don't apply once this
lives inside the app's own repo):
  * The ``broadcast`` / ``vscode_open_request`` WebSocket push that made the
    monolith's dashboard auto-open a popup tab. There is no equivalent
    workspace-wide ``/ws/status`` channel in the decoupled runtime — this
    tool just returns the URL; the caller (human or agent) opens it.
  * ``.tmp/awserv_api_key`` file lookup. This tool doesn't actually need to
    authenticate anywhere — the URL it builds is a plain browser link into
    this app's own reverse-proxied mount, not a workspace API call — so no
    ``X-Api-Key`` is needed at all, unlike ``aw-app-whiteboard``'s MCP.

Kept: the host/container path translation, and the ``vscode-remote:`` URI
scheme code-server's ``openFile`` action requires — a bare ``file://``
silently fails to open (same rationale as the original ``routes/skills.py``
comment this was copied from).

**Read-only caveat (new in this port):** ``aw-app.json`` mounts this
workspace's whole tree at ``/opt/aw-workspace`` **read-only**
(``$AW_WORKSPACE_ROOT`` — aw-workspace's container-volume vocabulary only
allows that mount read-only, unlike the monolith's read-write bind). Files
opened through this tool are viewable and diffable in the editor, but saves
inside code-server itself will fail; edit through the app you're already
using this session for (Bash/Edit/Write) and use code-server for reading
and reviewing.

Run: ``python -m mcp_server.server`` (stdio). Registered via this repo's
root ``mcp.json`` — the gateway spawns it with cwd set to the app root.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

# Path inside the code-server container where the workspace tree is
# bind-mounted (see aw-app.json's $AW_WORKSPACE_ROOT volume). Used to
# translate host paths (e.g. what an agent session sees at
# /opt/aw-workspace/...) into the URIs code-server's frontend can open.
#
# Deliberately the SAME absolute path the workspace has outside the
# container. It used to be /home/coder/project mapped onto the host's
# repos/ dir, which made the translation below load-bearing and meant a
# path quoted in chat was never the path the editor showed. Two roots that
# are equal make it an identity for anything under the workspace, and — the
# actual reason for the change — the editor now opens on the whole
# workspace instead of repos/ alone, so src/, skills/ and apps/ are
# reachable from the editor that is supposed to show them.
CODE_SERVER_WORKSPACE = os.environ.get(
    "AW_CODE_SERVER_WORKSPACE", "/opt/aw-workspace"
).rstrip("/")

# The host-side path that maps 1:1 onto CODE_SERVER_WORKSPACE — this
# process usually runs on the SAME machine/mount as the workspace (spawned
# by aw-app-mcp-gateway with the shared filesystem), so an agent-supplied
# absolute path under this root gets translated; anything else is treated
# as already container-relative/absolute. Override via
# AW_WORKSPACE_ROOT_HOST if that mount point ever changes.
WORKSPACE_ROOT_HOST = os.environ.get(
    "AW_WORKSPACE_ROOT_HOST",
    os.environ.get("AW_WORKSPACE_CONTAINER_DIR", "/opt/aw-workspace"),
).rstrip("/")

# Base URL this app's window is reverse-proxied under
# (aw-workspace's runtime mounts every installed app at
# /api/apps/<id>/... on the workspace's own origin — see
# docs/app-workspace-api-auth.md in aw-app-template). AW_PUBLIC_URL lets a
# deployment override this with a different externally-reachable front-end
# host if the API host and the browser-facing host ever diverge;
# AW_WORKSPACE_API_URL (published to <workspace_home>/.env at boot) is the
# next-best default; bare loopback is the last resort for same-host testing.
def _base_url() -> str:
    override = os.environ.get("AW_PUBLIC_URL")
    if override:
        return override.rstrip("/")
    external = os.environ.get("AW_WORKSPACE_API_URL") or _read_workspace_env(
        "AW_WORKSPACE_API_URL"
    )
    if external:
        return external.rstrip("/")
    return f"http://127.0.0.1:{os.environ.get('AW_PORT', '9030')}"


def _workspace_home_path() -> str:
    home = os.environ.get("AW_WORKSPACE_HOME")
    if home:
        return home
    root = os.path.realpath(os.environ.get("AW_WORKSPACE_CONTAINER_DIR", "/opt/aw-workspace"))
    return os.path.join(root, ".aw-workspace")


def _read_workspace_env(name: str) -> str | None:
    env_file = os.path.join(_workspace_home_path(), ".env")
    prefix = f"{name}="
    try:
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                if line.startswith(prefix):
                    return line[len(prefix):].strip()
    except OSError:
        return None
    return None


def _relative_base(path: str, workspace: str | None) -> Path:
    """Host-side directory a RELATIVE ``path`` is resolved against.

    Callers overwhelmingly pass a repo-relative path (``aw-backend/src/api/
    app.py``), so ``repos/`` stays the first candidate rather than the
    workspace root that is now mounted — resolving ``aw-backend/...``
    against the root yields a path that does not exist, and this app's most
    expensive failure mode is exactly that: code-server opens a blank pane
    instead of reporting the miss. The root is tried second, so
    ``src/apps/runtime.py`` (workspace-relative, and only meaningful now
    that the whole tree is visible) resolves too.

    The candidates are probed with ``path`` appended, not on their own —
    ``repos/`` always exists, so testing the bases alone would always pick
    it and the second candidate would be dead code.

    When neither candidate exists the repos/ answer wins, preserving the
    previous behaviour for a path that is wrong either way.
    """
    root = Path(WORKSPACE_ROOT_HOST)
    repos = root / "repos"
    candidates = [repos / workspace, root / workspace] if workspace else [repos, root]
    for base in candidates:
        if (base / path).exists():
            return base
    return candidates[0]


def _to_container_path(path: str, workspace: str | None) -> str:
    """Return an absolute container-side path under CODE_SERVER_WORKSPACE.

    Rules (first match wins):
      1. ``path`` already lives inside the container workspace → use as-is.
      2. ``path`` is absolute on the host under WORKSPACE_ROOT_HOST →
         translate ``/opt/aw-workspace/foo`` → ``<cs_root>/foo``. The app
         now mounts the tree at its own path, so the two roots are normally
         equal and this is an identity — kept because the env overrides
         above exist precisely so they can diverge.
      3. ``path`` is absolute but elsewhere → trust the caller; it's a
         container-absolute path.
      4. ``path`` is relative → resolve against ``workspace`` if given,
         else ``repos/`` (see ``_relative_base``), and re-translate.
    """
    if not path:
        raise ValueError("path is required")

    host_root = Path(WORKSPACE_ROOT_HOST)
    cs_root = Path(CODE_SERVER_WORKSPACE)
    p = Path(path)

    if not p.is_absolute():
        if workspace:
            base = Path(workspace)
            if base.is_absolute() and str(base).startswith(str(cs_root)):
                return str(base / path)
        joined = (_relative_base(path, workspace) / path).resolve()
        try:
            rel = joined.relative_to(host_root)
            return str(cs_root / rel)
        except ValueError:
            return str(joined)

    if str(p).startswith(str(cs_root)):
        return str(p)
    try:
        rel = p.relative_to(host_root)
        return str(cs_root / rel)
    except ValueError:
        return str(p)


def _build_url(file_path: str, workspace: str | None) -> tuple[str, str, str]:
    """Returns (url, container_file, container_folder)."""
    container_file = None
    if file_path:
        container_file = _to_container_path(file_path, workspace)

    if workspace:
        container_folder = _to_container_path(workspace, None).rstrip("/")
    elif container_file:
        container_folder = os.path.dirname(container_file) or CODE_SERVER_WORKSPACE
    else:
        container_folder = CODE_SERVER_WORKSPACE

    url = f"{_base_url()}/api/apps/code-server/?folder={quote(container_folder, safe='/')}"
    if container_file:
        file_uri = f"vscode-remote:{container_file}"
        payload_arr = json.dumps([["openFile", file_uri]], separators=(",", ":"))
        url += f"&payload={quote(payload_arr, safe='')}"

    return url, container_file, container_folder


def _tool_result(text: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def handle_request(request: dict) -> dict | None:
    method = request.get("method", "")
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "aw-vscode", "version": "1.0.0"},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "open_file",
                        "description": (
                            "Build a link to open a file (or just a folder) in "
                            "this workspace's embedded code-server (VS Code in "
                            "the browser). The workspace repos are mounted "
                            "READ-ONLY inside code-server, so use this to view "
                            "or review a file, not to save changes from "
                            "inside the editor. Returns the URL to click; the "
                            "code-server container auto-starts on first open "
                            "if it isn't already running."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": (
                                        "Path to the file. Accepts: (a) an "
                                        "absolute path under "
                                        "/opt/aw-workspace — the whole "
                                        "workspace tree is bind-mounted at "
                                        "that same path inside the editor, "
                                        "read-only; (b) a path relative to "
                                        "`workspace` if given, else "
                                        "relative to /opt/aw-workspace/repos "
                                        "and then to /opt/aw-workspace."
                                    ),
                                },
                                "workspace": {
                                    "type": "string",
                                    "description": (
                                        "Optional folder to root the file "
                                        "explorer pane at. Defaults to the "
                                        "file's parent dir."
                                    ),
                                },
                            },
                            "required": ["file_path"],
                        },
                    },
                ],
            },
        }

    if method == "tools/call":
        params = request.get("params", {}) or {}
        tool_name = params.get("name")
        args = params.get("arguments", {}) or {}

        if tool_name == "open_file":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": _open_file(args.get("file_path", ""), args.get("workspace")),
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": _tool_result(f"Unknown tool: {tool_name}", is_error=True),
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def _open_file(file_path: str, workspace: str | None) -> dict:
    if not file_path:
        return _tool_result("file_path is required.", is_error=True)

    try:
        url, container_file, _container_folder = _build_url(file_path, workspace)
    except Exception as exc:  # noqa: BLE001
        return _tool_result(f"open_file failed: {exc}", is_error=True)

    lines = [url]
    if container_file:
        lines.insert(0, f"Opened {container_file} in code-server (read-only mount):")
    return _tool_result("\n".join(lines))


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        response = handle_request(request)
        if response is None:
            continue

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
