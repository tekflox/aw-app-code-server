#!/usr/bin/env python3
"""Validates aw-app.json against schemas/aw-app.schema.json. Run with the
AW venv (jsonschema is installed there): .venv/aw/bin/python tests/validate_manifest.py

This test proves the manifest is structurally valid. Runtime validation needs
an AW workspace with the container runtime available.
"""
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent

manifest = json.loads((ROOT / "aw-app.json").read_text())
schema = json.loads((ROOT / "schemas" / "aw-app.schema.json").read_text())

jsonschema.validate(instance=manifest, schema=schema)

# Skills contributed by this app must exist on disk.
for skill in manifest["contributes"].get("skills", []):
    skill_path = ROOT / skill["path"]
    if not skill_path.is_file():
        print(f"FAIL: skill file missing: {skill_path}", file=sys.stderr)
        sys.exit(1)

print("OK: aw-app.json is valid and all skills exist")
