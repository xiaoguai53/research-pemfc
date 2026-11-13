"""Execute the pinned OPEM official API, then replay saved inputs.

This is reference evidence, not production implementation. It does not use
generated wrappers or reconstruct the Amphlett scientific calculation.
"""

from __future__ import annotations

import ast
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import inspect
import json
import math
from pathlib import Path
import platform
import subprocess
import sys

from opem.Static.Amphlett import Static_Analysis


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent
SOURCE = ROOT / "repo" / "opem"
PIN = "27d343fb966361a4e6cc99650241f651778fc50f"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def compare(a: object, b: object, path: str = "result") -> int:
    """Check all values, with a tight tolerance for a deterministic replay."""
    if isinstance(a, bool) or a is None or isinstance(a, str):
        assert type(a) is type(b) and a == b, path
        return 0
    if isinstance(a, (int, float)):
        assert isinstance(b, (int, float)) and not isinstance(b, bool), path
        assert math.isfinite(a) and math.isfinite(b), path
        assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12), path
        return 1
    if isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), path
        return sum(compare(value, b[key], f"{path}.{key}") for key, value in a.items())
    if isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), path
        return sum(compare(x, y, f"{path}[{n}]") for n, (x, y) in enumerate(zip(a, b)))
    raise AssertionError(f"Unsupported reference output type at {path}: {type(a)!r}")


def execute() -> None:
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    actual_pin = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip()
    assert actual_pin == PIN
    notebook = SOURCE / "Documents" / "Amphlett.ipynb"
    cells = json.loads(notebook.read_text(encoding="utf-8"))["cells"]
    assignment = ast.parse("".join(cells[65]["source"])).body[0]
    assert isinstance(assignment, ast.Assign) and assignment.targets[0].id == "Test_Vector"
    official = ast.literal_eval(assignment.value)
    save_json(EVIDENCE / "data" / "source-cells.json", {
        "source": "Documents/Amphlett.ipynb",
        "source_sha256": sha256(notebook),
        "cell_index_convention": "zero-based",
        "cells": {str(n): "".join(cells[n]["source"]) for n in [63, 64, 65, 67, 69]},
    })
    installed_source = Path(inspect.getsourcefile(Static_Analysis))
    repo_implementation = SOURCE / "opem" / "Static" / "Amphlett.py"
    assert sha256(installed_source) == sha256(repo_implementation)
    scenarios = {
        "official": (official, "Exact official Full Run vector from notebook cell 65, also README Library example."),
        "temperature_353_15K": ({**official, "T": 353.15}, "Changed-input scenario; only operating temperature changed from official vector. Not a hardware-validated case."),
        "oxygen_partial_pressure_0_21atm": ({**official, "PO2": 0.21}, "Changed-input scenario; prescribed oxygen partial pressure 0.21 atm, not a complete humid-air or air-cooled system model."),
    }
    results = {}
    for case, (inputs, provenance) in scenarios.items():
        case_dir = EVIDENCE / "outputs" / case
        case_dir.mkdir(parents=True, exist_ok=True)
        input_file = EVIDENCE / "data" / f"{case}.json"
        save_json(input_file, inputs)
        with (case_dir / "native.log").open("w", encoding="utf-8") as log, redirect_stdout(log), redirect_stderr(log):
            native = Static_Analysis(InputMethod=deepcopy(inputs), TestMode=True, PrintMode=False, ReportMode=True, Folder=str(case_dir))
            assert native.get("Status") is True, native
            replay_inputs = json.loads(input_file.read_text(encoding="utf-8"))
            replay = Static_Analysis(InputMethod=deepcopy(replay_inputs), TestMode=True, PrintMode=False, ReportMode=False, Folder=str(case_dir))
            values_checked = compare(native, replay)
        assert len(native["I"]) == 750
        assert native["I"][0] == 0 and native["I"][-1] == 74.9
        assert all(len(native[key]) == 750 for key in ["P", "V", "EFF", "Ph", "Eta_Active", "Eta_Conc", "Eta_Ohmic", "VE"])
        save_json(case_dir / "native-result.json", native)
        save_json(case_dir / "replay-result.json", replay)
        csv_files = list(case_dir.rglob("*.csv"))
        html_files = list(case_dir.rglob("*.html"))
        opem_files = list(case_dir.rglob("*.opem"))
        assert len(csv_files) == len(html_files) == len(opem_files) == 1
        html = html_files[0].read_text(encoding="utf-8")
        assert "Voltage-Stack" in html and "Eta Active" in html and "Power(Thermal)" in html
        results[case] = {
            "provenance": provenance,
            "input_path": input_file.relative_to(ROOT).as_posix(),
            "result_path": (case_dir / "native-result.json").relative_to(ROOT).as_posix(),
            "replay_result_path": (case_dir / "replay-result.json").relative_to(ROOT).as_posix(),
            "sample_count": len(native["I"]),
            "first_current_A": native["I"][0],
            "last_current_A": native["I"][-1],
            "first_voltage_V": native["V"][0],
            "last_voltage_V": native["V"][-1],
            "max_stack_power_W": max(native["P"]),
            "native_reports": [p.relative_to(ROOT).as_posix() for p in csv_files + html_files + opem_files],
            "replay": {"passed": True, "numerical_values_checked": values_checked, "relative_tolerance": 1e-12, "absolute_tolerance": 1e-12, "reason": "Same deterministic implementation and saved input; no stochastic component or independent numerical method."},
        }
    assert results["official"]["last_voltage_V"] != results["temperature_353_15K"]["last_voltage_V"]
    assert results["official"]["last_voltage_V"] != results["oxygen_partial_pressure_0_21atm"]["last_voltage_V"]
    summary = {
        "status": "succeeded",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "repository": {"url": "https://github.com/ECSIM/opem", "commit": PIN},
        "runtime": {"python": sys.executable, "python_version": platform.python_version(), "opem_version": importlib.metadata.version("opem"), "installed_implementation": str(installed_source), "installed_implementation_sha256": sha256(installed_source)},
        "source_hashes": {p.relative_to(ROOT).as_posix(): sha256(p) for p in [notebook, repo_implementation, SOURCE / "opem" / "Functions.py", SOURCE / "opem" / "Params.py", SOURCE / "test" / "test_Amphlett.py"]},
        "scenarios": results,
        "figures": {"format": "source-native HTML chart definitions", "files": [v["native_reports"][1] for v in results.values()], "notes": "Preserved the charts generated by selected native Full Run; notebook Plot section was not selected. Raster image extraction is not applicable. HTML charts require their upstream remote JavaScript dependencies."},
    }
    save_json(EVIDENCE / "execution-summary.json", summary)
    print(json.dumps({"status": "succeeded", "scenario_count": len(results), "samples_each": 750, "summary": str(EVIDENCE / "execution-summary.json")}, indent=2))


if __name__ == "__main__":
    execute()
