"""Make the tutorial's example creature once and save it as static files (no database rows, no model calls later).

Runs against a backend that is already running (default http://127.0.0.1:8000), with live models:
  1. a Fusion run: Tiger + Bat, anime style, and its image as a lab version,
  2. the animal card of that image (profile + four angles),
  3. saved to Chimeras.
Writes the images to frontend/public/example/ and the version + card to frontend/src/example/example.json.

    .venv/Scripts/python scripts/make_example.py [--base http://127.0.0.1:8000]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public" / "example"
DATA = ROOT / "frontend" / "src" / "example" / "example.json"
VISITOR = str(uuid.uuid5(uuid.NAMESPACE_URL, "chimera-lab:example"))
SIRE, DAM, STYLE = "Tiger", "Bat", "anime"


def wait(fn: Any, done: Any, what: str, timeout: float = 600, every: float = 3) -> Any:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = fn()
        if done(value):
            return value
        print(f"  … {what}", flush=True)
        time.sleep(every)
    sys.exit(f"Timed out waiting for {what}.")


def ext_of(url: str, content_type: str) -> str:
    for e in (".webp", ".png", ".jpg", ".jpeg"):
        if url.split("?")[0].lower().endswith(e):
            return e
    return {"image/png": ".png", "image/jpeg": ".jpg"}.get(content_type, ".webp")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    base = ap.parse_args().base.rstrip("/")
    c = httpx.Client(base_url=base, headers={"X-Visitor-Id": VISITOR}, timeout=120)

    def ok(r: httpx.Response) -> Any:
        if r.status_code >= 400:
            sys.exit(f"{r.request.method} {r.request.url} -> {r.status_code}: {r.text[:500]}")
        return r.json()

    print(f"1/3 Fusion: {SIRE} + {DAM} ({STYLE})")
    run = ok(c.post("/evo/agent/runs", data={"sireName": SIRE, "damName": DAM, "style": STYLE}))
    if "runId" not in run:
        sys.exit(f"The run did not start: {run}")
    run_id = run["runId"]
    snap = wait(lambda: ok(c.get(f"/evo/agent/runs/{run_id}")),
                lambda s: s.get("status") in ("succeeded", "failed", "interrupted"), "the Fusion run")
    if snap["status"] != "succeeded":
        sys.exit(f"The run ended {snap['status']}: {snap.get('error')}")
    version = ok(c.post("/evo/lab/versions/from-run", json={"runId": run_id}))
    vid = version["id"]
    print(f"  version {vid}: {version.get('title')}")

    print("2/3 Animal card")
    ok(c.post(f"/evo/lab/versions/{vid}/card"))
    card = wait(lambda: ok(c.get(f"/evo/lab/versions/{vid}/card"))["card"],
                lambda k: bool(k) and k.get("status") in ("ready", "failed"), "the animal card", every=5)
    if card["status"] != "ready":
        sys.exit(f"The card failed: {card.get('error')}")

    print("3/3 Save to Chimeras")
    saved = ok(c.put(f"/evo/lab/versions/{vid}/saved", json={"saved": True}))

    PUBLIC.mkdir(parents=True, exist_ok=True)
    DATA.parent.mkdir(parents=True, exist_ok=True)

    def fetch(url: str, name: str) -> str:
        r = httpx.get(url if url.startswith("http") else f"{base}{url}", timeout=120, follow_redirects=True)
        r.raise_for_status()
        file = f"{name}{ext_of(url, r.headers.get('content-type', ''))}"
        (PUBLIC / file).write_bytes(r.content)
        return f"/example/{file}"

    image = fetch(version["imageUrl"], "tiger-bat")
    angles = [{"view": a["view"], "url": fetch(a["url"], f"angle-{a['view']}")} for a in card["angles"]]
    example_card = {**card, "angles": angles}
    example_version = {
        **saved, "id": "example_v1", "runId": None, "creatureId": None, "imageUrl": image,
        "workspaceId": "example", "card": example_card, "saved": True,
    }
    DATA.write_text(json.dumps({"names": {"a": SIRE, "b": DAM}, "style": STYLE, "version": example_version},
                               indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {DATA.relative_to(ROOT)} and {len(angles) + 1} images in {PUBLIC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
