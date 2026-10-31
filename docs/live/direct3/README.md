# "Chimera" vs "hybrid": same photos, one word changed

The same pair as `direct2` (bald eagle + common octopus). Direct Meta API calls with the OpenAI SDK only, no Chimera Lab code. `comparison.png` shows all four images.

| Run | Prompt word | Model(s) | Tokens | Image |
|---|---|---|---|---|
| One-shot | chimera | muse-image-1.0 | 15,087 | `oneshot_chimera.webp` |
| One-shot | hybrid | muse-image-1.0 | 37,962 | `oneshot_hybrid.webp` |
| Two-step | chimera | muse-spark-1.3 → muse-image-1.0 | 9,317 + 29,057 | `../direct2/B_chimera.webp` |
| Two-step | hybrid | muse-spark-1.3 → muse-image-1.0 | 9,093 + 28,877 | `twostep_hybrid.webp` |

**Observations** (one run each, so treat these as indications, not findings):

- **Same design either way.** Both words produced the same concept: an eagle head and chest on eight octopus arms gripping a mossy branch. Neither model read "hybrid" as a real biological cross (an intermediate animal, or a "these can't interbreed" response).
- **"Hybrid" pushed for more blending:**
  - One-shot "hybrid" took 2.5× the tokens. Its reasoning shows it generated a first version, then "another blended version… pushes the eagle-octopus mix further". In the result, octopus skin starts higher on the chest.
  - Spark's "hybrid" plan aimed for a "50/50 hybrid": wings with webbed membrane and suckers on the trailing edges, and an octopus mantle hump on the back. The render is more fused (mantle visible under the wings) and less splayed than the "chimera" render.
- **One-shot output is close to an edit of the eagle photo:** same branch, same fog, same pose, whichever word is used.

The two-step render first failed on a proxy connection reset (`ws_closed_mid_exchange`). `retry_render.py` re-rendered from Spark's saved brief. Spend: 3 images and 1 Spark call (plus the dropped request).
