from dataclasses import dataclass

@dataclass
class LoginRequestDto:
    username: str
    password: str

