# Live fixture images

**These are AI-generated images, not real photographs.** Each was made once with Meta's `muse-image-1.0` (text-to-image, Responses API) by `scripts/live_fixtures.py` on 2026-10-30, and is reused by the live tests (`CHIMERA_LIVE=1`). Tests never regenerate them.

| File | Prompt subject |
|---|---|
| `lion.webp` | an adult male African lion with a full mane, standing in dry savanna grass |
| `tiger.webp` | an adult Bengal tiger walking along a forest edge |
| `horse.webp` | a bay domestic horse standing in a green paddock, full body side view |
| `donkey.webp` | a grey domestic donkey standing on a dirt path, full body side view |
| `bald_eagle.webp` | a bald eagle perched on a branch, wings folded, full body |
| `common_octopus.webp` | a common octopus (Octopus vulgaris) on a rocky sea floor, arms spread |

Each prompt wraps the subject in: "A photorealistic wildlife photograph of {subject}. Natural light, sharp focus, the whole animal clearly visible and centred, plain uncluttered background, no people, no text, no watermark."

All six are 1600×1600 WebP. Response ids, latency and tokens are in `docs/LIVE_LOG.md`.
