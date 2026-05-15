"""External data contracts and CSV adapters for operational use."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from shorthaul_agent.models import Instance
from shorthaul_agent.time_utils import parse_time_to_minutes


CSV_SCHEMAS: dict[str, list[dict[str, str]]] = {
    "fleets.csv": [
        {"name": "id", "required": "yes", "description": "Fleet identifier used by routes."},
        {"name": "vehicle_count", "required": "yes", "description": "Number of owned vehicles in this fleet."},
        {"name": "fixed_cost", "required": "no", "description": "Daily or planning-horizon fixed cost."},
        {"name": "variable_cost_per_trip", "required": "no", "description": "Owned-vehicle cost per assigned trip."},
        {"name": "normal_load_minutes", "required": "no", "description": "Loading time without container."},
        {"name": "normal_unload_minutes", "required": "no", "description": "Unloading time without container."},
        {"name": "container_load_minutes", "required": "no", "description": "Loading time with container."},
        {"name": "container_unload_minutes", "required": "no", "description": "Unloading time with container."},
    ],
    "routes.csv": [
        {"name": "id", "required": "yes", "description": "Unique route id."},
        {"name": "origin", "required": "yes", "description": "Origin site or depot."},
        {"name": "destination", "required": "yes", "description": "Destination station or customer cluster."},
        {"name": "wave", "required": "yes", "description": "Dispatch wave label, such as 0600 or AM-1."},
        {"name": "latest_dispatch_minute", "required": "yes", "description": "Minute offset from planning start; 1800 means D+1 06:00."},
        {"name": "travel_minutes", "required": "yes", "description": "Line-haul travel duration."},
        {"name": "fleet_id", "required": "yes", "description": "Fleet id that can serve this route."},
        {"name": "variable_cost", "required": "no", "description": "Route-level owned-trip cost."},
        {"name": "external_cost", "required": "no", "description": "Explicit external-carrier cost. Optional."},
        {"name": "external_cost_multiplier", "required": "no", "description": "Multiplier when external_cost is omitted."},
    ],
    "forecast.csv": [
        {"name": "route_id", "required": "yes", "description": "Route id matching routes.csv."},
        {"name": "minute", "required": "yes", "description": "Demand time bucket as minute offset; 1380 means D+0 23:00."},
        {"name": "volume", "required": "yes", "description": "Forecast demand volume for the bucket."},
    ],
    "milk_run_pairs.csv": [
        {"name": "left_destination", "required": "yes", "description": "First destination in a compatible pair."},
        {"name": "right_destination", "required": "yes", "description": "Second destination in a compatible pair."},
    ],
}


CSV_TEMPLATES: dict[str, str] = {
    "fleets.csv": (
        "id,vehicle_count,fixed_cost,variable_cost_per_trip,normal_load_minutes,normal_unload_minutes,"
        "container_load_minutes,container_unload_minutes\n"
        "Fleet-A,3,520,80,45,45,20,20\n"
        "Fleet-B,2,480,70,45,45,20,20\n"
    ),
    "routes.csv": (
        "id,origin,destination,wave,latest_dispatch_minute,travel_minutes,fleet_id,variable_cost,external_cost,external_cost_multiplier\n"
        "Site-A - Stop-01 - 0600,Site-A,Stop-01,0600,1800,35,Fleet-A,150,,1.35\n"
        "Site-A - Stop-02 - 0600,Site-A,Stop-02,0600,1800,25,Fleet-A,120,,1.35\n"
        "Site-B - Stop-03 - 1400,Site-B,Stop-03,1400,2280,28,Fleet-B,110,,1.35\n"
    ),
    "forecast.csv": (
        "route_id,minute,volume\n"
        "Site-A - Stop-01 - 0600,1380,600\n"
        "Site-A - Stop-01 - 0600,1460,500\n"
        "Site-A - Stop-02 - 0600,1430,400\n"
        "Site-B - Stop-03 - 1400,2100,900\n"
    ),
    "milk_run_pairs.csv": "left_destination,right_destination\nStop-01,Stop-02\n",
}


def schema_payload() -> dict[str, Any]:
    return {
        "format": "shorthaul-agent/v1",
        "required_files": ["fleets.csv", "routes.csv", "forecast.csv"],
        "optional_files": ["milk_run_pairs.csv", "config_overrides.json"],
        "csv_schemas": CSV_SCHEMAS,
        "time_fields": {
            "minute_offset": "Integer minutes from planning start. Example: 1800 means D+1 06:00.",
            "clock_text": "HH:MM and HHMM are accepted in JSON; CSV templates use minute offsets to avoid day-boundary ambiguity.",
        },
        "api_payload": {
            "request": "Natural-language dispatch requirement.",
            "prefer_cpsat": "Boolean. True uses CP-SAT when available; false forces heuristic.",
            "config_overrides": "ProblemConfig overrides such as capacity and objective weights.",
            "instance": "Scenario object containing fleets, routes, and forecast buckets.",
        },
        "endpoints": {
            "json_solve": "POST /schedule",
            "multipart_upload_solve": "POST /schedule/upload",
            "server_local_csv_solve": "POST /schedule/from-csv-dir",
            "validate_json": "POST /validate-instance",
        },
    }


def build_payload_from_csv_dir(
    data_dir: str | Path,
    request_text: str,
    *,
    instance_id: str = "external-instance",
    date: str = "",
    prefer_cpsat: bool = True,
    config_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data_path = Path(data_dir)
    instance = load_instance_from_csv_dir(data_path, instance_id=instance_id, date=date)
    overrides = load_config_overrides_from_csv_dir(data_path)
    if config_overrides:
        overrides.update(config_overrides)
    return {
        "request": request_text,
        "prefer_cpsat": prefer_cpsat,
        "config_overrides": overrides,
        "instance": instance.to_dict(),
    }


def load_instance_from_csv_dir(data_dir: str | Path, *, instance_id: str = "external-instance", date: str = "") -> Instance:
    data_path = Path(data_dir)
    fleets = [_normalize_fleet(row) for row in _read_required_csv(data_path / "fleets.csv")]
    routes = [_normalize_route(row) for row in _read_required_csv(data_path / "routes.csv")]
    forecast = [_normalize_forecast(row) for row in _read_required_csv(data_path / "forecast.csv")]
    return Instance.from_dict({"id": instance_id, "date": date, "fleets": fleets, "routes": routes, "forecast": forecast})


def load_config_overrides_from_csv_dir(data_dir: str | Path) -> dict[str, Any]:
    data_path = Path(data_dir)
    overrides: dict[str, Any] = {}
    config_path = data_path / "config_overrides.json"
    if config_path.exists():
        overrides.update(json.loads(config_path.read_text(encoding="utf-8")))

    pairs_path = data_path / "milk_run_pairs.csv"
    if pairs_path.exists():
        pairs = []
        for row in _read_required_csv(pairs_path):
            left = _clean(row.get("left_destination"))
            right = _clean(row.get("right_destination"))
            if left and right:
                pairs.append([left, right])
        if pairs:
            overrides["milk_run_pairs"] = pairs
    return overrides


def _read_required_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required CSV file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        if not reader.fieldnames:
            raise ValueError(f"CSV file has no header: {path}")
        return [dict(row) for row in reader]


def _normalize_fleet(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _required(row, "id"),
        "vehicle_count": _int(row, "vehicle_count"),
        "fixed_cost": _int(row, "fixed_cost", 600),
        "variable_cost_per_trip": _int(row, "variable_cost_per_trip", 80),
        "normal_load_minutes": _int(row, "normal_load_minutes", 45),
        "normal_unload_minutes": _int(row, "normal_unload_minutes", 45),
        "container_load_minutes": _int(row, "container_load_minutes", 20),
        "container_unload_minutes": _int(row, "container_unload_minutes", 20),
    }


def _normalize_route(row: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "id": _required(row, "id"),
        "origin": _required(row, "origin"),
        "destination": _required(row, "destination"),
        "wave": _required(row, "wave"),
        "latest_dispatch_minute": _minute(row, "latest_dispatch_minute"),
        "travel_minutes": _int(row, "travel_minutes"),
        "fleet_id": _required(row, "fleet_id"),
        "variable_cost": _int(row, "variable_cost", 120),
        "external_cost_multiplier": _float(row, "external_cost_multiplier", 1.35),
    }
    external_cost = _optional_int(row, "external_cost")
    if external_cost is not None:
        payload["external_cost"] = external_cost
    return payload


def _normalize_forecast(row: dict[str, Any]) -> dict[str, Any]:
    return {"route_id": _required(row, "route_id"), "minute": _minute(row, "minute"), "volume": _int(row, "volume")}


def _required(row: dict[str, Any], key: str) -> str:
    value = _clean(row.get(key))
    if not value:
        raise ValueError(f"Missing required field: {key}")
    return value


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _int(row: dict[str, Any], key: str, default: int | None = None) -> int:
    value = _clean(row.get(key))
    if not value:
        if default is None:
            raise ValueError(f"Missing required integer field: {key}")
        return default
    return int(round(float(value)))


def _optional_int(row: dict[str, Any], key: str) -> int | None:
    value = _clean(row.get(key))
    return None if not value else int(round(float(value)))


def _float(row: dict[str, Any], key: str, default: float) -> float:
    value = _clean(row.get(key))
    return default if not value else float(value)


def _minute(row: dict[str, Any], key: str) -> int:
    value = _clean(row.get(key))
    if not value:
        raise ValueError(f"Missing required time field: {key}")
    if value.lstrip("-").isdigit():
        return int(value)
    return parse_time_to_minutes(value)
