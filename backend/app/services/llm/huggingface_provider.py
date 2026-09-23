import time
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.services.llm.base import LLMResult
from app.services.llm.qwen_provider import LLMProviderError


class HuggingFaceProvider:
    """Hugging Face Inference Providers adapter using its OpenAI-compatible router."""

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    def _endpoint(self, path: str) -> str:
        return f"{self.settings.hf_base_url.rstrip('/')}{path}"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.hf_token}", "Content-Type": "application/json"}

    async def generate(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResult:
        if not self.settings.hf_token:
            raise LLMProviderError("Hugging Face token is not configured", error_type="not_configured")
        payload = {"model": self.settings.hf_model, "messages": messages, "temperature": self.settings.llm_temperature, "max_tokens": self.settings.llm_max_tokens, **kwargs}
        started = time.perf_counter()
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds)
        try:
            try:
                response = await client.post(self._endpoint("/v1/chat/completions"), headers=self._headers(), json=payload)
                response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise LLMProviderError("Hugging Face request timed out", error_type="timeout") from exc
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                error_type = "rate_limited" if status_code == 429 else "provider_unavailable" if status_code >= 500 else "provider_error"
                raise LLMProviderError("Hugging Face request failed", status_code=status_code, error_type=error_type) from exc
            except httpx.HTTPError as exc:
                raise LLMProviderError("Hugging Face network request failed", error_type="network_error") from exc
            try:
                body = response.json()
            except ValueError as exc:
                raise LLMProviderError("Hugging Face returned invalid JSON", error_type="invalid_response") from exc
            choice = body.get("choices", [{}])[0]
            text = choice.get("message", {}).get("content") or choice.get("text")
            if not isinstance(text, str) or not text.strip():
                raise LLMProviderError("Hugging Face returned no content", error_type="invalid_response")
            usage = body.get("usage") or {}
            return LLMResult(text=text.strip(), input_tokens=int(usage.get("prompt_tokens", 0) or 0), output_tokens=int(usage.get("completion_tokens", 0) or 0), model=str(body.get("model") or self.settings.hf_model), provider="huggingface", latency_ms=round((time.perf_counter() - started) * 1000), raw=body)
        finally:
            if owns_client:
                await client.aclose()

    async def health(self) -> bool:
        if not self.settings.hf_token:
            return False
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=min(self.settings.llm_timeout_seconds, 10.0))
        try:
            response = await client.get(self._endpoint("/v1/models"), headers=self._headers())
            return response.is_success
        except httpx.HTTPError:
            return False
        finally:
            if owns_client:
                await client.aclose()
