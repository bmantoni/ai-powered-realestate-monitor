"""Email HTML generation using Jinja2 templates."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Set

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.models import DailySnapshot, Property


DEFAULT_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "email.html")


class EmailGenerator:
    """Renders an HTML email from property listings and snapshot data."""

    def __init__(self, template_path: str | None = None) -> None:
        """Initialise the generator with a Jinja2 template.

        Args:
            template_path: Absolute or relative path to the email template.
                Defaults to ``templates/email.html`` one directory above ``src/``.
        """
        self.template_path = template_path or DEFAULT_TEMPLATE_PATH
        self._template_dir = os.path.dirname(self.template_path)
        self._template_name = os.path.basename(self.template_path)

        self._env = Environment(
            loader=FileSystemLoader(self._template_dir),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self._template = self._env.get_template(self._template_name)

    def render(
        self,
        properties: list[Property],
        snapshot: DailySnapshot,
        new_ids: Set[str],
        price_changed_ids: Set[str],
        removed_ids: Set[str],
    ) -> str:
        """Render the email template and return the HTML string.

        Args:
            properties: List of properties to display.
            snapshot: Daily snapshot with market metrics.
            new_ids: Set of property IDs that are new today.
            price_changed_ids: Set of property IDs with price changes.
            removed_ids: Set of property IDs that were removed.

        Returns:
            Rendered HTML email content.
        """
        return self._template.render(
            date=snapshot.date,
            snapshot=snapshot,
            properties=properties,
            new_ids=new_ids,
            price_changed_ids=price_changed_ids,
            removed_ids=removed_ids,
        )
