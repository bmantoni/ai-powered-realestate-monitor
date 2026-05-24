"""Email delivery via SendGrid (primary) with dry-run support."""

from __future__ import annotations

from typing import Optional

from loguru import logger
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, Email, Mail, Subject, To

from src.config import Config


class EmailSender:
    """Sends HTML emails using SendGrid or logs them in dry-run mode."""

    def __init__(self, config: Config) -> None:
        """Initialise with application configuration.

        Args:
            config: Application configuration including email credentials.
        """
        self.config = config
        self.sendgrid_api_key = config.sendgrid_api_key

    def send_email(self, html_content: str, subject: str) -> Optional[int]:
        """Send an HTML email via the configured provider.

        In dry-run mode the email is logged instead of sent.

        Args:
            html_content: Full HTML body of the email.
            subject: Email subject line.

        Returns:
            HTTP status code if sent successfully, or ``None`` in dry-run mode.

        Raises:
            ValueError: If the email provider is unsupported or API key is missing.
            Exception: Re-raises any SendGrid API error.
        """
        if self.config.smtp_provider == "sendgrid":
            return self._send_via_sendgrid(html_content, subject)

        raise ValueError(f"Unsupported email provider: {self.config.smtp_provider}")

    def _send_via_sendgrid(self, html_content: str, subject: str) -> int:
        """Deliver email through SendGrid.

        Args:
            html_content: Full HTML body.
            subject: Email subject.

        Returns:
            HTTP status code from the SendGrid API response.

        Raises:
            ValueError: If the SendGrid API key is not configured.
        """
        if not self.sendgrid_api_key:
            raise ValueError("SendGrid API key is required but not configured.")

        sg = SendGridAPIClient(api_key=self.sendgrid_api_key)

        message = Mail(
            from_email=Email(self.config.email_from),
            to_emails=To(self.config.email_recipient),
            subject=Subject(subject),
            html_content=Content("text/html", html_content),
        )

        response = sg.send(message)
        logger.info("Email sent via SendGrid: status=%s", response.status_code)
        return response.status_code
