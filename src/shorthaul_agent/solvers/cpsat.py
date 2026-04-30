"""OR-Tools CP-SAT scheduler.

The project can run without OR-Tools by falling back to the heuristic solver, but
this module preserves the verifiable optimization layer required by the design.
"""

from __future__ import annotations

from shorthaul_agent.models import Assignment, DispatchTask, Fleet, Instance, ProblemConfig, ScheduleSolution, Vehicle
from shorthaul_agent.solvers.heuristic import calculate_kpis


class CpSatScheduler:
    name = "ortools-cpsat"

    @staticmethod
    def available() -> bool:
        try:
            import ortools.sat.python.cp_model  # noqa: F401
        except ImportError:
            return False
        return True

    def solve(self, instance: Instance, tasks: list[DispatchTask], config: ProblemConfig) -> ScheduleSolution:
        try:
            from ortools.sat.python import cp_model
        except ImportError as exc:
            raise RuntimeError("OR-Tools is not installed. Install the optional solver dependency.") from exc

        fleets = {fleet.id: fleet for fleet in instance.fleets}
        vehicles = _build_vehicles(instance.fleets)
        model = cp_model.CpModel()
        horizon = max((task.latest_minute + _max_duration(task, fleets[task.fleet_id]) for task in tasks), default=24 * 60)

        start_vars = []
        end_vars = []
        duration_vars = []
        container_vars = []
        external_vars = []
        assignment_vars: dict[tuple[int, int], object] = {}

        for task_idx, task in enumerate(tasks):
            start = model.NewIntVar(task.earliest_minute, task.latest_minute, f"start_{task_idx}")
            duration = model.NewIntVar(0, horizon, f"duration_{task_idx}")
            end = model.NewIntVar(0, horizon * 2, f"end_{task_idx}")
            use_container = model.NewBoolVar(f"use_container_{task_idx}")
            external = model.NewBoolVar(f"external_{task_idx}")

            fleet = fleets[task.fleet_id]
            normal_duration = fleet.normal_load_minutes + fleet.normal_unload_minutes + 2 * task.travel_minutes
            container_duration = fleet.container_load_minutes + fleet.container_unload_minutes + 2 * task.travel_minutes
            model.Add(duration == normal_duration + (container_duration - normal_duration) * use_container)
            model.Add(end == start + duration)

            if (not config.allow_container) or task.volume > config.container_capacity:
                model.Add(use_container == 0)
            model.Add(use_container == 0).OnlyEnforceIf(external)

            own_assignments = []
            for vehicle_idx, vehicle in enumerate(vehicles):
                assign = model.NewBoolVar(f"assign_{task_idx}_{vehicle_idx}")
                if vehicle.fleet_id != task.fleet_id:
                    model.Add(assign == 0)
                own_assignments.append(assign)
                assignment_vars[(task_idx, vehicle_idx)] = assign

            if config.allow_external:
                model.Add(sum(own_assignments) + external == 1)
            else:
                model.Add(sum(own_assignments) == 1)
                model.Add(external == 0)

            start_vars.append(start)
            end_vars.append(end)
            duration_vars.append(duration)
            container_vars.append(use_container)
            external_vars.append(external)

        vehicle_used_vars = []
        for vehicle_idx, vehicle in enumerate(vehicles):
            used = model.NewBoolVar(f"vehicle_used_{vehicle_idx}")
            vehicle_assignments = [assignment_vars[(task_idx, vehicle_idx)] for task_idx in range(len(tasks))]
            for assign in vehicle_assignments:
                model.Add(assign <= used)
            model.Add(used <= sum(vehicle_assignments))
            intervals = [
                model.NewOptionalIntervalVar(
                    start_vars[task_idx],
                    duration_vars[task_idx],
                    end_vars[task_idx],
                    assignment_vars[(task_idx, vehicle_idx)],
                    f"interval_{task_idx}_{vehicle_idx}",
                )
                for task_idx in range(len(tasks))
            ]
            model.AddNoOverlap(intervals)
            vehicle_used_vars.append((vehicle, used))

        unused_capacity_vars = []
        for task_idx, task in enumerate(tasks):
            unused = model.NewIntVar(0, config.vehicle_capacity, f"unused_capacity_{task_idx}")
            model.Add(
                unused
                == config.vehicle_capacity
                - task.volume
                + (config.container_capacity - config.vehicle_capacity) * container_vars[task_idx]
            )
            unused_capacity_vars.append(unused)

        cost_terms = []
        own_task_terms = []
        for vehicle_idx, vehicle in enumerate(vehicles):
            for task_idx, task in enumerate(tasks):
                assign = assignment_vars[(task_idx, vehicle_idx)]
                cost_terms.append((task.variable_cost + vehicle.variable_cost_per_trip) * assign)
                own_task_terms.append(assign)

        for task_idx, task in enumerate(tasks):
            cost_terms.append(task.external_cost * external_vars[task_idx])

        weights = config.objective_weights
        cost_weight = int(weights.cost * 100)
        turnover_weight = int(weights.turnover * 100)
        fill_weight = int(weights.fill_rate * 100)
        model.Minimize(
            cost_weight * sum(cost_terms)
            - turnover_weight * 1000 * sum(own_task_terms)
            + fill_weight * sum(unused_capacity_vars)
        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = config.solver_time_limit_seconds
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return ScheduleSolution(
                status=solver.StatusName(status),
                objective=float("inf"),
                assignments=[],
                kpis={},
                warnings=["CP-SAT did not find a feasible schedule."],
                solver=self.name,
            )

        assignments: list[Assignment] = []
        for task_idx, task in enumerate(tasks):
            vehicle_id = None
            fleet_id = task.fleet_id
            is_external = bool(solver.Value(external_vars[task_idx]))
            if is_external:
                vehicle_id = f"External_{task.id}"
            else:
                for vehicle_idx, vehicle in enumerate(vehicles):
                    if solver.Value(assignment_vars[(task_idx, vehicle_idx)]):
                        vehicle_id = vehicle.id
                        fleet_id = vehicle.fleet_id
                        break
            if vehicle_id is None:
                continue
            assignments.append(
                Assignment(
                    task_id=task.id,
                    route_ids=task.route_ids,
                    vehicle_id=vehicle_id,
                    fleet_id=fleet_id,
                    start_minute=solver.Value(start_vars[task_idx]),
                    end_minute=solver.Value(end_vars[task_idx]),
                    volume=task.volume,
                    use_container=bool(solver.Value(container_vars[task_idx])) and not is_external,
                    is_external=is_external,
                )
            )

        kpis = calculate_kpis(instance, tasks, assignments, config)
        return ScheduleSolution(
            status=solver.StatusName(status),
            objective=float(solver.ObjectiveValue()),
            assignments=assignments,
            kpis=kpis,
            warnings=[],
            solver=self.name,
        )


def _build_vehicles(fleets: list[Fleet]) -> list[Vehicle]:
    vehicles: list[Vehicle] = []
    for fleet in fleets:
        for idx in range(1, fleet.vehicle_count + 1):
            vehicles.append(
                Vehicle(
                    id=f"Own_{fleet.id}_{idx}",
                    fleet_id=fleet.id,
                    fixed_cost=fleet.fixed_cost,
                    variable_cost_per_trip=fleet.variable_cost_per_trip,
                    normal_load_minutes=fleet.normal_load_minutes,
                    normal_unload_minutes=fleet.normal_unload_minutes,
                    container_load_minutes=fleet.container_load_minutes,
                    container_unload_minutes=fleet.container_unload_minutes,
                )
            )
    return vehicles


def _max_duration(task: DispatchTask, fleet: Fleet) -> int:
    normal = fleet.normal_load_minutes + fleet.normal_unload_minutes
    container = fleet.container_load_minutes + fleet.container_unload_minutes
    return max(normal, container) + 2 * task.travel_minutes
