"""SMTP delivery for account verification and recovery messages."""
import smtplib
import ssl
import logging
from email.message import EmailMessage

from . import config


class MailDeliveryError(RuntimeError):
    pass


def _sender_address():
    # Gmail rejects arbitrary From addresses unless separately configured as
    # aliases. Prefer the authenticated account so stale shell variables cannot
    # silently make account emails undeliverable.
    if config.SMTP_HOST.strip().lower() == "smtp.gmail.com" and config.SMTP_USERNAME:
        return config.SMTP_USERNAME
    return config.SMTP_FROM


def send_email(recipient, subject, body):
    if not config.SMTP_HOST:
        logging.getLogger(__name__).warning("SMTP host is missing; load TOUCHLINE_SMTP_HOST from the process environment or .env")
        raise MailDeliveryError("not_configured")
    message = EmailMessage()
    message["From"] = _sender_address()
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    stage = "connection"
    try:
        if config.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(
                config.SMTP_HOST,
                config.SMTP_PORT,
                timeout=config.SMTP_TIMEOUT,
                context=ssl.create_default_context(),
            ) as client:
                stage = "server greeting"
                client.ehlo()
                if config.SMTP_USERNAME:
                    stage = "authentication"
                    client.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                stage = "message submission"
                client.send_message(message)
        else:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=config.SMTP_TIMEOUT) as client:
                stage = "server greeting"
                client.ehlo()
                if config.SMTP_STARTTLS:
                    stage = "TLS negotiation"
                    client.starttls(context=ssl.create_default_context())
                    stage = "server greeting after TLS"
                    client.ehlo()
                if config.SMTP_USERNAME:
                    stage = "authentication"
                    client.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                stage = "message submission"
                client.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        # Keep SMTP replies, recipient addresses, and credentials out of the log.
        logging.getLogger(__name__).warning("SMTP delivery failed during %s (%s)", stage, type(error).__name__)
        raise MailDeliveryError("delivery_failed") from error
