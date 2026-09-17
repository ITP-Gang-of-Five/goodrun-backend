from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.common.exceptions import DomainError, ForbiddenError, UnauthorisedError


async def error_handler(request: Request, exc: Exception) -> JSONResponse:
    status_code = getattr(exc, "status_code", 500)
    error_code = getattr(exc, "error_code", "INTERNAL_ERROR")
    description = getattr(exc, "message", str(exc))
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": error_code, "description": description}},
    )


def init_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, error_handler)
    app.add_exception_handler(UnauthorisedError, error_handler)
    app.add_exception_handler(ForbiddenError, error_handler)
