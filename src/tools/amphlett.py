"""Thin MCP wrapper around the pinned OPEM Amphlett Full Run API."""

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import inspect
import json
import math
from pathlib import Path
import tempfile
from threading import Lock
from typing import Annotated

from fastmcp import FastMCP
from opem import Functions
from opem.Static import Amphlett
from pydantic import BeforeValidator, Field


COMMIT = "27d343fb966361a4e6cc99650241f651778fc50f"
REFERENCE = f"https://github.com/ECSIM/opem/blob/{COMMIT}/Documents/Amphlett.ipynb"
MAX_SAMPLES = 10_000
_SOURCE_CALL_LOCK = Lock()
_ARRAY_FIELDS = ("I", "V", "P", "EFF", "Ph", "Eta_Active", "Eta_Conc", "Eta_Ohmic", "VE")
amphlett_mcp = FastMCP(name="OPEM Amphlett static PEMFC")


def _number_input(value):
    # Check raw MCP values before Pydantic can turn booleans into 0/1.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Physical numeric parameters must be numbers, not booleans or strings.")
    return value


def _integer_input(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("cell_count must be a positive integer, not a boolean, string, or float.")
    return value


@amphlett_mcp.tool()
def opem_simulate_polarization(
    temperature_K: Annotated[float, Field(description="Prescribed cell operating temperature in kelvin; not a solved stack temperature."), BeforeValidator(_number_input)],
    hydrogen_partial_pressure_atm: Annotated[float, Field(description="Hydrogen species partial pressure in atm, strictly positive."), BeforeValidator(_number_input)],
    oxygen_partial_pressure_atm: Annotated[float, Field(description="Oxygen species partial pressure in atm, not total air pressure."), BeforeValidator(_number_input)],
    active_area_cm2: Annotated[float, Field(description="Single-cell electrochemically active area in cm², strictly positive."), BeforeValidator(_number_input)],
    membrane_thickness_cm: Annotated[float, Field(description="Membrane thickness in cm, strictly positive."), BeforeValidator(_number_input)],
    membrane_water_content: Annotated[float, Field(description="Prescribed dimensionless membrane parameter lambda, from 14 through 23; not ambient RH."), BeforeValidator(_number_input)],
    cell_count: Annotated[int, Field(description="Positive integer number of single cells connected in series."), BeforeValidator(_integer_input)],
    current_start_A: Annotated[float, Field(description="Nonnegative current sweep start in A, with at least two supported samples."), BeforeValidator(_number_input)],
    current_stop_A: Annotated[float, Field(description="Exclusive current stop in A; OPEM caps it at active_area_cm2 times max_current_density_A_cm2."), BeforeValidator(_number_input)],
    current_step_A: Annotated[float, Field(description="Positive current increment in A, advancing under OPEM rounding; at most 10,000 samples."), BeforeValidator(_number_input)],
    max_current_density_A_cm2: Annotated[float, Field(description="Positive limiting current density JMax in A/cm², used by the source concentration-loss model."), BeforeValidator(_number_input)],
    electronic_resistance_ohm: Annotated[float, Field(description="Nonnegative electronic resistance in ohm; native OPEM default is zero."), BeforeValidator(_number_input)] = 0,
    output_dir: Annotated[str | None, "Output base directory; a new isolated invocation subdirectory is created, default ./results."] = None,
) -> dict:
    """Simulate static PEMFC polarization using the original OPEM Amphlett API.
    Prescribed cell parameters and current sweep → native result files and a compact stack-power summary.
    """
    native_input = {
        "T": temperature_K,
        "PH2": hydrogen_partial_pressure_atm,
        "PO2": oxygen_partial_pressure_atm,
        "A": active_area_cm2,
        "l": membrane_thickness_cm,
        "lambda": membrane_water_content,
        "N": cell_count,
        "i-start": current_start_A,
        "i-stop": current_stop_A,
        "i-step": current_step_A,
        "JMax": max_current_density_A_cm2,
        "R": electronic_resistance_ohm,
        "Name": "polarization",
    }
    for key, value in native_input.items():
        if key != "Name" and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
            raise ValueError(f"{key} must be a finite number.")
    for key in ("T", "PH2", "PO2", "A", "l", "JMax"):
        if native_input[key] <= 0:
            raise ValueError(f"{key} must be strictly positive in its documented units.")
    if not isinstance(cell_count, int) or isinstance(cell_count, bool) or cell_count < 1:
        raise ValueError("cell_count must be a positive integer.")
    if not 14 <= membrane_water_content <= 23:
        raise ValueError("membrane_water_content (lambda) must be between 14 and 23; upstream silently changes out-of-range values.")
    if electronic_resistance_ohm < 0:
        raise ValueError("electronic_resistance_ohm must be nonnegative.")
    if current_start_A < 0 or current_step_A <= 0 or current_stop_A <= current_start_A:
        raise ValueError("Current sweep requires start >= 0, step > 0, and stop > start.")

    effective_stop = min(current_stop_A, active_area_cm2 * max_current_density_A_cm2)
    precision = Functions.get_precision(current_step_A)
    second_current = Functions.rounder(current_start_A + current_step_A, precision)
    if second_current <= current_start_A:
        raise ValueError("current_step_A does not advance under OPEM rounding; choose a supported larger increment.")
    if second_current >= effective_stop:
        raise ValueError("Current sweep must contain at least two samples below the exclusive current limit.")
    estimated_samples = (effective_stop - current_start_A) / current_step_A
    if not math.isfinite(estimated_samples) or estimated_samples > MAX_SAMPLES:
        raise ValueError(f"Current sweep exceeds the operational limit of {MAX_SAMPLES} samples.")
    if Functions.rounder(effective_stop + current_step_A, precision) <= effective_stop:
        raise ValueError("current_step_A cannot advance near the current limit under OPEM rounding.")

    base = Path(output_dir).expanduser().resolve() if output_dir is not None else Path.cwd() / "results"
    base.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="amphlett-", dir=base))
    input_path = run_dir / "inputs.json"
    input_path.write_text(json.dumps(native_input, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    log_path = run_dir / "upstream.log"
    # OPEM prints some diagnostics even with PrintMode=False. Serialize its calls
    # while redirecting those process-level streams away from MCP protocol stdout.
    with _SOURCE_CALL_LOCK, log_path.open("w", encoding="utf-8") as log, redirect_stdout(log), redirect_stderr(log):
        result = Amphlett.Static_Analysis(
            InputMethod=dict(native_input),
            TestMode=True,
            PrintMode=False,
            ReportMode=True,
            Folder=str(run_dir),
        )
    if not isinstance(result, dict) or result.get("Status") is not True:
        raise ValueError(f"OPEM Amphlett failed for these inputs; diagnostics: {log_path}")
    sample_count = len(result.get("I", []))
    if sample_count < 2 or sample_count > MAX_SAMPLES:
        raise ValueError(f"OPEM returned an unsupported sample count; diagnostics: {log_path}")
    for key in _ARRAY_FIELDS:
        values = result.get(key)
        if not isinstance(values, list) or len(values) != sample_count or any(
            isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            for value in values
        ):
            raise ValueError(f"OPEM returned incomplete or nonfinite {key} results; diagnostics: {log_path}")
    for key in ("V0", "K"):
        value = result.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"OPEM returned nonfinite {key}; diagnostics: {log_path}")

    result_path = run_dir / "native-result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    reports = [(run_dir / "Amphlett" / f"polarization.{extension}") for extension in ("csv", "html", "opem")]
    if not all(path.is_file() for path in reports):
        raise ValueError(f"OPEM did not produce all native reports; diagnostics: {log_path}")
    source_file = Path(inspect.getsourcefile(Amphlett.Static_Analysis))
    source = {
        "repository": "https://github.com/ECSIM/opem",
        "pinned_commit": COMMIT,
        "callable": "opem.Static.Amphlett.Static_Analysis",
        "installed_version": importlib.metadata.version("opem"),
        "implementation_sha256": hashlib.sha256(source_file.read_bytes()).hexdigest(),
    }
    warnings = [
        "Static prescribed-temperature/lambda PEMFC model; no air-cooled thermal/water dynamics or fan power.",
        "PO2 is oxygen partial pressure. The native Ph uses fixed Eth=1.23 V and is not a validated fan-sizing heat load.",
        "Stack voltage/power are returned; activation, ohmic and concentration losses are single-cell values.",
        "Native HTML charts require their upstream external JavaScript dependencies.",
    ]
    if any(voltage < 0 for voltage in result["V"]):
        warnings.append("The source predicts negative voltage at some currents; those points are not a physical power-producing operating range.")
    max_index = max(range(sample_count), key=result["P"].__getitem__)
    summary = {
        "sample_count": sample_count,
        "first_current_A": result["I"][0],
        "last_current_A": result["I"][-1],
        "effective_exclusive_stop_A": effective_stop,
        "max_sampled_stack_power_W": result["P"][max_index],
        "current_at_max_sampled_power_A": result["I"][max_index],
        "stack_voltage_at_max_sampled_power_V": result["V"][max_index],
        "native_efficiency_at_max_sampled_power": result["EFF"][max_index],
    }
    provenance_path = run_dir / "provenance.json"
    provenance_path.write_text(json.dumps({
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": source,
        "inputs": native_input,
        "summary": summary,
        "limitations": warnings,
    }, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    artifacts = [
        {"description": description, "path": str(path.resolve())}
        for description, path in [
            ("Preserved native model inputs with original units", input_path),
            ("Complete unmodified native result dictionary including all curve arrays", result_path),
            ("Source identity, units and model limitations", provenance_path),
            ("Captured upstream diagnostics", log_path),
            ("Native OPEM data CSV", reports[0]),
            ("Native OPEM interactive chart report", reports[1]),
            ("Native OPEM text report", reports[2]),
        ]
    ]
    return {
        "message": "Computed the original OPEM Amphlett static PEMFC model; full curves are in the returned artifacts.",
        "reference": REFERENCE,
        "artifacts": artifacts,
        "summary": summary,
        "source": source,
        "warnings": warnings,
    }
