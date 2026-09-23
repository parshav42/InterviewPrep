import httpx
import pytest

from app.core.config import Settings
from app.services.llm.huggingface_provider import HuggingFaceProvider


@pytest.mark.asyncio
async def test_huggingface_provider_generates_with_openai_compatible_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer hf_test_token"
        body = request.read()
        assert b"Qwen/Qwen3-4B-Instruct-2507:fastest" in body
        return httpx.Response(200, json={"model": "Qwen/Qwen3-4B-Instruct-2507:fastest", "choices": [{"message": {"content": "Hello from Hugging Face"}}], "usage": {"prompt_tokens": 4, "completion_tokens": 5}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(hf_token="hf_test_token", hf_base_url="https://router.huggingface.co", hf_model="Qwen/Qwen3-4B-Instruct-2507:fastest")
    result = await HuggingFaceProvider(settings, client).generate([{"role": "user", "content": "Hello"}])
    await client.aclose()
    assert result.text == "Hello from Hugging Face"
    assert result.provider == "huggingface"
    assert result.input_tokens == 4
    assert result.output_tokens == 5


@pytest.mark.asyncio
async def test_huggingface_health_requires_token():
    provider = HuggingFaceProvider(Settings(hf_token=None))
    assert await provider.health() is False
