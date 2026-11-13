"""Print local MCP configuration using the interpreter running this script."""

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=["codex", "json", "toml"], default="codex")
    args = parser.parse_args()
    # Preserve the venv interpreter path: resolving a POSIX symlink would select the system Python.
    interpreter = str(Path(sys.executable).absolute())
    server = str(Path(__file__).resolve().parents[1] / "src" / "opem_mcp.py")
    if args.client == "codex":
        command = ["codex", "mcp", "add", "fuelcell", "--", interpreter, server]
        print(subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command))
    elif args.client == "json":
        print(json.dumps({"mcpServers": {"fuelcell": {"command": interpreter, "args": [server]}}}, indent=2, ensure_ascii=False))
    else:
        print("[mcp_servers.fuelcell]")
        print("command = " + json.dumps(interpreter, ensure_ascii=False))
        print("args = " + json.dumps([server], ensure_ascii=False))


if __name__ == "__main__":
    main()
