"""Same two photos, only the word changes: 'chimera' vs 'hybrid'. Direct Meta API, no Chimera Lab code."""
import base64, json, os, time
from pathlib import Path
import openai

ROOT = Path("/home/user/chimera-lab")
OUT = ROOT / "docs/live/direct3"
KEY = os.environ["META_API_KEY"]
c = openai.OpenAI(base_url="https://api.meta.ai/v1", api_key=KEY, timeout=240, max_retries=0)
LIVE = ROOT / "backend/tests/fixtures/live"
pick = [LIVE / "bald_eagle.webp", LIVE / "common_octopus.webp"]  # same pair as direct2

def img(p):
    return {"type": "input_image", "image_url": "data:image/webp;base64," + base64.b64encode(p.read_bytes()).decode()}

def strip(o):
    if isinstance(o, dict):
        return {k: (f"<base64 {len(v)} chars>" if k == "result" and isinstance(v, str) and len(v) > 200 else strip(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [strip(x) for x in o]
    return o

def save(name, payload):
    assert KEY not in json.dumps(payload)
    (OUT / name).write_text(json.dumps(strip(payload), indent=2))

def run(model, text, stem):
    t = time.time()
    d = c.responses.create(model=model, input=[{"role": "user", "content": [{"type": "input_text", "text": text}, img(pick[0]), img(pick[1])]}]).model_dump()
    print(f"== {stem} ({model}, {time.time() - t:.1f}s) usage {d.get('usage', {}).get('total_tokens')}")
    for it in d.get("output", []) or []:
        if it["type"] == "reasoning":
            print("[reasoning summary]", " ".join(s["text"] for s in it.get("summary") or []))
        elif it["type"] == "message":
            txt = " ".join(p.get("text", "") for p in it["content"])
            if txt: print("[text]", txt)
        elif it["type"] == "image_generation_call":
            if it.get("result"):
                (OUT / f"{stem}.webp").write_bytes(base64.b64decode(it["result"])); print("[image saved]")
            else:
                print("[image call", it.get("status"), "]")
    save(f"{stem}.json", {"inputs": [p.name for p in pick], "prompt": text, "response": d})
    return d

d = json.loads((OUT / "spark_hybrid_thinking.json").read_text())["response"]
text = " ".join(p.get("text", "") for it in d["output"] if it["type"] == "message" for p in it["content"])
brief = text.split("IMAGE PROMPT", 1)[-1].lstrip(":* \n") if "IMAGE PROMPT" in text else text
print("BRIEF:", brief)
run("muse-image-1.0", brief, "twostep_hybrid")
