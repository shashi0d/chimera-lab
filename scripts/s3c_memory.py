"""S3c memory probe: peak memory of one agent creature at live image sizes, in mock mode (no API calls).

    .venv/Scripts/python.exe scripts/s3c_memory.py [label]

One rhinoceros beetle x brown bear creature, driven by a scripted policy to the render cap (4 renders, an edit after
each inspect that has covering failures). The mock renderer's images are replaced by real ~0.5 MB Muse Image webps
from docs/evolution/live/s3c (so image sizes match a live run); the mock critics, SAM and judge run as usual.

Prints and appends to docs/evolution/live/s3c/memory.json: tracemalloc peak (Python allocations), the process peak
working set (Windows), and the image bytes the run still holds when it finishes.
"""

from __future__ import annotations

import asyncio
import ctypes
import gc
import json
import shutil
import sys
import tempfile
import tracemalloc
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.evolution import agent as A  # noqa: E402
from app.evolution.engine import EvoEngine  # noqa: E402
from app.services import build_services  # noqa: E402
from tests.conftest import make_settings  # noqa: E402

LIVE = ROOT / "docs" / "evolution" / "live"
OUT = LIVE / "s3c" / "memory.json"


def peak_working_set_mb() -> float | None:
    if sys.platform != "win32":
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    class PMC(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.PeakWorkingSetSize / 2**20


def held_image_bytes(obj: Any) -> int:
    """Image bytes (webp/png/jpeg payloads) or base64 data URLs reachable from the run."""
    seen: set[int] = set()
    total = 0
    stack = [obj]
    while stack:
        o = stack.pop()
        if id(o) in seen:
            continue
        seen.add(id(o))
        if isinstance(o, (bytes, bytearray)):
            if o[:4] == b"RIFF" or o[:4] == b"\x89PNG" or o[:3] == b"\xff\xd8\xff":
                total += len(o)
        elif isinstance(o, str):
            if o.startswith("data:image/") or (len(o) > 20000 and o[:8] in ("UklGRi", "iVBORw0K")):
                total += len(o)
        elif isinstance(o, dict):
            stack.extend(o.values())
        elif isinstance(o, (list, tuple, set)):
            stack.extend(o)
        elif hasattr(o, "__dict__") and type(o).__module__.startswith("app.evolution.agent"):
            stack.extend(vars(o).values())
    return total


def policy(run: A.AgentRun) -> tuple[str, dict[str, Any]] | None:
    s = run.state
    for slot, name in (("sire", run.sire_name), ("dam", run.dam_name)):
        if slot not in s.resolved:
            return "resolve_animal", {"name": name, "reason": slot}
    if s.candidates is None:
        return "propose_candidates", {"reason": "options"}
    if s.chosen is None:
        return "choose_candidate", {"candidate_id": "C1", "reason": "top"}
    if not run.audit_current():
        return "audit_plan", {"reason": "audit"}
    if s.order:
        last = s.images[s.order[-1]]
        if last.inspect is None:
            return "inspect", {"image_id": last.id, "reason": "check"}
        cov = [f["key"] for f in last.inspect["failures"] if f["kind"] == "covering"]
        if cov and last.parent is None:
            return "edit", {"image_id": last.id, "failure_keys": cov, "reason": "covering"}
    if s.renders < run.cfg["max_renders"]:
        method = "growth_edit" if s.renders % 2 == 0 else "single_pass"  # 6 images: host + grown, single, ...
        return "render", {"method": method, "reason": "again"}
    if s.finalized is None:
        return "finalize", {"image_id": run.best_image_id(), "reason": "best"}
    return None


async def main(label: str) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="s3c_mem_"))
    store = tmp / "learned.json"
    shutil.copy(ROOT / "data" / "learned_animals.json", store)
    eng = EvoEngine(build_services(make_settings(tmp, evo_learned_path=str(store))))
    live_imgs = sorted((LIVE / "s3c" / "agent").glob("*/r*/img*.webp"))[:12]
    pool = [p.read_bytes() for p in live_imgs]
    orig = eng.renderer.generate
    n = {"i": 0}

    async def generate(prompt: str, refs: list[bytes], aspect: str | None, prev: str | None = None) -> Any:
        img = await orig(prompt, refs, aspect, prev)
        img.data = bytes(bytearray(pool[n["i"] % len(pool)]))  # a fresh allocation, as a live download
        n["i"] += 1
        return img

    eng.renderer.generate = generate  # type: ignore[method-assign]
    pool_mb = sum(map(len, pool)) / 2**20
    gc.collect()
    tracemalloc.start()
    base, _ = tracemalloc.get_traced_memory()
    doc, run = await eng.agent_fuse("rhinoceros beetle", "brown bear", "speculative", brain=A.PolicyBrain(policy))
    gc.collect()
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    res = {"label": label, "images": len(run.state.order), "renders": run.state.renders, "edits": run.state.edits,
           "tool_calls": run.state.calls, "image_pool_mb_preloaded": round(pool_mb, 2),
           "tracemalloc_peak_mb": round((peak - base) / 2**20, 2),
           "tracemalloc_retained_after_run_mb": round((cur - base) / 2**20, 2),
           "image_bytes_held_by_run_mb": round(held_image_bytes(run) / 2**20, 2),
           "image_bytes_in_messages": held_image_bytes(run.messages),
           "peak_working_set_mb": round(peak_working_set_mb() or 0, 1)}
    shutil.rmtree(tmp, ignore_errors=True)
    return res


if __name__ == "__main__":
    r = asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "run"))
    print(json.dumps(r, indent=1))
    hist = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []
    hist.append(r)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(hist, indent=1), encoding="utf-8")
