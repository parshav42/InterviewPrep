from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.domain import AIUsage
from app.services.llm.base import LLMResult


def record_ai_usage(db: Session, *, user_id, interview_id, request_type: str, result: LLMResult, status: str = "success", error_type: str | None = None) -> None:
    settings = get_settings()
    estimated_cost = result.input_tokens / 1_000_000 * settings.llm_input_cost_per_1m + result.output_tokens / 1_000_000 * settings.llm_output_cost_per_1m
    db.add(AIUsage(user_id=user_id, interview_id=interview_id, provider=result.provider, model=result.model, request_type=request_type, input_tokens=result.input_tokens, output_tokens=result.output_tokens, estimated_cost=estimated_cost, latency_ms=result.latency_ms, status=status, error_type=error_type))
    db.commit()
