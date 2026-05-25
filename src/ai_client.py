"""AI client interface and implementations for different providers."""

from __future__ import annotations

import abc
from typing import Any


class AIClient(abc.ABC):
    """Abstract interface for AI providers."""

    @abc.abstractmethod
    async def generate_json(self, prompt: str) -> list[dict[str, Any]]:
        """Generate a JSON list response from the AI for the given prompt.

        Args:
            prompt: The prompt to send to the AI model.

        Returns:
            A list of dictionaries parsed from the AI's JSON response.
        """
        ...

    @abc.abstractmethod
    async def generate_text(self, prompt: str) -> str:
        """Generate a plain text response from the AI for the given prompt.

        Args:
            prompt: The prompt to send to the AI model.

        Returns:
            The raw text response from the AI model.
        """
        ...


class GeminiAIClient(AIClient):
    """Google Gemini AI client implementation."""

    def __init__(self, api_key: str, model: str | None = None) -> None:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model or "gemini-2.5-flash")
        self.call_count: int = 0

    async def generate_json(self, prompt: str) -> list[dict[str, Any]]:
        self.call_count += 1
        import json
        response = await self._model.generate_content_async(prompt)
        text = response.text
        # Extract JSON from markdown code blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as exc:
            raise ValueError(f"AI returned invalid JSON: {exc}\nResponse text: {text[:200]}...") from exc

    async def generate_text(self, prompt: str) -> str:
        self.call_count += 1
        response = await self._model.generate_content_async(prompt)
        return response.text.strip()


class MockAIClient(AIClient):
    """Test/mock implementation of AIClient for unit testing."""

    def __init__(self, response: list[dict[str, Any]] | None = None):
        self._response = response if response is not None else []
        self._text_response: str = ""
        self._side_effect: Exception | None = None
        self.last_prompt: str = ""
        self.call_count: int = 0

    def set_response(self, response: list[dict[str, Any]]) -> None:
        """Set the JSON response to return on the next call."""
        self._response = response
        self._side_effect = None

    def set_text_response(self, response: str) -> None:
        """Set the text response to return on the next generate_text call."""
        self._text_response = response
        self._side_effect = None

    def set_side_effect(self, exception: Exception) -> None:
        """Set an exception to raise on the next call."""
        self._side_effect = exception

    async def generate_json(self, prompt: str) -> list[dict[str, Any]]:
        """Return the configured mock response."""
        self.last_prompt = prompt
        self.call_count += 1
        if self._side_effect is not None:
            raise self._side_effect
        return list(self._response)

    async def generate_text(self, prompt: str) -> str:
        """Return the configured mock text response."""
        self.last_prompt = prompt
        self.call_count += 1
        if self._side_effect is not None:
            raise self._side_effect
        return self._text_response
