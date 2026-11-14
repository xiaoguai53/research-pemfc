import hashlib
import json
from pathlib import Path
import pytest
from fastmcp import Client
from research_mcp import mcp
from research_core.common import export_run,read_json,load_table,input_info
from ._helpers import ROOT,EXAMPLES,call,artifact,dump


EXPECTED={"opem_simulate_polarization","research_analyze_measurements","research_compare_conditions","research_calibrate_model","research_design_experiments","research_model_sensitivity","research_suggest_experiments","research_search_literature","research_prior_art_plan"}


async def test_inventory_schemas_and_original_baseline(tmp_path):
    async with Client(mcp) as client:
        tools=await client.list_tools()
    assert {t.name for t in tools}==EXPECTED
    for tool in tools:
        schema=tool.input_schema
        assert all(p.get("description") for p in schema["properties"].values()),tool.name
    args=json.loads((ROOT/"examples/amphlett-official.json").read_text());args["output_dir"]=str(tmp_path)
    r=await call("opem_simulate_polarization",args)
    assert r["summary"]["sample_count"]==750 and len(r["artifacts"])==7
    actual=artifact(r,"native-result.json")
    expected=json.loads((ROOT/"notebooks/amphlett_reference/outputs/official/native-result.json").read_text())
    assert json.loads(actual.read_text())==expected


@pytest.mark.parametrize("tool,args",[
    ("research_design_experiments",{"bounds_path":str(EXAMPLES/"experiment-bounds.json"),"n_samples":True}),
    ("research_model_sensitivity",{"parameters_path":str(EXAMPLES/"model-parameters.json"),"bounds_path":str(EXAMPLES/"sensitivity-bounds.json"),"current_A":True}),
    ("research_compare_conditions",{"data_path":str(EXAMPLES/"measurements-synthetic.csv"),"metric":"net_power_W","group_a":"baseline","group_b":"candidate","design_type":"paired","target_current_A":True}),
    ("research_search_literature",{"query":"fuel cell","limit":True}),
])
async def test_raw_boolean_arguments_fail_through_transport(tool,args):
    with pytest.raises(Exception,match="booleans"):
        await call(tool,args)


async def test_manifest_integrity_export_and_no_full_arrays(tmp_path):
    r=await call("research_analyze_measurements",{"data_path":str(EXAMPLES/"measurements-synthetic.csv"),"output_dir":str(tmp_path)})
    manifest=read_json(artifact(r,"manifest.json"));root=Path(r["run_dir"])
    for name,expected in manifest["files"].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected
    assert "reference" in r
    assert len(json.dumps(r))<15000
    exported=export_run(root)
    assert exported.is_file()
    artifact(r,"derived-measurements.csv").write_text("changed")
    with pytest.raises(ValueError,match="changed"):
        export_run(root)


def test_strict_json_and_duplicate_table_columns(tmp_path):
    bad=tmp_path/"bad.json";bad.write_text('{"x":NaN}')
    with pytest.raises(ValueError):read_json(bad)
    bad.write_text('{"x":1,"x":2}')
    with pytest.raises(ValueError,match="Duplicate"):read_json(bad)
    table=tmp_path/"bad.csv";table.write_text('current_A,current_A\n1,2\n')
    with pytest.raises(ValueError,match="Duplicate"):load_table(table)
