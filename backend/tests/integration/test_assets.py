"""TASKSHEET 7.1 input cases, server side."""

import io

import pytest
from PIL import Image
from tests.conftest import EDGE, IMAGES, upload


async def test_upload_jpeg_returns_metadata(client):
    r = await upload(client, IMAGES / "lion.jpg")
    assert r.status_code == 201
    body = r.json()
    assert body["width"] == 900 and body["height"] == 900
    assert len(body["sha256"]) == 64 and body["url"].endswith("/content")
    content = await client.get(body["url"])
    assert content.status_code == 200 and content.headers["content-type"] == "image/jpeg"
    meta = await client.get(f"/assets/{body['assetId']}")
    assert meta.json()["assetId"] == body["assetId"]


@pytest.mark.parametrize("name", ["anim.gif", "doc.pdf", "vector.svg"])
async def test_unsupported_types_rejected_by_content_not_extension(client, name):
    r = await upload(client, EDGE / name, name="looks_fine.jpg")
    assert r.status_code == 415
    err = r.json()["error"]
    assert err["code"] == "UNSUPPORTED_FILE" and err["retryable"] is False
    assert "JPEG" in err["message"]


async def test_heic_converted_to_jpeg(client):
    path = EDGE / "flamingo.heic"
    if not path.exists():
        pytest.skip("HEIC encoder unavailable")
    r = await upload(client, path)
    assert r.status_code == 201
    content = await client.get(r.json()["url"])
    assert content.content[:3] == b"\xff\xd8\xff"


async def test_corrupt_image(client):
    r = await upload(client, EDGE / "corrupt.jpg")
    assert r.status_code == 422 and r.json()["error"]["code"] == "IMAGE_CORRUPT"


async def test_too_small(client):
    r = await upload(client, EDGE / "too_small.jpg")
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "IMAGE_TOO_SMALL" and err["details"]["minShortSide"] == 256


async def test_too_large_enforced_server_side(tmp_path):
    import httpx
    from app.main import create_app
    from tests.conftest import make_settings

    app = create_app(make_settings(tmp_path, max_upload_bytes=50_000))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await upload(c, IMAGES / "tiger.jpg")  # ~55 KB
    assert r.status_code == 413 and r.json()["error"]["code"] == "FILE_TOO_LARGE"


async def test_huge_dimensions_downscaled(client):
    r = await upload(client, EDGE / "huge_3000.png")
    assert r.status_code == 201
    assert max(r.json()["width"], r.json()["height"]) == 2048


async def test_exif_orientation_applied_and_metadata_stripped(client):
    r = await upload(client, EDGE / "exif_rotated_gps.jpg")
    body = r.json()
    # 600x400 with orientation 6 displays as 400x600
    assert (body["width"], body["height"]) == (400, 600)
    content = (await client.get(body["url"])).content
    with Image.open(io.BytesIO(content)) as im:
        exif = im.getexif()
        assert 0x8825 not in exif and 0x0112 not in exif


async def test_same_image_twice_has_same_sha(client):
    a = (await upload(client, IMAGES / "lion.jpg")).json()
    b = (await upload(client, IMAGES / "lion.jpg", name="copy.jpg")).json()
    assert a["sha256"] == b["sha256"] and a["assetId"] != b["assetId"]


async def test_unknown_asset_404_envelope(client):
    r = await client.get("/assets/ast_missing")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
