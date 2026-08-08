#!/usr/bin/env python3
"""Validates mcp.json — the file the MCP Gateway app's
``scan_app_mcp_servers()`` reads from this app's root directory (same
mcpServers shape as the in-repo project's .mcp.json: command/args/env/type).

Run with: python3 tests/validate_mcp_config.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

config = json.loads((ROOT / "mcp.json").read_text())

assert "mcpServers" in config, "mcp.json must have a top-level 'mcpServers' object"
servers = config["mcpServers"]
assert "vscode" in servers, "expected a 'vscode' server entry"

vscode = servers["vscode"]
assert vscode.get("type", "stdio") == "stdio", "vscode server must be stdio (spawned by the gateway container)"
assert vscode.get("command"), "vscode server needs a 'command'"
args = vscode.get("args", [])
assert args == ["-m", "mcp_server.server"], f"expected the mcp_server.server module, got {args!r}"

print("OK: mcp.json is structurally valid")
