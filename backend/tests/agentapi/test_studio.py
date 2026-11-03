from __future__ import annotations

import io
import asyncio

from PIL import Image

from app.adapters.base import GeneratedImage


def image_bytes(color: str) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(out, "PNG")
    return out.getvalue()


async def test_concept_and_branching_revisions_keep_creator_intent_and_references(client):
    calls = []

    class Renderer:
        async def generate(self, prompt, refs, aspect, previous_response_id=None):
            calls.append((prompt, refs, previous_response_id))
            return GeneratedImage(image_bytes("blue"), "image/png", "test", f"response-{len(calls)}")

    client.app.state.services.image_gen = Renderer()
    brief = "Monkey upper body, spider hips and eight spider legs"
    response = await client.post("/evo/studio/concept", data={"animal1": "monkey", "animal2": "spider", "brief": brief},
                                 files={"image1": ("monkey.png", image_bytes("red"), "image/png"),
                                        "image2": ("spider.png", image_bytes("green"), "image/png")})
    assert response.status_code == 201, response.text
    first = response.json()
    assert brief in calls[0][0]
    assert len(calls[0][1]) == 2
    assert "responseId" not in first
    assert (await client.get(first["imageUrl"])).status_code == 200
    edit = await client.post(f"/evo/studio/versions/{first['id']}/revise", json={"instruction": "Longer legs"})
    assert edit.status_code == 201, edit.text
    assert edit.json()["parentId"] == first["id"]
    assert calls[1][2] == "response-1"
    branch = await client.post(f"/evo/studio/versions/{first['id']}/revise", json={"instruction": "Blue fur"})
    assert branch.status_code == 201
    assert calls[2][2] == "response-1"
    denied = await client.post(f"/evo/studio/versions/{first['id']}/revise", json={"instruction": "change"},
                               headers={"X-Session-Id": "other-session-1"})
    assert denied.status_code == 404


async def test_rejects_missing_animal_and_invalid_reference(client):
    missing = await client.post("/evo/studio/concept", data={"animal1": "monkey", "brief": "spider legs"})
    assert missing.status_code == 422
    invalid = await client.post("/evo/studio/concept", data={"animal1": "monkey", "animal2": "spider", "brief": "legs"},
                                files={"image1": ("bad.png", b"not an image", "image/png")})
    assert invalid.status_code == 422


async def test_saved_history_and_review_use_the_selected_image_and_original_brief(client, monkeypatch):
    from app.agentapi import studio

    class Renderer:
        async def generate(self, prompt, refs, aspect, previous_response_id=None):
            return GeneratedImage(image_bytes("blue"), "image/png", "test", "response")

    captured = {}

    async def fake_review(settings, image, brief, change):
        captured.update(image=image, brief=brief, change=change)
        return {"observation": "A creature", "suggestions": "Try longer legs."}

    monkeypatch.setattr(studio, "review_image", fake_review)
    client.app.state.services.image_gen = Renderer()
    first = (await client.post("/evo/studio/concept", data={"animal1": "monkey", "animal2": "spider", "brief": "Eight legs"})).json()
    child = (await client.post(f"/evo/studio/versions/{first['id']}/revise", json={"instruction": "Blue fur"})).json()
    review = await client.post(f"/evo/studio/versions/{child['id']}/review")
    assert review.status_code == 200
    assert captured == {"image": image_bytes("blue"), "brief": "Eight legs", "change": "Blue fur"}
    assert review.json()["suggestions"] == "Try longer legs."
    history = await client.get("/evo/studio/versions")
    assert {v["id"] for v in history.json()["versions"]} == {first["id"], child["id"]}
    assert all("responseId" not in v for v in history.json()["versions"])
    other = await client.get("/evo/studio/versions", headers={"X-Session-Id": "other-session-1"})
    assert other.json()["versions"] == []


async def test_background_generation_survives_request_and_can_be_recovered(client):
    started, release = asyncio.Event(), asyncio.Event()

    class SlowRenderer:
        async def generate(self, prompt, refs, aspect, previous_response_id=None):
            started.set()
            await release.wait()
            return GeneratedImage(image_bytes("blue"), "image/png", "test", "response-background")

    client.app.state.services.image_gen = SlowRenderer()
    response = await client.post("/evo/studio/concept?background=1", data={"animal1": "monkey", "animal2": "spider", "brief": "Eight legs"})
    assert response.status_code == 202
    await asyncio.wait_for(started.wait(), 2)
    running = (await client.get("/evo/studio/jobs")).json()["jobs"]
    assert running[0]["id"] == response.json()["id"]
    assert running[0]["status"] == "running"
    assert running[0]["stage"] == "Generating your concept"
    other = await client.get("/evo/studio/jobs", headers={"X-Session-Id": "other-session-1"})
    assert other.json()["jobs"] == []
    release.set()
    await asyncio.wait_for(client.app.state.studio_tasks[response.json()["id"]], 2)
    done = (await client.get("/evo/studio/jobs")).json()["jobs"][0]
    assert done["status"] == "succeeded"
    assert done["result"]["instruction"] == "Eight legs"
    assert (await client.get(done["result"]["imageUrl"])).status_code == 200


async def test_orphaned_local_job_reports_interruption(client):
    # Persist a job that no longer has a running task, as after a server restart.
    request = client.build_request("GET", "/evo/studio/jobs")
    from app.agentapi.caps import visitor_key
    visitor = visitor_key(request.headers["x-session-id"], "127.0.0.1")
    await client.app.state.services.db.put("assets", "studiojob_orphan", {
        "id": "studiojob_orphan", "kind": "studio_job", "visitor": visitor, "status": "running", "createdAt": "2026-01-01"})
    result = (await client.get("/evo/studio/jobs")).json()["jobs"]
    assert result[0]["status"] == "interrupted"


async def test_painted_edit_preserves_unpainted_pixels_and_next_edit_uses_composite(client):
    calls = []

    class Renderer:
        async def generate(self, prompt, refs, aspect, previous_response_id=None):
            calls.append((refs, previous_response_id))
            return GeneratedImage(image_bytes("red" if len(calls) == 1 else "blue"), "image/png", "test", f"response-{len(calls)}")

    client.app.state.services.image_gen = Renderer()
    first = (await client.post("/evo/studio/concept", data={"animal1": "monkey", "animal2": "spider", "brief": "Eight legs"})).json()
    mask = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    for x in range(16):
        for y in range(32):
            mask.putpixel((x, y), (255, 0, 0, 255))
    buf = io.BytesIO(); mask.save(buf, "PNG")
    response = await client.post(f"/evo/studio/versions/{first['id']}/region", data={"instruction": "Change this area"},
                                 files={"mask": ("mask.png", buf.getvalue(), "image/png")})
    assert response.status_code == 201, response.text
    child = response.json()
    merged = (await client.get(child["imageUrl"])).content
    with Image.open(io.BytesIO(merged)) as img:
        assert img.getpixel((30, 16)) == (255, 0, 0)
        assert img.getpixel((3, 16)) == (0, 0, 255)
    assert calls[1][1] == "response-1"
    revised = await client.post(f"/evo/studio/versions/{child['id']}/revise", json={"instruction": "More texture"})
    assert revised.status_code == 201
    assert calls[2] == ([merged], None)


async def test_collaborator_proposes_action_without_running_it(client, monkeypatch):
    from app.agentapi import studio
    calls = []

    class Renderer:
        async def generate(self, prompt, refs, aspect, previous_response_id=None):
            calls.append(prompt)
            return GeneratedImage(image_bytes("red"), "image/png", "test", "response")

    async def fake_plan(settings, brief, selected_instruction, conversation, observation):
        assert brief == "Eight spider legs"
        assert conversation[-1]["content"] == "Make the legs longer"
        return {"message": "Let's try this.", "action": {"type": "revise", "reason": "Your request", "instruction": "Longer legs"}}

    client.app.state.services.image_gen = Renderer()
    monkeypatch.setattr(studio, "plan_collaboration", fake_plan)
    concept = await client.post("/evo/studio/concept", data={"animal1": "monkey", "animal2": "spider", "brief": "Eight spider legs"})
    version = concept.json()
    answer = await client.post(f"/evo/studio/versions/{version['id']}/collaborate", json={"messages": [{"role": "user", "content": "Make the legs longer"}]})
    assert answer.status_code == 200
    assert answer.json()["action"]["instruction"] == "Longer legs"
    assert len(calls) == 1
    denied = await client.post(f"/evo/studio/versions/{version['id']}/collaborate", json={"messages": [{"role": "user", "content": "Change it"}]}, headers={"X-Session-Id": "other-session-1"})
    assert denied.status_code == 404


async def test_review_is_saved_and_given_to_collaborator_for_that_version(client, monkeypatch):
    from app.agentapi import studio
    captured = []

    class Renderer:
        async def generate(self, prompt, refs, aspect, previous_response_id=None):
            return GeneratedImage(image_bytes("red"), "image/png", "test", "response")

    async def fake_review(settings, image, brief, change):
        return {"observation": "A second spider face is visible", "suggestions": "Consider removing it"}

    async def fake_plan(settings, brief, selected_instruction, conversation, observation):
        captured.append(observation)
        return {"message": "Consider removing it.", "action": None}

    client.app.state.services.image_gen = Renderer()
    monkeypatch.setattr(studio, "review_image", fake_review)
    monkeypatch.setattr(studio, "plan_collaboration", fake_plan)
    version = (await client.post("/evo/studio/concept", data={"animal1": "monkey", "animal2": "spider", "brief": "Eight legs"})).json()
    before = await client.get(f"/evo/studio/versions/{version['id']}/review")
    assert before.json()["review"] is None
    assert (await client.post(f"/evo/studio/versions/{version['id']}/review")).status_code == 200
    assert (await client.get(f"/evo/studio/versions/{version['id']}/review")).json()["review"]["observation"] == "A second spider face is visible"
    result = await client.post(f"/evo/studio/versions/{version['id']}/collaborate", json={"messages": [{"role": "user", "content": "What next?"}]})
    assert result.status_code == 200
    assert captured == ["A second spider face is visible"]
    denied = await client.get(f"/evo/studio/versions/{version['id']}/review", headers={"X-Session-Id": "other-session-1"})
    assert denied.status_code == 404


async def test_studio_has_separate_visible_action_limit(client):
    client.app.state.studio_caps.settings.evo_visitor_daily_runs = 1
    initial = (await client.get("/evo/studio/limits")).json()
    assert initial["used"] == 0 and initial["limit"] == 1
    first = await client.post("/evo/studio/concept", data={"animal1": "monkey", "animal2": "spider", "brief": "Eight legs"})
    assert first.status_code == 201
    limits = (await client.get("/evo/studio/limits")).json()
    assert limits["used"] == 1
    blocked = await client.post(f"/evo/studio/versions/{first.json()['id']}/review")
    assert blocked.status_code == 429
    assert "studio action limit" in blocked.json()["error"]["message"]
    from app.agentapi.caps import visitor_key
    visitor = visitor_key("test-session-1", "127.0.0.1")
    assert await client.app.state.agent.caps.used(visitor) == (0, 0)


async def test_final_mark_and_original_image_download_are_reversible_and_session_scoped(client):
    class Renderer:
        async def generate(self, prompt, refs, aspect, previous_response_id=None):
            return GeneratedImage(image_bytes("blue"), "image/png", "test", "response")

    client.app.state.services.image_gen = Renderer()
    version = (await client.post("/evo/studio/concept", data={"animal1": "monkey", "animal2": "spider", "brief": "Eight legs"})).json()
    url = f"/evo/studio/versions/{version['id']}"
    assert (await client.put(url + "/final", json={"isFinal": True})).status_code == 200
    assert (await client.get("/evo/studio/versions")).json()["versions"][0]["isFinal"] is True
    download = await client.get(url + "/download")
    assert download.status_code == 200 and download.content == image_bytes("blue")
    assert download.headers["content-type"] == "image/png"
    assert "attachment;" in download.headers["content-disposition"]
    assert (await client.get(url + "/download", headers={"X-Session-Id": "other-session-1"})).status_code == 404
    assert (await client.put(url + "/final", json={"isFinal": False})).status_code == 200
    assert (await client.get("/evo/studio/versions")).json()["versions"][0]["isFinal"] is False
