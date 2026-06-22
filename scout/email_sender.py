import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Tuple

def send_cold_email(
    smtp_host: str,
    smtp_port: int,
    sender_email: str,
    sender_password: str,
    recipient_email: str,
    subject: str,
    body: str
) -> Tuple[bool, str]:
    """Send a cold email via SMTP with STARTTLS. Returns (success, message)."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, int(smtp_port), timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [recipient_email], msg.as_string())

        return True, f"Sent successfully to {recipient_email}"
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed. Check your email and password (use an App Password for Gmail)."
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"
