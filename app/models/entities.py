from dataclasses import dataclass

@dataclass 
class LoginRecord:
    user_id: int
    password_hash: str