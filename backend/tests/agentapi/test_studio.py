from __future__ import annotations

import io

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
