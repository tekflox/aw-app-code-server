"""Unit tests for mcp_server/server.py's path translation and URL building —
no running workspace or container needed."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_server import server  # noqa: E402


@pytest.fixture
def fake_workspace(tmp_path, monkeypatch):
    """A workspace tree on disk, because resolving a RELATIVE path probes the
    filesystem to pick between repos/ and the root.

    Pointing WORKSPACE_ROOT_HOST at it (and leaving CODE_SERVER_WORKSPACE on
    the real /opt/aw-workspace) keeps these tests hermetic AND still
    exercises the host->container translation. Reading the real
    /opt/aw-workspace instead passes on a workspace machine and fails
    everywhere else — which is exactly how this first went red in CI.
    """
    (tmp_path / "repos" / "aw-backend" / "src" / "api").mkdir(parents=True)
    (tmp_path / "repos" / "aw-backend" / "src" / "api" / "app.py").touch()
    (tmp_path / "src" / "apps").mkdir(parents=True)
    (tmp_path / "src" / "apps" / "runtime.py").touch()
    monkeypatch.setattr(server, "WORKSPACE_ROOT_HOST", str(tmp_path))
    return tmp_path


def test_relative_path_still_resolves_against_repos(fake_workspace):
    """The editor roots at the workspace now, but a repo-relative path is
    what callers actually pass — resolving it against the root instead would
    yield a path that doesn't exist and open a blank pane, silently."""
    container = server._to_container_path("aw-backend/src/api/app.py", None)
    assert container == "/opt/aw-workspace/repos/aw-backend/src/api/app.py"


def test_workspace_relative_path_resolves_against_the_root(fake_workspace):
    """Only reachable because the whole tree is mounted: src/ is not under
    repos/, so this used to translate to a repos/src/... path that isn't
    there."""
    container = server._to_container_path("src/apps/runtime.py", None)
    assert container == "/opt/aw-workspace/src/apps/runtime.py"


def test_unresolvable_relative_path_keeps_the_repos_answer(fake_workspace):
    """Wrong under either base, so the pre-existing behaviour wins rather
    than the answer flipping on which candidate was probed last."""
    container = server._to_container_path("nope/whatever.py", None)
    assert container == "/opt/aw-workspace/repos/nope/whatever.py"


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


def test_open_file_emits_manifest_event_and_keeps_url(monkeypatch):
    emitted = []
    monkeypatch.setattr(server, "_emit_open_file", emitted.append)

    result = server._open_file(
        "/opt/aw-workspace/repos/aw-backend/README.md", None
    )

    assert result["isError"] is False
    assert emitted and emitted[0].startswith("http")
    assert emitted[0] in result["content"][0]["text"]


def test_open_file_keeps_clickable_fallback_when_event_fails(monkeypatch):
    monkeypatch.setattr(server, "_emit_open_file", lambda _url: "test failure")

    result = server._open_file(
        "/opt/aw-workspace/repos/aw-backend/README.md", None
    )

    assert result["isError"] is False
    assert "Warning: automatic window open failed" not in result["content"][0]["text"]
    assert "Warning: test failure." in result["content"][0]["text"]


def test_emit_open_file_posts_scoped_event_without_exposing_token(monkeypatch):
    captured = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(
        server,
        "_app_event_credentials",
        lambda: ("https://workspace.example/events", "awev1_secret"),
    )
    monkeypatch.setattr(server, "urlopen", fake_urlopen)

    assert server._emit_open_file("https://workspace.example/code") is None
    assert captured["url"] == "https://workspace.example/events"
    assert captured["headers"]["X-aw-app-event-token"] == "awev1_secret"
    assert captured["body"] == {
        "event": "open_file",
        "data": {"url": "https://workspace.example/code"},
    }
    assert captured["timeout"] == 5


def test_tools_list_exposes_open_file():
    result = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = [t["name"] for t in result["result"]["tools"]]
    assert names == ["open_file"]
