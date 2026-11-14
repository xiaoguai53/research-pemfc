import pandas as pd
import numpy as np
import pytest
from ._helpers import call,artifact,load,EXAMPLES


async def recommend(history,out):
    return await call("research_suggest_experiments",{"history_path":str(history),"bounds_path":str(EXAMPLES/"experiment-bounds.json"),"objective_column":"net_power_W","constraint_column":"stack_temperature_C","constraint_upper":55.,"n_candidates":3,"seed":42,"output_dir":str(out)})


async def test_history_constraints_pending_truth_and_seed_replay(tmp_path):
    source=EXAMPLES/"history-synthetic.csv"
    a=await recommend(source,tmp_path);b=await recommend(source,tmp_path)
    pa=pd.read_csv(artifact(a,"pending-candidates.csv"));pb=pd.read_csv(artifact(b,"pending-candidates.csv"))
    pd.testing.assert_frame_equal(pa,pb)
    assert set(pa.columns)=={"candidate_id","fan_pwm_fraction","current_A","status"}
    assert set(pa.status)=={"awaiting_measurement"}
    assert a["summary"]["candidate_feasibility_verified"] is False
    assert a["summary"]["data_kind"] == "SYNTHETIC_ANALYTIC_TOY_NOT_A_FUEL_CELL_THERMAL_MODEL"
    assert pa.fan_pwm_fraction.between(.3,.9).all() and pa.current_A.between(10,40).all()
    raw=pd.read_csv(source)
    trials=load(artifact(a,"native-trial-records.json"))
    completed=[t for t in trials if t["state"]=="COMPLETE"]
    assert len(completed)==len(raw)
    for expected,actual in zip(raw.to_dict("records"),completed):
        assert actual["value"]==expected["net_power_W"]
        assert actual["constraints"]["stack_temperature_C"]==pytest.approx(expected["stack_temperature_C"]-55.)
    assert any(t["constraints"]["stack_temperature_C"]>0 for t in completed)
    feasible=raw.loc[raw.stack_temperature_C<=55]
    assert a["summary"]["best_observed_feasible"]["measured_objective"]==feasible.net_power_W.max()
    pending=[t for t in trials if t["state"]=="RUNNING"]
    assert len(pending)==3 and all(t["value"] is None for t in pending)


async def test_startup_is_random_and_history_ids_must_be_unique(tmp_path):
    frame=pd.read_csv(EXAMPLES/"history-synthetic.csv").head(4)
    path=tmp_path/"small.csv";frame.to_csv(path,index=False)
    r=await recommend(path,tmp_path)
    assert r["summary"]["sampler_phase"]=="startup_random"
    frame.loc[1,"trial_id"]=frame.loc[0,"trial_id"];frame.to_csv(path,index=False)
    with pytest.raises(Exception,match="unique"):
        await recommend(path,tmp_path)
