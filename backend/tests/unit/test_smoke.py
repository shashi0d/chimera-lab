from tests.conftest import IMAGES


async def test_health_reports_mock_mode(client):
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "mock"
    assert body["status"] == "ok"
    assert body["dataSource"] == "full"  # fixture path given explicitly and exists


def test_fixture_images_exist():
    assert (IMAGES / "lion.jpg").exists()
