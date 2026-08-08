#!/bin/sh
# Seed pre-baked extensions into the bind-mounted profile dir.
#
# aw-app.json mounts $AW_APP_DATA onto /home/coder — code-server's persisted
# home/profile. That mount shadows whatever the Dockerfile installed into
# ~/.local/share/code-server/extensions at build time, so extensions baked
# into the image would otherwise be silently invisible at runtime.
#
# Workaround: install build-time extensions to a SEED path that is NOT
# shadowed (/opt/code-server-extensions-seed), then on each container start
# copy any missing ones into the mounted path. User-installed extensions
# already persist because they live in the bind-mounted dir; this script
# only fills in defaults that aren't there yet, so it's idempotent and never
# clobbers a user's installation.
set -eu

SEED_DIR="/opt/code-server-extensions-seed"
TARGET_DIR="${HOME}/.local/share/code-server/extensions"

if [ ! -d "$SEED_DIR" ]; then
  exit 0
fi

mkdir -p "$TARGET_DIR"

copied=0
for ext in "$SEED_DIR"/*/; do
  [ -d "$ext" ] || continue
  name="$(basename "$ext")"
  if [ ! -d "$TARGET_DIR/$name" ]; then
    cp -a "$ext" "$TARGET_DIR/"
    copied=$((copied + 1))
  fi
done

# Rebuild extensions.json from whatever now lives in TARGET_DIR. code-server
# reads this file as the source of truth for "what's installed"; writing it
# from the seed dir on first boot guarantees the freshly-copied extensions
# are recognized without requiring a manual reinstall.
if [ "$copied" -gt 0 ] && [ -f "$SEED_DIR/extensions.json" ]; then
  cp -a "$SEED_DIR/extensions.json" "$TARGET_DIR/extensions.json"
fi

echo "[seed-extensions] copied $copied default extension(s) into $TARGET_DIR"
