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

- **The workspace mount is read-write, at a price.** It reaches parity with
  the monolith's read-write bind, but `$AW_WORKSPACE_ROOT` at `mode: rw`
  costs the high-risk `fs:workspace-write` capability — signed/marketplace
  apps only. The first cut of this port was read-only because core had no
  capability covering a container that can rewrite core's own source, every
  app's data and the secret store; the fix was to add one, not to widen
  `fs:workspace-read`. See `mcp_server/server.py`'s module docstring and
  `skills/aw-vscode/SKILL.md`.
- **No dashboard auto-popup.** The monolith broadcast a
  `vscode_open_request` event over its own `/ws/status` so the dashboard
  auto-opened a popup tab. There's no equivalent workspace-wide channel in
  the decoupled runtime — `open_file` just returns the URL to click.
- **`$HOME` persistence** still works the same way: `aw-app.json` mounts
  `$AW_APP_DATA` (a per-app directory under the workspace's own durable
  storage tree) onto `/home/coder`, so extensions and CLI agent logins
  (`claude` / `codex` / `copilot`) survive container recreates, same as the
  monolith's `./data/code-server-data:/home/coder`.

- **It opens on the workspace root, at the workspace's own path.** The
  editor roots at `/opt/aw-workspace` and the bind-mount lands there too,
  rather than at a container-local `/home/coder/project`. That was a
  deliberate change from the first port, which mounted only `repos/`: half
  of what actually gets worked on here (`src/`, `skills/`, `apps/`) was
  unreachable from the editor meant to show it, and every path had to be
  mentally translated between what an agent quoted and what the editor
  displayed.

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
