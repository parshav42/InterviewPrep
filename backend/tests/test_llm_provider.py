import httpx
import pytest

from app.core.config import Settings
from app.services.llm.qwen_provider import LLMProviderError, QwenProvider


@pytest.mark.asyncio
async def test_qwen_provider_normalizes_openai_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(200, json={"model": "Qwen/Qwen3-8B", "choices": [{"message": {"content": "Hello from remote Qwen"}}], "usage": {"prompt_tokens": 12, "completion_tokens": 5}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = QwenProvider(Settings(llm_base_url="https://gpu.example.com", llm_api_key="test-key"), client)
    result = await provider.generate([{"role": "user", "content": "Hello"}])
    await client.aclose()
    assert result.text == "Hello from remote Qwen"
    assert result.input_tokens == 12
    assert result.output_tokens == 5


@pytest.mark.asyncio
async def test_qwen_provider_controls_timeout_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = QwenProvider(Settings(llm_base_url="https://gpu.example.com"), client)
    with pytest.raises(LLMProviderError, match="timed out"):
        await provider.generate([])
    await client.aclose()
