class DomainError(Exception):
    def __init__(self, message: str = "A domain error occurred."):
        self.message = message
        super().__init__(self.message)


class UnauthorisedError(Exception):
    def __init__(self, message: str = "You are not authorised to access that resource"):
        self.message = message
        super().__init__(self.message)
