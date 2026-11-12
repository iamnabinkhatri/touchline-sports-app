"""Check SMTP configuration and login without sending a message."""
import smtplib
import ssl
import sys

from . import config


def main():
    if not config.SMTP_HOST:
        print("SMTP host is missing. Set TOUCHLINE_SMTP_HOST in .env.")
        return 2
    try:
        if config.SMTP_PORT == 465:
            client = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=config.SMTP_TIMEOUT, context=ssl.create_default_context())
        else:
            client = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=config.SMTP_TIMEOUT)
        with client:
            client.ehlo()
            if config.SMTP_PORT != 465 and config.SMTP_STARTTLS:
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
            if config.SMTP_USERNAME:
                client.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
        print("SMTP connection, TLS, and login succeeded. No email was sent.")
        if config.SMTP_FROM.lower() != config.SMTP_USERNAME.lower():
            print("Note: sender address differs from SMTP username; Gmail usually requires them to match.")
        return 0
    except smtplib.SMTPAuthenticationError:
        print("SMTP authentication was rejected. Check the full email address and Google App Password in .env.")
    except (smtplib.SMTPConnectError, TimeoutError, OSError):
        print("Could not connect to the SMTP server. Check network access, host, port, and TLS settings.")
    except smtplib.SMTPException as error:
        print(f"SMTP setup failed ({type(error).__name__}). Check host, port, and TLS settings.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
