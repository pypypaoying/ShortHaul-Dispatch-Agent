"""End-to-end experiments for the official MathorCup D dataset."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import numpy as np
import pandas as pd

from shorthaul_agent.models import Assignment, Fleet, ForecastBucket, Instance, ProblemConfig, Route, ScheduleSolution
from shorthaul_agent.solvers.heuristic import calculate_kpis
from shorthaul_agent.solvers import CpSatScheduler, HeuristicScheduler, generate_dispatch_tasks
from shorthaul_agent.time_utils import format_minutes


FOCUS_ROUTES = ["场地3 - 站点83 - 0600", "场地3 - 站点83 - 1400"]
PAPER_BASELINES = {
    "problem2": {"total_cost": 56776.0, "own_vehicle_turnover": 2.49},
    "problem3": {"total_cost": 47106.0, "own_vehicle_turnover": 2.62},
}


@dataclass
class ExperimentConfig:
    name: str = "d_problem_baseline"
    data_dir: str = "D题"
    output_dir: str = "outputs"
    target_date: str = "2024-12-16"
    base_date: str = "2024-12-15"
    forecast_model: str = "statistical_baseline"
    task_generation_strategy: str = "full_load_plus_tail_set_cover"
    solver_strategy: str = "cpsat_with_heuristic_fallback"
    prefer_cpsat: bool = True
    solver_time_limit_seconds: float = 20.0
    run_weight_grid: bool = True
    focus_routes: list = None

    def __post_init__(self) -> None:
        if self.focus_routes is None:
            self.focus_routes = list(FOCUS_ROUTES)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentConfig":
        allowed = {field.name for field in cls.__dataclass_fields__.values()}
        filtered = {key: value for key, value in data.items() if key in allowed}
        return cls(**filtered)


@dataclass
class AgentStepResult:
    agent: str
    status: str
    summary: str
    metrics: Dict[str, Any]


@dataclass
class DDataset:
    routes: pd.DataFrame
    history: pd.DataFrame
    known_daily: pd.DataFrame
    milk_run_rules: pd.DataFrame
    fleets: pd.DataFrame
    result_templates: Dict[str, pd.DataFrame]


def run_experiment(data_dir: Path, output_dir: Path, prefer_cpsat: bool = True, config_path: Optional[Path] = None) -> Dict[str, Any]:
    experiment_config = load_experiment_config(config_path) if config_path else ExperimentConfig()
    experiment_config.data_dir = str(data_dir)
    experiment_config.output_dir = str(output_dir)
    experiment_config.prefer_cpsat = prefer_cpsat
    return run_configured_experiment(experiment_config)


def load_experiment_config(config_path: Path) -> ExperimentConfig:
    text = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() == ".json":
        return ExperimentConfig.from_dict(json.loads(text))
    return ExperimentConfig.from_dict(parse_simple_yaml(text))


def parse_simple_yaml(text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if raw_value.startswith("[") and raw_value.endswith("]"):
            value = [item.strip().strip("\"'") for item in raw_value[1:-1].split(",") if item.strip()]
        elif raw_value.lower() in {"true", "false"}:
            value = raw_value.lower() == "true"
        else:
            value = raw_value.strip("\"'")
            try:
                value = float(value) if "." in value else int(value)
            except ValueError:
                pass
        data[key] = value
    return data


def run_configured_experiment(experiment_config: ExperimentConfig) -> Dict[str, Any]:
    data_dir = Path(experiment_config.data_dir)
    output_dir = Path(experiment_config.output_dir)
    agent_trace: list = []

    data_agent = DProblemDataAgent()
    forecast_agent = ForecastAgent()
    demand_agent = DemandGenerationAgent()
    solver_agent = ExperimentSolverAgent()
    repair_agent = ExperimentRepairAgent()
    audit_agent = ConstraintAuditAgent()
    explanation_agent = ExperimentExplanationAgent()

    dataset = data_agent.run(data_dir, agent_trace)
    output_dir.mkdir(parents=True, exist_ok=True)

    target_date = pd.Timestamp(experiment_config.target_date)
    base_date = pd.Timestamp(experiment_config.base_date)

    daily_forecast, ten_min_forecast = forecast_agent.run(dataset, target_date, experiment_config, agent_trace)

    result1 = dataset.result_templates["结果表1"].copy()
    result1["线路编码"] = result1["线路编码"].map(normalize_route_code)
    result1 = result1.drop(columns=["货量"], errors="ignore").merge(
        daily_forecast[["线路编码", "predicted_volume"]],
        on="线路编码",
        how="left",
    )
    result1["货量"] = result1["predicted_volume"].fillna(0).round().astype(int)
    result1 = result1.drop(columns=["predicted_volume"])

    result2 = ten_min_forecast[["线路编码", "日期", "分钟起始", "包裹量"]].copy()

    instance_no_container, config_p2, config_p3, tasks_p2, tasks_p3 = demand_agent.run(
        dataset,
        result2,
        target_date,
        base_date,
        experiment_config,
        agent_trace,
    )
    task_audit_p2 = audit_agent.audit_tasks("problem2", tasks_p2, config_p2, agent_trace)
    task_audit_p3 = audit_agent.audit_tasks("problem3", tasks_p3, config_p3, agent_trace)

    solution_p2 = solver_agent.solve_problem("problem2", instance_no_container, tasks_p2, config_p2, agent_trace)
    result3 = assignments_to_result_table(solution_p2, target_date, base_date, include_container=False)

    candidate_p3 = solver_agent.solve_problem("problem3_cpsat", instance_no_container, tasks_p3, config_p3, agent_trace)
    baseline_p3 = repair_agent.build_non_regression_baseline(solution_p2, tasks_p3, instance_no_container, config_p3, agent_trace)
    solution_p3 = repair_agent.choose_problem3_solution(candidate_p3, baseline_p3, agent_trace)
    result4 = assignments_to_result_table(solution_p3, target_date, base_date, include_container=True)
    solution_audit_p2 = audit_agent.audit_solution("problem2", solution_p2, tasks_p2, config_p2, agent_trace)
    solution_audit_p3 = audit_agent.audit_solution("problem3", solution_p3, tasks_p3, config_p3, agent_trace)
    sensitivity = run_sensitivity_analysis(result2, solution_p3, instance_no_container, config_p3, base_date)
    weight_grid = run_weight_grid_search(solution_p2, candidate_p3, baseline_p3) if experiment_config.run_weight_grid else []

    result1.to_excel(output_dir / "result_table_1.xlsx", index=False)
    result2.to_excel(output_dir / "result_table_2.xlsx", index=False)
    result3.to_excel(output_dir / "result_table_3.xlsx", index=False)
    result4.to_excel(output_dir / "result_table_4.xlsx", index=False)
    sensitivity.to_csv(output_dir / "sensitivity_analysis.csv", index=False, encoding="utf-8-sig")
    sensitivity.to_excel(output_dir / "sensitivity_analysis.xlsx", index=False)
    audit_report = {
        "problem2_tasks": task_audit_p2,
        "problem3_tasks": task_audit_p3,
        "problem2_solution": solution_audit_p2,
        "problem3_solution": solution_audit_p3,
    }
    write_json(output_dir / "constraint_audit.json", audit_report)
    (output_dir / "constraint_audit.md").write_text(render_constraint_audit(audit_report), encoding="utf-8")
    visual_outputs = write_visual_artifacts(output_dir, solution_p2, solution_p3, sensitivity, result1, result3, result4)

    summary = explanation_agent.build_summary(
        experiment_config=experiment_config,
        dataset=dataset,
        result1=result1,
        result2=result2,
        result3=result3,
        result4=result4,
        tasks_p2=len(tasks_p2),
        tasks_p3=len(tasks_p3),
        solution_p2=solution_p2,
        solution_p3=solution_p3,
        candidate_p3=candidate_p3,
        baseline_p3=baseline_p3,
        sensitivity=sensitivity,
        visual_outputs=visual_outputs,
        audit_report=audit_report,
        agent_trace=agent_trace,
        weight_grid=weight_grid,
    )
    write_json(output_dir / "experiment_summary.json", summary)
    (output_dir / "experiment_report.md").write_text(render_report(summary), encoding="utf-8")
    return summary


class DProblemDataAgent:
    name = "DataIngestionAgent"

    def run(self, data_dir: Path, trace: list) -> DDataset:
        dataset = load_d_dataset(data_dir)
        trace.append(
            AgentStepResult(
                self.name,
                "ok",
                "Loaded official D-problem attachments and result templates.",
                {
                    "routes": int(dataset.routes["线路编码"].nunique()),
                    "history_rows": int(len(dataset.history)),
                    "known_daily_rows": int(len(dataset.known_daily)),
                    "milk_run_rules": int(len(dataset.milk_run_rules)),
                    "fleets": int(dataset.fleets["车队编码"].nunique()),
                },
            )
        )
        return dataset


class ForecastAgent:
    name = "ForecastAgent"

    def run(self, dataset: DDataset, target_date: pd.Timestamp, config: ExperimentConfig, trace: list) -> tuple:
        daily_forecast = forecast_daily_volume(dataset, target_date)
        ten_min_forecast = disaggregate_to_10min(dataset, daily_forecast, target_date)
        trace.append(
            AgentStepResult(
                self.name,
                "ok",
                "Generated daily and 10-minute forecasts with the statistical baseline.",
                {
                    "forecast_model": config.forecast_model,
                    "daily_rows": int(len(daily_forecast)),
                    "ten_min_rows": int(len(ten_min_forecast)),
                    "total_predicted_volume": int(daily_forecast["predicted_volume"].sum()),
                },
            )
        )
        return daily_forecast, ten_min_forecast


class DemandGenerationAgent:
    name = "DemandGenerationAgent"

    def run(
        self,
        dataset: DDataset,
        result2: pd.DataFrame,
        target_date: pd.Timestamp,
        base_date: pd.Timestamp,
        experiment_config: ExperimentConfig,
        trace: list,
    ) -> tuple:
        instance = build_instance(dataset, result2, target_date, base_date)
        milk_run_pairs = build_milk_run_pairs(dataset.milk_run_rules)
        common_config = {
            "vehicle_capacity": 1000,
            "container_capacity": 800,
            "max_stops": 3,
            "allow_external": True,
            "prefer_cpsat": experiment_config.prefer_cpsat,
            "solver_time_limit_seconds": experiment_config.solver_time_limit_seconds,
            "milk_run_pairs": milk_run_pairs,
        }
        config_p2 = ProblemConfig(allow_container=False, **common_config)
        config_p3 = ProblemConfig(allow_container=True, **common_config)
        tasks_p2 = generate_dispatch_tasks(instance, config_p2)
        tasks_p3 = generate_dispatch_tasks(instance, config_p3)
        trace.append(
            AgentStepResult(
                self.name,
                "ok",
                "Generated full-load, tail-load and milk-run tasks for problems 2 and 3.",
                {
                    "task_generation_strategy": experiment_config.task_generation_strategy,
                    "problem2_tasks": len(tasks_p2),
                    "problem3_tasks": len(tasks_p3),
                    "milk_run_pairs": len(milk_run_pairs),
                },
            )
        )
        return instance, config_p2, config_p3, tasks_p2, tasks_p3


class ExperimentSolverAgent:
    name = "SolverAgent"

    def solve_problem(self, label: str, instance: Instance, tasks: list, config: ProblemConfig, trace: list) -> ScheduleSolution:
        solution = solve_with_fallback(instance, tasks, config)
        trace.append(
            AgentStepResult(
                self.name,
                "ok" if solution.assignments else "warning",
                f"Solved {label} with {solution.solver}.",
                {
                    "label": label,
                    "solver": solution.solver,
                    "status": solution.status,
                    "assigned_tasks": len(solution.assignments),
                    "total_cost": solution.kpis.get("total_cost", 0),
                    "external_tasks": solution.kpis.get("external_task_count", 0),
                },
            )
        )
        return solution


class ExperimentRepairAgent:
    name = "RepairAgent"

    def build_non_regression_baseline(self, solution: ScheduleSolution, tasks: list, instance: Instance, config: ProblemConfig, trace: list) -> ScheduleSolution:
        baseline = convert_problem2_to_container_baseline(solution, tasks, instance, config)
        trace.append(
            AgentStepResult(
                self.name,
                "ok",
                "Built a problem-3 non-regression baseline from the problem-2 schedule.",
                {
                    "baseline_cost": baseline.kpis.get("total_cost", 0),
                    "container_tasks": count_container_tasks(baseline),
                },
            )
        )
        return baseline

    def choose_problem3_solution(self, candidate: ScheduleSolution, baseline: ScheduleSolution, trace: list) -> ScheduleSolution:
        chosen = choose_lower_cost_solution(candidate, baseline)
        trace.append(
            AgentStepResult(
                self.name,
                "ok",
                "Selected the lower-cost problem-3 solution, preserving the pure CP-SAT candidate for comparison.",
                {
                    "candidate_solver": candidate.solver,
                    "candidate_cost": candidate.kpis.get("total_cost", 0),
                    "baseline_cost": baseline.kpis.get("total_cost", 0),
                    "selected_solver": chosen.solver,
                },
            )
        )
        return chosen


class ConstraintAuditAgent:
    name = "ConstraintAuditAgent"

    def audit_tasks(self, label: str, tasks: list, config: ProblemConfig, trace: list) -> Dict[str, Any]:
        audit = audit_tasks(tasks, config)
        trace.append(AgentStepResult(self.name, "ok" if not audit["violations"] else "warning", f"Audited {label} generated tasks.", audit))
        return audit

    def audit_solution(self, label: str, solution: ScheduleSolution, tasks: list, config: ProblemConfig, trace: list) -> Dict[str, Any]:
        audit = audit_solution(solution, tasks, config)
        trace.append(AgentStepResult(self.name, "ok" if not audit["violations"] else "warning", f"Audited {label} schedule solution.", audit))
        return audit


class ExperimentExplanationAgent:
    name = "ExplanationAgent"

    def build_summary(self, **kwargs) -> Dict[str, Any]:
        summary = build_summary(**kwargs)
        kwargs["agent_trace"].append(
            AgentStepResult(
                self.name,
                "ok",
                "Built experiment summary, KPI comparison and report-ready explanation.",
                {
                    "summary_sections": list(summary.keys()),
                    "visual_outputs": len(summary["outputs"].get("visual_outputs", [])),
                },
            )
        )
        summary["agent_trace"] = serialize_agent_trace(kwargs["agent_trace"])
        return summary


def load_d_dataset(data_dir: Path) -> DDataset:
    attachment_dir = data_dir / "附件"
    result_dir = data_dir / "结果表"
    routes = pd.read_excel(attachment_dir / "附件1.xlsx")
    history = pd.read_excel(attachment_dir / "附件2.xlsx")
    known_daily = pd.read_excel(attachment_dir / "附件3.xlsx")
    milk_run_rules = pd.read_excel(attachment_dir / "附件4.xlsx")
    fleets = pd.read_excel(attachment_dir / "附件5.xlsx")
    templates = {
        "结果表1": pd.read_excel(result_dir / "结果表1.xlsx"),
        "结果表2": pd.read_excel(result_dir / "结果表2.xlsx"),
        "结果表3": pd.read_excel(result_dir / "结果表3.xlsx"),
        "结果表4": pd.read_excel(result_dir / "结果表4.xlsx"),
    }

    for frame in (routes, history, known_daily):
        frame["线路编码"] = frame["线路编码"].map(normalize_route_code)
    for frame in templates.values():
        if "线路编码" in frame.columns:
            frame["线路编码"] = frame["线路编码"].map(normalize_route_code)
    routes["车队编码"] = routes["车队编码"].map(normalize_fleet_code)
    fleets["车队编码"] = fleets["车队编码"].map(normalize_fleet_code)
    return DDataset(routes, history, known_daily, milk_run_rules, fleets, templates)


def forecast_daily_volume(dataset: DDataset, target_date: pd.Timestamp) -> pd.DataFrame:
    history = dataset.history.copy()
    history["date"] = pd.to_datetime(history["日期"]).dt.normalize()
    history["minute"] = history["分钟起始"].map(time_to_minute)
    route_meta = dataset.routes[["线路编码", "车队编码"]].copy()
    route_meta["wave"] = route_meta["线路编码"].map(route_wave)
    history = history.merge(route_meta, on="线路编码", how="left")
    history["service_date"] = history["date"]
    history.loc[(history["wave"] == "0600") & (history["minute"] >= 21 * 60), "service_date"] += pd.Timedelta(days=1)

    actual_daily = (
        history.groupby(["线路编码", "service_date"], as_index=False)["包裹量"]
        .sum()
        .rename(columns={"service_date": "日期", "包裹量": "actual_volume"})
    )
    known = dataset.known_daily.copy()
    known["日期"] = pd.to_datetime(known["日期"]).dt.normalize()
    known = known.rename(columns={"包裹量": "known_volume"})
    joined = actual_daily.merge(known, on=["线路编码", "日期"], how="inner")
    joined = joined.merge(route_meta, on="线路编码", how="left")
    joined = joined[(joined["known_volume"] > 0) & (joined["日期"] < target_date)]
    joined["ratio"] = (joined["actual_volume"] / joined["known_volume"]).clip(0.3, 3.0)

    route_factor = joined.groupby("线路编码")["ratio"].median()
    fleet_wave_factor = joined.groupby(["车队编码", "wave"])["ratio"].median()
    wave_factor = joined.groupby("wave")["ratio"].median()
    global_factor = float(joined["ratio"].median()) if not joined.empty else 1.0

    target_known = known[known["日期"] == target_date].merge(route_meta, on="线路编码", how="right")
    predictions = []
    historical_mean = actual_daily.groupby("线路编码")["actual_volume"].mean()
    for row in target_known.itertuples(index=False):
        route_id = row.线路编码
        wave = row.wave
        fleet_id = row.车队编码
        known_volume = getattr(row, "known_volume", np.nan)
        if pd.isna(known_volume):
            known_volume = historical_mean.get(route_id, 0.0)
            factor = 1.0
        else:
            factor = route_factor.get(route_id, np.nan)
            if pd.isna(factor):
                factor = fleet_wave_factor.get((fleet_id, wave), np.nan)
            if pd.isna(factor):
                factor = wave_factor.get(wave, global_factor)
        predictions.append(
            {
                "线路编码": route_id,
                "日期": target_date.strftime("%Y-%m-%d"),
                "known_volume": float(known_volume) if not pd.isna(known_volume) else 0.0,
                "factor": float(factor) if not pd.isna(factor) else 1.0,
                "predicted_volume": max(int(round(float(known_volume) * float(factor))), 0),
            }
        )
    return pd.DataFrame(predictions)


def disaggregate_to_10min(dataset: DDataset, daily_forecast: pd.DataFrame, target_date: pd.Timestamp) -> pd.DataFrame:
    history = dataset.history.copy()
    history["date"] = pd.to_datetime(history["日期"]).dt.normalize()
    history["minute"] = history["分钟起始"].map(time_to_minute)
    route_meta = dataset.routes[["线路编码", "车队编码"]].copy()
    route_meta["wave"] = route_meta["线路编码"].map(route_wave)
    history = history.merge(route_meta, on="线路编码", how="left")
    history["service_date"] = history["date"]
    history.loc[(history["wave"] == "0600") & (history["minute"] >= 21 * 60), "service_date"] += pd.Timedelta(days=1)
    daily_actual = history.groupby(["线路编码", "service_date"])["包裹量"].transform("sum")
    history["proportion"] = np.where(daily_actual > 0, history["包裹量"] / daily_actual, 0.0)

    route_time = history.groupby(["线路编码", "minute"])["proportion"].mean().to_dict()
    fleet_wave_time = history.groupby(["车队编码", "wave", "minute"])["proportion"].mean().to_dict()
    wave_time = history.groupby(["wave", "minute"])["proportion"].mean().to_dict()
    meta_by_route = route_meta.set_index("线路编码").to_dict(orient="index")
    daily_by_route = daily_forecast.set_index("线路编码")["predicted_volume"].to_dict()

    result2 = dataset.result_templates["结果表2"].copy()
    result2["线路编码"] = result2["线路编码"].map(normalize_route_code)
    result2["minute"] = result2["分钟起始"].map(time_to_minute)

    filled_frames = []
    for route_id, group in result2.groupby("线路编码", sort=False):
        meta = meta_by_route.get(route_id, {"车队编码": "", "wave": route_wave(route_id)})
        weights = []
        for minute in group["minute"].tolist():
            weight = route_time.get((route_id, minute), np.nan)
            if pd.isna(weight):
                weight = fleet_wave_time.get((meta["车队编码"], meta["wave"], minute), np.nan)
            if pd.isna(weight):
                weight = wave_time.get((meta["wave"], minute), np.nan)
            weights.append(float(weight) if not pd.isna(weight) else 1.0)
        volumes = allocate_integer_volume(int(daily_by_route.get(route_id, 0)), weights)
        out = group.drop(columns=["minute"]).copy()
        out["包裹量"] = volumes
        filled_frames.append(out)
    return pd.concat(filled_frames, ignore_index=True)


def build_instance(dataset: DDataset, result2: pd.DataFrame, target_date: pd.Timestamp, base_date: pd.Timestamp) -> Instance:
    fleets = [
        Fleet(
            id=row.车队编码,
            vehicle_count=int(row.自有车数量),
            fixed_cost=100,
            variable_cost_per_trip=0,
            normal_load_minutes=45,
            normal_unload_minutes=45,
            container_load_minutes=10,
            container_unload_minutes=10,
        )
        for row in dataset.fleets.itertuples(index=False)
    ]

    routes = []
    for row in dataset.routes.itertuples(index=False):
        route_id = row.线路编码
        wave = route_wave(route_id)
        latest_dt = target_date + pd.Timedelta(hours=6 if wave == "0600" else 14)
        latest_minute = int((latest_dt.normalize() - base_date).days * 1440 + latest_dt.hour * 60 + latest_dt.minute)
        routes.append(
            Route(
                id=route_id,
                origin=row.起始场地,
                destination=row.目的场地,
                wave=wave,
                latest_dispatch_minute=latest_minute,
                travel_minutes=max(int(math.ceil(float(row.在途时长) * 60)), 1),
                fleet_id=row.车队编码,
                variable_cost=int(row.自有变动成本),
                external_cost=int(row.外部承运商成本),
            )
        )

    forecast = []
    for row in result2.itertuples(index=False):
        row_date = pd.to_datetime(row.日期).normalize()
        minute = time_to_minute(row.分钟起始)
        absolute_minute = int((row_date - base_date).days * 1440 + minute)
        forecast.append(
            ForecastBucket(
                route_id=row.线路编码,
                minute=absolute_minute,
                volume=int(round(float(row.包裹量))),
            )
        )
    return Instance(id="mathorcup-d-real-data", date=target_date.strftime("%Y-%m-%d"), routes=routes, fleets=fleets, forecast=forecast)


def solve_with_fallback(instance: Instance, tasks: list, config: ProblemConfig) -> ScheduleSolution:
    if config.prefer_cpsat and CpSatScheduler.available():
        solution = CpSatScheduler().solve(instance, tasks, config)
        if solution.assignments:
            return solution
    solution = HeuristicScheduler().solve(instance, tasks, config)
    if config.prefer_cpsat:
        solution.warnings.append("CP-SAT unavailable or did not return assignments; used heuristic fallback.")
    return solution


def convert_problem2_to_container_baseline(
    solution: ScheduleSolution,
    tasks: list,
    instance: Instance,
    config: ProblemConfig,
) -> ScheduleSolution:
    """Use the problem-2 schedule as a feasible problem-3 baseline.

    Container use is optional. Any normal schedule remains feasible in problem 3;
    for self-owned tasks not exceeding container capacity, switching to a
    container only shortens the vehicle occupation interval.
    """
    task_by_id = {task.id: task for task in tasks}
    fleet_by_id = {fleet.id: fleet for fleet in instance.fleets}
    assignments = []
    for assignment in solution.assignments:
        task = task_by_id.get(assignment.task_id)
        fleet = fleet_by_id.get(assignment.fleet_id)
        use_container = (
            config.allow_container
            and not assignment.is_external
            and task is not None
            and fleet is not None
            and assignment.volume <= config.container_capacity
        )
        if task is not None and fleet is not None:
            if use_container:
                duration = fleet.container_load_minutes + fleet.container_unload_minutes + 2 * task.travel_minutes
            else:
                duration = fleet.normal_load_minutes + fleet.normal_unload_minutes + 2 * task.travel_minutes
            end_minute = assignment.start_minute + duration
        else:
            end_minute = assignment.end_minute
        assignments.append(
            Assignment(
                task_id=assignment.task_id,
                route_ids=list(assignment.route_ids),
                vehicle_id=assignment.vehicle_id,
                fleet_id=assignment.fleet_id,
                start_minute=assignment.start_minute,
                end_minute=end_minute,
                volume=assignment.volume,
                use_container=use_container,
                is_external=assignment.is_external,
            )
        )
    kpis = calculate_kpis(instance, tasks, assignments, config)
    return ScheduleSolution(
        status="FEASIBLE_BASELINE",
        objective=solution.objective,
        assignments=assignments,
        kpis=kpis,
        warnings=["Problem 3 used non-regression baseline derived from the problem-2 schedule."],
        solver="problem2-baseline-with-containers",
    )


def choose_lower_cost_solution(candidate: ScheduleSolution, baseline: ScheduleSolution) -> ScheduleSolution:
    candidate_cost = float(candidate.kpis.get("total_cost", float("inf"))) if candidate.kpis else float("inf")
    baseline_cost = float(baseline.kpis.get("total_cost", float("inf"))) if baseline.kpis else float("inf")
    if baseline_cost < candidate_cost:
        return baseline
    if baseline_cost == candidate_cost and count_container_tasks(baseline) > count_container_tasks(candidate):
        return baseline
    return candidate


def count_container_tasks(solution: ScheduleSolution) -> int:
    return sum(1 for assignment in solution.assignments if assignment.use_container)


def assignments_to_result_table(
    solution: ScheduleSolution,
    target_date: pd.Timestamp,
    base_date: pd.Timestamp,
    include_container: bool,
) -> pd.DataFrame:
    records = []
    for assignment in sorted(solution.assignments, key=lambda item: (item.start_minute, item.task_id)):
        dispatch_dt = base_date.to_pydatetime() + timedelta(minutes=int(assignment.start_minute))
        record = {
            "线路编码": ";".join(assignment.route_ids),
            "日期": dispatch_dt.strftime("%Y-%m-%d"),
            "预计发运时间": dispatch_dt.strftime("%H:%M:%S"),
        }
        if include_container:
            record["是否使用容器"] = "是" if assignment.use_container else "否"
        record["发运车辆"] = "外部" if assignment.is_external else assignment.vehicle_id
        records.append(record)
    columns = ["线路编码", "日期", "预计发运时间"]
    if include_container:
        columns.append("是否使用容器")
    columns.append("发运车辆")
    return pd.DataFrame(records, columns=columns)


def build_summary(
    experiment_config: ExperimentConfig,
    dataset: DDataset,
    result1: pd.DataFrame,
    result2: pd.DataFrame,
    result3: pd.DataFrame,
    result4: pd.DataFrame,
    tasks_p2: int,
    tasks_p3: int,
    solution_p2: ScheduleSolution,
    solution_p3: ScheduleSolution,
    candidate_p3: ScheduleSolution,
    baseline_p3: ScheduleSolution,
    sensitivity: pd.DataFrame,
    visual_outputs: list,
    audit_report: Dict[str, Any],
    agent_trace: list,
    weight_grid: list,
) -> Dict[str, Any]:
    focus = {}
    for route in experiment_config.focus_routes:
        focus[route] = {
            "daily_forecast": int(result1.loc[result1["线路编码"] == route, "货量"].sum()),
            "ten_min_rows": int((result2["线路编码"] == route).sum()),
            "problem2_rows": int(result3["线路编码"].astype(str).str.contains(re.escape(route), regex=True).sum()),
            "problem3_rows": int(result4["线路编码"].astype(str).str.contains(re.escape(route), regex=True).sum()),
        }

    return {
        "experiment": {
            "name": experiment_config.name,
            "forecast_model": experiment_config.forecast_model,
            "task_generation_strategy": experiment_config.task_generation_strategy,
            "solver_strategy": experiment_config.solver_strategy,
            "target_date": experiment_config.target_date,
            "base_date": experiment_config.base_date,
            "prefer_cpsat": experiment_config.prefer_cpsat,
        },
        "data": {
            "routes": int(dataset.routes["线路编码"].nunique()),
            "fleets": int(dataset.fleets["车队编码"].nunique()),
            "history_rows": int(len(dataset.history)),
            "known_daily_rows": int(len(dataset.known_daily)),
            "milk_run_rules": int(len(dataset.milk_run_rules)),
        },
        "outputs": {
            "result_table_1_rows": int(len(result1)),
            "result_table_1_missing": int(result1["货量"].isna().sum()),
            "result_table_2_rows": int(len(result2)),
            "result_table_2_missing": int(result2["包裹量"].isna().sum()),
            "result_table_3_rows": int(len(result3)),
            "result_table_4_rows": int(len(result4)),
            "sensitivity_rows": int(len(sensitivity)),
            "visual_outputs": visual_outputs,
            "constraint_audit": "constraint_audit.json",
        },
        "problem2": {
            "task_count": tasks_p2,
            "solver": solution_p2.solver,
            "status": solution_p2.status,
            "kpis": solution_p2.kpis,
            "paper_baseline": PAPER_BASELINES["problem2"],
            "warnings": solution_p2.warnings,
            "container_task_count": count_container_tasks(solution_p2),
        },
        "problem3": {
            "task_count": tasks_p3,
            "solver": solution_p3.solver,
            "status": solution_p3.status,
            "kpis": solution_p3.kpis,
            "paper_baseline": PAPER_BASELINES["problem3"],
            "warnings": solution_p3.warnings,
            "container_task_count": count_container_tasks(solution_p3),
            "pure_cpsat_candidate": {
                "solver": candidate_p3.solver,
                "status": candidate_p3.status,
                "total_cost": candidate_p3.kpis.get("total_cost", 0),
                "own_vehicle_turnover": candidate_p3.kpis.get("own_vehicle_turnover", 0),
                "container_task_count": count_container_tasks(candidate_p3),
            },
            "non_regression_baseline": {
                "solver": baseline_p3.solver,
                "status": baseline_p3.status,
                "total_cost": baseline_p3.kpis.get("total_cost", 0),
                "own_vehicle_turnover": baseline_p3.kpis.get("own_vehicle_turnover", 0),
                "container_task_count": count_container_tasks(baseline_p3),
            },
        },
        "focus_routes": focus,
        "sensitivity": summarize_sensitivity(sensitivity),
        "constraint_audit": summarize_constraint_audit(audit_report),
        "weight_grid_search": weight_grid,
        "reproduction_status": build_reproduction_status(solution_p2, solution_p3),
    }


def render_report(summary: Dict[str, Any]) -> str:
    p2 = summary["problem2"]
    p3 = summary["problem3"]
    lines = [
        "# D题真实数据第一批实验报告",
        "",
        "## 实验配置",
        f"- 实验名称：{summary['experiment']['name']}",
        f"- 预测模型：{summary['experiment']['forecast_model']}",
        f"- 任务生成：{summary['experiment']['task_generation_strategy']}",
        f"- 求解策略：{summary['experiment']['solver_strategy']}",
        "",
        "## 数据概览",
        f"- 线路数：{summary['data']['routes']}",
        f"- 车队数：{summary['data']['fleets']}",
        f"- 历史 10 分钟货量：{summary['data']['history_rows']} 行",
        f"- 日度预知货量：{summary['data']['known_daily_rows']} 行",
        f"- 可串点关系：{summary['data']['milk_run_rules']} 行",
        "",
        "## 输出校验",
        f"- 结果表 1：{summary['outputs']['result_table_1_rows']} 行，缺失 {summary['outputs']['result_table_1_missing']} 个",
        f"- 结果表 2：{summary['outputs']['result_table_2_rows']} 行，缺失 {summary['outputs']['result_table_2_missing']} 个",
        f"- 结果表 3：{summary['outputs']['result_table_3_rows']} 行",
        f"- 结果表 4：{summary['outputs']['result_table_4_rows']} 行",
        f"- 敏感性分析：{summary['outputs']['sensitivity_rows']} 个场景",
        f"- 可视化/解释文件：{len(summary['outputs']['visual_outputs'])} 个",
        "",
        "## 问题 2 KPI",
        _kpi_line(p2),
        "",
        "## 问题 3 KPI",
        _kpi_line(p3),
        "",
        "## 重点线路",
    ]
    for route, item in summary["focus_routes"].items():
        lines.append(
            f"- {route}: 日预测 {item['daily_forecast']}，10分钟行数 {item['ten_min_rows']}，"
            f"问题2调度行 {item['problem2_rows']}，问题3调度行 {item['problem3_rows']}"
        )
    lines.append("")
    if summary["outputs"]["visual_outputs"]:
        lines.append("## 可视化与解释文件")
        for output in summary["outputs"]["visual_outputs"]:
            lines.append(f"- `{output}`")
        lines.append("")
    lines.append("## 问题 4 敏感性分析")
    sensitivity = summary["sensitivity"]
    lines.append(
        f"- 基准场景装载 {sensitivity['baseline_loaded_volume']:.0f}，滞留 {sensitivity['baseline_stranded_volume']:.0f}，"
        f"按时装载率 {sensitivity['baseline_on_time_rate']:.2%}"
    )
    lines.append(
        f"- 最差服务场景：{sensitivity['worst_service_scenario']}，按时装载率 {sensitivity['worst_on_time_rate']:.2%}，"
        f"滞留 {sensitivity['worst_stranded_volume']:.0f}"
    )
    lines.append(
        f"- 最大滞留场景：{sensitivity['max_stranded_scenario']}，滞留 {sensitivity['max_stranded_volume']:.0f}"
    )
    lines.append("")
    lines.append("## 约束审计")
    audit = summary["constraint_audit"]
    lines.append(f"- 审计状态：{audit['status']}")
    lines.append(f"- 违规数量：{audit['violation_count']}")
    lines.append(f"- 警告数量：{audit['warning_count']}")
    lines.append("")
    lines.append("## 复现程度")
    reproduction = summary["reproduction_status"]
    lines.append(f"- 当前结论：{reproduction['level']}")
    for item in reproduction["notes"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 说明")
    lines.append("- 本批实验使用可解释统计预测基线，非 LSTM-MLP。")
    lines.append("- 若求解器显示 heuristic，表示 CP-SAT 未可用或未返回可行分配，已自动启发式兜底。")
    return "\n".join(lines)


def render_constraint_audit(audit_report: Dict[str, Any]) -> str:
    lines = ["# 约束审计报告", ""]
    for section, audit in audit_report.items():
        lines.append(f"## {section}")
        lines.append(f"- 检查对象数量：{audit.get('checked_count', 0)}")
        lines.append(f"- 违规数量：{len(audit.get('violations', []))}")
        lines.append(f"- 警告数量：{len(audit.get('warnings', []))}")
        for violation in audit.get("violations", [])[:20]:
            lines.append(f"- 违规：{violation}")
        for warning in audit.get("warnings", [])[:20]:
            lines.append(f"- 警告：{warning}")
        lines.append("")
    return "\n".join(lines)


def write_visual_artifacts(
    output_dir: Path,
    solution_p2: ScheduleSolution,
    solution_p3: ScheduleSolution,
    sensitivity: pd.DataFrame,
    result1: pd.DataFrame,
    result3: pd.DataFrame,
    result4: pd.DataFrame,
) -> list:
    outputs = []
    focus_report = output_dir / "focus_routes_report.md"
    focus_report.write_text(render_focus_routes_report(result1, result3, result4), encoding="utf-8")
    outputs.append(focus_report.name)

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return outputs

    gantt_p2 = output_dir / "gantt_problem2.png"
    gantt_p3 = output_dir / "gantt_problem3.png"
    sensitivity_png = output_dir / "sensitivity_on_time.png"
    plot_gantt(solution_p2, gantt_p2, "Problem 2 Dispatch Gantt")
    plot_gantt(solution_p3, gantt_p3, "Problem 3 Dispatch Gantt")
    plot_sensitivity(sensitivity, sensitivity_png)
    outputs.extend([gantt_p2.name, gantt_p3.name, sensitivity_png.name])
    plt.close("all")
    return outputs


def render_focus_routes_report(result1: pd.DataFrame, result3: pd.DataFrame, result4: pd.DataFrame) -> str:
    lines = ["# 重点线路预测与调度解释", ""]
    for route in FOCUS_ROUTES:
        daily_volume = int(result1.loc[result1["线路编码"] == route, "货量"].sum())
        lines.append(f"## {route}")
        lines.append(f"- 日度预测货量：{daily_volume}")
        lines.append("- 问题 2 调度：")
        focus_p2 = result3[result3["线路编码"].astype(str).str.contains(re.escape(route), regex=True)]
        lines.extend(format_records_for_markdown(focus_p2, ["线路编码", "日期", "预计发运时间", "发运车辆"]))
        lines.append("- 问题 3 调度：")
        focus_p3 = result4[result4["线路编码"].astype(str).str.contains(re.escape(route), regex=True)]
        lines.extend(format_records_for_markdown(focus_p3, ["线路编码", "日期", "预计发运时间", "是否使用容器", "发运车辆"]))
        lines.append("")
    return "\n".join(lines)


def format_records_for_markdown(frame: pd.DataFrame, columns: list) -> list:
    if frame.empty:
        return ["  - 无调度记录"]
    lines = []
    for row in frame[columns].head(20).itertuples(index=False):
        values = [str(value) for value in row]
        lines.append("  - " + " | ".join(values))
    return lines


def plot_gantt(solution: ScheduleSolution, path: Path, title: str) -> None:
    import matplotlib.pyplot as plt

    assignments = [item for item in solution.assignments if not item.is_external]
    assignments = sorted(assignments, key=lambda item: (item.vehicle_id, item.start_minute))
    vehicle_ids = sorted({item.vehicle_id for item in assignments})[:40]
    y_map = {vehicle_id: idx for idx, vehicle_id in enumerate(vehicle_ids)}

    fig_height = max(6, len(vehicle_ids) * 0.22)
    fig, ax = plt.subplots(figsize=(14, fig_height))
    for assignment in assignments:
        if assignment.vehicle_id not in y_map:
            continue
        y = y_map[assignment.vehicle_id]
        color = "#2E86AB" if not assignment.use_container else "#2A9D8F"
        ax.barh(y, max(assignment.end_minute - assignment.start_minute, 1), left=assignment.start_minute, height=0.8, color=color)
    ax.set_yticks(list(y_map.values()))
    ax.set_yticklabels([ascii_vehicle_label(vehicle_id) for vehicle_id in vehicle_ids], fontsize=7)
    ax.set_xlabel("Minutes since 2024-12-15 00:00")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def ascii_vehicle_label(vehicle_id: str) -> str:
    return vehicle_id.replace("车队", "Fleet")


def plot_sensitivity(sensitivity: pd.DataFrame, path: Path) -> None:
    import matplotlib.pyplot as plt

    labels = [f"{row.scenario_type}\n{row.parameter}" for row in sensitivity.itertuples(index=False)]
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(labels, sensitivity["on_time_rate"], marker="o", color="#1D4ED8", label="On-time load rate")
    ax1.set_ylabel("On-time load rate")
    ax1.set_ylim(0, 1.05)
    ax1.tick_params(axis="x", rotation=35)
    ax2 = ax1.twinx()
    ax2.bar(labels, sensitivity["stranded_volume"], alpha=0.25, color="#DC2626", label="Stranded volume")
    ax2.set_ylabel("Stranded volume")
    ax1.set_title("Sensitivity: service level and stranded volume")
    ax1.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def run_sensitivity_analysis(
    forecast: pd.DataFrame,
    solution: ScheduleSolution,
    instance: Instance,
    config: ProblemConfig,
    base_date: pd.Timestamp,
) -> pd.DataFrame:
    """Evaluate a fixed problem-3 schedule under volume bias and arrival drift scenarios."""
    scenarios = [{"scenario_type": "baseline", "parameter": "base", "volume_factor": 1.0, "shift_minutes": 0}]
    scenarios.extend(
        {"scenario_type": "volume_bias", "parameter": f"{factor:+.0%}", "volume_factor": factor, "shift_minutes": 0}
        for factor in (0.7, 0.9, 1.1, 1.3)
    )
    scenarios.extend(
        {"scenario_type": "time_shift", "parameter": f"{shift:+d}min", "volume_factor": 1.0, "shift_minutes": shift}
        for shift in (-60, -30, 30, 60, 90)
    )

    records = []
    baseline = None
    for scenario in scenarios:
        metrics = simulate_fixed_schedule(forecast, solution, instance, config, base_date, scenario["volume_factor"], scenario["shift_minutes"])
        row = {**scenario, **metrics}
        if scenario["scenario_type"] == "baseline":
            baseline = row
        records.append(row)

    frame = pd.DataFrame(records)
    if baseline:
        for column in ("loaded_volume", "stranded_volume", "on_time_rate", "own_vehicle_turnover", "avg_packages_per_vehicle"):
            base_value = float(baseline[column])
            if base_value == 0:
                frame[f"{column}_relative_change"] = 0.0
            else:
                frame[f"{column}_relative_change"] = frame[column] / base_value - 1.0
    return frame


def audit_tasks(tasks: list, config: ProblemConfig) -> Dict[str, Any]:
    violations = []
    warnings = []
    for task in tasks:
        if task.volume <= 0:
            violations.append(f"{task.id}: non-positive volume {task.volume}")
        if task.volume > config.vehicle_capacity:
            violations.append(f"{task.id}: volume {task.volume} exceeds vehicle capacity {config.vehicle_capacity}")
        if task.stop_count > config.max_stops:
            violations.append(f"{task.id}: stop count {task.stop_count} exceeds max stops {config.max_stops}")
        if task.earliest_minute > task.latest_minute:
            violations.append(f"{task.id}: infeasible time window")
        if task.source == "tail_milk_run" and config.milk_run_pairs:
            destinations = task.destinations
            for left_idx, left in enumerate(destinations):
                for right in destinations[left_idx + 1 :]:
                    if tuple(sorted((left, right))) not in config.milk_run_pairs:
                        violations.append(f"{task.id}: incompatible milk-run pair {left}, {right}")
    return {"checked_count": len(tasks), "violations": violations, "warnings": warnings}


def audit_solution(solution: ScheduleSolution, tasks: list, config: ProblemConfig) -> Dict[str, Any]:
    task_by_id = {task.id: task for task in tasks}
    violations = []
    warnings = []
    assigned_task_ids = {assignment.task_id for assignment in solution.assignments}
    if len(assigned_task_ids) != len(tasks):
        violations.append(f"assigned unique tasks {len(assigned_task_ids)} != generated tasks {len(tasks)}")
    by_vehicle: Dict[str, list] = {}
    for assignment in solution.assignments:
        task = task_by_id.get(assignment.task_id)
        if task is None:
            violations.append(f"{assignment.task_id}: assignment references unknown task")
            continue
        if assignment.start_minute > task.latest_minute:
            violations.append(f"{assignment.task_id}: starts after latest dispatch")
        if assignment.volume > config.container_capacity and assignment.use_container:
            violations.append(f"{assignment.task_id}: container task exceeds container capacity")
        if assignment.use_container and assignment.is_external:
            violations.append(f"{assignment.task_id}: external carrier uses container")
        if not assignment.is_external:
            by_vehicle.setdefault(assignment.vehicle_id, []).append(assignment)
    for vehicle_id, assignments in by_vehicle.items():
        sorted_assignments = sorted(assignments, key=lambda item: item.start_minute)
        for current, nxt in zip(sorted_assignments, sorted_assignments[1:]):
            if current.end_minute > nxt.start_minute:
                violations.append(f"{vehicle_id}: overlap between {current.task_id} and {nxt.task_id}")
    if solution.status not in {"OPTIMAL", "FEASIBLE", "FEASIBLE_BASELINE"}:
        warnings.append(f"solver status is {solution.status}")
    return {"checked_count": len(solution.assignments), "violations": violations, "warnings": warnings}


def summarize_constraint_audit(audit_report: Dict[str, Any]) -> Dict[str, Any]:
    violations = sum(len(audit.get("violations", [])) for audit in audit_report.values())
    warnings = sum(len(audit.get("warnings", [])) for audit in audit_report.values())
    return {
        "status": "pass" if violations == 0 else "fail",
        "violation_count": violations,
        "warning_count": warnings,
    }


def serialize_agent_trace(trace: list) -> list:
    serialized = []
    for item in trace:
        if isinstance(item, AgentStepResult):
            serialized.append(
                {
                    "agent": item.agent,
                    "status": item.status,
                    "summary": item.summary,
                    "metrics": item.metrics,
                }
            )
        else:
            serialized.append(item)
    return serialized


def run_weight_grid_search(solution_p2: ScheduleSolution, candidate_p3: ScheduleSolution, baseline_p3: ScheduleSolution) -> list:
    """Score existing candidate solutions under a small objective grid.

    This is intentionally lightweight: it does not rerun CP-SAT repeatedly, but
    it exposes how weight choices would rank the available feasible solutions.
    """
    candidates = {
        "problem2_cpsat": solution_p2,
        "problem3_cpsat_candidate": candidate_p3,
        "problem3_non_regression_baseline": baseline_p3,
    }
    grid = [
        {"cost": 1.0, "turnover": 0.5, "fill_rate": 0.2},
        {"cost": 1.5, "turnover": 0.3, "fill_rate": 0.1},
        {"cost": 0.8, "turnover": 0.8, "fill_rate": 0.2},
        {"cost": 1.0, "turnover": 0.4, "fill_rate": 0.5},
    ]
    results = []
    for weights in grid:
        scored = []
        for name, solution in candidates.items():
            kpis = solution.kpis
            score = (
                weights["cost"] * kpis.get("total_cost", 0)
                - weights["turnover"] * 1000 * kpis.get("own_vehicle_turnover", 0)
                + weights["fill_rate"] * kpis.get("unused_capacity", 0)
            )
            scored.append({"candidate": name, "score": score})
        best = min(scored, key=lambda item: item["score"])
        results.append({"weights": weights, "best_candidate": best["candidate"], "scores": scored})
    return results


def build_reproduction_status(solution_p2: ScheduleSolution, solution_p3: ScheduleSolution) -> Dict[str, Any]:
    p2_cost_gap = solution_p2.kpis.get("total_cost", 0) - PAPER_BASELINES["problem2"]["total_cost"]
    p3_cost_gap = solution_p3.kpis.get("total_cost", 0) - PAPER_BASELINES["problem3"]["total_cost"]
    return {
        "level": "engineering_baseline_not_exact_reproduction",
        "notes": [
            f"问题2成本较论文参考高 {p2_cost_gap:.0f}，周转率为 {solution_p2.kpis.get('own_vehicle_turnover', 0):.2f}。",
            f"问题3成本较论文参考高 {p3_cost_gap:.0f}，当前使用 {solution_p3.solver}。",
            "预测模型为统计基线，尚未复刻论文 LSTM-MLP。",
            "问题3保留纯 CP-SAT 候选与非退化基线对比，避免把修复方案误报为纯优化结果。",
        ],
    }


def simulate_fixed_schedule(
    forecast: pd.DataFrame,
    solution: ScheduleSolution,
    instance: Instance,
    config: ProblemConfig,
    base_date: pd.Timestamp,
    volume_factor: float,
    shift_minutes: int,
) -> Dict[str, float]:
    arrivals: Dict[str, list] = {}
    total_actual_volume = 0
    for row in forecast.itertuples(index=False):
        row_date = pd.to_datetime(row.日期).normalize()
        absolute_minute = int((row_date - base_date).days * 1440 + time_to_minute(row.分钟起始) + shift_minutes)
        volume = int(round(float(row.包裹量) * volume_factor))
        volume = max(volume, 0)
        total_actual_volume += volume
        arrivals.setdefault(row.线路编码, []).append([absolute_minute, volume])

    for route_buckets in arrivals.values():
        route_buckets.sort(key=lambda item: item[0])

    loaded_volume = 0
    loaded_by_own = 0
    loaded_assignment_count = 0
    own_loaded_assignment_count = 0
    for assignment in sorted(solution.assignments, key=lambda item: item.start_minute):
        capacity = config.container_capacity if assignment.use_container else config.vehicle_capacity
        remaining_capacity = capacity
        assignment_loaded = 0
        for route_id in assignment.route_ids:
            buckets = arrivals.get(route_id, [])
            for bucket in buckets:
                if bucket[0] > assignment.start_minute or remaining_capacity <= 0:
                    break
                take = min(bucket[1], remaining_capacity)
                bucket[1] -= take
                remaining_capacity -= take
                assignment_loaded += take
        loaded_volume += assignment_loaded
        if assignment_loaded > 0:
            loaded_assignment_count += 1
            if not assignment.is_external:
                own_loaded_assignment_count += 1
                loaded_by_own += assignment_loaded

    stranded_volume = max(total_actual_volume - loaded_volume, 0)
    total_own_vehicle_count = sum(fleet.vehicle_count for fleet in instance.fleets)
    external_task_count = sum(1 for assignment in solution.assignments if assignment.is_external)
    vehicle_denominator = total_own_vehicle_count + external_task_count
    return {
        "total_actual_volume": float(total_actual_volume),
        "loaded_volume": float(loaded_volume),
        "loaded_by_own": float(loaded_by_own),
        "stranded_volume": float(stranded_volume),
        "on_time_rate": loaded_volume / total_actual_volume if total_actual_volume else 1.0,
        "loaded_assignment_count": float(loaded_assignment_count),
        "own_loaded_assignment_count": float(own_loaded_assignment_count),
        "own_vehicle_turnover": own_loaded_assignment_count / total_own_vehicle_count if total_own_vehicle_count else 0.0,
        "avg_packages_per_vehicle": loaded_volume / vehicle_denominator if vehicle_denominator else 0.0,
        "total_cost": float(solution.kpis.get("total_cost", 0.0)),
    }


def summarize_sensitivity(sensitivity: pd.DataFrame) -> Dict[str, Any]:
    baseline = sensitivity[sensitivity["scenario_type"] == "baseline"].iloc[0]
    worst_service = sensitivity.sort_values("on_time_rate").iloc[0]
    max_stranded = sensitivity.sort_values("stranded_volume", ascending=False).iloc[0]
    return {
        "baseline_loaded_volume": float(baseline["loaded_volume"]),
        "baseline_stranded_volume": float(baseline["stranded_volume"]),
        "baseline_on_time_rate": float(baseline["on_time_rate"]),
        "worst_service_scenario": f"{worst_service['scenario_type']} {worst_service['parameter']}",
        "worst_on_time_rate": float(worst_service["on_time_rate"]),
        "worst_stranded_volume": float(worst_service["stranded_volume"]),
        "max_stranded_scenario": f"{max_stranded['scenario_type']} {max_stranded['parameter']}",
        "max_stranded_volume": float(max_stranded["stranded_volume"]),
    }


def _kpi_line(problem: Dict[str, Any]) -> str:
    kpis = problem["kpis"]
    baseline = problem["paper_baseline"]
    return (
        f"- 求解器：{problem['solver']}，状态：{problem['status']}，任务数：{problem['task_count']}，"
        f"总成本：{kpis.get('total_cost', 0):.0f}（论文参考 {baseline['total_cost']:.0f}），"
        f"自有车周转率：{kpis.get('own_vehicle_turnover', 0):.2f}（论文参考 {baseline['own_vehicle_turnover']:.2f}），"
        f"车辆均包裹：{kpis.get('avg_packages_per_vehicle', 0):.2f}，"
        f"外部承运：{kpis.get('external_task_count', 0):.0f}，"
        f"容器任务：{problem.get('container_task_count', 0)}"
    )


def build_milk_run_pairs(rules: pd.DataFrame) -> set:
    pairs = set()
    for row in rules.itertuples(index=False):
        left = normalize_site(getattr(row, "站点编号1"))
        right = normalize_site(getattr(row, "站点编号2"))
        pairs.add(tuple(sorted((left, right))))
    return pairs


def normalize_route_code(value: Any) -> str:
    text = str(value).strip()
    text = re.sub(r"\s*-\s*", " - ", text)
    text = re.sub(r"(场地|站点)\s+(\d+)", r"\1\2", text)
    return text


def normalize_fleet_code(value: Any) -> str:
    return re.sub(r"\s+", "", str(value).strip())


def normalize_site(value: Any) -> str:
    return re.sub(r"\s+", "", str(value).strip())


def route_wave(route_id: str) -> str:
    return normalize_route_code(route_id).split(" - ")[-1]


def time_to_minute(value: Any) -> int:
    if isinstance(value, pd.Timestamp):
        return value.hour * 60 + value.minute
    if isinstance(value, datetime):
        return value.hour * 60 + value.minute
    if isinstance(value, time):
        return value.hour * 60 + value.minute
    if isinstance(value, timedelta):
        return int(value.total_seconds() // 60)
    text = str(value)
    match = re.search(r"(\d{1,2}):(\d{2})(?::\d{2})?", text)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    raise ValueError(f"Unsupported time value: {value!r}")


def allocate_integer_volume(total: int, weights: Iterable[float]) -> list:
    weights_array = np.array([max(float(weight), 0.0) for weight in weights], dtype=float)
    if len(weights_array) == 0:
        return []
    if weights_array.sum() <= 0:
        weights_array[:] = 1.0
    raw = weights_array / weights_array.sum() * int(total)
    floors = np.floor(raw).astype(int)
    remainder = int(total) - int(floors.sum())
    if remainder > 0:
        order = np.argsort(-(raw - floors))
        floors[order[:remainder]] += 1
    return floors.tolist()


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
