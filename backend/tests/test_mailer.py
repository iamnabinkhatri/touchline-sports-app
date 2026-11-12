import unittest
from unittest.mock import patch

from backend import mailer


class MailerTests(unittest.TestCase):
    def test_gmail_sender_uses_authenticated_account(self):
        with patch.object(mailer.config, "SMTP_HOST", "smtp.gmail.com"), \
             patch.object(mailer.config, "SMTP_USERNAME", "owner@gmail.test"), \
             patch.object(mailer.config, "SMTP_FROM", "stale-sender@gmail.test"):
            self.assertEqual(mailer._sender_address(), "owner@gmail.test")

    def test_other_smtp_providers_keep_configured_sender(self):
        with patch.object(mailer.config, "SMTP_HOST", "smtp.example.test"), \
             patch.object(mailer.config, "SMTP_USERNAME", "login@example.test"), \
             patch.object(mailer.config, "SMTP_FROM", "sender@example.test"):
            self.assertEqual(mailer._sender_address(), "sender@example.test")


if __name__ == "__main__":
    unittest.main()
