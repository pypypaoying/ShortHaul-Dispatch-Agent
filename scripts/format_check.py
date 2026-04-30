"""Small repository formatting guard used by CI.

It intentionally avoids third-party dependencies so the project has a stable
format check even before optional developer tooling is installed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK_SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".json", ".txt"}
EXCLUDED_DIRS = {".git", ".venv", ".conda", "__pycache__", "D题", "outputs", "outputs_heuristic", ".pytest_cache"}


def iter_files():
    result = subprocess.run(["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True)
    for raw_path in result.stdout.splitlines():
        path = ROOT / raw_path
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in Path(raw_path).parts):
            continue
        if path.suffix.lower() in CHECK_SUFFIXES:
            yield path


def main() -> None:
    failures = []
    for path in iter_files():
        text = path.read_text(encoding="utf-8")
        if text and not text.endswith("\n"):
            failures.append(f"{path.relative_to(ROOT)}: missing final newline")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if line.rstrip(" \t") != line:
                failures.append(f"{path.relative_to(ROOT)}:{line_number}: trailing whitespace")

    if failures:
        print("\n".join(failures))
        raise SystemExit(1)
    print("format check ok")


if __name__ == "__main__":
    main()
