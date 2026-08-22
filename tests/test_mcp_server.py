"""Unit tests for mcp_server/server.py's path translation and URL building —
no running workspace or container needed."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_server import server  # noqa: E402


def test_relative_path_still_resolves_against_repos():
    """The editor roots at the workspace now, but a repo-relative path is
    what callers actually pass — resolving it against the root instead would
    yield a path that doesn't exist and open a blank pane, silently."""
    container = server._to_container_path("aw-backend/src/api/app.py", None)
    assert container == "/opt/aw-workspace/repos/aw-backend/src/api/app.py"


def test_workspace_relative_path_resolves_against_the_root():
    """Only reachable because the whole tree is mounted: src/ is not under
    repos/, so this used to translate to a repos/src/... path that isn't
    there."""
    container = server._to_container_path("src/apps/runtime.py", None)
    assert container == "/opt/aw-workspace/src/apps/runtime.py"


def test_absolute_workspace_path_is_an_identity():
    """Same absolute path inside and outside the container — the point of
    mounting at /opt/aw-workspace rather than /home/coder/project."""
    for path in (
        "/opt/aw-workspace/repos/aw-backend/README.md",
        "/opt/aw-workspace/skills/aw-vscode/SKILL.md",
        "/opt/aw-workspace/src/apps/runtime.py",
    ):
        assert server._to_container_path(path, None) == path


def test_absolute_path_outside_the_workspace_is_trusted():
    container = server._to_container_path("/etc/hosts", None)
    assert container == "/etc/hosts"


def test_build_url_uses_vscode_remote_scheme_and_folder_param():
    os.environ["AW_PUBLIC_URL"] = "https://workspace.example.com"
    try:
        url, container_file, container_folder = server._build_url(
            "/opt/aw-workspace/repos/aw-backend/README.md", None
        )
    finally:
        del os.environ["AW_PUBLIC_URL"]

    assert url.startswith("https://workspace.example.com/api/apps/code-server/?folder=")
    assert "payload=" in url
    assert container_file == "/opt/aw-workspace/repos/aw-backend/README.md"
    assert container_folder == "/opt/aw-workspace/repos/aw-backend"


def test_build_url_defaults_the_folder_to_the_workspace_root():
    """No file, no workspace → the window opens on /opt/aw-workspace, which
    is the default this whole change exists for."""
    _, container_file, container_folder = server._build_url("", None)
    assert container_file is None
    assert container_folder == "/opt/aw-workspace"


def test_open_file_requires_file_path():
    result = server._open_file("", None)
    assert result["isError"] is True


def test_tools_list_exposes_open_file():
    result = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = [t["name"] for t in result["result"]["tools"]]
    assert names == ["open_file"]
