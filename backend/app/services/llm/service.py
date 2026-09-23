from functools import lru_cache
import asyncio
from typing import Any

from app.core.config import get_settings
from app.services.llm.base import LLMProvider, LLMResult
from app.services.llm.mock_provider import MockLLMProvider
from app.services.llm.qwen_provider import QwenProvider
from app.services.llm.qwen_provider import LLMProviderError
from app.services.llm.huggingface_provider import HuggingFaceProvider


class LLMService:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def generate(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResult:
        for attempt in range(2):
            try:
                return await self.provider.generate(messages, **kwargs)
            except LLMProviderError as exc:
                if attempt == 1 or exc.error_type not in {"timeout", "network_error", "rate_limited", "provider_unavailable"}:
                    raise
                await asyncio.sleep(0.2 * (attempt + 1))
        raise RuntimeError("LLM retry loop exhausted")

    async def health(self) -> bool:
        return await self.provider.health()


@lru_cache
def get_llm_service() -> LLMService:
    settings = get_settings()
    if settings.llm_provider == "mock":
        return LLMService(MockLLMProvider())
    if settings.llm_provider == "huggingface":
        return LLMService(HuggingFaceProvider(settings))
    if settings.llm_provider == "qwen_remote":
        return LLMService(QwenProvider(settings))
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
