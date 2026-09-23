# Remote Qwen3-8B inference

InterviewAI does not run an 8B model on the laptop. The FastAPI service calls a remote HTTPS OpenAI-compatible endpoint. vLLM is the recommended server because it exposes `/v1/chat/completions` and `/v1/models`.

## GPU server

On a GPU machine with Docker and NVIDIA Container Toolkit:

```bash
docker run --gpus all --restart unless-stopped \
  -p 8000:8000 \
  -e VLLM_API_KEY="$LLM_API_KEY" \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen3-8B \
  --host 0.0.0.0 \
  --api-key "$LLM_API_KEY"
```

Place this behind HTTPS and a firewall/reverse proxy in production. Do not expose the GPU server without authentication. Verify it from a trusted machine:

```bash
curl -H "Authorization: Bearer $LLM_API_KEY" https://gpu.example.com/v1/models
curl -X POST https://gpu.example.com/v1/chat/completions \
  -H "Authorization: Bearer $LLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen3-8B","messages":[{"role":"user","content":"Say hello in one sentence."}],"max_tokens":32}'
```

## FastAPI configuration

Set these only in the backend environment:

```dotenv
LLM_PROVIDER=qwen_remote
LLM_BASE_URL=https://gpu.example.com
LLM_API_KEY=replace-me
LLM_MODEL=Qwen/Qwen3-8B
LLM_TIMEOUT_SECONDS=120
LLM_MAX_TOKENS=1000
LLM_TEMPERATURE=0.7
```

The browser never receives `LLM_API_KEY`. The backend calls `/v1/chat/completions`; the health probe calls `/v1/models` and does not generate text.

## Deployment notes

- Use a GPU with enough VRAM for the selected Qwen3-8B quantization and context length.
- Monitor GPU memory, request latency, 429s, 5xx responses, and token usage.
- Use a private network or allowlist the backend's egress IP.
- Set model pricing variables in the backend environment before using cost reports.
- The local laptop needs only the FastAPI dependencies; it does not download model weights.
