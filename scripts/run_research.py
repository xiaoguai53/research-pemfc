"""Run non-writing research operations or a clearly labeled offline validation demo."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from research_core import data, calibration, design, evidence
from research_core.common import export_run, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["analyze", "compare", "calibrate", "design", "sensitivity", "recommend", "search", "prior-art", "demo", "export"]:
        command = sub.add_parser(name)
        if name != "export":
            command.add_argument("--output", type=Path, default=ROOT / "results" / "workbench")
        if name in ("analyze", "compare", "calibrate"):
            command.add_argument("--input", required=True)
        if name == "compare":
            command.add_argument("--metric", required=True)
            command.add_argument("--baseline", required=True)
            command.add_argument("--candidate", required=True)
            command.add_argument("--design", choices=["paired", "independent"], required=True)
            command.add_argument("--current", type=float, required=True)
            command.add_argument("--tolerance", type=float, default=.1)
        if name == "calibrate":
            command.add_argument("--config", required=True)
        if name in ("design", "sensitivity", "recommend"):
            command.add_argument("--bounds", required=True)
        if name == "design":
            command.add_argument("--samples", type=int, default=12)
            command.add_argument("--centers", type=int, default=3)
        if name == "sensitivity":
            command.add_argument("--parameters", required=True)
            command.add_argument("--current", type=float, required=True)
            command.add_argument("--base-samples", type=int, default=128)
        if name == "recommend":
            command.add_argument("--history", required=True)
            command.add_argument("--objective", required=True)
            command.add_argument("--constraint", required=True)
            command.add_argument("--upper", type=float, required=True)
            command.add_argument("--count", type=int, default=3)
        if name in ("search", "prior-art"):
            command.add_argument("--query", required=True)
        if name == "search":
            command.add_argument("--limit", type=int, default=15)
        if name == "prior-art":
            command.add_argument("--feature", action="append", required=True)
        if name == "export":
            command.add_argument("--run", required=True)
    a = parser.parse_args()
    output = str(a.output) if hasattr(a, "output") else None
    if a.command == "analyze":
        result = data.analyze_measurements(a.input, output_dir=output)
    elif a.command == "compare":
        result = data.compare_conditions(a.input, a.metric, a.baseline, a.candidate, a.design, a.current, a.tolerance, output_dir=output)
    elif a.command == "calibrate":
        result = calibration.calibrate_amphlett(a.input, a.config, output_dir=output)
    elif a.command == "design":
        result = design.generate_design(a.bounds, a.samples, a.centers, output_dir=output)
    elif a.command == "sensitivity":
        result = design.model_sensitivity(a.parameters, a.bounds, a.current, a.base_samples, output_dir=output)
    elif a.command == "recommend":
        result = design.suggest_experiments(a.history, a.bounds, a.objective, a.constraint, a.upper, a.count, output_dir=output)
    elif a.command == "search":
        result = evidence.search_literature(a.query, a.limit, output_dir=output)
    elif a.command == "prior-art":
        result = evidence.prior_art_plan(a.query, a.feature, output_dir=output)
    elif a.command == "export":
        result = {"bundle": str(export_run(a.run))}
    else:
        e = ROOT / "examples" / "workbench"
        results = {
            "data": data.analyze_measurements(str(e / "measurements-synthetic.csv"), output_dir=output),
            "comparison": data.compare_conditions(str(e / "measurements-synthetic.csv"), "net_power_W", "baseline", "candidate", "paired", 20., output_dir=output),
            "calibration": calibration.calibrate_amphlett(str(e / "polarization-synthetic.csv"), str(e / "calibration.json"), output_dir=output),
            "sensitivity": design.model_sensitivity(str(e / "model-parameters.json"), str(e / "sensitivity-bounds.json"), 40., n_base=64, output_dir=output),
            "design": design.generate_design(str(e / "experiment-bounds.json"), output_dir=output),
            "next_experiments": design.suggest_experiments(str(e / "history-synthetic.csv"), str(e / "experiment-bounds.json"), "net_power_W", "stack_temperature_C", 55., output_dir=output),
            "prior_art_plan": evidence.prior_art_plan("air cooled PEM fuel cell", ["fan control net power", "membrane water thermal management"], output_dir=output),
        }
        result = {"data_kind": "SYNTHETIC_SOFTWARE_VALIDATION_NOT_EXPERIMENTAL", "results": results}
        a.output.mkdir(parents=True, exist_ok=True)
        write_json(a.output / "demo-workflow.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
