"""Tests for the email sender module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.config import Config
from src.email_sender import EmailSender


class TestEmailSender:
    """Comprehensive tests for EmailSender."""

    @pytest.fixture
    def config(self) -> Config:
        """Return a Config with email settings enabled."""
        return Config(
            email_recipient="recipient@example.com",
            email_from="snowshoe-bot@example.com",
            smtp_provider="sendgrid",
            sendgrid_api_key="SG.test-key",
            dry_run=False,
        )

    @pytest.fixture
    def dry_run_config(self) -> Config:
        """Return a Config with dry_run enabled."""
        return Config(
            email_recipient="recipient@example.com",
            email_from="snowshoe-bot@example.com",
            smtp_provider="sendgrid",
            sendgrid_api_key="SG.test-key",
            dry_run=True,
        )

    @pytest.fixture
    def sender(self, config: Config) -> EmailSender:
        """Return an EmailSender instance wired to a live config."""
        return EmailSender(config)

    @pytest.fixture
    def dry_run_sender(self, dry_run_config: Config) -> EmailSender:
        """Return an EmailSender instance in dry-run mode."""
        return EmailSender(dry_run_config)

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

    def test_init_sets_sendgrid_api_key(self, sender: EmailSender) -> None:
        """The sender should expose the SendGrid API key from config."""
        assert sender.sendgrid_api_key == "SG.test-key"

    # ------------------------------------------------------------------ #
    #  dry_run = False  (real sends)
    # ------------------------------------------------------------------ #

    @patch("src.email_sender.SendGridAPIClient")
    def test_send_email_calls_sendgrid_api(
        self,
        mock_client_cls: MagicMock,
        sender: EmailSender,
        sample_html: str,
    ) -> None:
        """send_email should instantiate SendGridAPIClient and call send()."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        sender.send_email(html_content=sample_html, subject="Daily Report")

        mock_client_cls.assert_called_once_with(api_key="SG.test-key")
        mock_client.send.assert_called_once()

    @patch("src.email_sender.SendGridAPIClient")
    def test_send_email_composes_message_correctly(
        self,
        mock_client_cls: MagicMock,
        sender: EmailSender,
        sample_html: str,
    ) -> None:
        """The Mail object passed to send() must have correct to, from, subject, and HTML content."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        sender.send_email(html_content=sample_html, subject="Daily Report")

        call_args = mock_client.send.call_args
        message = call_args[0][0]

        # to — stored inside personalizations
        assert message.personalizations[0].tos[0]["email"] == "recipient@example.com"
        # from
        assert message.from_email.email == "snowshoe-bot@example.com"
        # subject
        assert message.subject.subject == "Daily Report"
        # html content
        payload = message.get()
        assert payload["content"][0]["value"] == sample_html
        assert payload["content"][0]["type"] == "text/html"

    @patch("src.email_sender.SendGridAPIClient")
    def test_send_email_returns_status_code(
        self,
        mock_client_cls: MagicMock,
        sender: EmailSender,
        sample_html: str,
    ) -> None:
        """send_email should return the HTTP status code from the SendGrid response."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_client = MagicMock()
        mock_client.send.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = sender.send_email(html_content=sample_html, subject="Daily Report")

        assert result == 202

    @patch("src.email_sender.SendGridAPIClient")
    def test_send_email_api_failure_raises_exception(
        self,
        mock_client_cls: MagicMock,
        sender: EmailSender,
        sample_html: str,
    ) -> None:
        """If SendGrid send() raises an exception, send_email should propagate it."""
        mock_client = MagicMock()
        from python_http_client.exceptions import HTTPError

        # HTTPError can take 4 args: status_code, reason, body, headers
        mock_client.send.side_effect = HTTPError(400, "Bad Request", b"{}", {})
        mock_client_cls.return_value = mock_client

        with pytest.raises(HTTPError):
            sender.send_email(html_content=sample_html, subject="Daily Report")

    def test_send_email_without_api_key_raises(
        self,
        sample_html: str,
    ) -> None:
        """When sendgrid_api_key is missing, send_email should raise ValueError."""
        cfg = Config(
            email_recipient="recipient@example.com",
            email_from="snowshoe-bot@example.com",
            smtp_provider="sendgrid",
            sendgrid_api_key=None,
            dry_run=False,
        )
        sender = EmailSender(cfg)

        with pytest.raises(ValueError, match="SendGrid API key"):
            sender.send_email(html_content=sample_html, subject="Daily Report")

    # ------------------------------------------------------------------ #
    #  Unsupported provider
    # ------------------------------------------------------------------ #

    def test_unsupported_provider_raises(self, sample_html: str) -> None:
        """An unsupported smtp_provider should raise ValueError on send."""
        cfg = Config(
            email_recipient="recipient@example.com",
            email_from="snowshoe-bot@example.com",
            smtp_provider="fax_machine",
            sendgrid_api_key="SG.test-key",
            dry_run=False,
        )
        sender = EmailSender(cfg)

        with pytest.raises(ValueError, match="Unsupported email provider"):
            sender.send_email(html_content=sample_html, subject="Daily Report")
