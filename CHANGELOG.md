# Change History

This file records user-facing Code Server changes. Keep historical
implementation notes here instead of expanding the marketplace description.

## Unreleased

- The workspace mount is now **read-write**, so saving in the editor really
  writes. This reaches parity with the monolith's bind, which the port had
  given up. It costs a new high-risk capability in aw-workspace core,
  `fs:workspace-write` — the read grant was deliberately not widened,
  because reading the tree and being able to rewrite core's own source, any
  app's data or the secret store are not the same request.
- High-risk means signed/marketplace apps only, which core could not
  actually enforce here until now: volume placeholders gated on what a
  manifest *declared*, and the Tier-2 signing gate is disabled pending F8,
  so a side-loaded app would have taken the writable bind just by asking.
  Core now gates this one on the *granted* set.
- Note what the mount includes: `.aw-workspace/` (the workspace `.env` and
  the secret store) is inside it, and is now writable rather than merely
  readable.

- The editor now opens on the **whole workspace** at `/opt/aw-workspace`
  instead of on `repos/` alone at `/home/coder/project`. Two things were
  wrong with the old default: `src/`, `skills/` and `apps/` — most of what
  is actually worked on here — were not reachable from the editor at all,
  and the container-local mount path meant a path quoted in a chat was
  never the path the editor showed, so every reference had to be
  translated by hand.
- Mounting at the workspace's own absolute path makes `open_file`'s
  host↔container translation an identity for anything under the
  workspace. Relative paths still resolve under `repos/` first (that is
  what callers pass), falling back to the workspace root, so
  `aw-backend/src/api/app.py` and `src/apps/runtime.py` both work.
- Needs the `$AW_WORKSPACE_ROOT` container-volume placeholder, added to
  aw-workspace core for this. Still read-only: there is no capability in
  core's catalog covering a container that can rewrite core's own source.

- Initial port from the `agentic-workspace` monolith's code-server
  integration (`src/api/routes/code_server.py`, `src/mcp/vscode.py`,
  `tools/code-server/`) onto the decoupled `aw-app-*` framework as a Tier-2
  container app.
- Added the `aw-vscode` skill so an agent knows when/how to open a file in
  the embedded editor.
- Workspace repos mount read-only (`$AW_WORKSPACE_REPOS` volume
  constraint) — a narrower guarantee than the monolith's read-write bind;
  called out in the MCP tool description and the skill.
