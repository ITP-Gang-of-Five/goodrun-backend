from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, description: str) -> None:
        #Following all the components of an error we defined in our API agreeement
        self.status_code = status_code
        self.code = code
        self.description = description

#This is a general error handler I used in a preivous project, it will allow us
#To wrap everythign in an API erorr handler so this will be raised if an error occurs
def add_error_handler(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, error: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": error.code, "description": error.description}},
        )
