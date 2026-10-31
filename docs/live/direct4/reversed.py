"""direct3 reversed (octopus first). Same two photos, only the word changes: 'chimera' vs 'hybrid'. Direct Meta API, no Chimera Lab code."""
import base64, json, os, time
from pathlib import Path
import openai

ROOT = Path("/home/user/chimera-lab")
OUT = ROOT / "docs/live/direct4"
KEY = os.environ["META_API_KEY"]
c = openai.OpenAI(base_url="https://api.meta.ai/v1", api_key=KEY, timeout=240, max_retries=0)
LIVE = ROOT / "backend/tests/fixtures/live"
pick = [LIVE / "common_octopus.webp", LIVE / "bald_eagle.webp"]  # REVERSED: octopus first, eagle second

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

# 1) One-shot, identical prompt except the word.
for word in ["chimera", "hybrid"]:
    run("muse-image-1.0", f"Create a {word}: one new creature that combines the animal in the first image with the animal in the second image.", f"oneshot_{word}")

# 2) Two-step for both words; PLAN is the direct2/direct3 text with only the word swapped.
BASE = ("You are given two animal photos. Think it through step by step, out loud, and show all your reasoning: "
        "identify each animal and its defining features, decide which features to take from each and why, choose a "
        "body plan that could plausibly stand and move, then choose pose, setting, lighting and style{suffix}. "
        "You cannot draw, so finish with a section headed IMAGE PROMPT: one paragraph an image model can render directly.")
for word, suffix in [("chimera", ""), ("hybrid", " for a hybrid of the two")]:
    for attempt in range(2):
        try:
            d = run("muse-spark-1.3", BASE.format(suffix=suffix), f"spark_{word}_thinking")
            text = " ".join(p.get("text", "") for it in d["output"] if it["type"] == "message" for p in it["content"])
            brief = text.split("IMAGE PROMPT", 1)[-1].lstrip(":* \n") if "IMAGE PROMPT" in text else text
            run("muse-image-1.0", brief, f"twostep_{word}")
            break
        except openai.APIConnectionError as e:
            print("connection dropped, retrying once:", e)
print("done")
