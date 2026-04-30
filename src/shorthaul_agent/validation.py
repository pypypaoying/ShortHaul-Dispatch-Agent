"""Constraint and data validation agent helpers."""

from __future__ import annotations

from collections import Counter

from shorthaul_agent.models import DispatchTask, Instance, ProblemConfig, ValidationReport


def validate_instance(instance: Instance, config: ProblemConfig) -> ValidationReport:
    report = ValidationReport()
    route_ids = [route.id for route in instance.routes]
    fleet_ids = {fleet.id for fleet in instance.fleets}

    duplicates = [route_id for route_id, count in Counter(route_ids).items() if count > 1]
    if duplicates:
        report.errors.append(f"Duplicate route ids: {duplicates}")
    if not instance.routes:
        report.errors.append("Instance has no routes.")
    if not instance.fleets:
        report.errors.append("Instance has no fleets.")
    if not instance.forecast:
        report.errors.append("Instance has no forecast buckets.")

    for route in instance.routes:
        if route.fleet_id not in fleet_ids:
            report.errors.append(f"Route {route.id} references unknown fleet {route.fleet_id}.")
        if route.latest_dispatch_minute < 0:
            report.errors.append(f"Route {route.id} has a negative latest dispatch minute.")
        if route.travel_minutes <= 0:
            report.errors.append(f"Route {route.id} must have positive travel time.")

    known_routes = set(route_ids)
    for bucket in instance.forecast:
        if bucket.route_id not in known_routes:
            report.warnings.append(f"Forecast bucket references unknown route {bucket.route_id}; it will be ignored.")
        if bucket.volume < 0:
            report.errors.append(f"Forecast bucket for {bucket.route_id} has negative volume.")

    if config.container_capacity > config.vehicle_capacity:
        report.warnings.append("Container capacity is larger than vehicle capacity; container use will not limit load.")
    if config.max_stops < 1:
        report.errors.append("max_stops must be at least 1.")
    return report


def validate_tasks(tasks: list[DispatchTask], config: ProblemConfig) -> ValidationReport:
    report = ValidationReport()
    for task in tasks:
        if task.volume <= 0:
            report.errors.append(f"Task {task.id} has non-positive volume.")
        if task.volume > config.vehicle_capacity:
            report.errors.append(f"Task {task.id} exceeds vehicle capacity.")
        if task.earliest_minute > task.latest_minute:
            report.errors.append(f"Task {task.id} has an infeasible time window.")
        if task.stop_count > config.max_stops:
            report.errors.append(f"Task {task.id} exceeds max stops.")
    return report
