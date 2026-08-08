---
name: aw-vscode
description: Open a file or folder in this workspace's browser-based VS Code (code-server) from an agent session — use whenever you or the user want a real editor view of a project file instead of a terminal dump, e.g. "open this in VS Code", "show me this file in the editor", "let's look at this in code-server".
---

# aw-vscode — open files in the browser-based VS Code

This workspace has a Code Server app installed (`aw-app-code-server`) — a
full VS Code running in a browser tab, with this workspace's repos mounted
**read-only** at `/home/coder/project` and a persistent `$HOME` so
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

- `file_path` accepts a host path under `/opt/aw-workspace/repos/...`, a
  container path under `/home/coder/project/...`, or a path relative to
  `workspace` (or to `/opt/aw-workspace/repos` if `workspace` is omitted).
- `workspace` is optional — it only roots the file-explorer pane; omit it
  to have the explorer default to the file's own parent directory.
- The tool returns a clickable URL. code-server auto-starts on first open
  if the container isn't already running (a few seconds' delay on that
  first click).

## The read-only caveat

The workspace mount inside code-server is **read-only** — this is a
platform constraint of `aw-workspace`'s Tier-2 container volume vocabulary
(`$AW_WORKSPACE_REPOS` can only be mounted `ro`), not a code-server setting.
Use this tool to **view, diff, and review** a file with a real editor's
syntax highlighting/outline/search — keep making actual edits through
whatever tool you're already using in this session (Bash/Edit/Write), not
through code-server's own save.

## When to reach for this vs. just quoting the file

Prefer a normal `Read`/inline quote when the user just needs the content
relayed conversationally (e.g. over Telegram). Reach for `open_file`
specifically when the user is at their workspace desktop and wants to
**work in an editor** — jump around a large file, use go-to-definition,
run a debugger, or hand off to a CLI coding agent already logged into that
persisted code-server profile.
