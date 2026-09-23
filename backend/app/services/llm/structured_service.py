from typing import Any

from app.schemas.ai import AnswerEvaluation, CandidateProfile, FinalFeedback, JobAnalysis, QuestionOutput
from app.services.llm.base import LLMProvider, LLMResult
from app.services.llm.structured import parse_structured


class StructuredLLMService:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def _structured(self, messages: list[dict[str, str]], schema: type[Any]) -> tuple[Any, LLMResult]:
        prompt = messages
        last_error: ValueError | None = None
        for attempt in range(3):
            result = await self.provider.generate(prompt, response_format={"type": "json_object"})
            try:
                return parse_structured(result.text, schema), result
            except ValueError as exc:
                last_error = exc
                prompt = messages + [{"role": "user", "content": "Return exactly one valid JSON object matching the requested schema. Do not include reasoning, prose, markdown, or code fences. Array fields must be JSON arrays, even when there is only one item."}]
        raise last_error or ValueError("LLM response did not match the expected schema")

    async def analyze_resume(self, text: str) -> tuple[CandidateProfile, LLMResult]:
        return await self._structured([{"role": "system", "content": "Extract a candidate profile as JSON with name, education, skills, programming_languages, frameworks, projects, internships, experience, certifications, achievements."}, {"role": "user", "content": text[:30000]}], CandidateProfile)

    async def analyze_job_description(self, title: str, description: str) -> tuple[JobAnalysis, LLMResult]:
        return await self._structured([{"role": "system", "content": "Extract job requirements as JSON with required_skills, preferred_skills, technical_topics, responsibilities, experience_requirements, interview_topics."}, {"role": "user", "content": f"Title: {title}\nDescription: {description[:30000]}"}], JobAnalysis)

    async def generate_question(self, context: str) -> tuple[QuestionOutput, LLMResult]:
        return await self._structured([{"role": "system", "content": "Generate one personalized adaptive interview question as JSON with question, category, difficulty, rationale."}, {"role": "user", "content": context[:40000]}], QuestionOutput)

    async def evaluate_answer(self, question: str, answer: str, context: str) -> tuple[AnswerEvaluation, LLMResult]:
        return await self._structured([{"role": "system", "content": "Evaluate the answer as JSON. All scores must be numbers from 0 to 100. Include technical_accuracy, communication, depth, relevance, problem_solving, overall_score, strengths, weaknesses, feedback, recommended_followup."}, {"role": "user", "content": f"Context: {context[:18000]}\nQuestion: {question}\nAnswer: {answer[:12000]}"}], AnswerEvaluation)

    async def generate_final_feedback(self, interview_context: str, evaluations: str) -> tuple[FinalFeedback, LLMResult]:
        return await self._structured([{"role": "system", "content": "Summarize the completed interview as JSON with overall_score from 0 to 100, summary, strengths, weaknesses, and recommended_practice."}, {"role": "user", "content": f"Interview context: {interview_context[:18000]}\nEvaluations: {evaluations[:18000]}"}], FinalFeedback)
