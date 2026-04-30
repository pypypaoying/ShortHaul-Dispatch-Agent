"""Command-line entrypoint for the short-haul scheduling agent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shorthaul_agent import DispatchOrchestrator, ProblemConfig
from shorthaul_agent.experiment import run_experiment
from shorthaul_agent.io import load_instance, write_json


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "run-experiment":
        parser = argparse.ArgumentParser(description="Run the official D-problem experiment.")
        parser.add_argument("command")
        parser.add_argument("--data-dir", default="D题", help="Path to the D-problem folder.")
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


if __name__ == "__main__":
    main()
