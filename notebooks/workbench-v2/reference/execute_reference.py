"""Run original scientific APIs to establish non-writing workbench references.

All calibration and optimizer data below are synthetic software benchmarks.
They are not experimental measurements or validation of an air-cooled stack.
"""

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import csv
import hashlib
import importlib.metadata
import inspect
import io
import json
from pathlib import Path
import sys

import numpy as np
import optuna
from scipy.optimize import least_squares
from scipy.stats import qmc
from SALib.sample import sobol as sobol_sample
from SALib.analyze import sobol as sobol_analyze
from SALib.test_functions import Ishigami
from opem.Static import Amphlett


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COMMIT = "27d343fb966361a4e6cc99650241f651778fc50f"
DATA_KIND = "SYNTHETIC_SOFTWARE_VALIDATION_NOT_EXPERIMENTAL"


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def save_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def point_voltage(current, parameters, temperature=None):
    """Call unchanged source functions in their original Static_Analysis order."""
    p = parameters
    T = p["T"] if temperature is None else temperature
    enernst = Amphlett.Enernst_Calc(T, p["PH2"], p["PO2"])
    b = Amphlett.B_Calc(T)
    activation = Amphlett.Eta_Act_Calc(T, p["PO2"], p["PH2"], current, p["A"])
    ohmic = Amphlett.Eta_Ohmic_Calc(current, p["l"], p["A"], T, p["lambda"], R_elec=p["R"])
    concentration = Amphlett.Eta_Conc_Calc(current, p["A"], b, p["JMax"])
    loss = Amphlett.Loss_Calc(activation, ohmic, concentration)
    cell = Amphlett.Vcell_Calc(enernst, loss)
    stack = Amphlett.VStack_Calc(p["N"], cell)
    assert stack is not None and np.isfinite(stack)
    return float(stack)


def predict(currents, temperatures, parameters):
    return np.array([point_voltage(float(i), parameters, float(t)) for i, t in zip(currents, temperatures)])


def source_chain(official):
    summaries = []
    for name, changes in [("official", {}), ("temperature353_15K", {"T": 353.15}), ("oxygen0_21atm", {"PO2": 0.21})]:
        p = dict(official, **changes)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            source = Amphlett.Static_Analysis(InputMethod=dict(p), TestMode=True, PrintMode=False, ReportMode=False)
        assert source["Status"] is True and len(source["I"]) == 750
        values = np.array([point_voltage(i, p) for i in source["I"]])
        np.testing.assert_allclose(values, source["V"], rtol=1e-12, atol=1e-12)
        replay_input = HERE / "data" / f"{name}-native-input.json"
        dump(replay_input, p)
        saved = json.loads(replay_input.read_text())
        replay = np.array([point_voltage(i, saved) for i in source["I"]])
        np.testing.assert_allclose(replay, values, rtol=1e-12, atol=1e-12)
        dump(HERE / "outputs" / name / "native-static-result.json", source)
        save_csv(HERE / "outputs" / name / "point-chain.csv", ["current_A", "temperature_K", "stack_voltage_V"], [
            {"current_A": i, "temperature_K": p["T"], "stack_voltage_V": v} for i, v in zip(source["I"], values)
        ])
        summaries.append({"scenario": name, "samples": len(values), "maximum_absolute_difference_V": float(np.max(np.abs(values-np.asarray(source["V"])))), "replay_passed": True})
    return summaries


def calibration(official):
    truth = dict(official, R=0.002, **{"lambda": 18.0})
    currents = np.linspace(5.0, 65.0, 25)
    temperatures = np.full_like(currents, truth["T"])
    voltage = predict(currents, temperatures, truth)
    holdout = np.arange(len(currents)) % 5 == 0
    rows = [{"sample_id": int(k), "current_A": float(i), "stack_voltage_V": float(v),
             "stack_temperature_C": float(t-273.15), "cell_count": truth["N"],
             "split": "holdout" if held else "train", "data_kind": DATA_KIND}
            for k, (i,v,t,held) in enumerate(zip(currents,voltage,temperatures,holdout))]
    fields = list(rows[0])
    save_csv(HERE / "data" / "calibration-measurements.csv", fields, rows)
    config = {"data_kind": DATA_KIND, "native_fixed_parameters": truth,
              "true_parameters": {"R": truth["R"], "lambda": truth["lambda"]},
              "train_rows": np.flatnonzero(~holdout).tolist(), "holdout_rows": np.flatnonzero(holdout).tolist(),
              "holdout_policy": "Fixed every fifth sample before optimization; interpolation-point holdout from one synthetic curve, not independent hardware validation.",
              "bounds": {"R": [0.0,0.01], "lambda": [14.0,23.0]}}
    dump(HERE / "data" / "calibration-config.json", config)
    outputs = {}
    for mode, names, start, bounds in [
        ("R_only", ["R"], [0.001], ([0.0],[0.01])),
        ("R_and_lambda", ["R","lambda"], [0.001,20.0], ([0.0,14.0],[0.01,23.0])),
    ]:
        def residual(x):
            p = dict(truth)
            p.update(dict(zip(names, x)))
            return predict(currents[~holdout], temperatures[~holdout], p)-voltage[~holdout]
        fit = least_squares(residual, start, bounds=bounds, x_scale="jac", ftol=1e-13, xtol=1e-13, gtol=1e-13)
        assert fit.success, fit.message
        fitted = dict(truth)
        fitted.update(dict(zip(names, fit.x)))
        predicted = predict(currents, temperatures, fitted)
        np.testing.assert_allclose(fit.x, [truth[n] for n in names], rtol=1e-7, atol=1e-9)
        np.testing.assert_allclose(predicted, voltage, rtol=1e-9, atol=1e-9)
        singular = np.linalg.svd(fit.jac, compute_uv=False)
        norms = np.linalg.norm(fit.jac, axis=0)
        scaled_singular = np.linalg.svd(fit.jac/norms, compute_uv=False)
        outputs[mode] = {"success": bool(fit.success), "message": str(fit.message),
                         "fitted_parameters": dict(zip(names, map(float, fit.x))), "nfev": int(fit.nfev),
                         "train_rmse_V": float(np.sqrt(np.mean((predicted[~holdout]-voltage[~holdout])**2))),
                         "holdout_rmse_V": float(np.sqrt(np.mean((predicted[holdout]-voltage[holdout])**2))),
                         "jacobian_rank": int(np.linalg.matrix_rank(fit.jac)),
                         "jacobian_condition_number": float(singular[0]/singular[-1]),
                         "column_normalized_jacobian_condition_number": float(scaled_singular[0]/scaled_singular[-1]),
                         "raw_jacobian": fit.jac.tolist(), "predictions_stack_voltage_V": predicted.tolist()}
    variable_temperatures = truth["T"] + 3.0*np.sin(np.linspace(0.0,2.0*np.pi,len(currents)))
    variable_voltage = predict(currents, variable_temperatures, truth)
    for row,t,v in zip(rows,variable_temperatures,variable_voltage):
        row = dict(row, stack_temperature_C=float(t-273.15), stack_voltage_V=float(v))
    variable_rows = [dict(row, stack_temperature_C=float(t-273.15), stack_voltage_V=float(v))
                     for row,t,v in zip(rows,variable_temperatures,variable_voltage)]
    save_csv(HERE / "data" / "calibration-variable-temperature.csv", fields, variable_rows)
    dump(HERE / "outputs" / "calibration-native-fit.json", outputs)
    return outputs


def lhs_reference():
    unit = qmc.LatinHypercube(d=2, seed=42).random(n=8)
    physical = qmc.scale(unit, [0.3,10.0], [0.9,40.0])
    replay = qmc.LatinHypercube(d=2, seed=42).random(n=8)
    np.testing.assert_array_equal(unit,replay)
    for k in range(2):
        np.testing.assert_array_equal(np.sort(np.floor(unit[:,k]*8).astype(int)),np.arange(8))
    save_csv(HERE / "outputs" / "lhs-native.csv", ["fan_pwm_fraction","current_A"], [dict(zip(["fan_pwm_fraction","current_A"],map(float,row))) for row in physical])
    dump(HERE / "data" / "lhs-config.json", {"library":"scipy.stats.qmc.LatinHypercube","seed":42,"samples":8,"bounds":{"fan_pwm_fraction":[0.3,0.9],"current_A":[10.0,40.0]},"data_kind":"DESIGN_NOT_OBSERVATIONS","unit_cube_sample":unit.tolist()})
    return {"samples":8,"seed":42,"each_stratum_once":True,"replay_passed":True}


def sobol_reference():
    problem = {"num_vars":3,"names":["x1","x2","x3"],"bounds":[[-np.pi,np.pi]]*3}
    values = sobol_sample.sample(problem,1024,calc_second_order=False,seed=42)
    y = Ishigami.evaluate(values)
    indices = sobol_analyze.analyze(problem,y,calc_second_order=False,seed=42,print_to_console=False)
    replay_values = sobol_sample.sample(problem,1024,calc_second_order=False,seed=42)
    replay = sobol_analyze.analyze(problem,Ishigami.evaluate(replay_values),calc_second_order=False,seed=42,print_to_console=False)
    np.testing.assert_array_equal(values,replay_values)
    for key in ["S1","ST","S1_conf","ST_conf"]:
        np.testing.assert_allclose(indices[key],replay[key],rtol=1e-12,atol=1e-12)
    dump(HERE / "data" / "sobol-ishigami-config.json", {"problem":problem,"N":1024,"calc_second_order":False,"seed":42,"source_function":"SALib.test_functions.Ishigami.evaluate","data_kind":"SOURCE_TEST_FUNCTION_NOT_EXPERIMENTAL","function_doc":inspect.getdoc(Ishigami.evaluate)})
    save_csv(HERE / "outputs" / "sobol-ishigami-samples.csv", ["x1","x2","x3","Y"], [{"x1":float(row[0]),"x2":float(row[1]),"x3":float(row[2]),"Y":float(yi)} for row,yi in zip(values,y)])
    result={key:indices[key].tolist() for key in ["S1","ST","S1_conf","ST_conf"]}
    dump(HERE / "outputs" / "sobol-ishigami-native-indices.json", result)
    return {"base_samples":1024,"model_evaluations":len(y),"indices":result,"replay_passed":True}


def optuna_reference():
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    history=[{"x":float(x),"objective":float(-(x-0.65)**2),"temperature_C":float(60+20*x)} for x in np.linspace(0.0,1.0,6)]
    def run():
        study=optuna.create_study(direction="maximize",sampler=optuna.samplers.TPESampler(seed=42,n_startup_trials=4,constant_liar=True))
        for row in history:
            study.enqueue_trial({"x":row["x"]})
            trial=study.ask()
            trial.suggest_float("x",0.0,1.0)
            trial.set_constraint("temperature_limit_C",row["temperature_C"]-75.0)
            study.tell(trial,row["objective"])
        candidates=[]
        for unused in range(4):
            trial=study.ask()
            candidates.append({"trial_number":trial.number,"x":trial.suggest_float("x",0.0,1.0),"status":"AWAITING_OBSERVATION"})
        return candidates
    candidates=run()
    assert candidates==run()
    dump(HERE / "data" / "optuna-toy-history.json", {"data_kind":"SYNTHETIC_TOY_BENCHMARK_NOT_MEASUREMENTS","history":history,"bounds":{"x":[0.0,1.0]},"direction":"maximize","constraint_temperature_upper_C":75.0,"n_startup_trials":4,"seed":42,"constant_liar":True,"native_constraint_API":"Trial.set_constraint(key,value)","constraint_semantics":"Feasible when every recorded constraint <=0."})
    dump(HERE / "outputs" / "optuna-native-candidates.json", candidates)
    return {"completed_native_trials":len(history),"proposed_pending_trials":len(candidates),"candidates":candidates,"replay_passed":True,"no_candidate_outcomes_fabricated":True}


def main():
    official_path=ROOT/"notebooks/amphlett_reference/data/official.json"
    official=json.loads(official_path.read_text())
    source_path=ROOT/"repo/opem/opem/Static/Amphlett.py"
    installed=Path(inspect.getsourcefile(Amphlett.Static_Analysis))
    assert hashlib.sha256(source_path.read_bytes()).hexdigest()==hashlib.sha256(installed.read_bytes()).hexdigest()
    result={"data_kind":DATA_KIND,"repository_commit":COMMIT,"python":sys.executable,"packages":{name:importlib.metadata.version(name) for name in ["opem","numpy","scipy","SALib","optuna"]},
            "point_chain":source_chain(official),"calibration":calibration(official),"lhs":lhs_reference(),"sobol":sobol_reference(),"optuna":optuna_reference(),
            "source_files":{"official_input":str(official_path.relative_to(ROOT)),"original_amphlett_sha256":hashlib.sha256(source_path.read_bytes()).hexdigest(),"installed_amphlett":str(installed)},
            "figures":"No plotting commands or notebooks selected; no source-native figure outputs produced.",
            "finished_at_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")}
    dump(HERE/"execution-summary.json",result)
    print(json.dumps({"status":"succeeded","point_chain_scenarios":len(result["point_chain"]),"calibration_modes":list(result["calibration"]),"sobol_evaluations":result["sobol"]["model_evaluations"]}))


if __name__ == "__main__":
    main()
