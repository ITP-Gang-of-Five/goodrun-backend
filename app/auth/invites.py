import secrets
from datetime import UTC, datetime, timedelta

from app.auth.passwords import hash_password
from app.common.mail import send_email
from app.queries import Queries
from app.storage import Invite, User

CODE_LENGTH = 6
INVITE_LIFETIME = timedelta(days=7)
MAX_FAILED_ATTEMPTS = 5

#TODO: in the future I'm sure this could be abstracted to a nicer location, especially if we want to make it fancier / put javascript in it
INVITE_BODY = """Hi,

You've been invited to join Good Run. To set up your account, open the Good
Run app and log in with this email address, using this code as your password:

    {code}

The code only works once and expires in {days} days.

If you weren't expecting this, you can ignore this email.
"""


def make_code() -> str:
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"


def send_invite(db: Queries, user: User) -> None:
    code = make_code()
    now = datetime.now(UTC)
    db.set_invite(
        Invite(
            user_id=user.id,
            code_hash=hash_password(code),
            expires_at=now + INVITE_LIFETIME,
            created_at=now,
        )
    )
    send_email(
        to=user.email,
        subject="You've been invited to Good Run",
        body=INVITE_BODY.format(code=code, days=INVITE_LIFETIME.days),
    )


def is_usable(invite: Invite | None) -> bool:
    return (
        invite is not None
        and invite.failed_attempts < MAX_FAILED_ATTEMPTS
        and invite.expires_at > datetime.now(UTC)
    )
