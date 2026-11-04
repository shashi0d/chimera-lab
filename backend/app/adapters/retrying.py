"""Muse Image calls with the shared retry policy (app.retry): a per-attempt timeout and backoff on rate limits,
timeouts and retryable upstream errors."""

from __future__ import annotations

from app.adapters.base import GeneratedImage, ImageGenAdapter
from app.config import Settings
from app.retry import call_with_retry


class RetryingImageGen:
    def __init__(self, inner: ImageGenAdapter, settings: Settings) -> None:
        self.inner = inner
        self.settings = settings
        self.model_id = inner.model_id

    async def generate(self, prompt: str, reference_images: list[bytes], aspect: str | None,
                       previous_response_id: str | None = None) -> GeneratedImage:
        s = self.settings
        return await call_with_retry(
            lambda: self.inner.generate(prompt, reference_images, aspect, previous_response_id),
            timeout=s.generate_timeout_seconds, base_delay=s.retry_base_seconds, max_attempts=s.retry_max_attempts)
