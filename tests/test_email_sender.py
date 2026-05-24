"""Tests for the email sender module (SMTP)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.config import Config
from src.email_sender import EmailSender


class TestEmailSender:
    """Comprehensive tests for EmailSender using SMTP."""

    @pytest.fixture
    def config(self) -> Config:
        """Return a Config with SMTP credentials."""
        return Config(
            email_recipient="recipient@example.com",
            email_from="sender@gmail.com",
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            smtp_username="sender@gmail.com",
            smtp_password="app-password",
            smtp_use_tls=True,
            dry_run=False,
        )

    @pytest.fixture
    def sender(self, config: Config) -> EmailSender:
        """Return an EmailSender instance wired to a live config."""
        return EmailSender(config)

    @pytest.fixture
    def sample_html(self) -> str:
        """Return a tiny HTML string for testing."""
        return "<html><body><h1>Test Email</h1></body></html>"

    # ------------------------------------------------------------------ #
    #  Initialisation
    # ------------------------------------------------------------------ #

    def test_init_stores_config(self, sender: EmailSender, config: Config) -> None:
        """The sender should store the supplied Config object."""
        assert sender.config is config

    # ------------------------------------------------------------------ #
    #  Successful sends
    # ------------------------------------------------------------------ #

    @patch("smtplib.SMTP")
    def test_send_email_calls_smtp(
        self,
        mock_smtp_cls: MagicMock,
        sender: EmailSender,
        sample_html: str,
    ) -> None:
        """send_email should instantiate SMTP and call sendmail()."""
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = sender.send_email(html_content=sample_html, subject="Daily Report")

        mock_smtp_cls.assert_called_once_with("smtp.gmail.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("sender@gmail.com", "app-password")
        mock_server.sendmail.assert_called_once()
        assert result == 200

    @patch("smtplib.SMTP")
    def test_send_email_composes_message_correctly(
        self,
        mock_smtp_cls: MagicMock,
        sender: EmailSender,
        sample_html: str,
    ) -> None:
        """The email message should have correct to, from, subject, and HTML content."""
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        sender.send_email(html_content=sample_html, subject="Daily Report")

        # Extract the message from sendmail call
        call_args = mock_server.sendmail.call_args
        from_addr = call_args[0][0]
        to_addrs = call_args[0][1]
        msg_string = call_args[0][2]

        assert from_addr == "sender@gmail.com"
        assert to_addrs == ["recipient@example.com"]
        assert "Subject: Daily Report" in msg_string
        assert "From: sender@gmail.com" in msg_string
        assert "To: recipient@example.com" in msg_string
        assert sample_html in msg_string

    # ------------------------------------------------------------------ #
    #  Missing credentials
    # ------------------------------------------------------------------ #

    def test_send_email_without_username_raises(
        self,
        sample_html: str,
    ) -> None:
        """When smtp_username is missing, send_email should raise ValueError."""
        cfg = Config(
            email_recipient="recipient@example.com",
            email_from="sender@gmail.com",
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            smtp_username=None,
            smtp_password="app-password",
            smtp_use_tls=True,
            dry_run=False,
        )
        sender = EmailSender(cfg)

        with pytest.raises(ValueError, match="SMTP credentials"):
            sender.send_email(html_content=sample_html, subject="Daily Report")

    def test_send_email_without_password_raises(
        self,
        sample_html: str,
    ) -> None:
        """When smtp_password is missing, send_email should raise ValueError."""
        cfg = Config(
            email_recipient="recipient@example.com",
            email_from="sender@gmail.com",
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            smtp_username="sender@gmail.com",
            smtp_password=None,
            smtp_use_tls=True,
            dry_run=False,
        )
        sender = EmailSender(cfg)

        with pytest.raises(ValueError, match="SMTP credentials"):
            sender.send_email(html_content=sample_html, subject="Daily Report")

    # ------------------------------------------------------------------ #
    #  SMTP errors
    # ------------------------------------------------------------------ #

    @patch("smtplib.SMTP")
    def test_send_email_smtp_failure_raises(
        self,
        mock_smtp_cls: MagicMock,
        sender: EmailSender,
        sample_html: str,
    ) -> None:
        """If SMTP sendmail raises an exception, send_email should propagate it."""
        import smtplib

        mock_server = MagicMock()
        mock_server.sendmail.side_effect = smtplib.SMTPException("Connection refused")
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(smtplib.SMTPException, match="Connection refused"):
            sender.send_email(html_content=sample_html, subject="Daily Report")

    # ------------------------------------------------------------------ #
    #  Non-TLS SMTP
    # ------------------------------------------------------------------ #

    @patch("smtplib.SMTP")
    def test_send_email_without_tls(
        self,
        mock_smtp_cls: MagicMock,
        sample_html: str,
    ) -> None:
        """When smtp_use_tls is False, starttls should not be called."""
        cfg = Config(
            email_recipient="recipient@example.com",
            email_from="sender@example.com",
            smtp_host="localhost",
            smtp_port=25,
            smtp_username="sender@example.com",
            smtp_password="password",
            smtp_use_tls=False,
            dry_run=False,
        )
        sender = EmailSender(cfg)

        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        sender.send_email(html_content=sample_html, subject="Daily Report")

        mock_server.starttls.assert_not_called()
        mock_server.login.assert_called_once()
