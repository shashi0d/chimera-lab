"""The Creature and GalleryItem views (docs/api_contract.md), built from an engine creature doc and its trace.

The same builder serves live runs (the agent's doc in memory) and the S5 showcase (the saved run folders), and
matches scripts/r1_make_fixtures.py, which made the contract fixtures from the same inputs.

Material-only critic checks (D-096) are removed from `remainingFailures`, from inspect events and from the card until
they have owner labels; `hiddenChecks` counts them. Every other critic result shows as it is.
"""

from __future__ import annotations

import json
from typing import Any

HIDDEN_CHECKS = ("material_look", "host_cover_kept", "donor_pieces")
GENERATED_LABEL = "Generated fusion"
ARG_CHARS = 120


def visible(failures: list[dict[str, Any]] | None) -> tuple[list[dict[str, Any]], int]:
    rows = list(failures or [])
    keep = [{"key": f["key"], "kind": f.get("kind"), "text": f.get("text")} for f in rows
            if f.get("key") not in HIDDEN_CHECKS]
    return keep, len(rows) - len(keep)


def short_args(args: dict[str, Any] | None) -> dict[str, Any]:
    """Each value cut to 120 characters (a long non-string value is cut as its JSON text)."""
    out: dict[str, Any] = {}
    for k, v in (args or {}).items():
        s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        out[k] = (s[: ARG_CHARS - 1] + "…") if len(s) > ARG_CHARS else v
    return out


def parent_view(common: str | None, scientific: str | None = None, source: str = "name",
                confidence: float | None = None) -> dict[str, Any]:
    return {"commonName": common, "scientificName": scientific, "source": source, "confidence": confidence}


def _pick(p: dict[str, Any], urls: dict[str, str]) -> dict[str, Any]:
    return {"imageId": p.get("image_id"), "imageUrl": urls.get(p.get("image_id") or ""), "rank": p.get("rank"),
            "of": p.get("of"), "structural": p.get("structural"), "failures": p.get("failures"),
            "reason": p.get("reason")}


def host_view(plan: dict[str, Any], sire: dict[str, Any], dam: dict[str, Any], trace: list[dict[str, Any]],
              chosen_by: str | None = None, reason: str | None = None) -> dict[str, Any]:
    host = plan.get("host")
    parents = plan.get("parents") or {}
    name = (sire["commonName"] if host and host == parents.get("sire") else
            dam["commonName"] if host and host == parents.get("dam") else (host or "blend").replace("_", " "))
    choose = next((s for s in trace if s.get("tool") == "choose_candidate" and s.get("ok", True)), None)
    set_host = next((s for s in trace if s.get("tool") == "set_host" and s.get("ok", True)), None)
    tie = "host tie" in json.dumps([s.get("summary") for s in trace], ensure_ascii=False)
    if chosen_by is None:
        chosen_by = "agent" if (choose or set_host) else "code"
    why = reason or ((set_host or choose or {}).get("reason") or "")
    return {"commonName": name, "reason": why, "tie": tie, "chosenBy": chosen_by}


def can_it_live_view(card: dict[str, Any]) -> dict[str, Any]:
    funcs = [{"function": f.get("function"), "result": f.get("result"), "detail": f.get("detail")}
             for f in card.get("can_it_live") or []]
    ok = sum(f["result"] in ("pass", "licensed", "repaired") for f in funcs)
    lic = [{"rule": x.get("rule") or x.get("id"), "compensation": x.get("compensation")}
           for x in card.get("licenses") or []]
    summary = f"{ok} of {len(funcs)} life functions work" + (
        f"; {len(lic)} declared fiction license(s)" if lic else "; no fiction licenses")
    return {"summary": summary, "functions": funcs, "licenses": lic}


def anatomy_view(amap: dict[str, Any], overlay_url: str | None) -> dict[str, Any]:
    return {"overlayUrl": overlay_url, "colors": amap.get("colors") or {},
            "parts": [{"part": p.get("part"), "parent": p.get("parent_name") or p.get("parent"),
                       "parentRole": p.get("parent_role"), "status": p.get("status"), "color": p.get("color"),
                       "maskArea": p.get("mask_area")} for p in amap.get("parts") or []]}


def public_card(card: dict[str, Any]) -> dict[str, Any]:
    """The engine card with the material-only checks removed from its remaining failures."""
    fails, _ = visible(card.get("remaining_failures"))
    return {k: v for k, v in card.items() if k != "remaining_failures"} | {"remaining_failures": fails}


def build_creature(*, creature_id: str, created_at: str, sire: dict[str, Any], dam: dict[str, Any], mode: str,
                   card: dict[str, Any], plan: dict[str, Any], route_mode: str | None, image_id: str,
                   trace: list[dict[str, Any]], images: list[dict[str, Any]], overlay_url: str | None,
                   run_id: str | None, stats: dict[str, Any], host_by: str | None = None,
                   host_reason: str | None = None) -> dict[str, Any]:
    """`images` is [{imageId, url, kind, verdict}] in render order."""
    urls = {i["imageId"]: i["url"] for i in images}
    fails, hidden = visible(card.get("remaining_failures"))
    fc = card.get("final_choice") or {}
    return {
        "creatureId": creature_id, "createdAt": created_at,
        "title": f"{sire['commonName']} × {dam['commonName']}",
        "sire": sire, "dam": dam, "mode": mode,
        "generatedLabel": GENERATED_LABEL, "realHybrid": route_mode == "hybrid", "showcase": False,
        "imageUrl": urls.get(image_id),
        "host": host_view(plan, sire, dam, trace, host_by, host_reason),
        "canItLive": can_it_live_view(card),
        "remainingFailures": fails, "hiddenChecks": hidden,
        "finalChoice": {"shownFirst": fc.get("shown_first", "agent"), "agree": bool(fc.get("agree", True)),
                        "agentPick": _pick(fc.get("agent_pick") or {"image_id": image_id}, urls),
                        "codePick": _pick(fc.get("code_pick") or {"image_id": image_id}, urls)},
        "anatomyMap": anatomy_view(card.get("anatomy_map") or {}, overlay_url),
        "images": images, "runId": run_id, "stats": stats,
        "card": public_card(card), "plan": plan,
    }


def gallery_item(c: dict[str, Any]) -> dict[str, Any]:
    return {k: c.get(k) for k in ("creatureId", "title", "sire", "dam", "mode", "imageUrl", "showcase", "createdAt")}
