import time
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.services.llm.base import LLMResult


class LLMProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, error_type: str = "provider_error") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type


class QwenProvider:
    """Remote OpenAI-compatible adapter for vLLM/TGI gateways serving Qwen3-8B."""

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    def _endpoint(self, path: str) -> str:
        base_url = (self.settings.llm_base_url or "").rstrip("/")
        if not base_url:
            raise LLMProviderError("Remote LLM endpoint is not configured", error_type="not_configured")
        return f"{base_url}{path}"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"
        return headers

    async def generate(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResult:
        payload = {"model": self.settings.llm_model, "messages": messages, "temperature": self.settings.llm_temperature, "max_tokens": self.settings.llm_max_tokens, **kwargs}
        started = time.perf_counter()
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds)
        try:
            try:
                response = await client.post(self._endpoint("/v1/chat/completions"), headers=self._headers(), json=payload)
                response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise LLMProviderError("Remote LLM request timed out", error_type="timeout") from exc
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                error_type = "rate_limited" if status_code == 429 else "provider_unavailable" if status_code >= 500 else "provider_error"
                raise LLMProviderError("Remote LLM request failed", status_code=status_code, error_type=error_type) from exc
            except httpx.HTTPError as exc:
                raise LLMProviderError("Remote LLM network request failed", error_type="network_error") from exc
            body = response.json()
            choice = body.get("choices", [{}])[0]
            text = choice.get("message", {}).get("content") or choice.get("text")
            if not isinstance(text, str) or not text.strip():
                raise LLMProviderError("Remote LLM returned no content", error_type="invalid_response")
            usage = body.get("usage") or {}
            return LLMResult(text=text.strip(), input_tokens=int(usage.get("prompt_tokens", 0) or 0), output_tokens=int(usage.get("completion_tokens", 0) or 0), model=str(body.get("model") or self.settings.llm_model), provider="qwen_remote", latency_ms=round((time.perf_counter() - started) * 1000), raw=body)
        except ValueError as exc:
            raise LLMProviderError("Remote LLM returned invalid JSON", error_type="invalid_response") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def health(self) -> bool:
        try:
            owns_client = self._client is None
            client = self._client or httpx.AsyncClient(timeout=min(self.settings.llm_timeout_seconds, 10.0))
            response = await client.get(self._endpoint("/v1/models"), headers=self._headers())
            healthy = response.is_success
            if owns_client:
                await client.aclose()
            return healthy
        except (LLMProviderError, httpx.HTTPError):
            return False
