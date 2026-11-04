"""Domain exception that maps 1:1 onto the API error envelope."""

from __future__ import annotations

import uuid
from typing import Any

from app.models.schemas import ApiError, ErrorCode

RETRYABLE = {ErrorCode.RATE_LIMITED, ErrorCode.UPSTREAM_TIMEOUT, ErrorCode.UPSTREAM_ERROR}

HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_FAILED: 422,
    ErrorCode.UNSUPPORTED_FILE: 415,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.IMAGE_CORRUPT: 422,
    ErrorCode.NOT_AN_ANIMAL: 422,
    ErrorCode.HUMAN_DETECTED: 422,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.UPSTREAM_TIMEOUT: 504,
    ErrorCode.UPSTREAM_ERROR: 502,
    ErrorCode.MODEL_REFUSED: 422,
    ErrorCode.BUDGET_EXCEEDED: 402,
    ErrorCode.RUN_NOT_FOUND: 404,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.INTERNAL: 500,
    ErrorCode.CAP_REACHED: 429,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
}

DEFAULT_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.INTERNAL: "Something went wrong on our side.",
    ErrorCode.UPSTREAM_ERROR: "The model service returned an error.",
    ErrorCode.UPSTREAM_TIMEOUT: "The model took too long to answer.",
    ErrorCode.RATE_LIMITED: "Too many requests. Try again shortly.",
}


class ChimeraError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        *,
        retryable: bool | None = None,
        retry_after_ms: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message or DEFAULT_MESSAGES.get(code, code.value.replace("_", " ").lower())
        self.retryable = code in RETRYABLE if retryable is None else retryable
        self.retry_after_ms = retry_after_ms
        self.details = details or {}
        super().__init__(f"{code.value}: {self.message}")

    status_override: int | None = None

    @property
    def status(self) -> int:
        return self.status_override or HTTP_STATUS.get(self.code, 500)

    def with_status(self, status: int) -> ChimeraError:
        """The Fusion API fixes some statuses differently from v1 (UNSUPPORTED_FILE is 422,
        an answered choice is 409); v1 keeps its own."""
        self.status_override = status
        return self

    def to_api(self) -> ApiError:
        return ApiError(
            code=self.code,
            message=self.message,
            retryable=self.retryable,
            retry_after_ms=self.retry_after_ms,
            details=self.details,
            error_id=uuid.uuid4().hex[:12] if self.code == ErrorCode.INTERNAL else None,
        )
