"""JSON input/output helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shorthaul_agent.models import Instance


def load_instance(path: str | Path) -> Instance:
    with Path(path).open("r", encoding="utf-8") as fp:
        return Instance.from_dict(json.load(fp))


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
