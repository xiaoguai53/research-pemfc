"""Print local configuration for the nine-tool research MCP server."""

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--client", choices=["codex", "json", "toml"], default="codex")
args = parser.parse_args()
interpreter = str(Path(sys.executable).absolute())
server = str(Path(__file__).resolve().parents[1] / "src" / "research_mcp.py")
if args.client == "codex":
    command = ["codex", "mcp", "add", "pemfc-research", "--", interpreter, server]
    print(subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command))
elif args.client == "json":
    print(json.dumps({"mcpServers": {"pemfc-research": {"command": interpreter, "args": [server]}}}, ensure_ascii=False, indent=2))
else:
    print("[mcp_servers.pemfc-research]")
    print("command = " + json.dumps(interpreter, ensure_ascii=False))
    print("args = " + json.dumps([server], ensure_ascii=False))
