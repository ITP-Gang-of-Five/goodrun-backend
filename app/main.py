from fastapi import FastAPI

from app.api.router import api_router
from app.common.handlers import init_exception_handlers

app = FastAPI(title="Good Run API", version="0.1.0")

# this converts domain and unauthorised errors into correct response codes
init_exception_handlers(app)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router)
