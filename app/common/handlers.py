from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from app.common.exceptions import UnauthorisedError, DomainError

async def unauthorized_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"success": False, "error": "UNAUTHORIZED", "detail": str(exc)}
    )

async def domain_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"success": False, "error": "DOMAIN ERROR", "detail": str(exc)}
    )

def init_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(UnauthorisedError, unauthorized_handler)
    app.add_exception_handler(DomainError, unauthorized_handler)