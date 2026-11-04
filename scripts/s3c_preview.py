"""S3c: print the code plan, transfers, identity part and compiled prompt for a pair (mock adapters, no calls).

    .venv/Scripts/python.exe scripts/s3c_preview.py "rhinoceros beetle" "brown bear" speculative [host]
"""
from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import Settings  # noqa: E402
from app.evolution.critic import questions  # noqa: E402
from app.evolution.engine import EvoEngine  # noqa: E402
from app.evolution.prompt import compile_prompt  # noqa: E402
from app.services import build_services  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


async def main(sire: str, dam: str, mode: str, host: str | None) -> None:
    tmp = Path(tempfile.mkdtemp())
    shutil.copy(ROOT / "data" / "learned_animals.json", tmp / "learned.json")
    st = Settings(chimera_mode="mock", local_data_dir=str(tmp), evo_learned_path=str(tmp / "learned.json"))
    eng = EvoEngine(build_services(st))
    s = await eng.plan_session(sire, dam, mode)
    if host:
        print("set_host", s.apply("set_host", {"animal": host}).ok)
    g = s.plan
    print("host:", g.host, "| tie note:", [c for c in g.card_trace if c == "RC-R10-01"])
    print("identity:", [p.model_dump() for p in g.identity_parts])
    print("licenses:", [(x.id, x.compensation, x.reason) for x in g.licenses])
    for t in g.transfers:
        print("transfer:", t.feature, t.cls, t.extent, "|", t.plate_pattern, "|", t.plate_source, "|", t.host_shell)
    print("checks:", [c.detail for c in g.checks if c.step == "identity"])
    print("\nPROMPT:\n" + compile_prompt(g, eng.tax))
    print("\nidentity questions:", [q.text for q in questions(g, eng.tax) if q.group == "identity"])


if __name__ == "__main__":
    a = sys.argv[1:]
    asyncio.run(main(a[0], a[1], a[2] if len(a) > 2 else "speculative", a[3] if len(a) > 3 else None))
