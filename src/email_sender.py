"""Email delivery via SMTP (Gmail, etc.) with dry-run support."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from loguru import logger

from src.config import Config


class EmailSender:
    """Sends HTML emails using SMTP or logs them in dry-run mode."""

    def __init__(self, config: Config) -> None:
        """Initialise with application configuration.

        Args:
            config: Application configuration including SMTP credentials.
        """
        self.config = config

    def send_email(self, html_content: str, subject: str) -> Optional[int]:
        """Send an HTML email via SMTP.

        Args:
            html_content: Full HTML body of the email.
            subject: Email subject line.

        Returns:
            200 if sent successfully.

        Raises:
            ValueError: If SMTP credentials are not configured.
            smtplib.SMTPException: Re-raises any SMTP error.
        """
        if not self.config.smtp_host:
            raise ValueError(
                "SMTP host not configured. "
                "Set SMTP_HOST environment variable (e.g., smtp.gmail.com)."
            )
        if not self.config.smtp_username or not self.config.smtp_password:
            raise ValueError(
                "SMTP credentials not configured. "
                "Set SMTP_USERNAME and SMTP_PASSWORD environment variables."
            )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.email_from
        msg["To"] = self.config.email_recipient

        # Attach HTML content
        msg.attach(MIMEText(html_content, "html"))

        try:
            with smtplib.SMTP(timeout=30) as server:
                server.connect(self.config.smtp_host, self.config.smtp_port)
                server.ehlo()
                if self.config.smtp_use_tls:
                    server.starttls()
                    server.ehlo()
                server.login(self.config.smtp_username, self.config.smtp_password)
                server.sendmail(
                    self.config.email_from,
                    [self.config.email_recipient],
                    msg.as_string(),
                )
            logger.info(
                "Email sent via SMTP ({host}:{port}) to {recipient}",
                host=self.config.smtp_host,
                port=self.config.smtp_port,
                recipient=self.config.email_recipient,
            )
            return 200
        except smtplib.SMTPException as exc:
            logger.error("SMTP error: {}", exc)
            raise
