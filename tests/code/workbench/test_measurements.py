import hashlib
import numpy as np
import pandas as pd
import pytest
from ._helpers import call, artifact, EXAMPLES, measured_frame


async def test_derived_values_no_source_mutation_and_identifiers(tmp_path):
    path = EXAMPLES / "measurements-synthetic.csv"
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = await call("research_analyze_measurements", {"data_path": str(path), "output_dir": str(tmp_path)})
    actual = pd.read_csv(artifact(result, "derived-measurements.csv"), dtype={"replicate_id": str})
    raw = measured_frame()
    np.testing.assert_allclose(actual.gross_power_W, raw.current_A * raw.stack_voltage_V, rtol=1e-12)
    np.testing.assert_allclose(actual.net_power_W, raw.current_A * raw.stack_voltage_V - raw.fan_power_W - raw.other_aux_power_W, rtol=1e-12)
    assert actual.replicate_id.tolist() == raw.replicate_id.tolist()
    assert result["summary"]["data_kind"] == "SYNTHETIC_SOFTWARE_VALIDATION_NOT_EXPERIMENTAL"
    assert result["summary"]["imputed_values"] == 0
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("power_columns,net,fan_subtracted", [([], False, False), (["fan_power_W"], False, True), (["fan_power_W", "other_aux_power_W"], True, True)])
async def test_explicit_auxiliary_boundaries(tmp_path, power_columns, net, fan_subtracted):
    frame = measured_frame()
    frame = frame.drop(columns=[name for name in ["fan_power_W", "other_aux_power_W"] if name not in power_columns])
    path = tmp_path / "input.csv"; frame.to_csv(path, index=False)
    r = await call("research_analyze_measurements", {"data_path": str(path), "output_dir": str(tmp_path)})
    actual = pd.read_csv(artifact(r, "derived-measurements.csv"))
    assert ("net_power_W" in actual) is net
    assert ("gross_minus_fan_power_W" in actual) is fan_subtracted


async def test_missing_consumption_is_retained_and_selected_excel_sheet(tmp_path):
    frame = measured_frame(); frame.loc[0, "fan_power_W"] = np.nan
    path = tmp_path / "sheets.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame({"unrelated": [1]}).to_excel(writer, sheet_name="Other", index=False)
        frame.to_excel(writer, sheet_name="Measurements", index=False)
    r = await call("research_analyze_measurements", {"data_path": str(path), "sheet_name": "Measurements", "output_dir": str(tmp_path)})
    actual = pd.read_csv(artifact(r, "derived-measurements.csv"), dtype={"replicate_id": str})
    assert actual.loc[0, ["fan_power_W", "net_power_W"]].isna().all()
    assert r["summary"]["valid_net_power_W_rows"] == len(frame)-1
    assert actual.replicate_id.iloc[0] == "001"


@pytest.mark.parametrize("column,value", [("current_A", True), ("current_A", np.nan), ("stack_voltage_V", "bad"), ("fan_power_W", -1)])
async def test_bad_measurements_are_tool_errors(tmp_path, column, value):
    frame = measured_frame(); frame[column] = frame[column].astype(object); frame.loc[0, column] = value
    path=tmp_path/"bad.csv"; frame.to_csv(path,index=False)
    with pytest.raises(Exception):
        await call("research_analyze_measurements", {"data_path":str(path),"output_dir":str(tmp_path)})
