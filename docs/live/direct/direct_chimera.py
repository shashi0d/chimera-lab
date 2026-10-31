"""Direct Meta API call: no Chimera Lab code, prompts or data. Two random photos + one plain prompt."""
import base64, json, os, random, sys, time
from pathlib import Path
import openai

ROOT = Path("/home/user/chimera-lab")
OUT = ROOT / "docs/live/direct"
photos = sorted((ROOT / "backend/tests/fixtures/live").glob("*.webp"))
pick = random.sample(photos, 2)
print("picked:", [p.name for p in pick])

client = openai.OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["META_API_KEY"], timeout=180, max_retries=0)

def img(p):
    return {"type": "input_image", "image_url": "data:image/webp;base64," + base64.b64encode(p.read_bytes()).decode()}

PROMPT = "Create a chimera: one new creature that combines the animal in the first image with the animal in the second image."
t = time.time()
r1 = client.responses.create(model="muse-image-1.0", input=[{"role": "user", "content": [{"type": "input_text", "text": PROMPT}, img(pick[0]), img(pick[1])]}])
d1 = r1.model_dump()
print("image call: %.1fs, id %s" % (time.time() - t, d1.get("id")))

def strip(o):
    if isinstance(o, dict):
        return {k: (f"<base64 {len(v)} chars>" if k == "result" and isinstance(v, str) and len(v) > 200 else strip(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [strip(x) for x in o]
    return o

for item in d1.get("output", []):
    if item.get("type") == "image_generation_call" and item.get("result"):
        (OUT / "chimera.webp").write_bytes(base64.b64decode(item["result"]))
        print("saved image")
(OUT / "1_image_response.json").write_text(json.dumps({"prompt": PROMPT, "inputs": [p.name for p in pick], "response": strip(d1)}, indent=2))

ASK = ("You just created that chimera. Please share your thought process in detail: how you read each input image, "
       "which features you took from each animal and why, how you decided the body plan, pose, setting and style, "
       "and the exact prompt or internal description you used to generate the image.")
t = time.time()
r2 = client.responses.create(model="muse-image-1.0", previous_response_id=d1["id"], input=[{"role": "user", "content": [{"type": "input_text", "text": ASK}]}])
d2 = r2.model_dump()
print("follow-up: %.1fs" % (time.time() - t))
(OUT / "2_thought_process_response.json").write_text(json.dumps({"question": ASK, "response": strip(d2)}, indent=2))
for item in d2.get("output", []):
    if item.get("type") == "image_generation_call" and item.get("result"):
        (OUT / "followup_image.webp").write_bytes(base64.b64decode(item["result"]))
        print("NOTE: follow-up also produced an image")
blob = json.dumps(d1) + json.dumps(d2)
assert os.environ["META_API_KEY"] not in blob and "Bearer" not in blob
print("ok")
