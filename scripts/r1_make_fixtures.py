"""R1 step 0: API fixtures (docs/api_fixtures/) from the real S5 benchmark runs, per docs/api_contract.md. No calls.

    .venv/Scripts/python.exe scripts/r1_make_fixtures.py

The success, cap and queued runs are converted from real S5 traces (b09, b06, b03). The host-tie run is the real b10
trace with an ask_user step added where the agent met the tie (the S5 runs were not interactive). The error run is
the start of the real b02 trace, cut off by an upstream error. Images are 768 px JPEGs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
S5 = ROOT / "docs" / "evolution" / "live" / "s5"
OUT = ROOT / "docs" / "api_fixtures"
IMG = OUT / "images"
T0 = datetime(2026, 11, 2, 15, 0, 0, tzinfo=UTC)
HIDDEN = {"material_look", "host_cover_kept", "donor_pieces"}
CAPS = {"renders": 4, "toolCalls": 30, "seconds": 900}
SHOWCASE = ["b09", "b01", "b03", "b08", "b11", "b05"]
NAMES = {"b01": ("axolotl", "Chinese pangolin"), "b02": ("rhinoceros beetle", "brown bear"),
         "b03": ("lion", "golden eagle"), "b05": ("donkey", "horse"), "b06": ("common octopus", "horse"),
         "b08": ("red fox", "barn owl"), "b09": ("Indian pangolin", "horse"), "b10": ("tortoise", "domestic goat"),
         "b11": ("crab", "gray wolf")}
SCI = {"axolotl": "Ambystoma mexicanum", "Chinese pangolin": "Manis pentadactyla", "lion": "Panthera leo",
       "golden eagle": "Aquila chrysaetos", "donkey": "Equus asinus", "horse": "Equus caballus",
       "common octopus": "Octopus vulgaris", "red fox": "Vulpes vulpes", "barn owl": "Tyto alba",
       "Indian pangolin": "Manis crassicaudata", "tortoise": "Testudo graeca", "domestic goat": "Capra hircus",
       "crab": "Cancer pagurus", "gray wolf": "Canis lupus", "rhinoceros beetle": "Oryctes nasicornis",
       "brown bear": "Ursus arctos"}


def J(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def jpg(src: Path, name: str, width: int = 768) -> str:
    IMG.mkdir(parents=True, exist_ok=True)
    if not src.exists():  # Muse Image sometimes returns a PNG (the agent saves it as imgN.png)
        src = next(src.parent.glob(src.stem + ".*"))
    with Image.open(src) as im:
        im = im.convert("RGB")
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        im.save(IMG / name, "JPEG", quality=84)
    return f"images/{name}"


def parent(name: str, source: str = "name", conf: float | None = None) -> dict[str, Any]:
    return {"commonName": name, "scientificName": SCI.get(name), "source": source, "confidence": conf}


def short(args: dict[str, Any] | None) -> dict[str, Any]:
    out = {}
    for k, v in (args or {}).items():
        s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        out[k] = (s[:119] + "…") if len(s) > 120 else v
    return out


class Stream:
    def __init__(self, run_id: str) -> None:
        self.run_id, self.events, self.t = run_id, [], T0

    def add(self, type_: str, seconds: float = 1.0, **payload: Any) -> dict[str, Any]:
        self.t += timedelta(seconds=seconds)
        e = {"id": len(self.events) + 1, "type": type_, "runId": self.run_id,
             "at": self.t.isoformat().replace("+00:00", "Z"), **payload}
        self.events.append(e)
        return e


def visible(fails: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    keep = [{"key": f["key"], "kind": f["kind"], "text": f["text"]} for f in fails if f["key"] not in HIDDEN]
    return keep, len(fails) - len(keep)


def replay(st: Stream, case: str, steps: list[dict[str, Any]], prefix: str, cap_after_last_render: bool = False,
           stop_before: int | None = None) -> dict[str, str]:
    """Trace steps -> step / render / inspect events. Returns imageId -> fixture image url."""
    d = S5 / case / "agent"
    crit = J(d / "critic.json")
    urls: dict[str, str] = {}
    for s in steps:
        if stop_before and s.get("n") and s["n"] >= stop_before:
            break
        if not s.get("n"):
            continue
        res = s.get("result") or {}
        err = None if s.get("ok") else (res.get("error") or ((res.get("errors") or [{}])[0].get("code")))
        st.add("step", seconds=float(s.get("seconds") or 1.0), n=s["n"], tool=s["tool"], args=short(s.get("arguments")),
               summary=s.get("summary", ""), reason=s.get("reason", ""), cards=s.get("cards") or [], ok=s.get("ok", True),
               error=err)
        if s["tool"] in ("render", "edit") and s.get("ok"):
            new = [res.get("host_image_id"), res.get("image_id")] if res.get("host_image_id") else [res.get("image_id")]
            for iid in [i for i in new if i]:
                urls[iid] = jpg(d / f"{iid}.webp", f"{prefix}_{iid}.jpg")
                info = crit.get(iid, {})
                st.add("render", seconds=0.1, n=s["n"], imageId=iid, url=urls[iid], kind=info.get("kind", "render"),
                       parent=info.get("parent"), method=(s.get("arguments") or {}).get("method", "edit"),
                       rendersUsed=res.get("renders_used"), rendersLeft=res.get("renders_left"))
            if cap_after_last_render and res.get("renders_left") == 0:
                st.add("cap_reached", seconds=0.1, scope="renders", limit=CAPS["renders"],
                       message="This run has used its 4 renders. The agent now finalizes its best image.")
        if s["tool"] == "inspect" and s.get("ok"):
            iid = res.get("image_id")
            fails, hidden = visible(res.get("failures") or [])
            st.add("inspect", seconds=0.1, n=s["n"], imageId=iid, verdict=res.get("verdict"), failures=fails,
                   hiddenChecks=hidden, bestSoFar=res.get("best_so_far"), rule=res.get("rule"))
    return urls


def creature(case: str, run_id: str, cid: str, prefix: str, host_by: str = "agent",
             host_reason: str | None = None) -> dict[str, Any]:
    d = S5 / case / "agent"
    doc, meta, plan, amap = J(d / "doc.json"), J(d / "meta.json"), J(d / "plan.json"), J(d / "anatomy_map.json")
    crit, trace = J(d / "critic.json"), J(d / "trace.json")
    card = doc["card"]
    sire, dam = NAMES[case]
    host = plan["host"]
    host_name = next((n for n in (sire, dam) if n.lower().replace(" ", "_") == host), host)
    choose = next(s for s in trace if s.get("tool") == "choose_candidate")
    fails, hidden = visible(card["remaining_failures"])
    funcs = [{"function": f["function"], "result": f["result"], "detail": f["detail"]} for f in card["can_it_live"]]
    ok = sum(f["result"] in ("pass", "licensed", "repaired") for f in funcs)
    lic = [{"rule": x.get("rule") or x.get("id"), "compensation": x.get("compensation")} for x in card["licenses"]]
    fc = card["final_choice"]

    def pick(p: dict[str, Any]) -> dict[str, Any]:
        return {"imageId": p["image_id"], "imageUrl": f"images/{prefix}_{p['image_id']}.jpg", "rank": p["rank"],
                "of": p["of"], "structural": p["structural"], "failures": p["failures"], "reason": p["reason"]}

    images = []
    for iid, info in crit.items():
        images.append({"imageId": iid, "url": jpg(d / f"{iid}.webp", f"{prefix}_{iid}.jpg"), "kind": info["kind"],
                       "verdict": info["verdict"]})
    overlay = jpg(d / "anatomy_map.png", f"{prefix}_anatomy.jpg", width=768)
    return {
        "creatureId": cid, "createdAt": "2026-11-01T21:00:00Z", "title": f"{sire} × {dam}",
        "sire": parent(sire), "dam": parent(dam), "mode": meta["mode"],
        "generatedLabel": "Generated fusion", "realHybrid": doc.get("route", {}).get("mode") == "hybrid",
        "showcase": case in SHOWCASE, "imageUrl": f"images/{prefix}_{doc['image_id']}.jpg",
        "host": {"commonName": host_name, "reason": host_reason or choose["reason"],
                 "tie": "host tie" in json.dumps([s.get("summary") for s in trace]), "chosenBy": host_by},
        "canItLive": {"summary": f"{ok} of {len(funcs)} life functions work"
                                 + (f"; {len(lic)} declared fiction license(s)" if lic else "; no fiction licenses"),
                      "functions": funcs, "licenses": lic},
        "remainingFailures": fails, "hiddenChecks": hidden,
        "finalChoice": {"shownFirst": "agent", "agree": fc["agree"], "agentPick": pick(fc["agent_pick"]),
                        "codePick": pick(fc["code_pick"])},
        "anatomyMap": {"overlayUrl": overlay, "colors": amap["colors"],
                       "parts": [{"part": p["part"], "parent": p["parent_name"], "parentRole": p["parent_role"],
                                  "status": p["status"], "color": p["color"], "maskArea": p["mask_area"]}
                                 for p in amap["parts"]]},
        "images": images, "runId": run_id,
        "stats": {"renders": meta["renders"], "edits": meta["edits"], "toolCalls": meta["tool_calls"],
                  "seconds": meta["wall_seconds"]},
        "card": {k: v for k, v in card.items() if k not in ("remaining_failures",)} | {"remaining_failures": fails},
        "plan": plan,
    }


def post_ok(run_id: str, case: str, mode: str, status: str = "running", position: int | None = None,
            source: str = "image") -> dict[str, Any]:
    sire, dam = NAMES[case]
    conf = 0.93 if source == "image" else None
    return {"status": 202, "body": {"runId": run_id, "status": status, "position": position,
                                    "eventsUrl": f"/evo/agent/runs/{run_id}/events",
                                    "runUrl": f"/evo/agent/runs/{run_id}", "sire": parent(sire, source, conf),
                                    "dam": parent(dam, source, conf), "mode": mode}}


def request(case: str, mode: str, images: bool = True) -> dict[str, Any]:
    sire, dam = NAMES[case]
    files = {"sireImage": f"<photo of a {sire}>", "damImage": f"<photo of a {dam}>"} if images else {}
    return {"method": "POST", "path": "/evo/agent/runs", "contentType": "multipart/form-data",
            "fields": {"mode": mode, **({} if images else {"sireName": sire, "damName": dam})}, "files": files}


def started(st: Stream, case: str, mode: str) -> None:
    sire, dam = NAMES[case]
    st.add("started", sire=parent(sire, "image", 0.93), dam=parent(dam, "image", 0.93), mode=mode, caps=CAPS)


def finalize(st: Stream, case: str, cid: str, prefix: str, stop: str) -> None:
    d = S5 / case / "agent"
    doc = J(d / "doc.json")
    fails, hidden = visible(doc["card"]["remaining_failures"])
    st.add("finalize", seconds=4.0, creatureId=cid, imageId=doc["image_id"],
           imageUrl=f"images/{prefix}_{doc['image_id']}.jpg", remainingFailures=fails, hiddenChecks=hidden,
           agree=doc["card"]["final_choice"]["agree"], stop=stop)


def write(name: str, data: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    # 1. success: b09, real trace
    rid, cid = "run_fx_success", "crt_fx_b09"
    st = Stream(rid)
    started(st, "b09", "realistic")
    replay(st, "b09", J(S5 / "b09/agent/trace.json"), "b09")
    finalize(st, "b09", cid, "b09", "finalized by the agent")
    cr = creature("b09", rid, cid, "b09")
    write("run_success.json", {"name": "run_success", "description": "Real S5 run b09 Indian pangolin x horse "
                               "(realistic), converted to the event stream.", "request": request("b09", "realistic"),
                               "response": post_ok(rid, "b09", "realistic"), "events": st.events, "creature": cr,
                               "snapshot": {"runId": rid, "status": "succeeded", "position": None,
                                            "sire": cr["sire"], "dam": cr["dam"], "mode": "realistic",
                                            "createdAt": "2026-11-02T15:00:00Z", "updatedAt": st.events[-1]["at"],
                                            "lastEventId": st.events[-1]["id"], "creatureId": cid, "error": None,
                                            "pendingChoice": None}})
    write("creature_b09.json", {"name": "creature_b09", "description": "GET /evo/creatures/crt_fx_b09",
                                "request": {"method": "GET", "path": f"/evo/creatures/{cid}"},
                                "response": {"status": 200, "body": cr}})

    # 2. host tie: real b10 trace with the ask added at the tie
    rid, cid = "run_fx_host_tie", "crt_fx_b10"
    st = Stream(rid)
    started(st, "b10", "realistic")
    tr = J(S5 / "b10/agent/trace.json")
    replay(st, "b10", [s for s in tr if s["n"] and s["n"] <= 3], "b10")
    choice = "choice_fx_1"
    st.add("needs_choice", seconds=2.0, n=4, choiceId=choice, kind="host_tie",
           question="Both animals can carry the body. Which should be the host?",
           options=["tortoise", "domestic goat"], expiresAt=(st.t + timedelta(seconds=120)).isoformat().replace("+00:00", "Z"))
    st.add("choice_resolved", seconds=14.0, choiceId=choice, answer="domestic goat", by="user")
    st.add("step", seconds=0.1, n=4, tool="ask_user", args={"question": "Which parent should be the body (host)?",
                                                           "options": "[\"tortoise\", \"domestic goat\"]"},
           summary="answer: domestic goat", reason="Structural host tie (RC-R10-01): neither size nor name order may "
           "decide; both bodies carry every function, so I ask which body the user wants.", cards=["RC-R10-01"],
           ok=True, error=None)
    later = []
    for s in tr:
        if s["n"] and s["n"] >= 4:
            later.append({**s, "n": s["n"] + 1})
    later[0] = {**later[0], "reason": "The user chose the domestic goat as host; C2 is the goat-host candidate."}
    replay(st, "b10", later, "b10")
    finalize(st, "b10", cid, "b10", "finalized by the agent")
    cr10 = creature("b10", rid, cid, "b10", host_by="user",
                    host_reason="You chose the domestic goat as host on a structural tie (RC-R10-01).")
    write("run_host_tie.json", {"name": "run_host_tie", "description": "S5 b10 tortoise x domestic goat with an "
                                "ask_user step added at the host tie (constructed: the S5 run decided itself). The "
                                "client answers with POST /evo/agent/runs/{id}/choice.",
                                "request": request("b10", "realistic"), "response": post_ok(rid, "b10", "realistic"),
                                "choiceRequest": {"method": "POST", "path": f"/evo/agent/runs/{rid}/choice",
                                                  "body": {"choiceId": choice, "answer": "domestic goat"},
                                                  "response": {"status": 200, "body": {"accepted": True}}},
                                "events": st.events, "creature": cr10})

    # 3. identify needs_choice
    write("identify_choice.json", {
        "name": "identify_choice", "description": "POST with two photos; the sire photo is not identified with "
        "confidence. No run is created; the client posts again with names.",
        "request": request("b10", "realistic"),
        "response": {"status": 200, "body": {"status": "needs_choice", "choice": {
            "kind": "identify", "slot": "sire", "question": "Which animal is in the first photo?",
            "options": [{"commonName": "tortoise", "scientificName": "Testudo graeca", "confidence": 0.54},
                        {"commonName": "Galápagos tortoise", "scientificName": "Chelonoidis niger", "confidence": 0.29},
                        {"commonName": "box turtle", "scientificName": "Terrapene carolina", "confidence": 0.11}],
            "allowOther": True},
            "identified": {"sire": None, "dam": parent("domestic goat", "image", 0.95)}}},
        "followUp": {"request": request("b10", "realistic", images=False), "response": post_ok("run_fx_host_tie",
                                                                                              "b10", "realistic",
                                                                                              source="name")}})

    # 4. cap: real b06 trace (4 renders)
    rid, cid = "run_fx_cap", "crt_fx_b06"
    st = Stream(rid)
    started(st, "b06", "realistic")
    replay(st, "b06", J(S5 / "b06/agent/trace.json"), "b06", cap_after_last_render=True)
    finalize(st, "b06", cid, "b06", "finalized by the agent at the render cap (4)")
    write("run_cap.json", {"name": "run_cap", "description": "Real S5 run b06 common octopus x horse: the agent used "
                           "all 4 renders (cap_reached), then finalized its best image.",
                           "request": request("b06", "realistic"), "response": post_ok(rid, "b06", "realistic"),
                           "events": st.events, "creature": creature("b06", rid, cid, "b06")})

    # 5. queued: real b03 trace after two queue positions
    rid, cid = "run_fx_queued", "crt_fx_b03"
    st = Stream(rid)
    st.add("queued", seconds=0, position=2, ahead=2)
    st.add("queued", seconds=170, position=1, ahead=1)
    started(st, "b03", "mythic")
    st.events[-1]["at"] = (st.t + timedelta(seconds=160)).isoformat().replace("+00:00", "Z")
    st.t += timedelta(seconds=160)
    replay(st, "b03", J(S5 / "b03/agent/trace.json"), "b03")
    finalize(st, "b03", cid, "b03", "finalized by the agent")
    write("run_queued.json", {"name": "run_queued", "description": "The concurrent limit is full: the run waits at "
                              "position 2, then 1, then runs (real S5 b03 lion x golden eagle, mythic).",
                              "request": request("b03", "mythic"),
                              "response": post_ok(rid, "b03", "mythic", status="queued", position=2),
                              "events": st.events, "creature": creature("b03", rid, cid, "b03")})

    # 6. refused uploads
    def refused(slot: str, status: int, code: str, message: str, **details: Any) -> dict[str, Any]:
        return {"status": status, "body": {"error": {"code": code, "message": message, "retryable": False,
                                                     "details": {"slot": slot, **details}}}}

    write("upload_refused.json", {"name": "upload_refused", "description": "POST refused before anything runs.",
                                  "cases": [
        {"request": {**request("b09", "realistic"), "files": {"sireImage": "<photo of a person>",
                                                              "damImage": "<photo of a horse>"}},
         "response": refused("sire", 422, "HUMAN_DETECTED", "This looks like a photo of a person. Chimera Lab only "
                             "uses animal photos.")},
        {"request": {**request("b09", "realistic"), "files": {"sireImage": "<scan.gif>", "damImage": "<horse.jpg>"}},
         "response": refused("sire", 422, "UNSUPPORTED_FILE", "Use a JPEG, PNG or WebP image.")},
        {"request": {**request("b09", "realistic"), "files": {"sireImage": "<pangolin.png, 11 MB>",
                                                              "damImage": "<horse.jpg>"}},
         "response": refused("sire", 413, "FILE_TOO_LARGE", "Images must be 8 MB or smaller.", maxBytes=8388608)},
        {"request": {**request("b09", "realistic"), "files": {"sireImage": "<photo of a teapot>",
                                                              "damImage": "<horse.jpg>"}},
         "response": refused("sire", 422, "NOT_AN_ANIMAL", "We couldn't find an animal in this image.")}]})

    # 7. daily cap
    write("cap_daily.json", {"name": "cap_daily", "description": "POST refused: today's runs are used up. The "
                             "gallery stays open.", "request": request("b09", "realistic"),
                             "response": {"status": 429, "body": {"error": {
                                 "code": "CAP_REACHED", "retryable": False,
                                 "message": "Today's live creature runs are used up. The gallery is still open; new "
                                            "runs open again at 00:00 UTC.",
                                 "details": {"scope": "daily_total", "limit": 50, "resetsAt": "2026-11-03T00:00:00Z"}}}}})

    # 8. error: the start of the real b02 trace, then an upstream error
    rid = "run_fx_error"
    st = Stream(rid)
    started(st, "b02", "speculative")
    replay(st, "b02", J(S5 / "b02/agent/trace.json"), "b02", stop_before=8)
    st.add("error", seconds=30, code="UPSTREAM_ERROR", retryable=True,
           message="The image model stopped answering, so this run ended. Nothing was charged to you; try again in "
                   "a few minutes.")
    write("run_error.json", {"name": "run_error", "description": "Real S5 b02 rhinoceros beetle x brown bear up to its "
                             "first inspect, then an upstream error ends the run (constructed).",
                             "request": request("b02", "speculative"), "response": post_ok(rid, "b02", "speculative"),
                             "events": st.events})

    # 9. gallery, 10. limits
    items = []
    for i, case in enumerate(SHOWCASE):
        d = S5 / case / "agent"
        doc, meta = J(d / "doc.json"), J(d / "meta.json")
        sire, dam = NAMES[case]
        items.append({"creatureId": f"crt_fx_{case}", "title": f"{sire} × {dam}", "sire": parent(sire),
                      "dam": parent(dam), "mode": meta["mode"],
                      "imageUrl": jpg(d / f"{doc['image_id']}.webp", f"{case}_{doc['image_id']}.jpg"),
                      "showcase": True, "createdAt": f"2026-11-01T2{i}:00:00Z"})
    write("gallery.json", {"name": "gallery", "description": "GET /evo/gallery: the six showcase creatures (S5 agent "
                           "images; the list is pending the owner's ratings).",
                           "request": {"method": "GET", "path": "/evo/gallery?limit=24"},
                           "response": {"status": 200, "body": {"items": items, "nextCursor": None}}})
    write("limits.json", {"name": "limits", "description": "GET /evo/agent/limits, open and capped.", "cases": [
        {"response": {"status": 200, "body": {"liveRuns": "open", "dailyTotal": {"used": 12, "limit": 50,
                                                                                  "resetsAt": "2026-11-03T00:00:00Z"},
                                              "visitor": {"used": 1, "limit": 3},
                                              "concurrent": {"running": 2, "limit": 3, "queued": 0}}}},
        {"response": {"status": 200, "body": {"liveRuns": "capped", "dailyTotal": {"used": 50, "limit": 50,
                                                                                    "resetsAt": "2026-11-03T00:00:00Z"},
                                              "visitor": {"used": 0, "limit": 3},
                                              "concurrent": {"running": 0, "limit": 3, "queued": 0}}}}]})
    print("fixtures:", sorted(p.name for p in OUT.glob("*.json")), "images:", len(list(IMG.glob("*.jpg"))))


if __name__ == "__main__":
    main()
