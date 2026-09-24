from datetime import datetime, timezone
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import current_user
from app.db.database import get_db
from app.db.models.domain import Answer, Feedback, Interview, InterviewQuestion, InterviewStatus, Job, Resume
from app.db.models.user import User
from app.schemas.domain import AnswerCreate, AnswerResponse, FeedbackResponse, InterviewCreate, InterviewResponse, QuestionResponse
from app.schemas.ai import FinalFeedback
from app.services.llm.factory import get_structured_llm_service
from app.services.llm.qwen_provider import LLMProviderError
from app.services.usage_service import record_ai_usage
from app.middleware.llm_rate_limit import check_llm_rate_limit
from app.core.config import get_settings
from app.services.credit_service import debit_interviews

router = APIRouter(prefix="/api/interviews", tags=["interviews"])
MIN_ANSWER_LENGTH = 10


def normalized_text(value: str) -> str:
    return " ".join("".join(character.lower() if character.isalnum() else " " for character in value).split())


def owned_interview(interview_id: UUID, user_id: UUID, db: Session) -> Interview:
    interview = db.scalar(select(Interview).where(Interview.id == interview_id, Interview.user_id == user_id))
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    return interview


def fallback_final_feedback(evaluations: list[tuple[Feedback, Answer, InterviewQuestion]] | None) -> FinalFeedback:
    if evaluations:
        score_values = []
        for feedback, _, _ in evaluations:
            values = [feedback.technical_score, feedback.communication_score, feedback.relevance_score, feedback.clarity_score, feedback.confidence_score]
            score_values.append(sum(values) / len(values))
        overall_score = round(sum(score_values) / len(score_values), 1)
        summary = "Final feedback could not be generated because the analysis service was unavailable. The results below reflect the answer evaluations captured during the interview."
    else:
        overall_score = 0.0
        summary = "Final feedback could not be generated because the analysis service was unavailable."
    return FinalFeedback(overall_score=overall_score, summary=summary, strengths=[], weaknesses=[], recommended_practice=[])


def classify_answer(text: str) -> str:
    cleaned = " ".join(str(text or "").strip().split())
    normalized = cleaned.lower()
    if not cleaned:
        return "empty"
    skip_tokens = ("next question", "next", "skip", "move on", "pass", "can we move on")
    give_up_tokens = ("i don't know", "i do not know", "dont know", "don't know", "no idea", "not sure", "idk", "don't remember", "do not remember")
    if any(token in normalized for token in skip_tokens):
        return "skip"
    if len(cleaned.split()) < 5 and any(token in normalized for token in give_up_tokens):
        return "give_up"
    if len(cleaned.split()) < 5:
        return "short"
    if any(token in normalized for token in give_up_tokens):
        return "give_up"
    return "normal"


def classify_answer_quality(answer_text: str) -> str:
    cleaned = " ".join(str(answer_text or "").strip().split())
    normalized = cleaned.lower()
    if not cleaned:
        return "vague"
    filler_patterns = ("i don't know", "i do not know", "not sure", "no idea", "unsure", "can't answer", "cannot answer")
    if any(pattern in normalized for pattern in filler_patterns):
        return "vague"
    emotional_patterns = ("frustrated", "annoyed", "nervous", "upset", "angry", "confused", "stressed", "panicked", "overwhelmed", "lost", "sorry", "feels bad", "feeling bad", "bad experience")
    if any(pattern in normalized for pattern in emotional_patterns):
        return "emotional"
    if len(cleaned.split()) < 10:
        return "short"
    strong_keywords = ("project", "design", "metrics", "team", "customer", "experience", "implementation", "architecture", "analysis", "leadership", "python", "performance", "data", "resume", "process", "impact", "outcome", "measurable", "improve", "tradeoff", "problem", "solution")
    if len(cleaned.split()) >= 8 and any(keyword in normalized for keyword in strong_keywords):
        return "strong"
    return "normal"


def _jaccard_similarity(left: str, right: str) -> float:
    left_tokens = {token for token in normalized_text(left).split() if token}
    right_tokens = {token for token in normalized_text(right).split() if token}
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    union = left_tokens | right_tokens
    if not union:
        return 0.0
    intersection = left_tokens & right_tokens
    return len(intersection) / len(union)


def _unique_next_question_text(interview: Interview, db: Session, base_question_text: str) -> str:
    question_history = db.scalars(select(InterviewQuestion).where(InterviewQuestion.interview_id == interview.id).order_by(InterviewQuestion.question_number.desc()).limit(3)).all()
    for previous in question_history:
        if previous.question_text and _jaccard_similarity(base_question_text, previous.question_text) > 0.8:
            return "What would you improve or do differently based on that experience?"
    return base_question_text


def interviewer_context(interview: Interview, user: User, db: Session, instruction: str) -> str:
    resume = db.get(Resume, interview.resume_id) if interview.resume_id else None
    job = db.get(Job, interview.job_id) if interview.job_id else None
    history = []
    questions = db.scalars(select(InterviewQuestion).where(InterviewQuestion.interview_id == interview.id).order_by(InterviewQuestion.question_number)).all()
    last_quality = "none"
    for item in questions:
        answer = db.scalar(select(Answer).where(Answer.question_id == item.id).order_by(Answer.answered_at.desc()))
        history.append(f"Q{item.question_number}: {item.question_text}\nA{item.question_number}: {answer.answer_text if answer else '[not answered]'}")
        if answer and answer.quality_signal:
            last_quality = answer.quality_signal
    return (
        f"Candidate name: {user.full_name}\n"
        f"Role: {job.title if job else 'Target role'}\n"
        f"Resume summary: {(resume.parsed_profile_json if resume else {})}\n"
        f"Job description: {(job.job_description if job else '')[:12000]}\n"
        f"Job analysis: {(job.parsed_analysis_json if job else {})}\n"
        f"Interview type: {interview.interview_type}\n"
        f"Difficulty: {interview.difficulty}\n"
        f"Last answer quality: {last_quality}\n"
        f"Previous questions and answers:\n{'\n'.join(history) or '[none]'}\n"
        f"Current question number: {len(questions) + 1}\n"
        f"Maximum questions: {get_settings().max_interview_questions}\n"
        f"Instruction: Generate the next thing the interviewer should say. {instruction}"
    )


@router.post("", response_model=InterviewResponse, status_code=201)
def create_interview(payload: InterviewCreate, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> Interview:
    if not payload.resume_id:
        raise HTTPException(status_code=422, detail="A resume is required to start an interview")
    if not db.scalar(select(Resume).where(Resume.id == payload.resume_id, Resume.user_id == user.id, Resume.deleted_at.is_(None))):
        raise HTTPException(status_code=404, detail="Resume not found")
    if payload.job_id and not db.scalar(select(Job).where(Job.id == payload.job_id, Job.user_id == user.id)):
        raise HTTPException(status_code=404, detail="Job not found")
    interview = Interview(user_id=user.id, **payload.model_dump())
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview


@router.get("")
def list_interviews(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> list[dict]:
    interviews: list[dict] = []
    for interview in db.scalars(select(Interview).where(Interview.user_id == user.id).order_by(Interview.created_at.desc())).all():
        score = interview.overall_score
        if score is None:
            score_row = db.scalar(select(Feedback).join(Answer, Feedback.answer_id == Answer.id).join(InterviewQuestion, Answer.question_id == InterviewQuestion.id).where(InterviewQuestion.interview_id == interview.id).order_by(Feedback.created_at.desc()).limit(1))
            if score_row is not None:
                score = (score_row.technical_score + score_row.communication_score + score_row.relevance_score + score_row.clarity_score + score_row.confidence_score) / 5
        interviews.append({
            "id": interview.id,
            "user_id": interview.user_id,
            "resume_id": interview.resume_id,
            "job_id": interview.job_id,
            "interview_type": interview.interview_type,
            "difficulty": interview.difficulty,
            "duration_target_minutes": interview.duration_target_minutes,
            "started_at": interview.started_at,
            "ended_at": interview.ended_at,
            "duration_seconds": interview.actual_duration_seconds,
            "score": score,
            "created_at": interview.created_at,
        })
    return interviews


@router.get("/{interview_id}", response_model=InterviewResponse)
def get_interview(interview_id: UUID, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> Interview:
    return owned_interview(interview_id, user.id, db)


@router.post("/{interview_id}/start", response_model=InterviewResponse, dependencies=[Depends(check_llm_rate_limit)])
async def start_interview(interview_id: UUID, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> Interview:
    interview = owned_interview(interview_id, user.id, db)
    if interview.status not in (InterviewStatus.CREATED, InterviewStatus.IN_PROGRESS):
        raise HTTPException(status_code=409, detail="Interview cannot be started")
    interview.status = InterviewStatus.IN_PROGRESS
    try:
        debit_interviews(db, user.id, 1, str(interview.id))
    except HTTPException as exc:
        if exc.status_code == status.HTTP_402_PAYMENT_REQUIRED:
            return JSONResponse(status_code=402, content={"detail": "no_credits", "message": "You've used all your interviews. Buy more to continue."})
        raise
    interview.started_at = interview.started_at or datetime.now(timezone.utc)
    if not db.scalar(select(InterviewQuestion).where(InterviewQuestion.interview_id == interview.id)):
        try:
            generated, result = await get_structured_llm_service().generate_question(interviewer_context(interview, user, db, "This is the opening. Greet the candidate and make them comfortable, then ask the first question."))
        except (ValueError, LLMProviderError) as exc:
            raise HTTPException(status_code=502, detail="Question generation is temporarily unavailable") from exc
        question = InterviewQuestion(interview_id=interview.id, question_number=1, question_text=generated.question, category=generated.category, difficulty=generated.difficulty)
        db.add(question)
    db.commit()
    if 'result' in locals():
        record_ai_usage(db, user_id=user.id, interview_id=interview.id, request_type="question_generation", result=result)
    db.refresh(interview)
    return interview


@router.post("/{interview_id}/answer", response_model=AnswerResponse, dependencies=[Depends(check_llm_rate_limit)])
async def submit_answer(interview_id: UUID, payload: AnswerCreate, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> AnswerResponse:
    interview = owned_interview(interview_id, user.id, db)
    question = db.scalar(select(InterviewQuestion).where(InterviewQuestion.id == payload.question_id, InterviewQuestion.interview_id == interview.id))
    if interview.status != InterviewStatus.IN_PROGRESS or not question:
        raise HTTPException(status_code=409, detail="Interview question is not active")
    answer_text = payload.answer_text.strip() if payload.answer_text is not None else ""
    if payload.answer_text is not None and payload.answer_text.strip() == "" and not getattr(payload, "skipped", False):
        raise HTTPException(status_code=422, detail="Please provide a substantive answer before continuing.")
    if interview.started_at:
        started_at = interview.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - started_at).total_seconds() >= interview.duration_target_minutes * 60:
            raise HTTPException(status_code=409, detail="Interview duration has expired")
    existing_feedback = db.scalar(select(Feedback).join(Answer, Feedback.answer_id == Answer.id).where(Answer.question_id == question.id, Answer.user_id == user.id))
    if existing_feedback:
        return existing_feedback

    skipped = bool(getattr(payload, "skipped", False))
    classification = classify_answer(answer_text)
    if skipped or classification == "skip":
        answer = Answer(question_id=question.id, user_id=user.id, answer_text=answer_text or "Skipped by candidate.", response_duration_seconds=payload.response_duration_seconds, quality_signal="skipped", skipped=True)
        db.add(answer)
        db.flush()
        next_number = (db.scalar(select(InterviewQuestion.question_number).where(InterviewQuestion.interview_id == interview.id).order_by(InterviewQuestion.question_number.desc()).limit(1)) or 0) + 1
        followup_result = None
        final_result = None
        followup_text = "What would you improve or do differently based on that experience?"
        followup_category = "Behavioral"
        followup_difficulty = interview.difficulty
        if next_number <= get_settings().max_interview_questions:
            try:
                followup, followup_result = await get_structured_llm_service().generate_question(interviewer_context(interview, user, db, "The candidate skipped or gave a very weak answer. Acknowledge briefly, then move to a different, relevant question without repeating the same question."))
                followup_text = _unique_next_question_text(interview, db, followup.question)
                followup_category = followup.category
                followup_difficulty = followup.difficulty
            except (ValueError, LLMProviderError):
                followup_text = _unique_next_question_text(interview, db, followup_text)
            db.add(InterviewQuestion(interview_id=interview.id, question_number=next_number, question_text=followup_text, category=followup_category, difficulty=followup_difficulty))
            db.commit()
            db.refresh(answer)
            next_question = db.scalar(select(InterviewQuestion).where(InterviewQuestion.interview_id == interview.id, ~select(Answer.id).where(Answer.question_id == InterviewQuestion.id).exists()).order_by(InterviewQuestion.question_number.desc()))
            response = AnswerResponse.model_construct(
                id=answer.id,
                answer_id=answer.id,
                technical_score=0,
                communication_score=0,
                relevance_score=0,
                clarity_score=0,
                confidence_score=0,
                strengths=[],
                weaknesses=[],
                suggestions=[],
                ai_feedback="The candidate skipped this question. Moving to a new one.",
                created_at=answer.answered_at,
                next_question=next_question,
                is_complete=False,
                feedback_url=None,
                closing_text=None,
            )
            return response

    if len(answer_text) < MIN_ANSWER_LENGTH and classification in {"short", "empty"}:
        answer = Answer(question_id=question.id, user_id=user.id, answer_text=answer_text or "No answer provided.", response_duration_seconds=payload.response_duration_seconds, quality_signal=classification, skipped=(classification == "empty"))
        db.add(answer)
        db.flush()
        if classification == "empty":
            followup_text = "No rush — take your time. If you’d rather, tell me about a project or a time you solved a problem."
            followup_category = "Behavioral"
            followup_difficulty = interview.difficulty
            next_number = (db.scalar(select(InterviewQuestion.question_number).where(InterviewQuestion.interview_id == interview.id).order_by(InterviewQuestion.question_number.desc()).limit(1)) or 0) + 1
            db.add(InterviewQuestion(interview_id=interview.id, question_number=next_number, question_text=_unique_next_question_text(interview, db, followup_text), category=followup_category, difficulty=followup_difficulty))
            db.commit()
            next_question = db.scalar(select(InterviewQuestion).where(InterviewQuestion.interview_id == interview.id, InterviewQuestion.question_number == next_number))
            response = AnswerResponse.model_construct(
                id=answer.id,
                answer_id=answer.id,
                technical_score=0,
                communication_score=0,
                relevance_score=0,
                clarity_score=0,
                confidence_score=0,
                strengths=[],
                weaknesses=[],
                suggestions=[],
                ai_feedback="No answer was provided; moving to a different question.",
                created_at=answer.answered_at,
                next_question=next_question,
                is_complete=False,
                feedback_url=None,
                closing_text=None,
            )
            return response

    if normalized_text(answer_text) == normalized_text(question.question_text):
        raise HTTPException(status_code=422, detail="Please provide a substantive answer before continuing.")

    quality_signal = classify_answer_quality(answer_text)
    resume = db.get(Resume, interview.resume_id) if interview.resume_id else None
    job = db.get(Job, interview.job_id) if interview.job_id else None
    interview_context = interviewer_context(interview, user, db, "Evaluate the candidate's answer.")
    try:
        evaluation, result = await get_structured_llm_service().evaluate_answer(question.question_text, answer_text, interview_context)
    except (ValueError, LLMProviderError) as exc:
        raise HTTPException(status_code=502, detail="Answer evaluation is temporarily unavailable") from exc
    answer = Answer(question_id=question.id, user_id=user.id, answer_text=answer_text, response_duration_seconds=payload.response_duration_seconds, quality_signal=quality_signal)
    db.add(answer)
    db.flush()
    feedback = Feedback(answer_id=answer.id, technical_score=evaluation.technical_accuracy, communication_score=evaluation.communication, relevance_score=evaluation.relevance, clarity_score=evaluation.depth, confidence_score=evaluation.problem_solving, strengths=evaluation.strengths, weaknesses=evaluation.weaknesses, suggestions=[evaluation.recommended_followup] if evaluation.recommended_followup else [], ai_feedback=evaluation.feedback)
    db.add(feedback)
    next_number = (db.scalar(select(InterviewQuestion.question_number).where(InterviewQuestion.interview_id == interview.id).order_by(InterviewQuestion.question_number.desc()).limit(1)) or 0) + 1
    followup_result = None
    final_result = None
    if next_number <= get_settings().max_interview_questions:
        try:
            followup, followup_result = await get_structured_llm_service().generate_question(interviewer_context(interview, user, db, "Acknowledge the previous answer briefly, then ask the next question."))
            followup_text = _unique_next_question_text(interview, db, followup.question)
            followup_category = followup.category
            followup_difficulty = followup.difficulty
        except (ValueError, LLMProviderError):
            followup_text = _unique_next_question_text(interview, db, "What would you improve or do differently based on that experience?")
            followup_category = "Behavioral"
            followup_difficulty = interview.difficulty
        db.add(InterviewQuestion(interview_id=interview.id, question_number=next_number, question_text=followup_text, category=followup_category, difficulty=followup_difficulty))
    else:
        evaluations = db.execute(select(Feedback, Answer, InterviewQuestion).join(Answer, Feedback.answer_id == Answer.id).join(InterviewQuestion, Answer.question_id == InterviewQuestion.id).where(InterviewQuestion.interview_id == interview.id)).all()
        evaluation_payload = json.dumps([{"question": item.question_text, "answer": item_answer.answer_text, "feedback": item_feedback.ai_feedback, "scores": {"technical": item_feedback.technical_score, "communication": item_feedback.communication_score, "relevance": item_feedback.relevance_score, "clarity": item_feedback.clarity_score, "confidence": item_feedback.confidence_score}} for item_feedback, item_answer, item in evaluations])
        try:
            final_feedback, final_result = await get_structured_llm_service().generate_final_feedback(interview_context, evaluation_payload)
        except (ValueError, LLMProviderError):
            final_feedback = fallback_final_feedback(evaluations)
        interview.ended_at = datetime.now(timezone.utc)
        interview.status = InterviewStatus.COMPLETED
        interview.final_feedback_json = final_feedback.model_dump()
        interview.overall_score = final_feedback.overall_score
        if interview.started_at:
            started_at = interview.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            interview.actual_duration_seconds = max(0, int((interview.ended_at - started_at).total_seconds()))
    db.commit()
    record_ai_usage(db, user_id=user.id, interview_id=interview.id, request_type="answer_evaluation", result=result)
    if followup_result:
        record_ai_usage(db, user_id=user.id, interview_id=interview.id, request_type="followup_generation", result=followup_result)
    if final_result:
        record_ai_usage(db, user_id=user.id, interview_id=interview.id, request_type="final_feedback", result=final_result)
    db.refresh(feedback)
    next_question = None if interview.status == InterviewStatus.COMPLETED else db.scalar(select(InterviewQuestion).where(InterviewQuestion.interview_id == interview.id, ~select(Answer.id).where(Answer.question_id == InterviewQuestion.id).exists()).order_by(InterviewQuestion.question_number.desc()))
    response = AnswerResponse.model_validate(feedback)
    response.next_question = next_question
    response.is_complete = interview.status == InterviewStatus.COMPLETED
    response.feedback_url = f"/api/interviews/{interview.id}/feedback" if response.is_complete else None
    response.closing_text = "That wraps up our interview. Thank you for your time - you'll see feedback on your screen shortly." if response.is_complete else None
    return response


@router.get("/{interview_id}/questions/current", response_model=QuestionResponse, status_code=status.HTTP_200_OK)
def current_question(interview_id: UUID, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> InterviewQuestion | Response:
    interview = owned_interview(interview_id, user.id, db)
    question = db.scalar(select(InterviewQuestion).where(InterviewQuestion.interview_id == interview_id, ~select(Answer.id).where(Answer.question_id == InterviewQuestion.id).exists()).order_by(InterviewQuestion.question_number.desc()))
    if not question:
        if interview.status == InterviewStatus.COMPLETED:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        raise HTTPException(status_code=404, detail="No interview question is available")
    return question


def _normalize_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _safe_duration_seconds(started_at: datetime | None, ended_at: datetime | None) -> int | None:
    start = _normalize_utc_datetime(started_at)
    end = _normalize_utc_datetime(ended_at)
    if start is None or end is None:
        return None
    return max(0, int((end - start).total_seconds()))


@router.post("/{interview_id}/end", response_model=InterviewResponse)
async def end_interview(interview_id: UUID, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)], abandon: bool = False) -> Interview:
    try:
        interview = owned_interview(interview_id, user.id, db)
        status_value = interview.status.value if hasattr(interview.status, "value") else str(interview.status)
        if status_value in {"COMPLETED", "ABANDONED", "CANCELLED"}:
            if interview.ended_at is not None and interview.started_at is not None:
                interview.actual_duration_seconds = _safe_duration_seconds(interview.started_at, interview.ended_at)
            elif interview.actual_duration_seconds is None:
                interview.actual_duration_seconds = None
            db.refresh(interview)
            return interview
        if interview.status not in (InterviewStatus.IN_PROGRESS, InterviewStatus.CREATED):
            raise HTTPException(status_code=409, detail="Interview is already finished")
        if abandon:
            interview.status = InterviewStatus.IN_PROGRESS
            interview.ended_at = None
            db.commit()
            db.refresh(interview)
            return interview
        evaluations = db.execute(select(Feedback, Answer, InterviewQuestion).join(Answer, Feedback.answer_id == Answer.id).join(InterviewQuestion, Answer.question_id == InterviewQuestion.id).where(InterviewQuestion.interview_id == interview.id)).all()
        resume = db.get(Resume, interview.resume_id) if interview.resume_id else None
        job = db.get(Job, interview.job_id) if interview.job_id else None
        interview_context = f"Role: {job.title if job else 'Target role'}\nInterview type: {interview.interview_type}\nDifficulty: {interview.difficulty}\nCandidate profile: {(resume.parsed_profile_json if resume else {})}\nJob analysis: {(job.parsed_analysis_json if job else {})}"
        evaluation_payload = json.dumps([{"question": question.question_text, "answer": answer.answer_text, "feedback": feedback.ai_feedback, "scores": {"technical": feedback.technical_score, "communication": feedback.communication_score, "relevance": feedback.relevance_score, "clarity": feedback.clarity_score, "confidence": feedback.confidence_score}} for feedback, answer, question in evaluations])
        try:
            final_feedback, final_result = await get_structured_llm_service().generate_final_feedback(interview_context, evaluation_payload)
        except (ValueError, LLMProviderError) as exc:
            logger = __import__("logging").getLogger(__name__)
            logger.exception("Final interview feedback generation failed")
            final_feedback = fallback_final_feedback(evaluations)
            final_result = None
        interview.ended_at = datetime.now(timezone.utc)
        interview.status = InterviewStatus.COMPLETED
        interview.final_feedback_json = final_feedback.model_dump()
        interview.actual_duration_seconds = _safe_duration_seconds(interview.started_at, interview.ended_at)
        interview.overall_score = final_feedback.overall_score
        db.commit()
        record_ai_usage(db, user_id=user.id, interview_id=interview.id, request_type="final_feedback", result=final_result)
        db.refresh(interview)
        return interview
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to end interview: {exc}") from exc


@router.get("/{interview_id}/feedback", response_model=list[FeedbackResponse])
def interview_feedback(interview_id: UUID, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> list[Feedback]:
    owned_interview(interview_id, user.id, db)
    return list(db.scalars(select(Feedback).join(Answer, Feedback.answer_id == Answer.id).join(InterviewQuestion, Answer.question_id == InterviewQuestion.id).where(InterviewQuestion.interview_id == interview_id)))


@router.delete("/{interview_id}", status_code=204)
def delete_interview(interview_id: UUID, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> None:
    interview = owned_interview(interview_id, user.id, db)
    db.delete(interview)
    db.commit()
