from tests.conftest import IMAGES


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_fixture_images_exist():
    assert (IMAGES / "lion.jpg").exists()
