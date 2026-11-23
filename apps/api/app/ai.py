"""AI provider layer — one `chat()` entry point with a fallback chain.

Chain (first available wins, failures fall through to the next):
  1. OpenAI        — when OPENAI_API_KEY is set (env only, never hardcoded)
  2. Gemini        — when GEMINI_API_KEY is set (env only)
  3. Pollinations  — free endpoint, no key: https://text.pollinations.ai/<prompt>
  4. Offline       — deterministic local template answer (clearly labelled)

`settings.ai_provider` (env AI_PROVIDER) can force a starting provider;
model names are configurable via OPENAI_MODEL / GEMINI_MODEL.
"""
import logging
from urllib.parse import quote

import httpx

from .config import settings

log = logging.getLogger("personal-os.ai")

_OFFLINE_NOTICE = (
    "[Offline AI mode — no cloud AI provider is configured or reachable, "
    "so this answer was generated locally by PERSONAL OS.]"
)


def _available(name: str) -> bool:
    if name == "openai":
        return bool(settings.openai_api_key)
    if name == "gemini":
        return bool(settings.gemini_api_key)
    return True  # pollinations (no key) and offline are always available


def _chain() -> list[str]:
    order = ["openai", "gemini", "pollinations", "offline"]
    forced = (settings.ai_provider or "").strip().lower()
    if forced in order:
        order.remove(forced)
        order.insert(0, forced)
    return [name for name in order if _available(name)]


def provider_name() -> str:
    """The provider `chat()` will try first right now."""
    return _chain()[0]


def _openai_chat(text: str, system: str | None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": text})
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        json={"model": settings.openai_model, "messages": messages},
        timeout=settings.ai_timeout_seconds,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _gemini_chat(text: str, system: str | None) -> str:
    prompt = f"{system}\n\n{text}" if system else text
    resp = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent",
        params={"key": settings.gemini_api_key},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=settings.ai_timeout_seconds,
    )
    resp.raise_for_status()
    parts = resp.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts).strip()


def _pollinations_chat(text: str, system: str | None) -> str:
    prompt = f"{system}\n\n{text}" if system else text
    resp = httpx.get(
        f"https://text.pollinations.ai/{quote(prompt, safe='')}",
        timeout=settings.ai_timeout_seconds,
    )
    resp.raise_for_status()
    out = resp.text.strip()
    if not out:
        raise RuntimeError("Pollinations returned an empty response")
    return out


def _offline_chat(text: str, system: str | None) -> str:
    return (
        f"{_OFFLINE_NOTICE}\n\n"
        f"Your request: \"{text}\"\n\n"
        "Structured local response:\n"
        "- The command was understood and recorded, but a full AI answer needs a "
        "configured provider (set OPENAI_API_KEY or GEMINI_API_KEY in the API "
        "environment, or check network access for the free fallback).\n"
        "- Nothing was invented locally: no facts, clients, emails or research "
        "results are fabricated in offline mode.\n"
        "- Task management, reporting, memory and permission features keep "
        "working offline because they run on the local database."
    )


_PROVIDERS = {
    "openai": _openai_chat,
    "gemini": _gemini_chat,
    "pollinations": _pollinations_chat,
    "offline": _offline_chat,
}


def chat(text: str, system: str | None = None) -> str:
    """Ask the first reachable provider; fall back down the chain on failure."""
    last_error: Exception | None = None
    for name in _chain():
        try:
            out = _PROVIDERS[name](text, system)
            if out:
                return out
            raise RuntimeError(f"{name} returned an empty response")
        except Exception as exc:  # fall through to the next provider
            last_error = exc
            log.warning("AI provider %s failed: %s", name, exc)
    # _chain() always ends with offline, which never raises — defensive only.
    raise RuntimeError(f"All AI providers failed: {last_error}")
