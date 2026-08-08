"""Unit tests for mcp_server/server.py's path translation and URL building —
no running workspace or container needed."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_server import server  # noqa: E402


def test_relative_path_resolves_against_workspace_repos_host():
    container = server._to_container_path("aw-backend/src/api/app.py", None)
    assert container == "/home/coder/project/aw-backend/src/api/app.py"


def test_absolute_host_path_translates_into_container_mount():
    container = server._to_container_path(
        "/opt/aw-workspace/repos/aw-backend/README.md", None
    )
    assert container == "/home/coder/project/aw-backend/README.md"


def test_absolute_container_path_used_as_is():
    container = server._to_container_path("/home/coder/project/foo.py", None)
    assert container == "/home/coder/project/foo.py"


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
    assert container_file == "/home/coder/project/aw-backend/README.md"
    assert container_folder == "/home/coder/project/aw-backend"


def test_open_file_requires_file_path():
    result = server._open_file("", None)
    assert result["isError"] is True


def test_tools_list_exposes_open_file():
    result = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = [t["name"] for t in result["result"]["tools"]]
    assert names == ["open_file"]
