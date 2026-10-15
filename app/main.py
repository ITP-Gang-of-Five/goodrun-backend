from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.common.handlers import init_exception_handlers
from app.errors import add_error_handler
from app.queries import pool

"""
The websites that are allowed to call this API from the browser, which is only our frontend
deployed on cloud flare pages.
Locally ours machines go through vite's api proxy so it never needs this
"""
ALLOWED_ORIGINS = ["https://goodrun-frontend.maximusdebski.workers.dev"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # open the connection pool on startup and close it on shutdown, so the
    # connections to Neon are made once rather than per request
    pool.open()
    yield
    pool.close()


app = FastAPI(title="Good Run API", version="0.1.0", lifespan=lifespan)

# logins are sent as an Authorization header rather than a cookie, so credentials
# don't need to be allowed
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
# add error handling
add_error_handler(app)

# this converts domain and unauthorised errors into correct response codes
init_exception_handlers(app)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router)
