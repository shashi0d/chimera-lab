"""Multimodal model thinks, then creates. Direct Meta API only; no Chimera Lab code, prompts or data."""
import base64, json, os, random, time
from pathlib import Path
import openai

ROOT = Path("/home/user/chimera-lab")
OUT = ROOT / "docs/live/direct2"
KEY = os.environ["META_API_KEY"]
c = openai.OpenAI(base_url="https://api.meta.ai/v1", api_key=KEY, timeout=240, max_retries=0)
photos = sorted((ROOT / "backend/tests/fixtures/live").glob("*.webp"))
pick = random.sample(photos, 2)
print("picked:", [p.name for p in pick])

def img(p):
    return {"type": "input_image", "image_url": "data:image/webp;base64," + base64.b64encode(p.read_bytes()).decode()}

def strip(o):
    if isinstance(o, dict):
        return {k: (f"<base64 {len(v)} chars>" if k == "result" and isinstance(v, str) and len(v) > 200 else strip(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [strip(x) for x in o]
    return o

def save(name, payload):
    blob = json.dumps(payload)
    assert KEY not in blob and "Bearer" not in blob
    (OUT / name).write_text(json.dumps(strip(payload), indent=2))

def images_of(d, stem):
    n = 0
    for it in d.get("output", []) or []:
        if it.get("type") == "image_generation_call" and it.get("result"):
            n += 1
            (OUT / f"{stem}{'' if n == 1 else n}.webp").write_bytes(base64.b64decode(it["result"]))
    return n

def show(d):
    for it in d.get("output", []) or []:
        if it["type"] == "reasoning":
            print("[reasoning summary]", " ".join(s["text"] for s in it.get("summary") or []))
        elif it["type"] == "message":
            print("[text]", " ".join(p.get("text", "") for p in it["content"]))
        else:
            print("[", it["type"], "]")
    print("usage", d.get("usage"))

THINK = ("You are given two animal photos. Think it through step by step, out loud, and show all your reasoning: "
         "identify each animal and its defining features, decide which features to take from each and why, choose a "
         "body plan that could plausibly stand and move, then choose pose, setting, lighting and style. "
         "Then create one image of the resulting chimera.")
meta = {"inputs": [p.name for p in pick]}

# Attempt A: one multimodal model, thinking + image tool in a single call.
t = time.time()
try:
    a = c.responses.create(model="muse-spark-1.3", tools=[{"type": "image_generation"}],
                           input=[{"role": "user", "content": [{"type": "input_text", "text": THINK}, img(pick[0]), img(pick[1])]}]).model_dump()
    print("== A: muse-spark-1.3 + image_generation tool, %.1fs" % (time.time() - t)); show(a)
    save("A_spark_with_image_tool.json", {**meta, "prompt": THINK, "response": a})
    got = images_of(a, "A_chimera")
except Exception as e:
    print("== A failed:", type(e).__name__, str(e)[:300]); got = 0
    (OUT / "A_spark_with_image_tool.json").write_text(json.dumps({**meta, "prompt": THINK, "error": f"{type(e).__name__}: {str(e)[:500]}"}, indent=2))

if got == 0:
    # Attempt B: Spark sees both photos and thinks in text, ending with a render brief; Muse Image renders it.
    PLAN = THINK.replace("Then create one image of the resulting chimera.",
                         "You cannot draw, so finish with a section headed IMAGE PROMPT: one paragraph an image model can render directly.")
    t = time.time()
    b1 = c.responses.create(model="muse-spark-1.3", input=[{"role": "user", "content": [{"type": "input_text", "text": PLAN}, img(pick[0]), img(pick[1])]}]).model_dump()
    print("== B1: muse-spark-1.3 thinking, %.1fs" % (time.time() - t)); show(b1)
    save("B1_spark_thinking.json", {**meta, "prompt": PLAN, "response": b1})
    text = " ".join(p.get("text", "") for it in b1["output"] if it["type"] == "message" for p in it["content"])
    brief = text.split("IMAGE PROMPT", 1)[-1].lstrip(":* \n") if "IMAGE PROMPT" in text else text
    t = time.time()
    b2 = c.responses.create(model="muse-image-1.0", input=[{"role": "user", "content": [{"type": "input_text", "text": brief}, img(pick[0]), img(pick[1])]}]).model_dump()
    print("== B2: muse-image-1.0 render, %.1fs" % (time.time() - t)); show(b2)
    save("B2_image_render.json", {**meta, "prompt": brief, "response": b2})
    images_of(b2, "B_chimera")
(OUT / "inputs.json").write_text(json.dumps(meta))
print("done")
