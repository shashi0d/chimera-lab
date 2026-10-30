from tests.conftest import fusion_graph


async def test_graph_round_trip(client):
    g = fusion_graph("a", "b", graph_id="graph-1")
    r = await client.put("/graphs/graph-1", json=g)
    assert r.status_code == 200
    loaded = (await client.get("/graphs/graph-1")).json()
    assert loaded["graphId"] == "graph-1" and len(loaded["nodes"]) == 3
    assert loaded["edges"][0]["sourcePort"] == "out"


async def test_graph_is_scoped_to_session(client):
    await client.put("/graphs/graph-2", json=fusion_graph("a", "b", graph_id="graph-2"))
    r = await client.get("/graphs/graph-2", headers={"X-Session-Id": "someone-else-123"})
    assert r.status_code == 404


async def test_graph_id_mismatch(client):
    r = await client.put("/graphs/other", json=fusion_graph("a", "b", graph_id="graph-3"))
    assert r.status_code == 422


async def test_validation_errors_use_envelope(client):
    r = await client.post("/runs", json={"nope": 1}, headers={"Idempotency-Key": "v"})
    body = r.json()
    assert r.status_code == 422 and body["error"]["code"] == "VALIDATION_FAILED"


async def test_cors_allowlist(client):
    ok = await client.options("/health", headers={"Origin": "http://localhost:5173",
                                                  "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = await client.options("/health", headers={"Origin": "https://evil.example",
                                                   "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


async def test_unknown_route_envelope(client):
    r = await client.get("/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
