from fastapi import APIRouter, FastAPI

app = FastAPI(title="Good Run API", version="0.1.0")
api = APIRouter(prefix="/api/v0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ponytail: stubs only; add auth, validation, and run models when those exist
@api.post("/auth/login")
def login() -> dict[str, str]:
    return {"access_token": "", "refresh_token": ""}


@api.post("/auth/refresh-token")
def refresh_token() -> dict[str, str]:
    return {"access_token": "", "refresh_token": ""}


@api.post("/location/", status_code=204)
def update_location() -> None:
    return None


@api.get("/runs/")
def get_runs() -> dict[str, list[object]]:
    return {"orders": []}


@api.post("/runs/")
def create_run() -> dict[str, object]:
    return {}


@api.get("/runs/current")
def current_runs() -> dict[str, object]:
    return {}


@api.get("/runs/{runID}")
def get_run(runID: str) -> dict[str, str]:
    return {"runID": runID}


@api.post("/runs/{runID}/accept", status_code=204)
def accept_run(runID: str) -> None:
    return None


@api.post("/runs/{runID}/cancel", status_code=204)
def cancel_run(runID: str) -> None:
    return None


@api.post("/runs/{runID}/complete", status_code=204)
def complete_run(runID: str) -> None:
    return None


@api.post("/runs/{runID}/remove", status_code=204)
def remove_run(runID: str) -> None:
    return None


app.include_router(api)
