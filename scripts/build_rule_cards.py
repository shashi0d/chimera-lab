#!/usr/bin/env python3
"""Parse every "### RC-" block in docs/evolution/research/*.md into data/rule_cards.json.

ALGORITHM.md section 2. The loader is the single source of truth for rule cards:
prompts quote cards by id and text from this file, never from memory.

Usage: python scripts/build_rule_cards.py [research_dir] [out_json]
Files with no cards (RESEARCH_SUMMARY.md) are skipped. Exit 1 on a malformed card.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CARD_RE = re.compile(r"^### (RC-R\d-\d+)\s*$")
FIELD_RE = re.compile(r"^(rule|applies_to|strength|status|source):\s*(.*)$")
FIELDS = ("rule", "applies_to", "strength", "status", "source")


def _list(value: str) -> list[str]:
    v = value.strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    return [x.strip() for x in v.split(",") if x.strip()]


def parse_file(path: Path) -> list[dict]:
    cards: list[dict] = []
    cur: dict | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = CARD_RE.match(line)
        if m:
            cur = {"id": m.group(1), "doc": path.name}
            cards.append(cur)
            continue
        if cur is None:
            continue
        if line.startswith("#") or line.strip() == "---":
            cur = None
            continue
        fm = FIELD_RE.match(line.strip())
        if fm and fm.group(1) not in cur:
            cur[fm.group(1)] = fm.group(2).strip()
    for c in cards:
        missing = [f for f in FIELDS if not c.get(f)]
        if missing:
            raise ValueError(f"{path.name} {c['id']}: missing {missing}")
        c["applies_to"] = _list(c["applies_to"])
        if c["strength"] not in ("hard", "soft") or c["status"] not in ("VERIFIED", "UNVERIFIED"):
            raise ValueError(f"{path.name} {c['id']}: bad strength/status")
    return [{k: c[k] for k in ("id", "doc", *FIELDS)} for c in cards]


def build(research_dir: Path) -> list[dict]:
    cards: list[dict] = []
    for f in sorted(research_dir.glob("*.md")):
        cards.extend(parse_file(f))
    ids = [c["id"] for c in cards]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate card ids: {sorted(dupes)}")
    return sorted(cards, key=lambda c: (c["id"].split("-")[1], int(c["id"].split("-")[2])))


def main(argv: list[str]) -> int:
    research = Path(argv[1]) if len(argv) > 1 else REPO / "docs/evolution/research"
    out = Path(argv[2]) if len(argv) > 2 else REPO / "data/rule_cards.json"
    try:
        cards = build(research)
    except ValueError as e:
        print(f"ERROR {e}")
        return 1
    out.write_text(json.dumps(cards, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    hard = sum(c["strength"] == "hard" for c in cards)
    print(f"wrote {len(cards)} cards ({hard} hard) to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
