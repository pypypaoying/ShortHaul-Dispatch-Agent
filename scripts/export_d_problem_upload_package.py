"""Export the local benchmark dataset into UI/API upload files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shorthaul_agent.d_problem_package import DEFAULT_UPLOAD_REQUEST, export_d_problem_upload_package  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a ShortHaul upload package from the local benchmark dataset.")
    parser.add_argument("--data-dir", default="D题", help="Folder containing 附件/ and 结果表/.")
    parser.add_argument("--output-dir", default="outputs_d_problem_upload_package", help="Folder to write upload-ready files.")
    parser.add_argument("--target-date", default="2024-12-16", help="Planning date used for the generated scenario.")
    parser.add_argument("--base-date", default="2024-12-15", help="Minute-offset base date.")
    parser.add_argument("--request", default="", help="Optional natural-language request text.")
    parser.add_argument("--no-cpsat", action="store_true", help="Set prefer_cpsat=false in payload.json.")
    args = parser.parse_args()

    request_text = args.request.strip() or DEFAULT_UPLOAD_REQUEST
    manifest = export_d_problem_upload_package(
        args.data_dir,
        args.output_dir,
        target_date=args.target_date,
        base_date=args.base_date,
        request_text=request_text,
        prefer_cpsat=not args.no_cpsat,
    )
    print(f"Upload package written to {Path(args.output_dir).resolve()}")
    print(f"Routes: {manifest['route_count']}")
    print(f"Fleets: {manifest['fleet_count']}")
    print(f"Forecast buckets: {manifest['forecast_bucket_count']}")
    print(f"Milk-run pairs: {manifest['milk_run_pair_count']}")


if __name__ == "__main__":
    main()
