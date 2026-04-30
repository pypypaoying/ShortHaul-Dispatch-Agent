from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shorthaul_agent.experiment import allocate_integer_volume, build_milk_run_pairs, normalize_route_code


def test_normalize_route_code_removes_internal_entity_spaces():
    assert normalize_route_code("场地 3 - 站点 83 - 0600") == "场地3 - 站点83 - 0600"


def test_allocate_integer_volume_preserves_total():
    volumes = allocate_integer_volume(101, [0.2, 0.3, 0.5])
    assert sum(volumes) == 101
    assert volumes == [20, 30, 51]


def test_build_milk_run_pairs_normalizes_sites():
    import pandas as pd

    pairs = build_milk_run_pairs(pd.DataFrame([{"站点编号1": "站点 1", "站点编号2": "站点2"}]))
    assert ("站点1", "站点2") in pairs
