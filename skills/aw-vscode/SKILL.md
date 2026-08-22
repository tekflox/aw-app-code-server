---
name: aw-vscode
description: Open a file or folder in this workspace's browser-based VS Code (code-server) from an agent session — use whenever you or the user want a real editor view of a project file instead of a terminal dump, e.g. "open this in VS Code", "show me this file in the editor", "let's look at this in code-server".
---

# aw-vscode — open files in the browser-based VS Code

This workspace has a Code Server app installed (`aw-app-code-server`) — a
full VS Code running in a browser tab. It opens on the **whole workspace**
at `/opt/aw-workspace` — the same absolute path the workspace has outside
the container, so a path quoted in chat is the path the editor and its
terminal both use. The tree is mounted **read-write**; `$HOME` persists, so
extensions and CLI agent logins (`claude` / `codex` / `copilot`) survive
container recreates.

## Opening a file

Call the `open_file` MCP tool this app registers (namespaced `vscode` in
`mcp.json`):

```json
{
  "file_path": "/opt/aw-workspace/repos/aw-backend/src/api/app.py",
  "workspace": "/opt/aw-workspace/repos/aw-backend"   // optional
}
```

- `file_path` accepts any absolute path under `/opt/aw-workspace/...`
  (used as-is — inside and outside are the same path now), or a relative
  path. A relative path resolves against `workspace` if given; otherwise
  it's tried under `repos/` first and then under the workspace root, so
  both `aw-backend/src/api/app.py` and `src/apps/runtime.py` work.
- `workspace` is optional — it only roots the file-explorer pane; omit it
  to have the explorer default to the file's own parent directory.
- The tool returns a clickable URL. code-server auto-starts on first open
  if the container isn't already running (a few seconds' delay on that
  first click).

## Edits in the editor really save

The workspace mount is **read-write** (since v0.12.0). Ctrl-S in
code-server writes the real file, and a terminal opened inside it can run
git, tests, or a CLI coding agent against the actual tree.

That means the usual care applies: it is the same checkout every agent
session and the workspace itself are using, not a copy. Two things worth
knowing — `repos/` is ONE shared checkout, so an edit here can collide with
another session's work; and the mount includes `.aw-workspace/` (the
workspace `.env` and the secret store), which is now writable, not just
readable.

## When to reach for this vs. just quoting the file

Prefer a normal `Read`/inline quote when the user just needs the content
relayed conversationally (e.g. over Telegram). Reach for `open_file`
specifically when the user is at their workspace desktop and wants to
**work in an editor** — jump around a large file, use go-to-definition,
run a debugger, or hand off to a CLI coding agent already logged into that
persisted code-server profile.
