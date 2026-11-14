"""Source-library experimental design, model sensitivity and measured-history TPE."""

import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import optuna
import pandas as pd
from scipy.stats import qmc
from SALib.sample import sobol as sobol_sample
from SALib.analyze import sobol as sobol_analyze

from .common import finish_run, input_info, load_table, new_run, read_json, write_json


def _integer(value, lower, upper, name):
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise ValueError(f"{name} must be an integer between {lower} and {upper}.")


def _factors(path):
    config = read_json(path)
    factors = config.get("factors") if isinstance(config, dict) else None
    if not isinstance(factors, list) or not 1 <= len(factors) <= 6:
        raise ValueError("Bounds JSON must contain 1–6 numeric factors.")
    names, lower, upper = [], [], []
    for factor in factors:
        name, unit = factor.get("name"), factor.get("unit")
        if name in {"design_role", "candidate_id", "status", "execution_order"}:
            raise ValueError(f"Factor name {name} is reserved for output metadata.")
        if not isinstance(name, str) or not name.isidentifier() or len(name) > 80 or name in names:
            raise ValueError("Factor names must be unique identifiers.")
        if not isinstance(unit, str) or not unit.strip():
            raise ValueError(f"Declare the unit of {name}; use '1' for a dimensionless quantity.")
        lo, hi = factor.get("lower"), factor.get("upper")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (lo, hi)) or lo >= hi:
            raise ValueError(f"Invalid numeric bounds for {name}.")
        if name.endswith("_fraction") and not 0 <= lo < hi <= 1:
            raise ValueError(f"{name} uses fractions between 0 and 1.")
        names.append(name); lower.append(float(lo)); upper.append(float(hi))
    return factors, names, np.asarray(lower), np.asarray(upper)


def generate_design(bounds_path, n_samples=12, center_replicates=3, seed=42, output_dir=None):
    _integer(n_samples, 2, 256, "n_samples")
    _integer(center_replicates, 0, 20, "center_replicates")
    _integer(seed, 0, 2**32 - 1, "seed")
    factors, names, lower, upper = _factors(bounds_path)
    sample = qmc.LatinHypercube(d=len(names), seed=seed).random(n=n_samples)
    values = qmc.scale(sample, lower, upper)
    if center_replicates:
        values = np.vstack([values, np.tile((lower + upper) / 2, (center_replicates, 1))])
    table = pd.DataFrame(values, columns=names)
    table["design_role"] = ["lhs_screening"] * n_samples + ["center_repeat"] * center_replicates
    table["candidate_id"] = [f"planned-{i + 1:03d}" for i in range(len(table))]
    table["status"] = "awaiting_measurement"
    table = table.iloc[np.random.default_rng(seed).permutation(len(table))].reset_index(drop=True)
    table.insert(0, "execution_order", np.arange(1, len(table) + 1))
    run = new_run("experiment-design", {"bounds": input_info(bounds_path), "factors": factors,
                                       "n_samples": n_samples, "center_replicates": center_replicates, "seed": seed}, output_dir)
    table.to_csv(run / "planned-experiments.csv", index=False)
    write_json(run / "factor-units.json", {f["name"]: f["unit"] for f in factors})
    fig, ax = plt.subplots(figsize=(7, 4))
    if len(names) >= 2:
        ax.scatter(table[names[0]], table[names[1]], color="#167d8d")
        ax.set(xlabel=f"{names[0]} [{factors[0]['unit']}]", ylabel=f"{names[1]} [{factors[1]['unit']}]")
    else:
        ax.scatter(table[names[0]], table["execution_order"], color="#167d8d")
        ax.set(xlabel=f"{names[0]} [{factors[0]['unit']}]", ylabel="Execution order")
    ax.set_title("Planned experiments — no measured outcomes")
    fig.tight_layout(); fig.savefig(run / "design.png", dpi=300); fig.savefig(run / "design.svg"); plt.close(fig)
    return finish_run(run, {"planned_count": len(table), "lhs_count": n_samples, "center_replicates": center_replicates,
                            "data_kind": "experimental_design_not_observations"},
                      {"name": "SciPy LatinHypercube + randomized execution order", "seed": seed,
                       "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.LatinHypercube.html"},
                      ["Factor bounds are user declarations. Planned candidates have no measured performance or verified operating feasibility."])


def model_sensitivity(parameters_path, bounds_path, current_A, n_base=128, seed=42, output_dir=None):
    from .calibration import amphlett_points

    _integer(n_base, 32, 2048, "n_base")
    _integer(seed, 0, 2**32 - 1, "seed")
    if n_base & (n_base - 1):
        raise ValueError("Sobol n_base must be a power of two.")
    if isinstance(current_A, bool) or not isinstance(current_A, (int, float)) or not math.isfinite(current_A) or current_A <= 0:
        raise ValueError("Sensitivity requires a finite positive fixed current in A.")
    parameters = read_json(parameters_path)
    if "base_parameters" in parameters:
        parameters = parameters["base_parameters"]
    factors, names, lower, upper = _factors(bounds_path)
    allowed = {"temperature_K", "hydrogen_partial_pressure_atm", "oxygen_partial_pressure_atm", "active_area_cm2",
               "membrane_thickness_cm", "membrane_water_content", "max_current_density_A_cm2", "electronic_resistance_ohm"}
    if not set(names) <= allowed:
        raise ValueError("Sobol factors must be continuous inputs actually used by the Amphlett model.")
    problem = {"num_vars": len(names), "names": names, "bounds": np.column_stack([lower, upper]).tolist()}
    sample = sobol_sample.sample(problem, n_base, calc_second_order=False, seed=seed)
    run = new_run("model-sensitivity", {"parameters": input_info(parameters_path), "bounds": input_info(bounds_path),
                                       "problem": problem, "fixed_current_A": current_A, "n_base": n_base, "seed": seed}, output_dir)
    frame = pd.DataFrame(sample, columns=names)
    frame.to_csv(run / "ordered-sobol-design.csv", index=False)
    values = []
    for row in sample:
        selected = dict(parameters)
        selected.update(zip(names, map(float, row)))
        try:
            values.append(float(amphlett_points([current_A], selected)[0]))
        except (ValueError, TypeError) as exc:
            write_json(run / "failed-design.json", {"completed_samples": len(values), "error": str(exc)})
            raise ValueError(f"A source-model sample is invalid; no samples were dropped. Revise bounds. Evidence: {run}") from exc
    y = np.asarray(values)
    if not np.isfinite(y).all() or np.var(y) <= 1e-24:
        raise ValueError("Output variance is zero or nonfinite; Sobol indices are undefined.")
    result = sobol_analyze.analyze(problem, y, calc_second_order=False, seed=seed, print_to_console=False)
    table = pd.DataFrame({"parameter": names, **{k: result[k] for k in ("S1", "S1_conf", "ST", "ST_conf")}})
    if not np.isfinite(table.drop(columns="parameter").to_numpy()).all():
        raise ValueError("SALib returned nonfinite sensitivity estimates.")
    frame["stack_voltage_V"] = y
    frame.to_csv(run / "ordered-sobol-responses.csv", index=False)
    table.to_csv(run / "sensitivity-indices.csv", index=False)
    fig, ax = plt.subplots(figsize=(8, 4))
    positions = np.arange(len(names))
    ax.bar(positions - .18, table.S1, width=.36, yerr=table.S1_conf, label="First order", color="#167d8d", capsize=3)
    ax.bar(positions + .18, table.ST, width=.36, yerr=table.ST_conf, label="Total order", color="#d78950", capsize=3)
    ax.set_xticks(positions, names, rotation=20, ha="right"); ax.set_ylabel("Sobol index"); ax.legend()
    fig.tight_layout(); fig.savefig(run / "sensitivity.png", dpi=300); fig.savefig(run / "sensitivity.svg"); plt.close(fig)
    return finish_run(run, {"model_evaluations": len(y), "n_base": n_base, "factor_count": len(names),
                            "output": "stack_voltage_V", "fixed_current_A": current_A, "data_kind": "model_sensitivity_not_experiment"},
                      {"name": "SALib Sobol sample/analyze + original OPEM point APIs", "second_order": False,
                       "url": "https://salib.readthedocs.io/en/latest/"},
                      ["Independent uniform input bounds are assumptions; indices are model-conditional, not causal effects from measured data.",
                       "Finite-sample estimates and intervals are preserved without clipping; prescribed temperature is not a solved air-cooled temperature."])


def suggest_experiments(history_path, bounds_path, objective_column, constraint_column, constraint_upper,
                        n_candidates=3, seed=42, trial_id_column="trial_id", output_dir=None):
    _integer(n_candidates, 1, 16, "n_candidates")
    _integer(seed, 0, 2**32 - 1, "seed")
    if isinstance(constraint_upper, bool) or not isinstance(constraint_upper, (int, float)) or not math.isfinite(constraint_upper):
        raise ValueError("Constraint upper limit must be finite and in the measured column's units.")
    factors, names, lower, upper = _factors(bounds_path)
    reserved = {objective_column, constraint_column, trial_id_column}
    if len(reserved) != 3 or set(names) & reserved:
        raise ValueError("Objective, outcome constraint and trial ID must be separate from input factors.")
    frame = load_table(history_path, string_columns=[trial_id_column])
    required = names + [objective_column, constraint_column, trial_id_column]
    if any(name not in frame for name in required):
        raise ValueError("History needs each input factor, the measured objective/constraint and an explicit trial ID.")
    if len(frame) > 1000 or frame[trial_id_column].isna().any() or frame[trial_id_column].duplicated().any():
        raise ValueError("History needs 1–1000 unique independent trial IDs; aggregate repeated time samples before optimization.")
    numeric = names + [objective_column, constraint_column]
    for name in numeric:
        if frame[name].map(lambda x: isinstance(x, (bool, np.bool_))).any():
            raise ValueError(f"{name} contains booleans rather than physical numbers.")
        frame[name] = pd.to_numeric(frame[name], errors="raise")
        if not np.isfinite(frame[name].to_numpy(dtype=float)).all():
            raise ValueError(f"{name} must contain complete finite measured values.")
    values = frame[names].to_numpy(dtype=float)
    if np.any(values < lower) or np.any(values > upper):
        raise ValueError("Historical inputs fall outside declared search bounds; revise the bounds explicitly.")
    sampler = optuna.samplers.TPESampler(seed=seed, constant_liar=True, n_startup_trials=10)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    for _, row in frame.iterrows():
        params = {name: float(row[name]) for name in names}
        study.enqueue_trial(params)
        trial = study.ask()
        for name, lo, hi in zip(names, lower, upper):
            trial.suggest_float(name, float(lo), float(hi))
        trial.set_user_attr("source_trial_id", str(row[trial_id_column]))
        trial.set_constraint(constraint_column, float(row[constraint_column]) - constraint_upper)
        study.tell(trial, float(row[objective_column]))
    rows = []
    existing = set(map(tuple, values.tolist()))
    for attempt in range(20 * n_candidates):
        if len(rows) == n_candidates:
            break
        trial = study.ask()
        proposal = {name: trial.suggest_float(name, float(lo), float(hi)) for name, lo, hi in zip(names, lower, upper)}
        key = tuple(proposal[name] for name in names)
        if key in existing:
            study.tell(trial, state=optuna.trial.TrialState.FAIL)
            continue
        existing.add(key)
        rows.append({"candidate_id": f"next-{len(rows) + 1:03d}", **proposal, "status": "awaiting_measurement"})
    if len(rows) != n_candidates:
        raise ValueError("Sampler could not create distinct new candidates within the bounded proposal budget.")
    run = new_run("next-experiments", {"history": input_info(history_path), "bounds": input_info(bounds_path),
                                      "objective_column": objective_column, "direction": "maximize", "constraint_column": constraint_column,
                                      "constraint_upper": constraint_upper, "n_candidates": n_candidates, "seed": seed}, output_dir)
    pd.DataFrame(rows).to_csv(run / "pending-candidates.csv", index=False)
    frame.to_csv(run / "observed-history.csv", index=False)
    write_json(run / "native-trial-records.json", [{"number": t.number, "state": t.state.name, "params": t.params,
                                                   "value": t.value, "constraints": t.constraints, "user_attrs": t.user_attrs} for t in study.trials])
    feasible = frame.loc[frame[constraint_column] <= constraint_upper]
    kinds = frame["data_kind"].dropna().astype(str).unique().tolist() if "data_kind" in frame else []
    data_kind = "; ".join(kinds) if kinds else "user_supplied_unverified"
    best = None
    if not feasible.empty:
        row = feasible.loc[feasible[objective_column].idxmax()]
        best = {"trial_id": str(row[trial_id_column]), "measured_objective": float(row[objective_column]),
                "measured_constraint": float(row[constraint_column])}
    return finish_run(run, {"history_count": len(frame), "observed_feasible_count": len(feasible), "data_kind": data_kind,
                            "candidate_count": len(rows), "sampler_phase": "startup_random" if len(frame) < 10 else "TPE",
                            "best_observed_feasible": best, "candidate_feasibility_verified": False},
                      {"name": "Optuna 5 constrained TPE ask/tell", "constraint_api": "Trial.set_constraint", "seed": seed,
                       "url": "https://optuna.readthedocs.io/en/stable/"},
                      ["Recommendations satisfy declared input bounds; outcome constraints require new measurements and are not guaranteed.",
                       "Pending candidates have no fabricated power, temperature or objective values. Each history row must be an independent completed trial."])
