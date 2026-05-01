"""Convert fine-grained volume forecasts into dispatch tasks."""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Optional

from shorthaul_agent.models import DispatchTask, ForecastBucket, Instance, ProblemConfig, Route


def generate_dispatch_tasks(instance: Instance, config: ProblemConfig) -> list[DispatchTask]:
    """Generate full-load tasks and consolidate tail-load tasks.

    This mirrors the paper's two-stage logic: first convert 10-minute forecasts into
    vehicle-capacity tasks, then solve a small set-covering problem over tail loads.
    """
    routes = {route.id: route for route in instance.routes}
    by_route: dict[str, list[ForecastBucket]] = defaultdict(list)
    for bucket in instance.forecast:
        if bucket.route_id in routes:
            by_route[bucket.route_id].append(bucket)

    full_tasks: list[DispatchTask] = []
    tail_tasks: list[DispatchTask] = []

    for route_id, buckets in by_route.items():
        route = routes[route_id]
        carry = 0
        task_index = 1
        for bucket in sorted(buckets, key=lambda item: item.minute):
            carry += bucket.volume
            while carry >= config.vehicle_capacity:
                full_tasks.append(
                    _task_from_route(
                        route=route,
                        task_id=f"{route.id}#full-{task_index}",
                        volume=config.vehicle_capacity,
                        earliest_minute=bucket.minute,
                        source="full_load",
                    )
                )
                task_index += 1
                carry -= config.vehicle_capacity

        if carry > 0:
            tail_tasks.append(
                _task_from_route(
                    route=route,
                    task_id=f"{route.id}#tail",
                    volume=carry,
                    earliest_minute=min(route.latest_dispatch_minute, max(bucket.minute for bucket in buckets)),
                    source="tail",
                )
            )

    return full_tasks + consolidate_tail_tasks(tail_tasks, config)


def consolidate_tail_tasks(tail_tasks: list[DispatchTask], config: ProblemConfig) -> list[DispatchTask]:
    if not tail_tasks:
        return []

    grouped: dict[tuple[str, str], list[DispatchTask]] = defaultdict(list)
    for task in tail_tasks:
        grouped[(task.origin, task.wave)].append(task)

    consolidated: list[DispatchTask] = []
    for group_tasks in grouped.values():
        if len(group_tasks) > config.set_cover_tail_threshold:
            consolidated.extend(group_tasks)
            continue
        cpsat_solution = _try_cpsat_tail_cover(group_tasks, config)
        if cpsat_solution is not None:
            consolidated.extend(cpsat_solution)
        else:
            consolidated.extend(_greedy_tail_cover(group_tasks, config))
    return consolidated


def _task_from_route(
    route: Route,
    task_id: str,
    volume: int,
    earliest_minute: int,
    source: str,
) -> DispatchTask:
    return DispatchTask(
        id=task_id,
        route_ids=[route.id],
        origin=route.origin,
        destinations=[route.destination],
        wave=route.wave,
        volume=volume,
        earliest_minute=earliest_minute,
        latest_minute=route.latest_dispatch_minute,
        travel_minutes=route.travel_minutes,
        fleet_id=route.fleet_id,
        variable_cost=route.variable_cost,
        external_cost=route.external_cost or int(route.variable_cost * route.external_cost_multiplier),
        source=source,
    )


def _merge_tail_tasks(tasks: list[DispatchTask], group_index: int) -> DispatchTask:
    first = tasks[0]
    route_ids: list[str] = []
    destinations: list[str] = []
    variable_cost = 0
    external_cost = 0
    for task in tasks:
        route_ids.extend(task.route_ids)
        destinations.extend(task.destinations)
        variable_cost = max(variable_cost, task.variable_cost)
        external_cost = max(external_cost, task.external_cost)

    return DispatchTask(
        id=f"{first.origin}-{first.wave}#milk-run-{group_index}",
        route_ids=route_ids,
        origin=first.origin,
        destinations=destinations,
        wave=first.wave,
        volume=sum(task.volume for task in tasks),
        earliest_minute=max(task.earliest_minute for task in tasks),
        latest_minute=min(task.latest_minute for task in tasks),
        travel_minutes=max(task.travel_minutes for task in tasks) + 10 * (len(tasks) - 1),
        fleet_id=first.fleet_id,
        variable_cost=variable_cost,
        external_cost=external_cost,
        source="tail_milk_run" if len(tasks) > 1 else "tail_single",
    )


def _candidate_tail_sets(tasks: list[DispatchTask], config: ProblemConfig) -> list[tuple[int, ...]]:
    indices = range(len(tasks))
    candidates: list[tuple[int, ...]] = [(idx,) for idx in indices]
    for size in range(2, config.max_stops + 1):
        for combo in combinations(indices, size):
            if sum(tasks[idx].volume for idx in combo) <= config.vehicle_capacity and _destinations_compatible(combo, tasks, config):
                latest = min(tasks[idx].latest_minute for idx in combo)
                earliest = max(tasks[idx].earliest_minute for idx in combo)
                if earliest <= latest:
                    candidates.append(combo)
    return candidates


def _try_cpsat_tail_cover(tasks: list[DispatchTask], config: ProblemConfig) -> Optional[list[DispatchTask]]:
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return None

    candidates = _candidate_tail_sets(tasks, config)
    model = cp_model.CpModel()
    selected = [model.NewBoolVar(f"tail_set_{idx}") for idx, _ in enumerate(candidates)]

    for task_idx in range(len(tasks)):
        covering = [selected[idx] for idx, combo in enumerate(candidates) if task_idx in combo]
        model.Add(sum(covering) == 1)

    weights = [_tail_cover_weight(candidate, tasks, config) for candidate in candidates]
    model.Minimize(sum(weights[idx] * selected[idx] for idx in range(len(candidates))))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = min(config.solver_time_limit_seconds, 3.0)
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    merged: list[DispatchTask] = []
    group_index = 1
    for idx, combo in enumerate(candidates):
        if solver.Value(selected[idx]):
            merged.append(_merge_tail_tasks([tasks[task_idx] for task_idx in combo], group_index))
            group_index += 1
    return merged


def _greedy_tail_cover(tasks: list[DispatchTask], config: ProblemConfig) -> list[DispatchTask]:
    remaining = sorted(tasks, key=lambda item: item.volume, reverse=True)
    groups: list[list[DispatchTask]] = []
    while remaining:
        current = [remaining.pop(0)]
        changed = True
        while changed and len(current) < config.max_stops:
            changed = False
            current_volume = sum(task.volume for task in current)
            latest = min(task.latest_minute for task in current)
            best_index = None
            best_weight = None
            for idx, candidate in enumerate(remaining):
                combined_volume = current_volume + candidate.volume
                combined_earliest = max(max(task.earliest_minute for task in current), candidate.earliest_minute)
                combined_latest = min(latest, candidate.latest_minute)
                combo_tasks = current + [candidate]
                compatible = _destinations_compatible(tuple(range(len(combo_tasks))), combo_tasks, config)
                if combined_volume <= config.vehicle_capacity and combined_earliest <= combined_latest and compatible:
                    weight = _tail_cover_weight(tuple(range(len(combo_tasks))), combo_tasks, config)
                    if best_weight is None or weight < best_weight:
                        best_index = idx
                        best_weight = weight
            if best_index is not None:
                current.append(remaining.pop(best_index))
                changed = True
        groups.append(current)

    return [_merge_tail_tasks(group, idx + 1) for idx, group in enumerate(groups)]


def _destinations_compatible(combo: tuple[int, ...], tasks: list[DispatchTask], config: ProblemConfig) -> bool:
    if not config.milk_run_pairs or len(combo) <= 1:
        return True
    destinations = [tasks[idx].destinations[0] for idx in combo]
    for left_idx, left in enumerate(destinations):
        for right in destinations[left_idx + 1 :]:
            if tuple(sorted((left, right))) not in config.milk_run_pairs:
                return False
    return True


def _tail_cover_weight(combo: tuple[int, ...], tasks: list[DispatchTask], config: ProblemConfig) -> int:
    merged = _merge_tail_tasks([tasks[idx] for idx in combo], 1)
    slack = config.vehicle_capacity - merged.volume
    single_external_cost = sum(tasks[idx].external_cost for idx in combo)
    external_saving = single_external_cost - merged.external_cost
    strategy = config.tail_cover_strategy

    if strategy == "cost_aware":
        tie_breaker = merged.external_cost * 100 + merged.variable_cost * 20 + merged.travel_minutes * 2 + slack
    elif strategy == "duration_aware":
        tie_breaker = merged.travel_minutes * 100 + merged.external_cost * 10 + slack
    elif strategy == "saving_aware":
        tie_breaker = -external_saving * 100 + merged.travel_minutes * 5 + slack
    elif strategy == "fill_aware":
        tie_breaker = slack * 100 + merged.external_cost * 10 + merged.travel_minutes
    else:
        tie_breaker = slack
    return 1_000_000 + int(tie_breaker)
