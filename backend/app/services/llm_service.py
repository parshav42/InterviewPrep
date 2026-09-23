"""Backward-compatible import surface for the provider package."""

from app.services.llm.mock_provider import MockLLMProvider
from app.services.llm.service import get_llm_service


from dataclasses import dataclass
from typing import Protocol


class LLMProvider(Protocol):
    def generate_question(self, *, role: str, resume_text: str, job_description: str, interview_type: str, difficulty: str, previous_answer: str | None = None) -> str: ...
    def analyze_answer(self, *, question: str, answer: str) -> dict: ...
    def generate_feedback(self, *, answers: list[str]) -> str: ...


@dataclass
class MockLLMProvider:
    """Deterministic development provider; replace with an adapter without changing API routes."""

    def generate_question(self, **kwargs: str | None) -> str:
        if kwargs.get("previous_answer"):
            return "What trade-off would you revisit in that approach?"
        return "Tell me about a project that best demonstrates your experience for this role."

    def analyze_answer(self, *, question: str, answer: str) -> dict:
        _ = question
        score = min(95.0, max(45.0, 60.0 + len(answer.split()) / 2))
        return {"technical_score": score, "communication_score": score, "relevance_score": score, "clarity_score": score, "confidence_score": score, "strengths": ["You connected your answer to practical experience."], "weaknesses": ["Add a measurable outcome where possible."], "suggestions": ["Use a concise situation, action, result structure."], "ai_feedback": "Good foundation. Make the impact and decision criteria more explicit."}

    def generate_feedback(self, *, answers: list[str]) -> str:
        _ = answers
        return "Your answers showed a solid foundation. Continue practicing structured responses."


def get_llm_provider() -> LLMProvider:
    return get_llm_service().provider


__all__ = ["MockLLMProvider", "get_llm_provider"]
