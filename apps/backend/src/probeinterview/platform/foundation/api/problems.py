"""RFC 9457 response construction."""

from starlette.responses import JSONResponse

from probeinterview.platform.foundation.api.contracts import ProblemDetails


def problem_response(problem: ProblemDetails) -> JSONResponse:
    """Serialize a Problem Details resource with its required media type."""

    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )
