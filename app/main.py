from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.common.handlers import init_exception_handlers
from app.errors import add_error_handler
from app.queries import pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # open the connection pool on startup and close it on shutdown, so the
    # connections to Neon are made once rather than per request
    pool.open()
    yield
    pool.close()


app = FastAPI(title="Good Run API", version="0.1.0", lifespan=lifespan)
# add error handling
add_error_handler(app)

# this converts domain and unauthorised errors into correct response codes
init_exception_handlers(app)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router)
