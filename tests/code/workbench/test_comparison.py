import numpy as np
import pandas as pd
import pytest
from scipy import stats
from ._helpers import call, artifact, measured_frame


async def compare(path, output, design="paired"):
    return await call("research_compare_conditions", {"data_path":str(path),"metric":"net_power_W","group_a":"baseline","group_b":"candidate","design_type":design,"target_current_A":20.,"current_tolerance_A":.1,"output_dir":str(output)})


async def test_true_replicate_effect_ci_and_time_duplication_invariance(tmp_path):
    raw = measured_frame()
    raw["net"] = raw.current_A*raw.stack_voltage_V-raw.fan_power_W-raw.other_aux_power_W
    grouped = raw.groupby(["replicate_id","condition"]).net.mean().unstack()
    expected = stats.ttest_rel(grouped.candidate.to_numpy(), grouped.baseline.to_numpy())
    path=tmp_path/"first.csv";raw.drop(columns="net").sample(frac=1,random_state=11).to_csv(path,index=False)
    a=await compare(path,tmp_path)
    duplicated=tmp_path/"dup.csv";pd.concat([raw.drop(columns="net")]*4).to_csv(duplicated,index=False)
    b=await compare(duplicated,tmp_path)
    for result in [a,b]:
        s=result["summary"]
        assert s["n_replicates_a"]==s["n_replicates_b"]==6
        np.testing.assert_allclose(s["mean_difference"],(grouped.candidate-grouped.baseline).mean(),rtol=1e-12)
        np.testing.assert_allclose(s["inference"]["p_value_two_sided"],expected.pvalue,rtol=1e-10)
        np.testing.assert_allclose(s["inference"]["mean_difference_ci"],expected.confidence_interval(.95),rtol=1e-12)
    np.testing.assert_allclose(a["summary"]["inference"]["mean_difference_ci"],b["summary"]["inference"]["mean_difference_ci"],rtol=1e-12)


async def test_welch_and_matching_load(tmp_path):
    frame=measured_frame()
    frame.loc[frame.condition=="candidate","replicate_id"]="B-"+frame.loc[frame.condition=="candidate","replicate_id"]
    wrong=frame.copy();wrong["current_A"]=30.;wrong["stack_voltage_V"]=10.
    path=tmp_path/"independent.csv";pd.concat([frame,wrong]).to_csv(path,index=False)
    r=await compare(path,tmp_path,"independent")
    v=frame.current_A*frame.stack_voltage_V-frame.fan_power_W-frame.other_aux_power_W
    grouped=frame.assign(outcome=v).groupby(["condition","replicate_id"]).outcome.mean()
    e=stats.ttest_ind(grouped.loc["candidate"],grouped.loc["baseline"],equal_var=False)
    np.testing.assert_allclose(r["summary"]["inference"]["mean_difference_ci"],e.confidence_interval(.95),rtol=1e-12)
    assert r["summary"]["actual_current_ranges"]["candidate"]=={"min_A":20.,"max_A":20.}


async def test_zero_contrast_variance_has_no_manufactured_inference(tmp_path):
    frame=measured_frame()
    for group,voltage in [("baseline",3.),("candidate",3.1)]:
        frame.loc[frame.condition==group,"stack_voltage_V"]=voltage
    frame["fan_power_W"]=2.;frame["other_aux_power_W"]=.5
    path=tmp_path/"constant.csv";frame.to_csv(path,index=False)
    r=await compare(path,tmp_path)
    assert r["summary"]["inference"]["status"]=="degenerate_no_inferential_claim"
    assert r["summary"]["inference"]["p_value_two_sided"] is None
    assert r["summary"]["inference"]["mean_difference_ci"] is None
    assert r["summary"]["mean_difference"]==pytest.approx(2.)


async def test_pair_ids_are_exact_strings_and_missing_pairs_fail(tmp_path):
    frame=measured_frame();extra=frame[frame.replicate_id=="001"].copy();extra["replicate_id"]="1"
    path=tmp_path/"identifiers.csv";pd.concat([frame,extra]).to_csv(path,index=False)
    r=await compare(path,tmp_path)
    assert r["summary"]["n_replicates_a"]==7
    per=pd.read_csv(artifact(r,"per-replicate.csv"),dtype={"replicate_id":str})
    assert {"001","1"}<=set(per.replicate_id)
    frame=frame.loc[~((frame.condition=="candidate")&(frame.replicate_id=="001"))]
    frame.to_csv(path,index=False)
    with pytest.raises(Exception,match="unmatched"):
        await compare(path,tmp_path)
