from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, description: str) -> None:
        # Following all the components of an error we defined in our API agreeement
        self.status_code = status_code
        self.code = code
        self.description = description


"""
Turns a validation failure into the field that caused it.

FastAPI hands us a list of problems, each with a loc like ("body", "email") or
("query", "volunteerId"). The first element is where it came from, the rest is the
path to the field, which is what the agreement says to name in the description.
"""


def _describe(error: dict[str, object]) -> str:
    location = error.get("loc") or ()
    assert isinstance(location, tuple | list)
    # drop the leading "body"/"query"/"path", what is left is the field itself
    field = ".".join(str(part) for part in location[1:])
    message = str(error.get("msg", "is not valid"))
    return f"{field}: {message}" if field else message


# This is a general error handler I used in a preivous project, it will allow us
# To wrap everythign in an API erorr handler so this will be raised if an error occurs
def add_error_handler(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, error: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": error.code, "description": error.description}},
        )

    """
    A request body or query param that doesn't match the shape we expect.

    Without this FastAPI answers with its own {"detail": [...]} shape, which is not
    what the API agreement promises, so the frontend would have to special case it.
    Registering it here means every endpoint gets the right shape for free.
    """

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        problems = error.errors()
        # only the first problem is reported, the frontend fixes them one at a time
        description = _describe(dict(problems[0])) if problems else "Invalid request"
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_ERROR", "description": description}},
        )
