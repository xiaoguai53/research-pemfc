from pathlib import Path
import json
import importlib.util

import numpy as np
import pandas as pd
from fastmcp import Client

from research_mcp import mcp

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "examples/workbench"
REFERENCE = ROOT / "notebooks/workbench-v2/reference"
spec = importlib.util.spec_from_file_location("native_workbench_reference", REFERENCE / "execute_reference.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def load(path):
    return json.loads(Path(path).read_text())


def dump(path, value):
    Path(path).write_text(json.dumps(value, allow_nan=False))
    return str(path)


def artifact(result, name):
    matches = [Path(a["path"]) for a in result["artifacts"] if Path(a["path"]).name == name]
    assert len(matches) == 1
    return matches[0]


async def call(tool, arguments):
    async with Client(mcp) as client:
        response = await client.call_tool(tool, arguments)
        return response.data


def measured_frame():
    return pd.read_csv(EXAMPLES / "measurements-synthetic.csv", dtype={"replicate_id": str, "condition": str})


def flat_native(p):
    mapping = {"temperature_K": "T", "hydrogen_partial_pressure_atm": "PH2", "oxygen_partial_pressure_atm": "PO2",
               "active_area_cm2": "A", "membrane_thickness_cm": "l", "membrane_water_content": "lambda",
               "cell_count": "N", "max_current_density_A_cm2": "JMax", "electronic_resistance_ohm": "R"}
    return {k: p[v] for k, v in mapping.items()}
