from app.services.llm.service import get_llm_service
from app.services.llm.structured_service import StructuredLLMService


def get_structured_llm_service() -> StructuredLLMService:
    return StructuredLLMService(get_llm_service().provider)
