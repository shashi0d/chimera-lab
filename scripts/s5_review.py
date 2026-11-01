"""S5 part 5: the owner review sheet, one self-contained HTML file (no calls).

    .venv/Scripts/python.exe scripts/s5_review.py

Per benchmark case: the agent's and the fixed pipeline's final images side by side, labels hidden and the order
randomized (seeded; the key is saved separately in benchmark/s5_review_key.json), each with its anatomy map overlay
and rating fields (works / partly / fails, plus a note). Ratings autosave in the browser and export as JSON.
Images are embedded as 640 px JPEGs so the file stays small.
"""

from __future__ import annotations

import base64
import html
import io
import json
import random
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
S5 = ROOT / "docs" / "evolution" / "live" / "s5"
BENCH = ROOT / "docs" / "evolution" / "benchmark"
SEED = 2026


def jpeg(path: Path, width: int = 640) -> str:
    with Image.open(path) as im:
        im = im.convert("RGB")
        h = round(im.height * width / im.width)
        out = io.BytesIO()
        im.resize((width, h), Image.LANCZOS).save(out, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


def main() -> None:
    cases = json.loads((ROOT / "data" / "evo_benchmark.json").read_text(encoding="utf-8"))["cases"]
    rng = random.Random(SEED)
    key, blocks = {}, []
    for c in cases:
        order = ["agent", "fixed"]
        rng.shuffle(order)
        key[c["id"]] = {"A": order[0], "B": order[1]}
        cards = []
        for slot, kind in zip(("A", "B"), order, strict=True):
            d = S5 / c["id"] / kind
            cid = f"{c['id']}-{slot}"
            radios = "".join(
                f'<label class="opt"><input type="radio" name="{cid}" value="{v}"><span>{v}</span></label>'
                for v in ("works", "partly", "fails"))
            cards.append(f"""
      <figure class="card" data-id="{cid}">
        <figcaption>Image {slot}</figcaption>
        <img class="main" src="{jpeg(d / 'image.webp')}" alt="Case {c['id']} image {slot}">
        <details><summary>Anatomy map</summary><img src="{jpeg(d / 'anatomy_map.png')}" alt="Anatomy map {slot}"></details>
        <div class="rate" role="radiogroup" aria-label="Rating for image {slot}">{radios}</div>
        <textarea placeholder="Note (optional)" aria-label="Note for image {slot}"></textarea>
      </figure>""")
        route = f" · {html.escape(c['route'])}" if c.get("route") else ""
        blocks.append(f"""
    <section class="case" id="{c['id']}">
      <h2><span class="id">{c['id']}</span> {html.escape(c['sire'])} × {html.escape(c['dam'])}
        <span class="mode">{html.escape(c['mode'])}{route}</span></h2>
      <div class="pair">{''.join(cards)}</div>
    </section>""")
    page = TEMPLATE.replace("{{BLOCKS}}", "".join(blocks)).replace("{{N}}", str(len(cases)))
    BENCH.mkdir(parents=True, exist_ok=True)
    (BENCH / "s5_review.html").write_text(page, encoding="utf-8")
    (BENCH / "s5_review_key.json").write_text(json.dumps({"seed": SEED, "note": "which system made image A and B "
                                                          "per case; open only after rating", "key": key}, indent=1),
                                              encoding="utf-8")
    print("wrote", BENCH / "s5_review.html", round((BENCH / "s5_review.html").stat().st_size / 2**20, 2), "MB")


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>S5 Owner Review</title>
<style>
:root { --bg: #f6f4ef; --fg: #1d1b18; --muted: #6b665d; --card: #ffffff; --line: #ddd8cc; --accent: #2f6f8f;
        --works: #2e7d4f; --partly: #b7791f; --fails: #b23a3a; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg: #171614; --fg: #ece8df; --muted: #a39d92;
        --card: #22201d; --line: #3a3732; --accent: #7fb8d4; } }
:root[data-theme="dark"] { --bg: #171614; --fg: #ece8df; --muted: #a39d92; --card: #22201d; --line: #3a3732;
        --accent: #7fb8d4; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
header { position: sticky; top: 0; z-index: 2; background: var(--bg); border-bottom: 1px solid var(--line);
         padding: 12px 16px; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between; }
header h1 { font-size: 18px; margin: 0; }
header p { margin: 0; color: var(--muted); font-size: 13px; max-width: 60ch; }
.tools { display: flex; gap: 8px; align-items: center; }
.progress { color: var(--muted); font-size: 13px; }
button { font: inherit; padding: 8px 14px; border-radius: 8px; border: 1px solid var(--accent); background: var(--accent);
         color: #fff; cursor: pointer; }
main { max-width: 1100px; margin: 0 auto; padding: 16px; }
.case { margin: 0 0 28px; }
.case h2 { font-size: 17px; margin: 0 0 10px; }
.id { color: var(--muted); font-variant-numeric: tabular-nums; margin-right: 4px; }
.mode { font-weight: 400; color: var(--muted); font-size: 14px; margin-left: 6px; }
.pair { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }
.card { margin: 0; background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px; }
.card figcaption { font-weight: 600; margin-bottom: 8px; }
.card img { width: 100%; height: auto; display: block; border-radius: 8px; }
details { margin: 8px 0; }
summary { cursor: pointer; color: var(--accent); font-size: 14px; }
details img { margin-top: 6px; }
.rate { display: flex; gap: 6px; margin: 10px 0 8px; flex-wrap: wrap; }
.opt { position: relative; }
.opt input { position: absolute; opacity: 0; }
.opt span { display: inline-block; padding: 6px 14px; border: 1px solid var(--line); border-radius: 999px; cursor: pointer; }
.opt input:focus-visible + span { outline: 2px solid var(--accent); outline-offset: 2px; }
.opt input[value="works"]:checked + span { background: var(--works); border-color: var(--works); color: #fff; }
.opt input[value="partly"]:checked + span { background: var(--partly); border-color: var(--partly); color: #fff; }
.opt input[value="fails"]:checked + span { background: var(--fails); border-color: var(--fails); color: #fff; }
textarea { width: 100%; min-height: 56px; font: inherit; color: var(--fg); background: var(--bg); border: 1px solid var(--line);
           border-radius: 8px; padding: 8px; resize: vertical; }
</style>
</head>
<body>
<header>
  <div>
    <h1>S5 benchmark: owner review</h1>
    <p>{{N}} cases. Two final images per case, made by two systems; which is which is hidden and the order is random.
       Rate each image works / partly / fails, add a note if useful, then export. Ratings are kept in this browser.</p>
  </div>
  <div class="tools"><span class="progress" id="progress"></span><button id="export" type="button">Export JSON</button></div>
</header>
<main>{{BLOCKS}}
</main>
<script>
(function () {
  var KEY = "s5_review_ratings_v1";
  var cards = Array.prototype.slice.call(document.querySelectorAll(".card"));
  function load() { try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { return {}; } }
  function save(d) { try { localStorage.setItem(KEY, JSON.stringify(d)); } catch (e) {} }
  function collect() {
    var out = {};
    cards.forEach(function (c) {
      var r = c.querySelector("input:checked");
      out[c.dataset.id] = { rating: r ? r.value : null, note: c.querySelector("textarea").value };
    });
    return out;
  }
  function progress() {
    var d = collect(), n = 0;
    Object.keys(d).forEach(function (k) { if (d[k].rating) n++; });
    document.getElementById("progress").textContent = n + " / " + cards.length + " rated";
  }
  var saved = load();
  cards.forEach(function (c) {
    var s = saved[c.dataset.id];
    if (s) {
      if (s.rating) { var i = c.querySelector('input[value="' + s.rating + '"]'); if (i) i.checked = true; }
      c.querySelector("textarea").value = s.note || "";
    }
    c.addEventListener("change", function () { save(collect()); progress(); });
    c.querySelector("textarea").addEventListener("input", function () { save(collect()); });
  });
  progress();
  document.getElementById("export").addEventListener("click", function () {
    var blob = new Blob([JSON.stringify({ sheet: "s5_review", exported: new Date().toISOString(), ratings: collect() }, null, 1)],
                        { type: "application/json" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "s5_review_ratings.json";
    document.body.appendChild(a); a.click(); a.remove();
  });
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
