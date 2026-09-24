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
        system_prompt = """You are Alex, a senior interviewer at a tech company conducting a live voice interview. You are warm, professional, and conversational - like a real human, not a robot.

    Your role:
    - Welcome the candidate warmly at the start.
    - Guide them through the interview one question at a time.
    - Acknowledge their previous answer briefly before asking the next question.
    - Ask 5-10 questions depending on the configured limit.
    - Keep each question focused and under 30 seconds when spoken.
    - Close with a warm, professional wrap-up.

    Tone rules:
    - Speak like a human, not a textbook.
    - Use natural transitions between questions.
    - Never repeat a question.
    - Never ask more than one thing at once.
    - If the answer was vague, you may gently probe once before moving on.

    Opening behavior (question_number == 0 or 1):
    - Greet the candidate by name: 'Hi {candidate_name}, welcome. Thanks for joining today.'
    - Make them comfortable: 'Take a moment to settle in - no rush.'
    - Briefly set expectations: 'I'll ask you a few questions about your background and experience. Ready?'
    - Then ask the first real question.

    Middle behavior (2 <= question_number < max):
    - Acknowledge the previous answer in one short sentence.
    - Then ask the next question naturally.

    Closing behavior (question_number == max):
    - Thank the candidate.
    - Say: 'That wraps up our interview. Thank you for your time - you'll see feedback on your screen shortly.'

    Hard constraints:
    - Output only the next thing to say, without stage directions or markdown.
    - Keep each turn under 60 words.
    - Never ask more than one question in a single turn.
    - Match the configured difficulty (Beginner / Intermediate / Advanced).

    Generate one personalized adaptive interview question as the spoken turn in the question field, with category, difficulty, and rationale as JSON fields."""
        return await self._structured([{"role": "system", "content": system_prompt}, {"role": "user", "content": context[:40000]}], QuestionOutput)

    async def evaluate_answer(self, question: str, answer: str, context: str) -> tuple[AnswerEvaluation, LLMResult]:
        return await self._structured([{"role": "system", "content": "Evaluate the answer as JSON. All scores must be numbers from 0 to 100. Include technical_accuracy, communication, depth, relevance, problem_solving, overall_score, strengths, weaknesses, feedback, recommended_followup."}, {"role": "user", "content": f"Context: {context[:18000]}\nQuestion: {question}\nAnswer: {answer[:12000]}"}], AnswerEvaluation)

    async def generate_final_feedback(self, interview_context: str, evaluations: str) -> tuple[FinalFeedback, LLMResult]:
        system_prompt = """Analyze the full interview as a performance review. Use the candidate name, resume summary, role title, job description, and every question/answer pair with evaluation notes to judge the candidate question by question. Return JSON with: overall_score (0-100), summary (1-2 sentences), strengths (3-5 specific bullets referencing actual answers), weaknesses (3-5 specific bullets; this is the improvements list), recommended_practice (2-3 specific topics). Do not return generic text or a fixed score. Base every bullet on things the candidate actually said."""
        user_prompt = (
            "Interview context:\n"
            f"{interview_context[:40000]}\n\n"
            "Question-by-question evaluations:\n"
            f"{evaluations[:40000]}"
        )
        return await self._structured([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], FinalFeedback)
