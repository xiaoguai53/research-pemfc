"""Run the verified model through MCP without requiring an AI client or API key."""

import argparse
import asyncio
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


async def run(input_path: Path, output: Path) -> dict:
    from fastmcp import Client

    sys.path.insert(0, str(ROOT / "src"))
    from tools.amphlett import amphlett_mcp

    arguments = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(arguments, dict):
        raise ValueError("The input JSON must be an object containing the tool's scalar parameters.")
    arguments["output_dir"] = str(output.resolve())
    async with Client(amphlett_mcp) as client:
        response = await client.call_tool("opem_simulate_polarization", arguments)
        return response.data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Model parameter JSON; template is documented in USAGE.md")
    parser.add_argument("--output", type=Path, default=ROOT / "results", help="Base directory; the model creates a separate directory per invocation")
    args = parser.parse_args()
    result = asyncio.run(run(args.input, args.output))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
