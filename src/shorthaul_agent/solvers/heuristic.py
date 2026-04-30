"""Deterministic fallback scheduler used when OR-Tools is unavailable."""

from __future__ import annotations

from dataclasses import dataclass

from shorthaul_agent.models import Assignment, DispatchTask, Fleet, Instance, ProblemConfig, ScheduleSolution, Vehicle


@dataclass(slots=True)
class _VehicleState:
    vehicle: Vehicle
    available_minute: int = 0
    used: bool = False
    task_count: int = 0


class HeuristicScheduler:
    name = "heuristic"

    def solve(self, instance: Instance, tasks: list[DispatchTask], config: ProblemConfig) -> ScheduleSolution:
        fleets = {fleet.id: fleet for fleet in instance.fleets}
        vehicle_states = self._build_vehicle_states(instance.fleets)
        assignments: list[Assignment] = []
        warnings: list[str] = []

        for task in sorted(tasks, key=lambda item: (item.latest_minute, item.earliest_minute, -item.volume)):
            candidates = [state for state in vehicle_states if state.vehicle.fleet_id == task.fleet_id]
            chosen = self._choose_vehicle(task, candidates, config)
            if chosen is None:
                if not config.allow_external:
                    warnings.append(f"Task {task.id} cannot be assigned without external capacity.")
                    continue
                external_vehicle = self._external_vehicle(task, fleets[task.fleet_id])
                start = task.earliest_minute
                duration = self._task_duration(task, external_vehicle, use_container=False)
                assignments.append(
                    Assignment(
                        task_id=task.id,
                        route_ids=task.route_ids,
                        vehicle_id=external_vehicle.id,
                        fleet_id=external_vehicle.fleet_id,
                        start_minute=start,
                        end_minute=start + duration,
                        volume=task.volume,
                        use_container=False,
                        is_external=True,
                    )
                )
                continue

            use_container = self._should_use_container(task, chosen.vehicle, config)
            start = max(task.earliest_minute, chosen.available_minute)
            duration = self._task_duration(task, chosen.vehicle, use_container)
            chosen.available_minute = start + duration
            chosen.used = True
            chosen.task_count += 1
            assignments.append(
                Assignment(
                    task_id=task.id,
                    route_ids=task.route_ids,
                    vehicle_id=chosen.vehicle.id,
                    fleet_id=chosen.vehicle.fleet_id,
                    start_minute=start,
                    end_minute=start + duration,
                    volume=task.volume,
                    use_container=use_container,
                    is_external=False,
                )
            )

        kpis = calculate_kpis(instance, tasks, assignments, config)
        return ScheduleSolution(
            status="FEASIBLE" if len(assignments) == len(tasks) else "PARTIAL",
            objective=_weighted_objective(kpis, config),
            assignments=assignments,
            kpis=kpis,
            warnings=warnings,
            solver=self.name,
        )

    def _build_vehicle_states(self, fleets: list[Fleet]) -> list[_VehicleState]:
        states: list[_VehicleState] = []
        for fleet in fleets:
            for idx in range(1, fleet.vehicle_count + 1):
                vehicle = Vehicle(
                    id=f"Own_{fleet.id}_{idx}",
                    fleet_id=fleet.id,
                    fixed_cost=fleet.fixed_cost,
                    variable_cost_per_trip=fleet.variable_cost_per_trip,
                    normal_load_minutes=fleet.normal_load_minutes,
                    normal_unload_minutes=fleet.normal_unload_minutes,
                    container_load_minutes=fleet.container_load_minutes,
                    container_unload_minutes=fleet.container_unload_minutes,
                )
                states.append(_VehicleState(vehicle=vehicle))
        return states

    def _choose_vehicle(
        self,
        task: DispatchTask,
        candidates: list[_VehicleState],
        config: ProblemConfig,
    ) -> _VehicleState | None:
        feasible: list[tuple[int, int, _VehicleState]] = []
        for state in candidates:
            start = max(task.earliest_minute, state.available_minute)
            use_container = self._should_use_container(task, state.vehicle, config)
            duration = self._task_duration(task, state.vehicle, use_container)
            if start <= task.latest_minute:
                feasible.append((start + duration, 0 if state.used else 1, state))
        if not feasible:
            return None
        feasible.sort(key=lambda item: (item[0], item[1], item[2].vehicle.id))
        return feasible[0][2]

    def _should_use_container(self, task: DispatchTask, vehicle: Vehicle, config: ProblemConfig) -> bool:
        return (
            config.allow_container
            and task.volume <= config.container_capacity
            and vehicle.container_load_minutes + vehicle.container_unload_minutes
            < vehicle.normal_load_minutes + vehicle.normal_unload_minutes
        )

    def _task_duration(self, task: DispatchTask, vehicle: Vehicle, use_container: bool) -> int:
        if use_container:
            handling = vehicle.container_load_minutes + vehicle.container_unload_minutes
        else:
            handling = vehicle.normal_load_minutes + vehicle.normal_unload_minutes
        return handling + 2 * task.travel_minutes

    def _external_vehicle(self, task: DispatchTask, fleet: Fleet) -> Vehicle:
        return Vehicle(
            id=f"External_{task.id}",
            fleet_id=fleet.id,
            fixed_cost=0,
            variable_cost_per_trip=fleet.variable_cost_per_trip,
            is_external=True,
            normal_load_minutes=fleet.normal_load_minutes,
            normal_unload_minutes=fleet.normal_unload_minutes,
            container_load_minutes=fleet.container_load_minutes,
            container_unload_minutes=fleet.container_unload_minutes,
        )


def calculate_kpis(
    instance: Instance,
    tasks: list[DispatchTask],
    assignments: list[Assignment],
    config: ProblemConfig,
) -> dict[str, float]:
    fleets = {fleet.id: fleet for fleet in instance.fleets}
    tasks_by_id = {task.id: task for task in tasks}
    own_vehicle_ids = {assignment.vehicle_id for assignment in assignments if not assignment.is_external}
    own_task_count = sum(1 for assignment in assignments if not assignment.is_external)
    external_task_count = sum(1 for assignment in assignments if assignment.is_external)
    total_own_vehicle_count = sum(fleet.vehicle_count for fleet in instance.fleets)

    used_own_vehicles = {
        (assignment.vehicle_id, assignment.fleet_id)
        for assignment in assignments
        if not assignment.is_external
    }
    fixed_cost = sum(fleets[fleet_id].fixed_cost for _, fleet_id in used_own_vehicles)

    own_variable_cost = 0.0
    external_cost = 0.0
    available_capacity = 0
    total_volume = 0
    for assignment in assignments:
        task = tasks_by_id[assignment.task_id]
        total_volume += assignment.volume
        available_capacity += config.container_capacity if assignment.use_container else config.vehicle_capacity
        base_cost = task.variable_cost + fleets[assignment.fleet_id].variable_cost_per_trip
        if assignment.is_external:
            external_cost += base_cost * 1.35
        else:
            own_variable_cost += base_cost

    total_cost = fixed_cost + own_variable_cost + external_cost
    return {
        "task_count": float(len(tasks)),
        "assigned_task_count": float(len(assignments)),
        "own_task_count": float(own_task_count),
        "external_task_count": float(external_task_count),
        "used_own_vehicle_count": float(len(own_vehicle_ids)),
        "total_own_vehicle_count": float(total_own_vehicle_count),
        "own_vehicle_turnover": own_task_count / total_own_vehicle_count if total_own_vehicle_count else 0.0,
        "avg_packages_per_vehicle": total_volume / len(assignments) if assignments else 0.0,
        "fill_rate": total_volume / available_capacity if available_capacity else 0.0,
        "unused_capacity": float(max(available_capacity - total_volume, 0)),
        "fixed_cost": float(fixed_cost),
        "own_variable_cost": float(own_variable_cost),
        "external_cost": float(external_cost),
        "total_cost": float(total_cost),
    }


def _weighted_objective(kpis: dict[str, float], config: ProblemConfig) -> float:
    weights = config.objective_weights
    return (
        weights.cost * kpis["total_cost"]
        - weights.turnover * 1000.0 * kpis["own_vehicle_turnover"]
        + weights.fill_rate * kpis["unused_capacity"]
    )
