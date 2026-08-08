# Change History

This file records user-facing Code Server changes. Keep historical
implementation notes here instead of expanding the marketplace description.

## Unreleased

- Initial port from the `agentic-workspace` monolith's code-server
  integration (`src/api/routes/code_server.py`, `src/mcp/vscode.py`,
  `tools/code-server/`) onto the decoupled `aw-app-*` framework as a Tier-2
  container app.
- Added the `aw-vscode` skill so an agent knows when/how to open a file in
  the embedded editor.
- Workspace repos mount read-only (`$AW_WORKSPACE_REPOS` volume
  constraint) — a narrower guarantee than the monolith's read-write bind;
  called out in the MCP tool description and the skill.
