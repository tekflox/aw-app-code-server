# Change History

This file records user-facing Code Server changes. Keep historical
implementation notes here instead of expanding the marketplace description.

## Unreleased

- The editor no longer raises the **iOS on-screen keyboard** when the
  workspace's "suppress keyboard" toggle is on. That toggle already worked
  for the shell's own fields, but could never reach in here: this app is
  served from `code-server.app.<apex>` while the shell is at `<apex>`, so
  the iframe is cross-origin and `contentDocument` is blocked. The image now
  bakes a suppressor into code-server's own `workbench.html`, and the shell
  tells it the toggle state over `postMessage`.
- The mechanism is `readonly` on VS Code's editor textarea (and the
  integrated terminal's), which keeps the keyboard down while still
  delivering hardware keydown — so every VS Code keybinding (arrows, Enter,
  Backspace, chords, Cmd+S) keeps running through VS Code's own untouched
  path. Only printable-character insertion is re-implemented, because
  `readonly` suppresses the `input` event VS Code reads from.
- **Trade-off, deliberately not hidden:** a readonly textarea cannot do IME
  composition, so dead-key/accented input (Portuguese `á`, `ã`) is affected
  while suppression is ON. Turning the toggle off restores it immediately.
- Modern VS Code picks between two editor input implementations at runtime
  and prefers `EditContext` wherever the browser has it — which produces a
  `div.native-edit-context` and **no textarea at all**, making the readonly
  mechanism a silent no-op. The suppressor therefore removes
  `globalThis.EditContext` before the workbench boots, forcing the textarea
  path. It only does so on phone-class devices, or where suppression has
  been used before, so a desktop user keeps the newer input path.
- The patch is applied at **image build time** and the build FAILS if it
  does not match — a `codercom/code-server:latest` bump that moves,
  restructures or CSP-hardens `workbench.html` would otherwise produce a
  healthy image whose suppressor is silently absent.

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
