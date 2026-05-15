"""Export the benchmark dataset into the public upload/API contract."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from shorthaul_agent.experiment import (
    build_instance,
    build_milk_run_pairs,
    disaggregate_to_10min,
    forecast_daily_volume,
    load_d_dataset,
)


DEFAULT_UPLOAD_REQUEST = (
    "请基于上传的完整短途运输数据生成 2024-12-16 的调度方案。目标是在满足车辆容量、"
    "发运时间窗、串点兼容关系和外部承运限制的前提下，降低总成本并提升自有车周转效率。"
)

DEFAULT_CONFIG_OVERRIDES: Dict[str, Any] = {
    "vehicle_capacity": 1000,
    "container_capacity": 800,
    "max_stops": 3,
    "allow_container": True,
    "allow_external": True,
    "tail_cover_strategy": "cost_aware",
    "tail_candidate_strategy": "exhaustive",
    "tail_beam_width": 12,
    "solver_time_limit_seconds": 20.0,
    "objective_weights": {"cost": 1.0, "turnover": 0.5, "fill_rate": 0.2},
}

FLEET_FIELDS = [
    "id",
    "vehicle_count",
    "fixed_cost",
    "variable_cost_per_trip",
    "normal_load_minutes",
    "normal_unload_minutes",
    "container_load_minutes",
    "container_unload_minutes",
]
ROUTE_FIELDS = [
    "id",
    "origin",
    "destination",
    "wave",
    "latest_dispatch_minute",
    "travel_minutes",
    "fleet_id",
    "variable_cost",
    "external_cost",
    "external_cost_multiplier",
]
FORECAST_FIELDS = ["route_id", "minute", "volume"]
MILK_RUN_FIELDS = ["left_destination", "right_destination"]


def export_d_problem_upload_package(
    data_dir: str | Path,
    output_dir: str | Path,
    *,
    target_date: str = "2024-12-16",
    base_date: str = "2024-12-15",
    request_text: str = DEFAULT_UPLOAD_REQUEST,
    prefer_cpsat: bool = True,
) -> Dict[str, Any]:
    """Build upload-ready CSV and JSON files from the local benchmark dataset."""
    dataset = load_d_dataset(Path(data_dir))
    target = pd.Timestamp(target_date)
    base = pd.Timestamp(base_date)
    daily_forecast = forecast_daily_volume(dataset, target)
    ten_min_forecast = disaggregate_to_10min(dataset, daily_forecast, target)
    instance = build_instance(dataset, ten_min_forecast, target, base)
    milk_run_pairs = sorted([list(pair) for pair in build_milk_run_pairs(dataset.milk_run_rules)])
    config_overrides = dict(DEFAULT_CONFIG_OVERRIDES)
    config_overrides["milk_run_pairs"] = milk_run_pairs
    payload = {
        "request": request_text,
        "prefer_cpsat": prefer_cpsat,
        "config_overrides": config_overrides,
        "instance": instance.to_dict(),
    }
    return write_upload_package(payload, output_dir, csv_config_overrides=DEFAULT_CONFIG_OVERRIDES)


def write_upload_package(
    payload: Dict[str, Any],
    output_dir: str | Path,
    *,
    csv_config_overrides: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Write payload.json plus the equivalent CSV upload files."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    instance = payload["instance"]
    config_overrides = payload.get("config_overrides", {})
    milk_run_pairs = config_overrides.get("milk_run_pairs", [])

    write_csv(out / "fleets.csv", instance.get("fleets", []), FLEET_FIELDS)
    write_csv(out / "routes.csv", instance.get("routes", []), ROUTE_FIELDS)
    write_csv(out / "forecast.csv", instance.get("forecast", []), FORECAST_FIELDS)
    write_csv(
        out / "milk_run_pairs.csv",
        [{"left_destination": left, "right_destination": right} for left, right in milk_run_pairs],
        MILK_RUN_FIELDS,
    )
    (out / "request.txt").write_text(str(payload.get("request", "")), encoding="utf-8")

    csv_config = dict(csv_config_overrides or config_overrides)
    csv_config.pop("milk_run_pairs", None)
    write_json(out / "config_overrides.json", csv_config)
    write_json(out / "payload.json", payload)

    manifest = {
        "format": "shorthaul-agent/v1",
        "files": [
            "payload.json",
            "request.txt",
            "fleets.csv",
            "routes.csv",
            "forecast.csv",
            "milk_run_pairs.csv",
            "config_overrides.json",
        ],
        "instance_id": instance.get("id", ""),
        "date": instance.get("date", ""),
        "route_count": len(instance.get("routes", [])),
        "fleet_count": len(instance.get("fleets", [])),
        "forecast_bucket_count": len(instance.get("forecast", [])),
        "milk_run_pair_count": len(milk_run_pairs),
        "prefer_cpsat": bool(payload.get("prefer_cpsat", True)),
    }
    write_json(out / "manifest.json", manifest)
    (out / "README.md").write_text(render_package_readme(manifest), encoding="utf-8")
    return manifest


def write_csv(path: Path, rows: list[Dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def render_package_readme(manifest: Dict[str, Any]) -> str:
    return "\n".join(
        [
            "# ShortHaul Upload Package",
            "",
            "This folder is aligned with the ShortHaul Dispatch Agent upload/API contract.",
            "",
            "## Contents",
            "",
            "- `payload.json`: complete request body for `POST /schedule` or UI upload.",
            "- `fleets.csv`, `routes.csv`, `forecast.csv`: required CSV upload files.",
            "- `milk_run_pairs.csv`: optional milk-run compatibility graph.",
            "- `config_overrides.json`: capacity, strategy, solver, and objective settings.",
            "- `request.txt`: natural-language dispatch requirement.",
            "",
            "## Summary",
            "",
            f"- Instance: `{manifest['instance_id']}`",
            f"- Date: `{manifest['date']}`",
            f"- Routes: {manifest['route_count']}",
            f"- Fleets: {manifest['fleet_count']}",
            f"- Forecast buckets: {manifest['forecast_bucket_count']}",
            f"- Milk-run pairs: {manifest['milk_run_pair_count']}",
            "",
            "## Run In Web UI",
            "",
            "1. Start the service and open `http://127.0.0.1:8000/`.",
            "2. In the upload section, either select `payload.json`, or select the CSV files.",
            "3. Click Upload and run.",
            "",
            "## Run Through CLI/API",
            "",
            "```powershell",
            "$env:PYTHONPATH=\"src\"",
            "python -m shorthaul_agent.cli build-payload --csv-dir outputs_d_problem_upload_package --request outputs_d_problem_upload_package/request.txt --output outputs_d_problem_upload_package/payload_from_csv.json",
            "```",
        ]
    )
