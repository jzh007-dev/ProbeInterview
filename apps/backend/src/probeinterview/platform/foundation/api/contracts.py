"""Typed HTTP resources and RFC 9457 extensions for foundation APIs."""

from typing import Literal

from pydantic import BaseModel


class HealthResource(BaseModel):
    """Typed response returned by the liveness endpoint."""

    status: Literal["ok"]


class ReadinessResource(BaseModel):
    """Typed response returned when required runtime dependencies are available."""

    status: Literal["ready"]
    dependencies: dict[str, Literal["available"]]


class FieldViolation(BaseModel):
    """Safe field-level validation detail."""

    field: str
    message: str
    code: str


class ProblemDetails(BaseModel):
    """RFC 9457 Problem Details with stable ProbeInterview extensions."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
    code: str
    request_id: str
    errors: list[FieldViolation] | None = None
    unavailable_dependencies: list[str] | None = None
    quota: dict[str, str | int] | None = None
