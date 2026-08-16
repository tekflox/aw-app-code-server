---
repo: architecture
path: docs/architecture/aw-app-code-server.md
source: generated
edited: false
checksum: sha256:bbc5df3c10bbad8a65d47ee19b6b75ee7a41d5645be2ba3954fe95b0dbabacb0
---
# Code Server

- **repo**: aw-app-code-server
- **layer**: app-container
- **technologies**: docker
- **health** (derived): planned

VS Code in the browser (code-server), with this workspace's repos mounted read-only and a persistent $HOME so extensions and CLI agent logins (claude / codex / copilot) survive container recreates. Ported from the agentic-workspace monolith's code-server integration (src/api/routes/code_server.py, src/mcp/vscode.py, tools/code-server/).

## Connections
_none_

## MCP tools
_none exposed_

## Requirements
_none documented_
