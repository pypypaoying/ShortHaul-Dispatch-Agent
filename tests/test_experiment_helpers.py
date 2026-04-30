from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shorthaul_agent.experiment import (
    allocate_integer_volume,
    audit_tasks,
    build_milk_run_pairs,
    build_reproduction_status,
    load_experiment_config,
    normalize_route_code,
)
from shorthaul_agent.models import DispatchTask, ProblemConfig, ScheduleSolution


def test_normalize_route_code_removes_internal_entity_spaces():
    assert normalize_route_code("场地 3 - 站点 83 - 0600") == "场地3 - 站点83 - 0600"


def test_allocate_integer_volume_preserves_total():
    volumes = allocate_integer_volume(101, [0.2, 0.3, 0.5])
    assert sum(volumes) == 101
    assert volumes == [20, 30, 51]


def test_build_milk_run_pairs_normalizes_sites():
    import pandas as pd

    pairs = build_milk_run_pairs(pd.DataFrame([{"站点编号1": "站点 1", "站点编号2": "站点2"}]))
    assert ("站点1", "站点2") in pairs


def test_experiment_config_yaml_loads_defaults():
    config = load_experiment_config(ROOT / "experiments" / "d_problem_baseline.yaml")
    assert config.name == "d_problem_baseline"
    assert config.prefer_cpsat is True
    assert "场地3 - 站点83 - 0600" in config.focus_routes


def test_task_audit_catches_capacity_violation():
    task = DispatchTask(
        id="bad",
        route_ids=["r1"],
        origin="o",
        destinations=["d"],
        wave="0600",
        volume=1200,
        earliest_minute=0,
        latest_minute=10,
        travel_minutes=10,
        fleet_id="f",
        variable_cost=1,
        external_cost=2,
        source="full_load",
    )
    audit = audit_tasks([task], ProblemConfig(vehicle_capacity=1000))
    assert audit["violations"]


def test_reproduction_status_marks_engineering_baseline():
    solution = ScheduleSolution(
        status="FEASIBLE",
        objective=0,
        assignments=[],
        kpis={"total_cost": 1, "own_vehicle_turnover": 1},
        solver="unit",
    )
    status = build_reproduction_status(solution, solution)
    assert status["level"] == "engineering_baseline_not_exact_reproduction"
