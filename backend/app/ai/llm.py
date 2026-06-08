"""
LLM client module - OpenAI-compatible API client with tool calling support.

Uses httpx for async HTTP calls to any OpenAI-compatible endpoint
(e.g., self-hosted DeepSeek, vLLM, Ollama, etc.).
"""

import json
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level client (lazy init)
_client: httpx.AsyncClient | None = None


def is_llm_available() -> bool:
    """Check if LLM is configured and available."""
    return bool(settings.llm_base_url)


def _get_client() -> httpx.AsyncClient:
    """Get or create the shared httpx async client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=settings.llm_base_url.rstrip("/"),
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
    return _client


def _build_headers() -> dict[str, str]:
    """Build request headers with optional auth."""
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key and settings.llm_api_key != "not-needed":
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    return headers


async def chat_completion(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 8092,
) -> dict[str, Any]:
    """
    Call the LLM chat completion API.

    Args:
        messages: OpenAI-format message list.
        tools: Optional tool definitions (OpenAI function calling format).
        temperature: Sampling temperature.
        max_tokens: Max tokens in response.

    Returns:
        Raw API response dict.
    """
    client = _get_client()

    body: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    resp = await client.post(
        "/chat/completions",
        json=body,
        headers=_build_headers(),
    )
    resp.raise_for_status()
    return resp.json()


async def close_client() -> None:
    """Close the httpx client (call on app shutdown)."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
