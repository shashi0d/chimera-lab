# Direct Meta call: no Chimera Lab logic

The user asked to see the Meta models' own behaviour, with none of the app's pipeline, prompts or data. `direct_chimera.py` and `ask_again.py` call `https://api.meta.ai/v1` with only the OpenAI SDK and the API key. The scripts import nothing from `backend/`.

1. **Image call** (`1_image_response.json`, `chimera.webp`):
   - Two of the six live photos were picked at random: **tiger** and **horse**.
   - Prompt, verbatim: *"Create a chimera: one new creature that combines the animal in the first image with the animal in the second image."*
   - Model `muse-image-1.0` (Responses API), 14.7 s, 15,236 tokens (217 reasoning).
   - Output: a reasoning summary, an empty text message, and one image (1920×1280).
2. **"Share your thought process" to the same model** (`2_thought_process_response.json`):
   - Sent via `previous_response_id`.
   - Muse Image answered with another image (`followup_image.webp`, the same creature at 1248×832) and no text.
3. **Same question with "Do NOT generate an image"** (`3_text_only_muse_image.json`):
   - Its reasoning says it is "drafting an explanation", but it still returned only an image (not saved) and empty text.
4. **Same question to `muse-spark-1.3`** (`4_muse_spark_followup.json`):
   - Sent on the same conversation (`previous_response_id`).
   - Returned a full text explanation (1,968 output tokens, 1,321 reasoning).
   - Caveat: this is the text model explaining the earlier turn, not Muse Image reporting its own internal state.

Spend: 3 image generations, 1 Spark call. The API key is absent from every saved file (checked by both scripts).
