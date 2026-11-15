"""Thin wrapper around the Google Gemini API (free tier) using the `google-genai` SDK."""
from __future__ import annotations

import os

DEFAULT_MODEL = "gemini-3.1-flash-lite"
FALLBACK_MODELS = ["gemini-flash-latest", "gemini-2.0-flash"]


class LLMError(RuntimeError):
    """Raised for any failure talking to the LLM; the message is safe to show to a player."""


def get_api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def _friendly(message: str) -> str:
    low = message.lower()
    if "429" in low or "resource_exhausted" in low or "quota" in low:
        return "The Gemini free-tier rate limit was reached. Wait a moment and try again."
    if "api key" in low or "api_key" in low or "401" in low or "403" in low or "permission" in low:
        return "Gemini rejected the API key. Check GEMINI_API_KEY."
    if "timeout" in low or "connect" in low:
        return "Could not reach the Gemini API. Check your internet connection."
    return "The Gemini API returned an error."


class GeminiClient:
    def __init__(self, api_key: str, model: str | None = None):
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover
            raise LLMError("Package 'google-genai' is missing. Run: py -m pip install -r requirements.txt") from exc
        self._client = genai.Client(api_key=api_key)
        self.model = model or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL

    def _candidates(self) -> list[str]:
        return [self.model] + [m for m in FALLBACK_MODELS if m != self.model]

    def generate(self, system: str, contents: list[tuple[str, str]], *, json_mode: bool = False,
                 temperature: float = 0.7, max_tokens: int = 1024) -> str:
        """`contents` is a list of (role, text) with role 'user' or 'model'."""
        from google.genai import types

        cfg = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json" if json_mode else None,
        )
        parts = [types.Content(role=r, parts=[types.Part.from_text(text=t)]) for r, t in contents]

        last: Exception | None = None
        for model in self._candidates():
            try:
                resp = self._client.models.generate_content(model=model, contents=parts, config=cfg)
                self.model = model  # remember the one that worked
                return (resp.text or "").strip()
            except Exception as exc:  # SDK raises various error types
                last = exc
                low = str(exc).lower()
                if "404" in low or "not_found" in low or "not found" in low:
                    continue  # model retired / unavailable: try the next one
                raise LLMError(_friendly(str(exc))) from exc
        raise LLMError("No usable Gemini model found. Set GEMINI_MODEL in .env.") from last
