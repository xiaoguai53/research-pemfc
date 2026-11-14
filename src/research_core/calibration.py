"""Bounded SciPy calibration of unchanged OPEM point functions."""

from contextlib import redirect_stderr, redirect_stdout
import io
from numbers import Integral, Real
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from opem.Static import Amphlett

from tools.amphlett import _SOURCE_CALL_LOCK
from .common import finish_run, input_info, load_table, new_run, read_json, write_json
from .data import numeric_column


COMMIT = "27d343fb966361a4e6cc99650241f651778fc50f"
SOURCE_URL = f"https://github.com/ECSIM/opem/blob/{COMMIT}/opem/Static/Amphlett.py"
PHYSICAL_KEYS = ("temperature_K", "hydrogen_partial_pressure_atm", "oxygen_partial_pressure_atm",
                 "active_area_cm2", "membrane_thickness_cm", "membrane_water_content", "cell_count",
                 "max_current_density_A_cm2", "electronic_resistance_ohm")
FIT_KEYS = ("electronic_resistance_ohm", "membrane_water_content")


def _number(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not np.isfinite(value):
        raise ValueError(f"{name} must be a finite physical number, not a boolean or string.")
    return float(value)


def _parameters(parameters):
    if not isinstance(parameters, dict):
        raise ValueError("base_parameters must be an object of explicit physical parameters.")
    result = dict(parameters)
    result.setdefault("electronic_resistance_ohm", 0)
    for key in PHYSICAL_KEYS:
        if key not in result:
            raise ValueError(f"Missing physical parameter: {key}")
        _number(result[key], key)
    n = result["cell_count"]
    if isinstance(n, (bool, np.bool_)) or not isinstance(n, Integral) or n <= 0:
        raise ValueError("cell_count must be a positive integer.")
    for key in ("temperature_K", "hydrogen_partial_pressure_atm", "oxygen_partial_pressure_atm", "active_area_cm2", "membrane_thickness_cm", "max_current_density_A_cm2"):
        if result[key] <= 0:
            raise ValueError(f"{key} must be strictly positive in its declared units.")
    if not 14 <= result["membrane_water_content"] <= 23:
        raise ValueError("membrane_water_content must be between 14 and 23; do not silently repair it.")
    if result["electronic_resistance_ohm"] < 0:
        raise ValueError("electronic_resistance_ohm must be nonnegative.")
    return result


def _vector(values, name):
    raw = np.asarray(values, dtype=object)
    if raw.ndim != 1 or not len(raw):
        raise ValueError(f"{name} must be a nonempty one-dimensional numeric sequence.")
    for value in raw:
        _number(value, name)
    return np.asarray(raw, dtype=float)


def amphlett_points(currents, parameters, temperatures_K=None):
    """Evaluate the original public OPEM chain at each explicit current/temperature."""
    p = _parameters(parameters)
    currents = _vector(currents, "currents")
    if len(currents) > 100_000:
        raise ValueError("At most 100,000 point evaluations per call are supported.")
    temperatures = np.full(len(currents), p["temperature_K"], dtype=float) if temperatures_K is None else _vector(temperatures_K, "temperatures_K")
    if len(temperatures) != len(currents) or np.any(temperatures <= 0):
        raise ValueError("Provide one positive temperature in K per current point.")
    if np.any(currents < 0) or np.any(currents >= p["active_area_cm2"] * p["max_current_density_A_cm2"]):
        raise ValueError("Every current must satisfy 0 <= I < active_area_cm2 * max_current_density_A_cm2.")
    result = []
    diagnostics = io.StringIO()
    # Reuse the baseline server's capture lock: stdout redirection is process-wide.
    with _SOURCE_CALL_LOCK, redirect_stdout(diagnostics), redirect_stderr(diagnostics):
        for i, t in zip(currents, temperatures):
            enernst = Amphlett.Enernst_Calc(t, p["hydrogen_partial_pressure_atm"], p["oxygen_partial_pressure_atm"])
            b = Amphlett.B_Calc(t)
            activation = Amphlett.Eta_Act_Calc(t, p["oxygen_partial_pressure_atm"], p["hydrogen_partial_pressure_atm"], i, p["active_area_cm2"])
            ohmic = Amphlett.Eta_Ohmic_Calc(i, p["membrane_thickness_cm"], p["active_area_cm2"], t, p["membrane_water_content"], R_elec=p["electronic_resistance_ohm"])
            concentration = Amphlett.Eta_Conc_Calc(i, p["active_area_cm2"], b, p["max_current_density_A_cm2"])
            loss = Amphlett.Loss_Calc(activation, ohmic, concentration)
            cell = Amphlett.Vcell_Calc(enernst, loss)
            voltage = Amphlett.VStack_Calc(p["cell_count"], cell)
            if isinstance(voltage, (bool, np.bool_)) or not isinstance(voltage, Real) or not np.isfinite(voltage):
                raise ValueError("Original OPEM calculation returned an invalid point; check the parameter domain. " + diagnostics.getvalue()[-600:])
            result.append(float(voltage))
    return np.asarray(result)


def _split(frame, config):
    seed = config.get("seed", 42)
    if isinstance(seed, bool) or not isinstance(seed, Integral) or seed < 0:
        raise ValueError("seed must be a nonnegative integer.")
    group_column = config.get("group_column")
    if group_column is None:
        group_column = next((name for name in ("run_id", "replicate_id") if name in frame), None)
    if group_column is not None:
        if not isinstance(group_column, str) or group_column not in frame or frame[group_column].isna().any() or frame[group_column].astype(str).str.strip().eq("").any():
            raise ValueError("group_column must identify complete actual run/replicate groups.")
        groups = frame[group_column].astype(str).to_numpy()
    else:
        groups = None
    split_column = config.get("split_column")
    if split_column is not None:
        if not isinstance(split_column, str) or split_column not in frame or frame[split_column].isna().any():
            raise ValueError("split_column must contain explicit train/holdout labels.")
        labels = frame[split_column].astype(str)
        if not labels.isin(["train", "holdout"]).all():
            raise ValueError("split_column allows only train and holdout labels.")
        held = labels.eq("holdout").to_numpy()
        policy = "explicit_prespecified_split"
    else:
        fraction = _number(config.get("holdout_fraction", 0.2), "holdout_fraction")
        if not 0 < fraction < 1:
            raise ValueError("holdout_fraction must be strictly between zero and one.")
        rng = np.random.default_rng(seed)
        units = np.unique(groups) if groups is not None else np.arange(len(frame))
        count = max(1, int(np.ceil(len(units) * fraction)))
        if count >= len(units):
            raise ValueError("At least one training and one held-out unit are required.")
        held_units = rng.permutation(units)[:count]
        held = np.isin(groups if groups is not None else np.arange(len(frame)), held_units)
        policy = "seeded_whole_group_holdout" if groups is not None else "seeded_current_point_interpolation_check"
    if not held.any() or held.all():
        raise ValueError("Both training and held-out observations are required.")
    details = {"policy": policy, "seed": int(seed), "group_column": group_column,
               "train_rows": np.flatnonzero(~held).tolist(), "holdout_rows": np.flatnonzero(held).tolist(),
               "validation_scope": "whole user-declared run/replicate holdout" if groups is not None else "point holdout within supplied curves; not independent experimental validation"}
    if groups is not None:
        train_groups, test_groups = sorted(set(groups[~held])), sorted(set(groups[held]))
        if set(train_groups) & set(test_groups):
            raise ValueError("A run/replicate group appears in both train and holdout; split complete groups.")
        details.update(train_groups=train_groups, holdout_groups=test_groups)
    return held, details


def _metrics(observed, predicted):
    residual = predicted - observed
    return {"n": len(observed), "rmse_V": float(np.sqrt(np.mean(residual**2))),
            "mae_V": float(np.mean(np.abs(residual))), "mean_residual_V": float(np.mean(residual))}


def calibrate_amphlett(data_path, config_path, output_dir=None):
    config = read_json(config_path)
    if not isinstance(config, dict):
        raise ValueError("Calibration configuration must be a JSON object.")
    base = _parameters(config.get("base_parameters"))
    fit_parameters = config.get("fit_parameters")
    if not isinstance(fit_parameters, dict) or not fit_parameters or any(name not in FIT_KEYS for name in fit_parameters):
        raise ValueError("Fit only explicit electronic_resistance_ohm and/or membrane_water_content bounds.")
    names, lower, upper, initial = [], [], [], []
    for name, bounds in fit_parameters.items():
        if not isinstance(bounds, list) or len(bounds) != 2:
            raise ValueError(f"{name} needs [lower, upper] bounds.")
        lo, hi = (_number(value, name + " bound") for value in bounds)
        if not lo < hi or (name == "electronic_resistance_ohm" and lo < 0) or (name == "membrane_water_content" and not 14 <= lo < hi <= 23):
            raise ValueError(f"{name} bounds do not satisfy the source-model domain.")
        x0 = _number(base[name], name)
        if not lo <= x0 <= hi:
            raise ValueError(f"Initial {name} in base_parameters lies outside its bounds.")
        names.append(name); lower.append(lo); upper.append(hi); initial.append(x0)
    max_nfev = config.get("max_nfev", 300)
    if isinstance(max_nfev, bool) or not isinstance(max_nfev, Integral) or not 1 <= max_nfev <= 2000:
        raise ValueError("max_nfev must be an integer between 1 and 2000.")
    string_columns = ["sample_id", "run_id", "replicate_id"] + [config.get("group_column"), config.get("split_column")]
    frame = load_table(data_path, sheet_name=config.get("sheet_name", 0), string_columns=[name for name in string_columns if isinstance(name, str)])
    if not 8 <= len(frame) <= 5000:
        raise ValueError("Calibration requires 8–5000 prespecified steady/quasi-static rows; no rows are silently sampled.")
    currents = numeric_column(frame, "current_A").to_numpy()
    voltage = numeric_column(frame, "stack_voltage_V").to_numpy()
    for name in ("cell_count", "active_area_cm2"):
        if name in frame:
            known = numeric_column(frame, name).to_numpy()
            if not np.allclose(known, base[name], rtol=1e-12, atol=1e-12):
                raise ValueError(f"Measured {name} differs from the fixed base parameter; select one consistent stack/area.")
    temperature_column = config.get("temperature_column")
    if temperature_column is None:
        temperature_column = next((name for name in ("stack_temperature_C", "stack_temperature_K") if name in frame), None)
    notes = []
    if temperature_column is None:
        temperatures = np.full(len(frame), base["temperature_K"])
        temperature_mode = "prescribed_fixed_temperature_K"
        notes.append("Measured temperature was not supplied: all points assume the explicitly prescribed base temperature.")
    else:
        if not isinstance(temperature_column, str) or temperature_column not in frame:
            raise ValueError("Declared measured temperature column is missing.")
        unit = config.get("temperature_unit", "C" if temperature_column.endswith("_C") else "K" if temperature_column.endswith("_K") else None)
        if unit not in ("C", "K"):
            raise ValueError("Declare measured temperature_unit as C or K.")
        temperatures = numeric_column(frame, temperature_column).to_numpy()
        if unit == "C":
            temperatures = temperatures + 273.15
        temperature_mode = "measured_per_row_temperature_K"
    # Validate all current/temperature domains before optimization, without a fitted response.
    amphlett_points(currents, base, temperatures)
    held, split = _split(frame, config)
    if int((~held).sum()) <= len(names) + 2:
        raise ValueError("Too few training observations for the requested fit parameters.")
    def parameters_at(x):
        parameters = dict(base)
        parameters.update({name: float(value) for name, value in zip(names, x)})
        return parameters
    def residual(x):
        return amphlett_points(currents[~held], parameters_at(x), temperatures[~held]) - voltage[~held]
    fit = least_squares(residual, initial, bounds=(lower, upper), method="trf", x_scale="jac",
                        max_nfev=int(max_nfev), ftol=1e-12, xtol=1e-12, gtol=1e-12)
    if not fit.success or not np.isfinite(fit.x).all():
        raise ValueError(f"Calibration did not converge successfully: {fit.message}")
    fitted = parameters_at(fit.x)
    predicted = amphlett_points(currents, fitted, temperatures)
    jac = np.asarray(fit.jac, dtype=float)
    singular = np.linalg.svd(jac, compute_uv=False)
    norms = np.linalg.norm(jac, axis=0)
    scaled_jac = np.divide(jac, norms, out=np.zeros_like(jac), where=norms > 0)
    scaled_singular = np.linalg.svd(scaled_jac, compute_uv=False)
    rank = int(np.linalg.matrix_rank(jac))
    scaled_rank = int(np.linalg.matrix_rank(scaled_jac))
    def condition(values):
        value = float(values[0] / values[-1]) if values[-1] > 0 else None
        return value if value is not None and np.isfinite(value) else None
    bound_flags = {name: bool(abs(value-lo) <= max((hi-lo)*1e-5, 1e-12) or abs(value-hi) <= max((hi-lo)*1e-5, 1e-12))
                   for name, value, lo, hi in zip(names, fit.x, lower, upper)}
    identifiability = {"jacobian_rank": rank, "column_normalized_jacobian_rank": scaled_rank,
                       "parameter_count": len(names), "raw_condition_number": condition(singular),
                       "column_normalized_condition_number": condition(scaled_singular),
                       "raw_singular_values": singular.tolist(), "column_normalized_singular_values": scaled_singular.tolist(),
                       "at_or_near_bounds": bound_flags, "parameter_confidence_intervals_computed": False}
    if rank < len(names) or scaled_rank < len(names) or identifiability["column_normalized_condition_number"] is None or identifiability["column_normalized_condition_number"] > 1000:
        notes.append("The local Jacobian is rank-deficient or poorly conditioned after column scaling; parameters may not be separately identifiable.")
    if any(bound_flags.values()):
        notes.append("At least one fitted parameter is at/near a requested bound; inspect range and model mismatch.")
    notes.extend(["Good residual agreement and optimizer convergence do not establish physical parameter identification or validated hardware performance.",
                  "Measured/prescribed temperature is an input to a quasi-static model; no air-cooled heat/water dynamics are solved."])
    if split["group_column"] is None:
        notes.append("A current-point holdout checks interpolation on supplied curves, not generalization to an independent experiment.")
    kinds = frame["data_kind"].dropna().astype(str).unique().tolist() if "data_kind" in frame else []
    data_kind = "; ".join(kinds) if kinds else "user_supplied_unverified"
    summary = {"fitted_parameters": {name: float(value) for name, value in zip(names, fit.x)},
               "train_metrics": _metrics(voltage[~held], predicted[~held]),
               "holdout_metrics": _metrics(voltage[held], predicted[held]),
               "optimizer": {"success": bool(fit.success), "status": int(fit.status), "message": str(fit.message),
                             "nfev": int(fit.nfev), "cost": float(fit.cost)},
               "split": split, "temperature_mode": temperature_mode, "data_kind": data_kind,
               "identifiability": identifiability}
    run = new_run("amphlett-calibration", {"source": input_info(data_path), "configuration_source": input_info(config_path),
                                         "config": config, "resolved_split": split}, output_dir)
    write_json(run / "fitted-parameters.json", summary["fitted_parameters"])
    write_json(run / "parameters-fitted.json", fitted)
    write_json(run / "identifiability.json", identifiability)
    output = frame.copy(deep=True)
    for column in ("model_stack_voltage_V", "residual_V", "analysis_split"):
        if column in output:
            raise ValueError(f"Reserved output column already present: {column}")
    output["model_stack_voltage_V"] = predicted
    output["residual_V"] = predicted - voltage
    output["analysis_split"] = np.where(held, "holdout", "train")
    output.to_csv(run / "predictions.csv", index=False)
    pd.DataFrame(jac, columns=names).assign(source_row_index=np.flatnonzero(~held)).to_csv(run / "training-jacobian.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for mask, label, color in [(~held, "Train", "#207178"), (held, "Held out", "#c47b29")]:
        axes[0].scatter(currents[mask], voltage[mask], color=color, label=f"{label} observations", s=22)
        axes[0].scatter(currents[mask], predicted[mask], color=color, marker="x", s=25)
        axes[1].scatter(currents[mask], predicted[mask]-voltage[mask], color=color, label=label, s=22)
    axes[0].set(xlabel="Current / A", ylabel="Stack voltage / V")
    axes[0].legend(fontsize=8)
    axes[1].axhline(0, color="grey", linestyle="--", linewidth=.8)
    axes[1].set(xlabel="Current / A", ylabel="Model minus observation / V")
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(run / "calibration.png", dpi=300)
    fig.savefig(run / "calibration.svg")
    plt.close(fig)
    return finish_run(run, summary, {"name": "New composition: bounded SciPy least_squares around original OPEM public point functions",
                                    "physical_model_source": SOURCE_URL, "opem_commit": COMMIT,
                                    "optimizer": "scipy.optimize.least_squares(method=trf,x_scale=jac)",
                                    "confidence_interval_scope": "No physical parameter uncertainty interval is inferred from residuals alone."}, notes)
