"""Independent source-backed scientific and MCP contract checks for Amphlett."""

import ast
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import csv
import hashlib
import inspect
import io
import json
import math
from pathlib import Path
import re
from typing import Annotated, get_origin, get_type_hints

from fastmcp import Client
from fastmcp.exceptions import ToolError
from opem import Functions
from opem.Static import Amphlett
import pytest

from tools import amphlett


ROOT = Path(__file__).resolve().parents[3]
NATIVE_REFERENCE = ROOT / "notebooks/amphlett_reference/outputs/official/native-result.json"
OFFICIAL_INPUT = json.loads((ROOT / "notebooks/amphlett_reference/data/official.json").read_text())
MAPPING = {
    "temperature_K": "T", "hydrogen_partial_pressure_atm": "PH2",
    "oxygen_partial_pressure_atm": "PO2", "active_area_cm2": "A",
    "membrane_thickness_cm": "l", "membrane_water_content": "lambda",
    "cell_count": "N", "current_start_A": "i-start", "current_stop_A": "i-stop",
    "current_step_A": "i-step", "max_current_density_A_cm2": "JMax",
    "electronic_resistance_ohm": "R",
}
OFFICIAL = {name: OFFICIAL_INPUT[key] for name, key in MAPPING.items()}
REQUIRED = set(OFFICIAL) - {"electronic_resistance_ohm"}


def compare_full(actual, expected):
    """Compare every source-native value, rejecting unexpected nonfinite values."""
    if isinstance(expected, bool):
        assert actual is expected
    elif isinstance(expected, (int, float)):
        assert not isinstance(actual, bool)
        assert math.isfinite(actual) and math.isfinite(expected)
        assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected)
        for a, e in zip(actual, expected):
            compare_full(a, e)
    elif isinstance(expected, dict):
        assert set(actual) == set(expected)
        for key in expected:
            compare_full(actual[key], expected[key])
    else:
        assert actual == expected


def direct_source(arguments, output):
    native = {key: arguments[name] for name, key in MAPPING.items() if name in arguments}
    native["Name"] = "independent"
    original = deepcopy(native)
    log = io.StringIO()
    with redirect_stdout(log), redirect_stderr(log):
        result = Amphlett.Static_Analysis(InputMethod=native, TestMode=True,
                                         PrintMode=False, ReportMode=True, Folder=str(output))
    assert native == original
    output.joinpath("direct-result.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    output.joinpath("direct.log").write_text(log.getvalue())
    return result


def native_artifacts(data):
    return {Path(item["path"]).name: Path(item["path"]) for item in data["artifacts"]}


def verify_csv_and_charts(files, expected):
    with files["polarization.csv"].open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len(expected["I"])
    columns = {
        "I (A)": "I", "VStack (V)": "V", "Power-Stack (W)": "P",
        "PEM Efficiency ()": "EFF", "Power-Thermal (W)": "Ph",
        "Eta Activation (V)": "Eta_Active", "Eta Concentration (V)": "Eta_Conc",
        "Eta Ohmic (V)": "Eta_Ohmic",
    }
    for column, field in columns.items():
        compare_full([float(row[column]) for row in rows], expected[field])
    html = files["polarization.html"].read_text()
    datasets = {label: ast.literal_eval(values) for label, values in re.findall(
        r"label: '([^']+)',\s*fill:false,\s*data: (\[[^\n]*\]),", html)}
    chart_fields = {
        "Power-Stack": "P", "Voltage-Stack": "V", "Linear-Apx": "VE",
        "Eta Active": "Eta_Active", "Eta Conc": "Eta_Conc", "Eta Ohmic": "Eta_Ohmic",
        "Efficiency": "EFF", "Efficiency vs Power": "EFF", "Power(Thermal)": "Ph",
    }
    assert set(datasets) == set(chart_fields)
    for label, field in chart_fields.items():
        compare_full(datasets[label], expected[field])
    label_arrays = [ast.literal_eval(values) for values in re.findall(r"labels: (\[[^\n]*\]),", html)]
    assert len(label_arrays) == 6
    for i, labels in enumerate(label_arrays):
        compare_full(labels, list(map(Functions.rounder, expected["P"])) if i == 4 else expected["I"])
    assert "<script" in html
    assert files["polarization.opem"].stat().st_size > 0


SCENARIOS = [
    ("official", {}), ("temperature", {"temperature_K": 353.15}),
    ("oxygen", {"oxygen_partial_pressure_atm": 0.21}),
    ("hydrogen", {"hydrogen_partial_pressure_atm": 1.5}),
    ("resistance", {"electronic_resistance_ohm": 0.002}),
    ("stack", {"cell_count": 5}), ("area", {"active_area_cm2": 60.0}),
    ("thickness", {"membrane_thickness_cm": 0.02}),
    ("hydration", {"membrane_water_content": 18}),
    ("density_cap", {"max_current_density_A_cm2": 1.2}),
    ("current_sweep", {"current_start_A": 5, "current_stop_A": 15, "current_step_A": 0.5}),
]


@pytest.mark.parametrize("name,changes", SCENARIOS, ids=[item[0] for item in SCENARIOS])
async def test_all_values_and_native_figures_against_direct_source(name, changes, tmp_path):
    arguments = {**OFFICIAL, **changes}
    expected = direct_source(arguments, tmp_path / "direct")
    if name == "official":
        compare_full(expected, json.loads(NATIVE_REFERENCE.read_text()))
    preserved = deepcopy(arguments)
    async with Client(amphlett.amphlett_mcp) as client:
        response = await client.call_tool("opem_simulate_polarization", {
            **arguments, "output_dir": str(tmp_path / "wrapped")})
    assert arguments == preserved
    data = response.data
    files = native_artifacts(data)
    assert len(files) == 7 and all(path.is_file() and path.is_absolute() for path in files.values())
    actual = json.loads(files["native-result.json"].read_text())
    compare_full(actual, expected)
    verify_csv_and_charts(files, expected)
    saved_input = json.loads(files["inputs.json"].read_text())
    for name, source_key in MAPPING.items():
        assert saved_input[source_key] == arguments[name]
    provenance = json.loads(files["provenance.json"].read_text())
    assert provenance["inputs"] == saved_input
    assert provenance["source"] == data["source"]
    assert data["source"]["implementation_sha256"] == hashlib.sha256(
        (ROOT / "repo/opem/opem/Static/Amphlett.py").read_bytes()).hexdigest()
    assert data["summary"]["sample_count"] == len(expected["I"])
    assert data["summary"]["max_sampled_stack_power_W"] == max(expected["P"])
    assert not set(expected) & set(data)  # Arrays stay in artifacts, not protocol payload.


INVALIDS = [
    ({"temperature_K": 0}, "strictly positive"),
    # MCP JSON serialization converts nonfinite numbers to null; both must still fail.
    ({"temperature_K": float("nan")}, "must be numbers"),
    ({"temperature_K": float("inf")}, "must be numbers"),
    ({"hydrogen_partial_pressure_atm": 0}, "strictly positive"),
    ({"oxygen_partial_pressure_atm": 0}, "strictly positive"),
    ({"active_area_cm2": 0}, "strictly positive"),
    ({"membrane_thickness_cm": 0}, "strictly positive"),
    ({"max_current_density_A_cm2": 0}, "strictly positive"),
    ({"membrane_water_content": 13.9}, "between 14 and 23"),
    ({"membrane_water_content": 23.1}, "between 14 and 23"),
    ({"cell_count": 0}, "positive integer"),
    ({"cell_count": 1.5}, "positive integer"),
    ({"electronic_resistance_ohm": -0.1}, "nonnegative"),
    ({"current_start_A": -1}, "start >= 0"),
    ({"current_step_A": 0}, "step > 0"),
    ({"current_step_A": -0.1}, "step > 0"),
    ({"current_stop_A": 0}, "stop > start"),
    ({"current_stop_A": 0.05}, "at least two samples"),
    ({"current_step_A": 1e-7}, "does not advance"),
    ({"current_step_A": 0.001}, "10000"),
    ({"temperature_K": "343.15"}, "not booleans or strings"),
    ({"cell_count": "1"}, "positive integer"),
]


@pytest.mark.parametrize("changes,message", INVALIDS)
async def test_invalid_inputs_are_mcp_errors(changes, message, tmp_path):
    async with Client(amphlett.amphlett_mcp) as client:
        with pytest.raises(ToolError, match=re.escape(message)):
            await client.call_tool("opem_simulate_polarization", {
                **OFFICIAL, **changes, "output_dir": str(tmp_path)})


@pytest.mark.parametrize("name", list(OFFICIAL))
async def test_boolean_is_never_coerced_to_physical_parameter(name, tmp_path):
    async with Client(amphlett.amphlett_mcp) as client:
        with pytest.raises(ToolError, match="boolean"):
            await client.call_tool("opem_simulate_polarization", {
                **OFFICIAL, name: True, "output_dir": str(tmp_path)})


async def test_schema_and_required_input_contract(tmp_path):
    async with Client(amphlett.amphlett_mcp) as client:
        tools = await client.list_tools()
        assert [tool.name for tool in tools] == ["opem_simulate_polarization"]
        schema = tools[0].input_schema
        assert set(schema["required"]) == REQUIRED
        assert set(schema["properties"]) == set(OFFICIAL) | {"output_dir"}
        assert all(field.get("description") for field in schema["properties"].values())
        missing = {name: value for name, value in OFFICIAL.items() if name != "temperature_K"}
        with pytest.raises(ToolError, match="temperature_K"):
            await client.call_tool("opem_simulate_polarization", missing)


async def test_default_resistance_repeat_isolation_and_input_preservation(tmp_path):
    arguments = {name: value for name, value in OFFICIAL.items() if name != "electronic_resistance_ohm"}
    arguments["output_dir"] = str(tmp_path)
    before = deepcopy(arguments)
    async with Client(amphlett.amphlett_mcp) as client:
        first = (await client.call_tool("opem_simulate_polarization", arguments)).data
        first_files = native_artifacts(first)
        hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in first_files.values()}
        second = (await client.call_tool("opem_simulate_polarization", arguments)).data
    assert arguments == before
    second_files = native_artifacts(second)
    assert set(first_files.values()).isdisjoint(second_files.values())
    assert hashes == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in first_files.values()}
    compare_full(json.loads(first_files["native-result.json"].read_text()),
                 json.loads(second_files["native-result.json"].read_text()))
    assert json.loads(first_files["inputs.json"].read_text())["R"] == 0


@pytest.mark.parametrize("failure", ["status", "missing-array", "nonfinite-array", "nonfinite-fit"])
async def test_swallowed_upstream_failures_are_not_success(monkeypatch, failure, tmp_path):
    native = json.loads(NATIVE_REFERENCE.read_text())
    if failure == "status":
        native = {"Status": False}
    elif failure == "missing-array":
        del native["V"]
    elif failure == "nonfinite-array":
        native["V"][3] = float("nan")
    else:
        native["K"] = float("inf")
    monkeypatch.setattr(Amphlett, "Static_Analysis", lambda **kwargs: native)
    async with Client(amphlett.amphlett_mcp) as client:
        with pytest.raises(ToolError, match="OPEM"):
            await client.call_tool("opem_simulate_polarization", {**OFFICIAL, "output_dir": str(tmp_path)})


def test_source_reuse_and_tool_format():
    source = Path(amphlett.__file__).read_text()
    tree = ast.parse(source)
    source_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute) and node.func.attr == "Static_Analysis"]
    assert len(source_calls) == 1
    function = amphlett.opem_simulate_polarization
    assert len(inspect.getdoc(function).splitlines()) == 2
    hints = get_type_hints(function, include_extras=True)
    for name in inspect.signature(function).parameters:
        assert get_origin(hints[name]) is Annotated
    assert not any(token in source for token in ("# @title", "# @param", "# @markdown"))
