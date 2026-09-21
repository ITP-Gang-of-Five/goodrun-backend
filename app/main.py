from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(title="Good Run API", version="0.1.0")


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router)
