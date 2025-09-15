from __future__ import annotations

import os
from typing import Iterable, Optional

try:
    # google-genai >= 0.2.0
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover
    genai = None  # type: ignore
    types = None  # type: ignore


def have_genai() -> bool:
    return genai is not None and types is not None


def build_client() -> Optional["genai.Client"]:  # type: ignore[name-defined]
    if not have_genai():
        return None
    api_key = os.getenv("GOOGLE_CLOUD_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(vertexai=True, api_key=api_key)  # type: ignore


def stream_generate(
    model: str = "gemini-2.5-flash",
    contents: Optional[list] = None,
    temperature: float = 0.0,
    top_p: float = 0.95,
    max_output_tokens: int = 10000000,
    thinking_budget: int = 0,
) -> Iterable[str]:
    """Yield text chunks using Google GenAI streaming if available."""
    client = build_client()
    if client is None:
        raise RuntimeError("google-genai is not installed or API key missing")
    cfg = types.GenerateContentConfig(
        temperature=temperature,
        top_p=top_p,
        max_output_tokens=max_output_tokens,
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ],
        thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
    )
    if contents is None:
        contents = [types.Content(role="user", parts=[])]
    for chunk in client.models.generate_content_stream(model=model, contents=contents, config=cfg):
        yield getattr(chunk, "text", "")
