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
    polish_external_assignments,
)
from shorthaul_agent.models import Assignment, DispatchTask, Fleet, Instance, ProblemConfig, ScheduleSolution  # noqa: E402
from shorthaul_agent.solvers.task_generation import _candidate_tail_sets, _tail_cover_weight, consolidate_tail_tasks  # noqa: E402


def make_tail_task(task_id: str, destination: str, volume: int, external_cost: int) -> DispatchTask:
    return DispatchTask(
        id=task_id,
        route_ids=[f"route-{task_id}"],
        origin="site",
        destinations=[destination],
        wave="0600",
        volume=volume,
        earliest_minute=0,
        latest_minute=600,
        travel_minutes=30,
        fleet_id="fleet",
        variable_cost=100,
        external_cost=external_cost,
        source="tail",
    )


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
    assert config.tail_cover_strategy == "cost_aware"
    assert config.tail_candidate_strategy == "exhaustive"
    assert config.tail_candidate_strategy_grid == ["exhaustive", "beam"]


def test_simple_yaml_parses_numeric_lists():
    parsed = parse_simple_yaml("cpsat_search_seeds: [0, 7, 19]\ncpsat_num_workers: 4\n")
    assert parsed["cpsat_search_seeds"] == [0, 7, 19]
    assert parsed["cpsat_num_workers"] == 4


def test_problem_config_merges_cpsat_seed_lists():
    config = ProblemConfig().merged({"cpsat_search_seeds": [3, 5], "cpsat_num_workers": 1})
    assert config.cpsat_search_seeds == (3, 5)
    assert config.cpsat_num_workers == 1


def test_tail_cover_saving_strategy_prefers_external_saving():
    tasks = [
        make_tail_task("a", "d1", 300, 500),
        make_tail_task("b", "d2", 300, 400),
        make_tail_task("c", "d3", 300, 100),
    ]
    config = ProblemConfig(tail_cover_strategy="saving_aware")

    high_saving_pair = _tail_cover_weight((0, 1), tasks, config)
    low_saving_pair = _tail_cover_weight((0, 2), tasks, config)

    assert high_saving_pair < low_saving_pair


def test_tail_cover_default_strategy_prefers_tighter_fill():
    tasks = [
        make_tail_task("a", "d1", 300, 500),
        make_tail_task("b", "d2", 400, 400),
        make_tail_task("c", "d3", 50, 100),
    ]
    config = ProblemConfig(vehicle_capacity=700)

    tight_pair = _tail_cover_weight((0, 1), tasks, config)
    loose_pair = _tail_cover_weight((0, 2), tasks, config)

    assert tight_pair < loose_pair


def test_tail_cover_uses_saving_strategy_for_candidate_selection():
    tasks = [
        make_tail_task("a", "d1", 300, 500),
        make_tail_task("b", "d2", 300, 400),
        make_tail_task("c", "d3", 300, 100),
    ]
    config = ProblemConfig(
        vehicle_capacity=700,
        max_stops=2,
        set_cover_tail_threshold=10,
        tail_cover_strategy="saving_aware",
    )

    consolidated = consolidate_tail_tasks(tasks, config)
    route_sets = {frozenset(task.route_ids) for task in consolidated}

    assert frozenset({"route-a", "route-b"}) in route_sets
    assert frozenset({"route-c"}) in route_sets


def test_tail_candidate_beam_preserves_singletons_and_prunes_search():
    tasks = [
        make_tail_task("a", "d1", 100, 500),
        make_tail_task("b", "d2", 120, 400),
        make_tail_task("c", "d3", 140, 300),
        make_tail_task("d", "d4", 160, 200),
        make_tail_task("e", "d5", 180, 100),
        make_tail_task("f", "d6", 200, 90),
    ]
    exhaustive = ProblemConfig(vehicle_capacity=700, max_stops=3, tail_candidate_strategy="exhaustive")
    beam = ProblemConfig(vehicle_capacity=700, max_stops=3, tail_candidate_strategy="beam", tail_beam_width=1)

    exhaustive_candidates = _candidate_tail_sets(tasks, exhaustive)
    beam_candidates = _candidate_tail_sets(tasks, beam)

    assert len(beam_candidates) < len(exhaustive_candidates)
    assert {(idx,) for idx in range(len(tasks))}.issubset(set(beam_candidates))
    assert all(sum(tasks[idx].volume for idx in combo) <= beam.vehicle_capacity for combo in beam_candidates)


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


def test_external_repair_converts_feasible_gap_to_owned_vehicle():
    instance = Instance(
        id="unit",
        date="2024-12-16",
        routes=[],
        fleets=[Fleet(id="fleet", vehicle_count=1, fixed_cost=0, variable_cost_per_trip=10)],
        forecast=[],
    )
    owned_task = DispatchTask(
        id="owned",
        route_ids=["r1"],
        origin="o",
        destinations=["d1"],
        wave="0600",
        volume=1000,
        earliest_minute=0,
        latest_minute=0,
        travel_minutes=5,
        fleet_id="fleet",
        variable_cost=10,
        external_cost=100,
        source="full_load",
    )
    external_task = DispatchTask(
        id="external",
        route_ids=["r2"],
        origin="o",
        destinations=["d2"],
        wave="0600",
        volume=1000,
        earliest_minute=200,
        latest_minute=300,
        travel_minutes=5,
        fleet_id="fleet",
        variable_cost=10,
        external_cost=100,
        source="full_load",
    )
    solution = ScheduleSolution(
        status="FEASIBLE",
        objective=0,
        assignments=[
            Assignment("owned", ["r1"], "Own_fleet_1", "fleet", 0, 100, 1000, False, False),
            Assignment("external", ["r2"], "External_external", "fleet", 200, 300, 1000, False, True),
        ],
        kpis={"total_cost": 120.0},
        solver="unit",
    )

    repaired = polish_external_assignments(instance, [owned_task, external_task], solution, ProblemConfig())

    assert repaired.kpis["external_task_count"] == 0
    assert repaired.kpis["total_cost"] < solution.kpis["total_cost"]
    assert repaired.solver == "unit+external-repair"


def test_external_repair_swaps_higher_saving_external_task():
    instance = Instance(
        id="unit",
        date="2024-12-16",
        routes=[],
        fleets=[Fleet(id="fleet", vehicle_count=1, fixed_cost=0, variable_cost_per_trip=10)],
        forecast=[],
    )
    low_saving = DispatchTask(
        id="low",
        route_ids=["r1"],
        origin="o",
        destinations=["d1"],
        wave="0600",
        volume=1000,
        earliest_minute=0,
        latest_minute=0,
        travel_minutes=5,
        fleet_id="fleet",
        variable_cost=10,
        external_cost=30,
        source="full_load",
    )
    high_saving = DispatchTask(
        id="high",
        route_ids=["r2"],
        origin="o",
        destinations=["d2"],
        wave="0600",
        volume=1000,
        earliest_minute=0,
        latest_minute=0,
        travel_minutes=5,
        fleet_id="fleet",
        variable_cost=10,
        external_cost=200,
        source="full_load",
    )
    solution = ScheduleSolution(
        status="FEASIBLE",
        objective=0,
        assignments=[
            Assignment("low", ["r1"], "Own_fleet_1", "fleet", 0, 100, 1000, False, False),
            Assignment("high", ["r2"], "External_high", "fleet", 0, 100, 1000, False, True),
        ],
        kpis={"total_cost": 220.0},
        solver="unit",
    )

    repaired = polish_external_assignments(instance, [low_saving, high_saving], solution, ProblemConfig())

    owned_ids = {assignment.task_id for assignment in repaired.assignments if not assignment.is_external}
    external_ids = {assignment.task_id for assignment in repaired.assignments if assignment.is_external}
    assert "high" in owned_ids
    assert "low" in external_ids
    assert repaired.kpis["total_cost"] < solution.kpis["total_cost"]
