from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shorthaul_agent.experiment import (  # noqa: E402
    allocate_integer_volume,
    audit_tasks,
    build_milk_run_pairs,
    build_reproduction_status,
    load_experiment_config,
    normalize_route_code,
    parse_simple_yaml,
)
from shorthaul_agent.models import DispatchTask, ProblemConfig, ScheduleSolution  # noqa: E402


def test_normalize_route_code_standardizes_hyphen_spacing():
    assert normalize_route_code("site3- stop83-0600") == "site3 - stop83 - 0600"


def test_allocate_integer_volume_preserves_total():
    volumes = allocate_integer_volume(101, [0.2, 0.3, 0.5])
    assert sum(volumes) == 101
    assert volumes == [20, 30, 51]


def test_build_milk_run_pairs_normalizes_sites():
    import pandas as pd

    pairs = build_milk_run_pairs(pd.DataFrame([{"\u7ad9\u70b9\u7f16\u53f71": "site 1", "\u7ad9\u70b9\u7f16\u53f72": "site2"}]))
    assert ("site1", "site2") in pairs


def test_experiment_config_yaml_loads_defaults():
    config = load_experiment_config(ROOT / "experiments" / "d_problem_baseline.yaml")
    assert config.name == "d_problem_baseline"
    assert config.prefer_cpsat is True
    assert config.cpsat_search_seeds == [0]
    assert len(config.focus_routes) == 2


def test_performance_config_loads_cpsat_portfolio_defaults():
    config = load_experiment_config(ROOT / "experiments" / "d_problem_performance.yaml")
    assert config.name == "d_problem_performance_portfolio"
    assert config.cpsat_search_seeds == [0, 7, 19]
    assert config.cpsat_num_workers == 8


def test_simple_yaml_parses_numeric_lists():
    parsed = parse_simple_yaml("cpsat_search_seeds: [0, 7, 19]\ncpsat_num_workers: 4\n")
    assert parsed["cpsat_search_seeds"] == [0, 7, 19]
    assert parsed["cpsat_num_workers"] == 4


def test_problem_config_merges_cpsat_seed_lists():
    config = ProblemConfig().merged({"cpsat_search_seeds": [3, 5], "cpsat_num_workers": 1})
    assert config.cpsat_search_seeds == (3, 5)
    assert config.cpsat_num_workers == 1


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
