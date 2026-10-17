import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

from app.errors import ApiError

load_dotenv()

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
_TIMEOUT = 20


def send_email(to: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = f"Good Run <{os.environ.get('SMTP_USER', 'goodrun@localhost')}>"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    deliver(message)


def deliver(message: EmailMessage) -> None:
    user = os.environ.get("SMTP_USER")
    if not user:
        print(message)
        return
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=_TIMEOUT) as smtp:
            smtp.login(user, os.environ.get("SMTP_PASSWORD", ""))
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as error:
        raise ApiError(
            502, "EMAIL_NOT_SENT", "Couldn't send the email, please try again"
        ) from error
