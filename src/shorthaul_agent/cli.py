"""Command-line entrypoint for the short-haul scheduling agent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shorthaul_agent import DispatchOrchestrator, ProblemConfig
from shorthaul_agent.baseline_comparison import compare_baselines
from shorthaul_agent.d_problem_package import DEFAULT_UPLOAD_REQUEST, export_d_problem_upload_package
from shorthaul_agent.experiment import run_experiment, run_task_generation_tuning
from shorthaul_agent.external_io import build_payload_from_csv_dir, build_payload_from_workbook
from shorthaul_agent.io import load_instance, write_json


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "run-experiment":
        parser = argparse.ArgumentParser(description="Run the official D-problem experiment.")
        parser.add_argument("command")
        parser.add_argument("--data-dir", default="D_PROBLEM_DATA", help="Path to the D-problem folder.")
        parser.add_argument("--output-dir", default="outputs", help="Directory for generated result tables and reports.")
        parser.add_argument("--config", default=None, help="Optional experiment YAML/JSON config path.")
        parser.add_argument("--no-cpsat", action="store_true", help="Force deterministic heuristic solver.")
        args = parser.parse_args()
        config_path = Path(args.config) if args.config else None
        summary = run_experiment(Path(args.data_dir), Path(args.output_dir), prefer_cpsat=not args.no_cpsat, config_path=config_path)
        print(f"Experiment complete. Result table 3 rows: {summary['outputs']['result_table_3_rows']}")
        print(f"Problem 2 solver: {summary['problem2']['solver']} / {summary['problem2']['status']}")
        print(f"Problem 3 solver: {summary['problem3']['solver']} / {summary['problem3']['status']}")
        print(f"Outputs written to {args.output_dir}")
        return

    if len(sys.argv) > 1 and sys.argv[1] == "compare-baselines":
        parser = argparse.ArgumentParser(description="Compare D-problem baselines and multi-agent runs.")
        parser.add_argument("command")
        parser.add_argument("--data-dir", default="D_PROBLEM_DATA", help="Path to the D-problem folder.")
        parser.add_argument("--output-dir", default="outputs_baseline_comparison", help="Directory for comparison artifacts.")
        parser.add_argument("--config", default=None, help="Optional experiment YAML/JSON config path.")
        parser.add_argument("--legacy-summary", default=None, help="Optional old experiment_summary.json for legacy comparison.")
        args = parser.parse_args()
        config_path = Path(args.config) if args.config else None
        legacy_summary = Path(args.legacy_summary) if args.legacy_summary else None
        summary = compare_baselines(
            data_dir=Path(args.data_dir),
            output_dir=Path(args.output_dir),
            config_path=config_path,
            legacy_summary=legacy_summary,
        )
        print("Baseline comparison complete.")
        print(f"Rows: {summary['table_rows']}")
        print(f"Best by problem: {summary['best_by_problem']}")
        print(f"Outputs written to {args.output_dir}")
        return

    if len(sys.argv) > 1 and sys.argv[1] == "tune-task-generation":
        parser = argparse.ArgumentParser(description="Run a tail-task generation strategy grid.")
        parser.add_argument("command")
        parser.add_argument("--data-dir", default="D_PROBLEM_DATA", help="Path to the D-problem folder.")
        parser.add_argument("--output-dir", default="outputs_task_generation_tuning", help="Directory for tuning artifacts.")
        parser.add_argument("--config", default=None, help="Optional experiment YAML/JSON config path.")
        parser.add_argument("--no-cpsat", action="store_true", help="Force deterministic heuristic solver.")
        parser.add_argument("--solver-time-limit", type=float, default=None, help="Override per-solve CP-SAT time limit.")
        parser.add_argument("--cpsat-seeds", default=None, help="Comma-separated CP-SAT seeds for each tuning run.")
        parser.add_argument("--tail-strategies", default=None, help="Comma-separated tail cover strategies.")
        parser.add_argument("--candidate-strategies", default=None, help="Comma-separated candidate generation strategies.")
        args = parser.parse_args()
        config_path = Path(args.config) if args.config else None
        summary = run_task_generation_tuning(
            data_dir=Path(args.data_dir),
            output_dir=Path(args.output_dir),
            config_path=config_path,
            prefer_cpsat=not args.no_cpsat,
            solver_time_limit_seconds=args.solver_time_limit,
            cpsat_search_seeds=parse_cli_list(args.cpsat_seeds, cast=int),
            tail_cover_strategies=parse_cli_list(args.tail_strategies),
            tail_candidate_strategies=parse_cli_list(args.candidate_strategies),
        )
        print("Task generation tuning complete.")
        print(f"Rows: {summary['row_count']}")
        print(f"Best: {summary['best']}")
        print(f"Outputs written to {args.output_dir}")
        return

    if len(sys.argv) > 1 and sys.argv[1] == "export-d-upload-package":
        parser = argparse.ArgumentParser(description="Export the local benchmark dataset into UI/API upload files.")
        parser.add_argument("command")
        parser.add_argument("--data-dir", default="D题", help="Folder containing 附件/ and 结果表/.")
        parser.add_argument("--output-dir", default="outputs_d_problem_upload_package", help="Folder to write upload-ready files.")
        parser.add_argument("--target-date", default="2024-12-16", help="Planning date used for the generated scenario.")
        parser.add_argument("--base-date", default="2024-12-15", help="Minute-offset base date.")
        parser.add_argument("--request", default="", help="Optional natural-language request text.")
        parser.add_argument("--no-cpsat", action="store_true", help="Set prefer_cpsat=false in payload.json.")
        args = parser.parse_args()
        manifest = export_d_problem_upload_package(
            args.data_dir,
            args.output_dir,
            target_date=args.target_date,
            base_date=args.base_date,
            request_text=args.request.strip() or DEFAULT_UPLOAD_REQUEST,
            prefer_cpsat=not args.no_cpsat,
        )
        print(f"Upload package written to {Path(args.output_dir).resolve()}")
        print(f"Routes: {manifest['route_count']}")
        print(f"Fleets: {manifest['fleet_count']}")
        print(f"Forecast buckets: {manifest['forecast_bucket_count']}")
        return

    if len(sys.argv) > 1 and sys.argv[1] == "build-payload":
        parser = argparse.ArgumentParser(description="Build a /schedule API payload from an external workbook or CSV files.")
        parser.add_argument("command")
        parser.add_argument("--workbook", default=None, help="Excel workbook using the ShortHaul template.")
        parser.add_argument("--csv-dir", default=None, help="Folder containing fleets.csv, routes.csv, forecast.csv, and optional milk_run_pairs.csv.")
        parser.add_argument("--request", required=True, help="Natural-language request text file.")
        parser.add_argument("--output", default="outputs/schedule_payload.json", help="Output JSON payload path.")
        parser.add_argument("--instance-id", default="external-instance", help="Instance id written into the payload.")
        parser.add_argument("--date", default="", help="Planning date label.")
        parser.add_argument("--no-cpsat", action="store_true", help="Set prefer_cpsat=false in the payload.")
        parser.add_argument("--config-overrides", default=None, help="Optional JSON file merged into config_overrides.")
        args = parser.parse_args()
        overrides = None
        if args.config_overrides:
            import json

            overrides = json.loads(Path(args.config_overrides).read_text(encoding="utf-8"))
        request_text = Path(args.request).read_text(encoding="utf-8")
        if args.workbook:
            payload = build_payload_from_workbook(
                args.workbook,
                request_text,
                instance_id=args.instance_id,
                date=args.date,
                prefer_cpsat=not args.no_cpsat,
                config_overrides=overrides,
            )
        elif args.csv_dir:
            payload = build_payload_from_csv_dir(
                args.csv_dir,
                request_text,
                instance_id=args.instance_id,
                date=args.date,
                prefer_cpsat=not args.no_cpsat,
                config_overrides=overrides,
            )
        else:
            parser.error("Provide either --workbook or --csv-dir.")
        write_json(args.output, payload)
        print(f"Schedule API payload written to {args.output}")
        return

    parser = argparse.ArgumentParser(description="Run the short-haul multi-agent scheduler.")
    parser.add_argument("--instance", required=True, help="Path to instance JSON.")
    parser.add_argument("--request", required=True, help="Path to natural-language request text.")
    parser.add_argument("--output", default="examples/sample_solution.json", help="Path for JSON result.")
    parser.add_argument("--no-cpsat", action="store_true", help="Force deterministic heuristic solver.")
    args = parser.parse_args()

    instance = load_instance(args.instance)
    request_text = Path(args.request).read_text(encoding="utf-8")
    config = ProblemConfig(prefer_cpsat=not args.no_cpsat)
    result = DispatchOrchestrator(config).run(request_text, instance)
    write_json(args.output, result.to_dict())
    print(result.explanation)
    print(f"\nJSON result written to {args.output}")


def parse_cli_list(value, cast=str):
    if not value:
        return None
    return [cast(item.strip()) for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    main()
