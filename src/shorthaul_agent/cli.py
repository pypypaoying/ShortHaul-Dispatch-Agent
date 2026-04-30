"""Command-line entrypoint for the short-haul scheduling agent."""

from __future__ import annotations

import argparse
from pathlib import Path

from shorthaul_agent import DispatchOrchestrator, ProblemConfig
from shorthaul_agent.io import load_instance, write_json


def main() -> None:
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
