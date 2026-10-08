"""
RFC 9457 Standardized Error Handling (Problem Details for HTTP APIs)
"""

from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppException(Exception):
    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        title: str = "Bad Request",
        detail: str = "An error occurred while processing the request.",
        code: str = "BAD_REQUEST",
        error_type: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ):
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.code = code
        self.error_type = error_type or f"https://ai-voice-studio.local/errors/{code.lower().replace('_', '-')}"
        self.extra = extra or {}


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    content = {
        "type": exc.error_type,
        "title": exc.title,
        "status": exc.status_code,
        "detail": exc.detail,
        "code": exc.code,
        "instance": request.url.path,
        **exc.extra,
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        media_type="application/problem+json",
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    title_map = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        409: "Conflict",
        422: "Unprocessable Entity",
        500: "Internal Server Error",
    }
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        500: "INTERNAL_ERROR",
    }
    status_code = exc.status_code
    title = title_map.get(status_code, "HTTP Error")
    code = code_map.get(status_code, f"HTTP_{status_code}")
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

    content = {
        "type": f"https://ai-voice-studio.local/errors/{code.lower().replace('_', '-')}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "code": code,
        "instance": request.url.path,
    }
    return JSONResponse(
        status_code=status_code,
        content=content,
        media_type="application/problem+json",
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    detail = "Request validation failed for one or more fields."
    if errors:
        first = errors[0]
        loc = " -> ".join(str(x) for x in first.get("loc", []))
        detail = f"Field '{loc}': {first.get('msg', 'invalid')}"

    content = {
        "type": "https://ai-voice-studio.local/errors/validation-error",
        "title": "Unprocessable Entity",
        "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "detail": detail,
        "code": "VALIDATION_ERROR",
        "instance": request.url.path,
        "errors": [{"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")} for e in errors],
    }
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=content,
        media_type="application/problem+json",
    )
