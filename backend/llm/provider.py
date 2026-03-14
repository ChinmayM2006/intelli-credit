"""
Unified LLM Provider — supports OpenAI, Gemini, and rule-based fallback.
"""
import json
import asyncio
from typing import Optional
from backend.config import OPENAI_API_KEY, GEMINI_API_KEY, LLM_PROVIDER


class LLMProvider:
    """Base class for LLM providers."""
    name = "base"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None,
                       json_mode: bool = False, max_tokens: int = 4096) -> str:
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.model = "gpt-4o-mini"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None,
                       json_mode: bool = False, max_tokens: int = 4096) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        kwargs = {"model": self.model, "messages": messages,
                  "max_tokens": max_tokens, "temperature": 0.3}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = await self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[OpenAI error: {e}]"


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    async def generate(self, prompt: str, system_prompt: Optional[str] = None,
                       json_mode: bool = False, max_tokens: int = 4096) -> str:
        full_prompt = ""
        if system_prompt:
            full_prompt = f"System instruction: {system_prompt}\n\n"
        full_prompt += prompt
        if json_mode:
            full_prompt += "\n\nRespond ONLY with valid JSON, no markdown."
        try:
            response = await asyncio.to_thread(self.model.generate_content, full_prompt)
            return response.text
        except Exception as e:
            return f"[Gemini error: {e}]"


class FallbackProvider(LLMProvider):
    name = "fallback"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None,
                       json_mode: bool = False, max_tokens: int = 4096) -> str:
        if json_mode:
            return json.dumps({"fallback": True, "message": "No LLM API key configured."})
        return "[AI Summary unavailable — using rule-based analysis.]"


_cached_provider: Optional[LLMProvider] = None


def get_llm() -> LLMProvider:
    global _cached_provider
    if _cached_provider is not None:
        return _cached_provider
    provider = LLM_PROVIDER.lower()
    if provider == "openai" and OPENAI_API_KEY:
        try:
            _cached_provider = OpenAIProvider()
            return _cached_provider
        except ImportError:
            pass
    elif provider == "gemini" and GEMINI_API_KEY:
        try:
            _cached_provider = GeminiProvider()
            return _cached_provider
        except ImportError:
            pass
    elif provider == "auto":
        if OPENAI_API_KEY:
            try:
                _cached_provider = OpenAIProvider()
                return _cached_provider
            except ImportError:
                pass
        if GEMINI_API_KEY:
            try:
                _cached_provider = GeminiProvider()
                return _cached_provider
            except ImportError:
                pass
    _cached_provider = FallbackProvider()
    return _cached_provider


def get_llm_status() -> dict:
    llm = get_llm()
    return {
        "provider": llm.name,
        "has_openai": bool(OPENAI_API_KEY),
        "has_gemini": bool(GEMINI_API_KEY),
        "mode": "ai" if llm.name != "fallback" else "rule-based",
    }
