"""The library: workspaces, saving creatures (the card is made in the background), deleting images (record and files),
editing a card's text, and the sketch edit."""

from __future__ import annotations

import io
from typing import Any

from PIL import Image

from tests.agentapi.test_agent_api import make_client, named_run, post_run  # noqa: F401  (make_client: fixture)
from tests.agentapi.test_prompt_mode import finished_version, prompt_client, wait_card, wait_job
from tests.conftest import auth, visitor_id

USER = visitor_id()


async def v1_in(c: Any, ws: str | None = None) -> dict[str, Any]:
    data = {"sireName": "horse", "damName": "pangolin", **({"workspaceId": ws} if ws else {})}
    return await finished_version(c, (await post_run(c, files={}, data=data)).json()["runId"])


async def file_exists(c: Any, url: str) -> bool:
    return (await c.get(url)).status_code == 200


# ====================================================================== workspaces


async def test_the_old_canvas_becomes_the_first_workspace(make_client):  # noqa: F811
    c, _ = await prompt_client(make_client)
    graph = {"nodes": [{"id": "n1"}], "edges": []}
    # The canvas as the app stored it before workspaces existed.
    await c.app.state.agent.services.db.put("graphs", f"workspace:{USER}", {"owner": USER, "graph": graph,
                                                                         "revision": 1, "updatedAt": "2026-11-01"})
    [ws] = (await c.get("/evo/lab/workspaces")).json()["workspaces"]
    assert ws["id"] == "main" and ws["name"] == "My workspace" and ws["imageCount"] == 0
    assert (await c.get("/evo/lab/workspaces/main")).json()["graph"] == graph


async def test_create_rename_save_and_list_workspaces(make_client):  # noqa: F811
    c, _ = await prompt_client(make_client)
    await c.get("/evo/lab/workspaces")
    r = await c.post("/evo/lab/workspaces", json={"name": "  Sea   creatures "})
    assert r.status_code == 201
    ws = r.json()
    assert ws["name"] == "Sea creatures" and ws["id"].startswith("ws")
    graph = {"nodes": [], "edges": []}
    saved = await c.put(f"/evo/lab/workspaces/{ws['id']}", json={"graph": graph, "name": "Reef"})
    assert saved.json()["name"] == "Reef" and saved.json()["revision"] == 1
    names = [w["name"] for w in (await c.get("/evo/lab/workspaces")).json()["workspaces"]]
    assert names[0] == "Reef" and "My workspace" in names  # most recently changed first
    assert (await c.get("/evo/lab/workspaces/nope")).status_code == 404


async def test_images_belong_to_the_workspace_they_were_made_in(make_client):  # noqa: F811
    c, _ = await prompt_client(make_client)
    await c.get("/evo/lab/workspaces")
    ws = (await c.post("/evo/lab/workspaces", json={"name": "B"})).json()["id"]
    a1 = await v1_in(c)  # no workspace: main
    b1 = await v1_in(c, ws)
    job = (await c.post(f"/evo/lab/versions/{b1['id']}/revise", json={"instruction": "longer legs"})).json()["id"]
    b2 = (await wait_job(c, job))["result"]
    assert b1["workspaceId"] == ws and b2["workspaceId"] == ws  # an edit stays in its parent's workspace
    listed = {w["id"]: w for w in (await c.get("/evo/lab/workspaces")).json()["workspaces"]}
    assert listed[ws]["thumbnails"][0] == b2["imageUrl"] and listed["main"]["thumbnails"] == [a1["imageUrl"]]
    main_ids = [i["id"] for i in (await c.get("/evo/lab/workspaces/main/images")).json()["images"]]
    b_ids = [i["id"] for i in (await c.get(f"/evo/lab/workspaces/{ws}/images")).json()["images"]]
    assert main_ids == [a1["id"]] and set(b_ids) == {b1["id"], b2["id"]}


async def test_deleting_a_workspace_deletes_its_images_but_not_ones_another_canvas_shows(make_client):  # noqa: F811
    c, _ = await prompt_client(make_client)
    await c.get("/evo/lab/workspaces")
    ws = (await c.post("/evo/lab/workspaces", json={"name": "B"})).json()["id"]
    gone = await v1_in(c, ws)
    shared = await v1_in(c, ws)
    graph = {"nodes": [{"id": "x", "type": "version", "data": {"version": {"id": shared["id"]}}}], "edges": []}
    await c.put("/evo/lab/workspaces/main", json={"graph": graph})
    r = await c.delete(f"/evo/lab/workspaces/{ws}")
    assert r.status_code == 200 and r.json()["imagesDeleted"] == 1
    db = c.app.state.agent.services.db
    assert await db.get("assets", gone["id"]) is None and not await file_exists(c, gone["imageUrl"])
    assert await db.get("assets", shared["id"]) is not None
    assert [w["id"] for w in (await c.get("/evo/lab/workspaces")).json()["workspaces"]] == ["main"]


async def test_deleting_the_main_workspace_does_not_bring_the_old_canvas_back(make_client):  # noqa: F811
    c, _ = await prompt_client(make_client)
    await c.app.state.agent.services.db.put("graphs", f"workspace:{USER}", {
        "owner": USER, "graph": {"nodes": [{"id": "old"}], "edges": []}, "revision": 1, "updatedAt": "2026-11-01"})
    await c.get("/evo/lab/workspaces")
    other = (await c.post("/evo/lab/workspaces", json={"name": "B"})).json()["id"]
    assert (await c.delete("/evo/lab/workspaces/main")).status_code == 200
    assert [w["id"] for w in (await c.get("/evo/lab/workspaces")).json()["workspaces"]] == [other]


# ====================================================================== deleting an image


async def test_deleting_an_image_removes_its_record_files_and_run(make_client):  # noqa: F811
    c, _ = await prompt_client(make_client)
    v1 = await v1_in(c)
    await c.post(f"/evo/lab/versions/{v1['id']}/card")
    card = await wait_card(c, v1["id"])
    urls = [v1["imageUrl"], *[a["url"] for a in card["angles"]]]
    assert all([await file_exists(c, u) for u in urls])
    r = await c.delete(f"/evo/lab/versions/{v1['id']}")
    assert r.status_code == 200
    db = c.app.state.agent.services.db
    assert await db.get("assets", v1["id"]) is None
    assert await db.get("creatures", v1["creatureId"]) is None and await db.get("agent_runs", v1["runId"]) is None
    assert not any([await file_exists(c, u) for u in urls])
    assert (await c.delete(f"/evo/lab/versions/{v1['id']}")).status_code == 404


async def test_an_edit_survives_deleting_the_image_it_came_from(make_client):  # noqa: F811
    c, _ = await prompt_client(make_client)
    v1 = await v1_in(c)
    job = (await c.post(f"/evo/lab/versions/{v1['id']}/revise", json={"instruction": "longer legs"})).json()["id"]
    v2 = (await wait_job(c, job))["result"]
    await c.delete(f"/evo/lab/versions/{v1['id']}")
    job = (await c.post(f"/evo/lab/versions/{v2['id']}/revise", json={"instruction": "blue mane"})).json()["id"]
    assert (await wait_job(c, job))["status"] == "succeeded"


async def test_only_the_owner_can_delete(make_client):  # noqa: F811
    c, _ = await prompt_client(make_client)
    v1 = await v1_in(c)
    r = await c.delete(f"/evo/lab/versions/{v1['id']}", headers=auth("user-2"))
    assert r.status_code == 404
    assert await c.app.state.agent.services.db.get("assets", v1["id"]) is not None


# ====================================================================== saving and cards


async def test_saving_is_immediate_and_the_card_follows_in_the_background(make_client):  # noqa: F811
    c, rec = await prompt_client(make_client)
    v1 = await v1_in(c)
    r = await c.put(f"/evo/lab/versions/{v1['id']}/saved", json={"saved": True})
    assert r.status_code == 200 and r.json()["saved"] is True and r.json()["card"]["status"] == "running"
    [row] = (await c.get("/evo/lab/chimeras")).json()["chimeras"]
    assert row["id"] == v1["id"]
    card = await wait_card(c, v1["id"])
    assert card["status"] == "ready" and len(card["angles"]) == 4
    calls = len(rec.calls)
    await c.put(f"/evo/lab/versions/{v1['id']}/saved", json={"saved": True})  # saving again: no second card
    assert len(rec.calls) == calls
    await c.put(f"/evo/lab/versions/{v1['id']}/saved", json={"saved": False})
    assert (await c.get("/evo/lab/chimeras")).json()["chimeras"] == []


async def test_editing_the_card_text_updates_the_profile_and_title(make_client):  # noqa: F811
    c, _ = await prompt_client(make_client)
    v1 = await v1_in(c)
    r = await c.put(f"/evo/lab/versions/{v1['id']}/profile", json={"name": "Dune Strider", "weight": "300 kg",
                                                                     "ignored": "x"})
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Dune Strider" and body["profile"]["weight"] == "300 kg"
    assert body["profile"]["trait"] == "SCALES"  # untouched fields stay
    refused = await c.put(f"/evo/lab/versions/{v1['id']}/profile", json={"name": "the president"})
    assert refused.status_code == 422 and refused.json()["error"]["details"]["offTopic"] is True


# ====================================================================== sketch


def drawing(size: int = 64, empty: bool = False) -> bytes:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if not empty:
        for x in range(10, 30):
            img.putpixel((x, 20), (255, 0, 0, 255))
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


async def test_a_sketch_sends_the_image_with_the_drawing_and_makes_a_new_version(make_client):  # noqa: F811
    c, rec = await prompt_client(make_client)
    v1 = await v1_in(c)
    r = await c.post(f"/evo/lab/versions/{v1['id']}/sketch", files={"sketch": ("s.png", drawing(), "image/png")},
                     data={"instruction": "a horn here"})
    assert r.status_code == 202, r.text
    done = await wait_job(c, r.json()["id"])
    assert done["status"] == "succeeded" and done["result"]["operation"] == "sketch"
    prompt, nrefs = rec.calls[-1]
    assert nrefs == 2 and "a horn here" in prompt and "Remove every drawn line" in prompt  # marked + clean
    assert "parent animals (horse or pangolin)" in prompt and "Never erase the area" in prompt
    assert "white background" in prompt


async def test_an_empty_or_off_topic_sketch_is_refused(make_client):  # noqa: F811
    c, rec = await prompt_client(make_client)
    v1 = await v1_in(c)
    calls = len(rec.calls)
    empty = await c.post(f"/evo/lab/versions/{v1['id']}/sketch",
                         files={"sketch": ("s.png", drawing(empty=True), "image/png")})
    assert empty.status_code == 422
    off = await c.post(f"/evo/lab/versions/{v1['id']}/sketch", files={"sketch": ("s.png", drawing(), "image/png")},
                       data={"instruction": "write a poem"})
    assert off.status_code == 422 and off.json()["error"]["details"]["offTopic"] is True
    assert len(rec.calls) == calls


def mask_png(size: int, box: tuple[int, int, int, int]) -> bytes:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for x in range(box[0], box[2]):
        for y in range(box[1], box[3]):
            img.putpixel((x, y), (255, 0, 0, 255))
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


async def test_paint_shows_the_model_where_and_fills_it_from_the_parent_animals(make_client):  # noqa: F811
    c, rec = await prompt_client(make_client)
    v1 = await v1_in(c)
    size = Image.open(io.BytesIO((await c.get(v1["imageUrl"])).content)).size[0]
    r = await c.post(f"/evo/lab/versions/{v1['id']}/paint", data={"instruction": "replace the tail with a tentacle"},
                     files={"mask": ("m.png", mask_png(size, (4, 4, 20, 20)), "image/png")})
    assert r.status_code == 202, r.text
    done = await wait_job(c, r.json()["id"])
    assert done["status"] == "succeeded"
    prompt, nrefs = rec.calls[-1]
    assert nrefs == 2  # the highlighted copy and the clean image
    assert "highlighted in translucent magenta" in prompt and "parent animals (horse and pangolin)" in prompt
    assert "Never erase the area" in prompt
    stored = await c.app.state.agent.services.db.get("assets", done["result"]["id"])
    assert [p["commonName"] for p in stored["generation"]["parents"]] == ["horse", "pangolin"]  # kept on edits


def test_the_highlight_marks_only_the_painted_area():
    from app.agentapi.lab import mark_region

    base = io.BytesIO()
    Image.new("RGB", (40, 40), (255, 255, 255)).save(base, "PNG")
    marked = Image.open(io.BytesIO(mark_region(base.getvalue(), mask_png(40, (10, 10, 20, 20))))).convert("RGB")
    assert marked.getpixel((15, 15)) != (255, 255, 255) and marked.getpixel((35, 35)) == (255, 255, 255)
