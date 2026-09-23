from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = "unknown"
    provider: str = "unknown"
    latency_ms: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    async def generate(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResult: ...
    async def health(self) -> bool: ...
