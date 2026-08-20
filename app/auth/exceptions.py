from app.common.exceptions import DomainError, UnauthorisedError


class UserAlreadyExistsError(DomainError):
    pass


class IncorrectPasswordError(UnauthorisedError):
    pass


class UserNotFoundError(DomainError):
    pass
