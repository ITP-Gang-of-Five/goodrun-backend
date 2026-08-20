from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.common.handlers import init_exception_handlers

from app.auth.login import validate_password, create_login
from app.auth.jwt_handler import verify_access_token, create_access_token

from app.models.dtos import LoginRequestDto


app = FastAPI(title="Good Run API", version="0.1.0")
api = APIRouter(prefix="/api/v0")

# this converts domain and unauthorised errors into correct response codes
init_exception_handlers(app)

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> int | None:
    token = credentials.credentials
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    return payload.get("userId")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@api.post("/auth/login")
def login(credentials: LoginRequestDto) -> dict[str, str]:
    user_id = validate_password(credentials.username, credentials.password)
    token = create_access_token({"userId": user_id})
    return {"access_token": token, "refresh_token": ""}

@api.post("/auth/signup")
def signup(credentials: LoginRequestDto) -> dict[str, str]:
    user_id = create_login(credentials.username, credentials.password)
    token = create_access_token({"userId": user_id})
    return {"access_token": token, "refresh_token": ""}


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


@api.post("/whoami}")
def whoami(jwt_token: str) -> dict | None:
    print(f"WHOAMI: {verify_access_token(jwt_token)}")
    return verify_access_token(jwt_token)


app.include_router(api)
