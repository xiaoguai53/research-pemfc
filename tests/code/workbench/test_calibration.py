import copy
import io
from contextlib import redirect_stdout,redirect_stderr
import numpy as np
import pandas as pd
import pytest
from opem.Static import Amphlett
from research_core.calibration import amphlett_points
from ._helpers import ROOT,REFERENCE,EXAMPLES,load,dump,flat_native,native,call,artifact


@pytest.mark.parametrize("change", [{},{"T":353.15},{"PO2":.21},{"N":5,"R":.002,"lambda":18.}])
def test_all_native_curve_points_and_input_preservation(change):
    p=load(ROOT/"notebooks/amphlett_reference/data/official.json");p.update(change)
    before=copy.deepcopy(p)
    with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
        source=Amphlett.Static_Analysis(InputMethod=dict(p),TestMode=True,PrintMode=False,ReportMode=False)
    actual=amphlett_points(source["I"],flat_native(p))
    np.testing.assert_allclose(actual,source["V"],rtol=1e-12,atol=1e-12)
    assert len(actual)==750 and p==before


def test_measured_temperature_is_used_for_each_point():
    p=load(REFERENCE/"data/calibration-config.json")["native_fixed_parameters"]
    i=np.linspace(5,65,25);t=np.linspace(333.15,353.15,25)
    expected=np.array([native.point_voltage(float(a),p,float(b)) for a,b in zip(i,t)])
    actual=amphlett_points(i,flat_native(p),t)
    np.testing.assert_allclose(actual,expected,rtol=1e-12,atol=1e-12)
    assert not np.allclose(actual,amphlett_points(i,flat_native(p)))


async def fit(path,config,out):
    return await call("research_calibrate_model",{"data_path":str(path),"config_path":str(config),"output_dir":str(out)})


async def test_recover_truth_and_holdout_response_cannot_leak(tmp_path):
    source=EXAMPLES/"polarization-synthetic.csv";config=EXAMPLES/"calibration.json"
    a=await fit(source,config,tmp_path)
    s=a["summary"]
    assert s["fitted_parameters"]["electronic_resistance_ohm"]==pytest.approx(.002,abs=1e-9)
    assert s["fitted_parameters"]["membrane_water_content"]==pytest.approx(18.,abs=1e-6)
    assert s["train_metrics"]["n"]==20 and s["holdout_metrics"]["n"]==5
    assert set(s["split"]["train_rows"]).isdisjoint(s["split"]["holdout_rows"])
    assert s["holdout_metrics"]["rmse_V"]<1e-9
    assert s["identifiability"]["jacobian_rank"]==2
    assert s["identifiability"]["column_normalized_condition_number"]<100
    assert s["identifiability"]["raw_condition_number"]>1000
    assert s["identifiability"]["parameter_confidence_intervals_computed"] is False
    frame=pd.read_csv(source);frame.loc[frame.split=="holdout","stack_voltage_V"]+=1
    changed=tmp_path/"heldout-corrupted.csv";frame.to_csv(changed,index=False)
    b=await fit(changed,config,tmp_path)
    np.testing.assert_allclose(list(b["summary"]["fitted_parameters"].values()),list(s["fitted_parameters"].values()),rtol=1e-10,atol=1e-10)
    assert b["summary"]["holdout_metrics"]["rmse_V"]>.99
    complete=load(artifact(a,"parameters-fitted.json"))
    prediction=pd.read_csv(artifact(a,"predictions.csv"))
    np.testing.assert_allclose(prediction.model_stack_voltage_V,amphlett_points(frame.current_A,complete,frame.stack_temperature_C+273.15),rtol=1e-12)


async def test_whole_group_holdout_keeps_distinct_real_ids(tmp_path):
    config=load(EXAMPLES/"calibration.json");config.pop("split_column");config["group_column"]="run_id"
    p=load(REFERENCE/"data/calibration-config.json")["native_fixed_parameters"]
    frames=[]
    for idx,label in enumerate(["001","1","002","2"]):
        i=np.linspace(5,65,10);t=np.full(10,340.+idx)
        frames.append(pd.DataFrame({"run_id":label,"current_A":i,"stack_voltage_V":[native.point_voltage(float(a),p,float(b)) for a,b in zip(i,t)],"stack_temperature_C":t-273.15,"cell_count":1,"data_kind":"synthetic_independent_group_contract"}))
    path=tmp_path/"groups.csv";pd.concat(frames).to_csv(path,index=False)
    r=await fit(path,dump(tmp_path/"config.json",config),tmp_path)
    split=r["summary"]["split"]
    assert set(split["train_groups"]).isdisjoint(split["holdout_groups"])
    assert set(split["train_groups"])|set(split["holdout_groups"])=={"001","1","002","2"}
    assert r["summary"]["temperature_mode"]=="measured_per_row_temperature_K"


@pytest.mark.parametrize("change", [{"membrane_water_content":13},{"cell_count":True},{"oxygen_partial_pressure_atm":0}])
def test_source_domain_errors_are_not_repaired(change):
    params=load(EXAMPLES/"model-parameters.json");params.update(change)
    with pytest.raises(ValueError):amphlett_points([10],params)
