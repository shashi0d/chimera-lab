import json, os, sys
from pathlib import Path
import openai
OUT = Path("/home/user/chimera-lab/docs/live/direct")
first = json.loads((OUT / "1_image_response.json").read_text())["response"]["id"]
c = openai.OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["META_API_KEY"], timeout=120, max_retries=0)
Q = ("Do NOT generate an image. Reply in plain text only. Explain the thought process behind the chimera you just created: "
     "how you read each input image, which features you took from each animal and why, how you chose body plan, pose, "
     "setting and style, and the internal description or prompt you used to render it.")
results = {}
for label, model in [("3_text_only_muse_image", "muse-image-1.0"), ("4_muse_spark_followup", "muse-spark-1.3")]:
    try:
        r = c.responses.create(model=model, previous_response_id=first, input=[{"role": "user", "content": [{"type": "input_text", "text": Q}]}]).model_dump()
    except Exception as e:
        r = {"error": f"{type(e).__name__}: {str(e)[:400]}"}
    for it in r.get("output", []) or []:
        if isinstance(it, dict) and it.get("result") and len(it["result"]) > 200:
            it["result"] = f"<base64 {len(it['result'])} chars>"
    blob = json.dumps(r); assert os.environ["META_API_KEY"] not in blob
    (OUT / f"{label}.json").write_text(json.dumps({"model": model, "question": Q, "response": r}, indent=2))
    print("=====", label)
    if "error" in r: print(r["error"]); continue
    for it in r["output"]:
        if it["type"] == "reasoning": print("[reasoning summary]", " ".join(s["text"] for s in it.get("summary") or []))
        elif it["type"] == "message": print("[text]", " ".join(p.get("text","") for p in it["content"]) or "(empty)")
        else: print("[", it["type"], "]")
    print("usage", r.get("usage"))
