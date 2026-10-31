# Input order reversed: octopus first, eagle second

`direct3` (and `direct2` for two-step "chimera") reran with only the image order swapped. Prompts are word for word the same. Direct Meta API calls with the OpenAI SDK only, no Chimera Lab code. `comparison_order.png`: left column eagle first, right column octopus first.

| Run | Eagle first | Octopus first |
|---|---|---|
| One-shot "chimera" | eagle on a branch, octopus arms below (15k tokens) | **octopus on the seafloor**, eagle head and wings on top (26k) |
| One-shot "hybrid" | same as above, more blended (38k) | **octopus on the seafloor**, eagle head and chest (15k) |
| Two-step "chimera" | eagle torso, 8 arms, no bird legs | eagle torso, **2 taloned eagle legs plus 6 arms**, wings with sucker texture |
| Two-step "hybrid" | eagle torso, 8 arms, mantle under the wings | eagle torso, 8 arms, white tail feathers |

**Observations** (one run each):

- **Muse Image alone anchors on the first image.** The first photo supplies the base body, scene and camera: the eagle's foggy branch, or the octopus's seafloor shot from above. The second photo becomes the attached features. Input order decides which animal is the "body".
- **Spark's plan is order-robust in structure.** In both orders it picked an eagle-based chassis, reasoning that an octopus body "can't stand in air". It also chose a perched pose over a tidepool both times. Order changed only the details: with octopus first, the "chimera" plan kept the eagle's legs and talons and used 6 arms instead of 8.
- One Muse Image reasoning summary mentions "the user's video", which is wrong; no video was involved.

Spend: 4 images and 2 Spark calls.
