"""D1-07: the real data/chimera_data.json, when it is present (skipped otherwise)."""

import pytest

from app.config import REPO_ROOT
from app.data.loader import load_data
from app.pipeline.steps import rules_check as rc

REAL_FILE = REPO_ROOT / "data" / "chimera_data.json"
pytestmark = pytest.mark.skipif(not REAL_FILE.exists(), reason="data/chimera_data.json not present")


def test_real_file_hybrids_and_rules():
    data = load_data(REAL_FILE)
    assert data.source == "full"
    resolution = data.hybrid_resolution()
    resolved = [r for r, p1, p2 in resolution if p1.animal_ids and p2.animal_ids]
    unresolved = {r["hybrid_id"]: [p.reason for p in (p1, p2) if not p.animal_ids] for r, p1, p2 in resolution
                  if not (p1.animal_ids and p2.animal_ids)}
    summary = rc.summarize(data)
    print(f"\nhybrids resolved {len(resolved)}/{len(resolution)}; unresolved: {unresolved}")
    print(f"rules mapped {summary['mapped']}/{summary['total']} (pair {summary['pair']}, plan {summary['plan']})")
    assert len(resolution) == 31 and len(resolved) >= 25
    assert summary["total"] == 130 and summary["mapped"] >= 40
    assert data.health(set(rc.CHECKS))["problems"] == []


def test_real_file_acceptance_pairs():
    data = load_data(REAL_FILE)
    tigon = next(h for h in data.find_hybrids("lion", "tiger") if h.row["hybrid_id"] == "tigon")
    assert (tigon.a.role, tigon.b.role) == ("mother", "father")  # A = lion is tigon's mother
    assert "mule" in {h.row["hybrid_id"] for h in data.find_hybrids("horse", "donkey")}
    eagle = next(r for r in data.section("animals") if r["common_name"] == "bald eagle")
    lion = next(r for r in data.section("animals") if r["common_name"] == "lion")
    assert data.find_mythology(eagle, lion)[0].row["creature_name"] == "griffin"
