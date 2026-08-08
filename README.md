# aw-app-code-server

VS Code in the browser (`codercom/code-server`) for `aw-workspace`. A
Tier-2 (container) port of the `agentic-workspace` monolith's code-server
integration:

| Monolith | This app |
|---|---|
| `tools/code-server/Dockerfile` + `seed-extensions.sh` | `container/Dockerfile` + `container/seed-extensions.sh` (same base image, same baked extensions) |
| `src/config/aw.json`'s `docker_services.code-server` (image, args, volumes) | `aw-app.json`'s `runtime` block; the `--bind-addr`/`--auth none` args are now baked into the image's `ENTRYPOINT`/`CMD` since Tier-2 apps here only ever run `docker run <image>` with no extra args |
| `src/api/routes/code_server.py` (`POST /api/code-server/open`, host↔container path translation, auto-start) | `mcp_server/server.py`'s `open_file` tool — same path translation, no separate HTTP route needed (the URL is built entirely client-side; auto-start is the framework's own `auto_start: true` config) |
| `src/mcp/vscode.py` (stdio MCP, `open_file` tool) | `mcp_server/server.py`, registered via this repo's own `mcp.json` |
| *(no dedicated skill in the monolith)* | `skills/aw-vscode/SKILL.md` — new, teaches an agent when/how to use `open_file` |

## What's different from the monolith

- **The workspace mount is read-only.** `aw-workspace`'s Tier-2 container
  volume vocabulary (`$AW_WORKSPACE_REPOS`) only allows mounting the
  workspace's repos **read-only** — the monolith bind-mounted its whole
  project directory read-write. Use code-server here to view/review/diff
  and to run a real editor's tooling (go-to-definition, search, a CLI
  agent's terminal); keep making actual edits through whatever tool your
  agent session is already using. See `mcp_server/server.py`'s module
  docstring and `skills/aw-vscode/SKILL.md` for the full rationale.
- **No dashboard auto-popup.** The monolith broadcast a
  `vscode_open_request` event over its own `/ws/status` so the dashboard
  auto-opened a popup tab. There's no equivalent workspace-wide channel in
  the decoupled runtime — `open_file` just returns the URL to click.
- **`$HOME` persistence** still works the same way: `aw-app.json` mounts
  `$AW_APP_DATA` (a per-app directory under the workspace's own durable
  storage tree) onto `/home/coder`, so extensions and CLI agent logins
  (`claude` / `codex` / `copilot`) survive container recreates, same as the
  monolith's `./data/code-server-data:/home/coder`.

## Layout

- `aw-app.json` — the manifest (`id: code-server`, `tier: container`).
- `container/Dockerfile` — the code-server image (same base + extensions as
  the monolith), published by `.github/workflows/build.yml` to
  `ghcr.io/tekflox/aw-app-code-server`.
- `container/seed-extensions.sh` — copies build-time-baked extensions into
  the mounted (and otherwise-shadowing) `$HOME` on first boot.
- `mcp.json` — registers the `vscode` stdio MCP server
  (`mcp_server/server.py`) with `aw-mcp-gateway`'s app scan.
- `mcp_server/server.py` — the `open_file` MCP tool: host/container path
  translation + the `vscode-remote:` deep-link URL code-server's
  `openFile` action requires.
- `skills/aw-vscode/SKILL.md` — teaches an agent when to reach for
  `open_file` vs. just relaying file contents inline.
- `schemas/aw-app.schema.json` — local structural validator, same schema
  every `aw-app-*` repo validates against.
- `tests/validate_manifest.py` — schema + skills-exist check.
- `tests/validate_mcp_config.py` — structural check of `mcp.json`.
- `tests/test_mcp_server.py` — unit tests for the path-translation/URL
  logic (no running workspace needed).

## Install

```
aw-workspace-cli marketplace install code-server
```

## CI/CD

`tests/validate_manifest.py` and `tests/test_*.py` run in
`tekflox/aw-marketplace`'s shared `app-release.yml` reusable workflow on
every push to `master` — a failure stops the release before any version
bump, tag, or marketplace catalog sync happens. `.github/workflows/build.yml`
builds and pushes the container image (manual `workflow_dispatch`, or
automatically on a release-bump push).
