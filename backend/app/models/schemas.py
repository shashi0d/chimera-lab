"""Pydantic models shared by the API: the error envelope and the vision model's animal reading.

Python attributes are snake_case; JSON on the wire is camelCase.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, json_schema_serialization_defaults_required=True
    )

    def dump(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, mode="json")


# ---------------------------------------------------------------- errors


class ErrorCode(str, Enum):
    VALIDATION_FAILED = "VALIDATION_FAILED"
    UNSUPPORTED_FILE = "UNSUPPORTED_FILE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    IMAGE_CORRUPT = "IMAGE_CORRUPT"
    NOT_AN_ANIMAL = "NOT_AN_ANIMAL"
    HUMAN_DETECTED = "HUMAN_DETECTED"
    RATE_LIMITED = "RATE_LIMITED"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    MODEL_REFUSED = "MODEL_REFUSED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL = "INTERNAL"
    CAP_REACHED = "CAP_REACHED"  # daily caps on agent runs and lab actions
    UNAUTHORIZED = "UNAUTHORIZED"  # no valid sign-in
    FORBIDDEN = "FORBIDDEN"  # signed in, but not the owner


class ApiError(ApiModel):
    code: ErrorCode
    message: str
    retryable: bool = False
    retry_after_ms: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    error_id: str | None = None


class ErrorEnvelope(ApiModel):
    error: ApiError


class AnimalReading(ApiModel):
    is_animal: bool
    contains_human: bool = False
    common_name: str | None = None
    scientific_name: str | None = None
    confidence: float = 0.0
    visible_parts: list[str] = Field(default_factory=list)
    body_plan: str | None = None
    notes: str = ""
