class DomainError(Exception):
    status_code: int = 400
    error_code: str = "DOMAIN_ERROR"

    def __init__(self, message: str = "A domain error occurred.") -> None:
        self.message = message
        super().__init__(self.message)


class UnauthorisedError(Exception):
    status_code: int = 401
    error_code: str = "UNAUTHORISED"

    def __init__(
        self, message: str = "You are not authorised to access that resource"
    ) -> None:
        self.message = message
        super().__init__(self.message)


class ForbiddenError(Exception):
    status_code: int = 403
    error_code: str = "FORBIDDEN"

    def __init__(
        self, message: str = "You are not allowed to perform this action"
    ) -> None:
        self.message = message
        super().__init__(self.message)
