import pytest

from app.schemas.ai import FinalFeedback
from app.services.llm.base import LLMResult
from app.services.llm.structured_service import StructuredLLMService
from app.services.llm.structured import parse_structured


class FakeProvider:
    def __init__(self):
        self.calls = 0

    async def generate(self, messages, **kwargs):
        _ = (messages, kwargs)
        self.calls += 1
        if self.calls == 1:
            return LLMResult(text="not json", model="test", provider="test")
        return LLMResult(text='{"question":"Explain your deployment choice.","category":"Technical","difficulty":"Intermediate","rationale":"Uses the target role context."}', model="test", provider="test")

    async def health(self):
        return True


@pytest.mark.asyncio
async def test_structured_service_retries_once_and_validates():
    provider = FakeProvider()
    result, metadata = await StructuredLLMService(provider).generate_question("role: ML Engineer")
    assert result.question.startswith("Explain")
    assert provider.calls == 2
    assert metadata.model == "test"


def test_parse_structured_accepts_json_surrounded_by_model_text():
    result = parse_structured('Thinking... ```json\n{"overall_score": 82, "summary": "Strong answer."}\n```', FinalFeedback)
    assert result.overall_score == 82
    assert result.summary == "Strong answer."


def test_final_feedback_normalizes_single_recommendation():
    result = parse_structured('{"overall_score": 82, "summary": "Strong answer.", "recommended_practice": "Practice model monitoring."}', FinalFeedback)
    assert result.recommended_practice == ["Practice model monitoring."]
