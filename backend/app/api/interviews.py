from datetime import datetime, timezone
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
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
from app.services.credit_service import debit_minutes

router = APIRouter(prefix="/api/interviews", tags=["interviews"])
MIN_ANSWER_LENGTH = 10


def normalized_text(value: str) -> str:
    return " ".join("".join(character.lower() if character.isalnum() else " " for character in value).split())


def owned_interview(interview_id: UUID, user_id: UUID, db: Session) -> Interview:
    interview = db.scalar(select(Interview).where(Interview.id == interview_id, Interview.user_id == user_id))
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    return interview


def interviewer_context(interview: Interview, user: User, db: Session, instruction: str) -> str:
    resume = db.get(Resume, interview.resume_id) if interview.resume_id else None
    job = db.get(Job, interview.job_id) if interview.job_id else None
    history = []
    questions = db.scalars(select(InterviewQuestion).where(InterviewQuestion.interview_id == interview.id).order_by(InterviewQuestion.question_number)).all()
    for item in questions:
        answer = db.scalar(select(Answer).where(Answer.question_id == item.id))
        history.append(f"Q{item.question_number}: {item.question_text}\nA{item.question_number}: {answer.answer_text if answer else '[not answered]'}")
    return (
        f"Candidate name: {user.full_name}\n"
        f"Role: {job.title if job else 'Target role'}\n"
        f"Resume summary: {(resume.parsed_profile_json if resume else {})}\n"
        f"Job description: {(job.job_description if job else '')[:12000]}\n"
        f"Job analysis: {(job.parsed_analysis_json if job else {})}\n"
        f"Interview type: {interview.interview_type}\n"
        f"Difficulty: {interview.difficulty}\n"
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


@router.get("", response_model=list[InterviewResponse])
def list_interviews(user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> list[Interview]:
    return list(db.scalars(select(Interview).where(Interview.user_id == user.id).order_by(Interview.created_at.desc())))


@router.get("/{interview_id}", response_model=InterviewResponse)
def get_interview(interview_id: UUID, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> Interview:
    return owned_interview(interview_id, user.id, db)


@router.post("/{interview_id}/start", response_model=InterviewResponse, dependencies=[Depends(check_llm_rate_limit)])
async def start_interview(interview_id: UUID, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> Interview:
    interview = owned_interview(interview_id, user.id, db)
    if interview.status not in (InterviewStatus.CREATED, InterviewStatus.IN_PROGRESS):
        raise HTTPException(status_code=409, detail="Interview cannot be started")
    interview.status = InterviewStatus.IN_PROGRESS
    debit_minutes(db, user.id, interview.duration_target_minutes, str(interview.id))
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
    answer_text = payload.answer_text.strip()
    if len(answer_text) < MIN_ANSWER_LENGTH or normalized_text(answer_text) == normalized_text(question.question_text):
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
    resume = db.get(Resume, interview.resume_id) if interview.resume_id else None
    job = db.get(Job, interview.job_id) if interview.job_id else None
    interview_context = interviewer_context(interview, user, db, "Evaluate the candidate's answer.")
    try:
        evaluation, result = await get_structured_llm_service().evaluate_answer(question.question_text, answer_text, interview_context)
    except (ValueError, LLMProviderError) as exc:
        raise HTTPException(status_code=502, detail="Answer evaluation is temporarily unavailable") from exc
    answer = Answer(question_id=question.id, user_id=user.id, answer_text=answer_text, response_duration_seconds=payload.response_duration_seconds)
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
            followup_text = followup.question
            followup_category = followup.category
            followup_difficulty = followup.difficulty
        except (ValueError, LLMProviderError):
            followup_text = "What would you improve or do differently based on that experience?"
            followup_category = "Behavioral"
            followup_difficulty = interview.difficulty
        db.add(InterviewQuestion(interview_id=interview.id, question_number=next_number, question_text=followup_text, category=followup_category, difficulty=followup_difficulty))
    else:
        evaluations = db.execute(select(Feedback, Answer, InterviewQuestion).join(Answer, Feedback.answer_id == Answer.id).join(InterviewQuestion, Answer.question_id == InterviewQuestion.id).where(InterviewQuestion.interview_id == interview.id)).all()
        evaluation_payload = json.dumps([{"question": item.question_text, "answer": item_answer.answer_text, "feedback": item_feedback.ai_feedback, "scores": {"technical": item_feedback.technical_score, "communication": item_feedback.communication_score, "relevance": item_feedback.relevance_score, "clarity": item_feedback.clarity_score, "confidence": item_feedback.confidence_score}} for item_feedback, item_answer, item in evaluations])
        try:
            final_feedback, final_result = await get_structured_llm_service().generate_final_feedback(interview_context, evaluation_payload)
        except (ValueError, LLMProviderError):
            final_feedback = FinalFeedback(overall_score=evaluation.overall_score, summary="Interview completed with the available answer evaluation.", strengths=evaluation.strengths, weaknesses=evaluation.weaknesses, recommended_practice=[evaluation.recommended_followup] if evaluation.recommended_followup else [])
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


@router.post("/{interview_id}/end", response_model=InterviewResponse)
async def end_interview(interview_id: UUID, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> Interview:
    interview = owned_interview(interview_id, user.id, db)
    if interview.status not in (InterviewStatus.IN_PROGRESS, InterviewStatus.CREATED):
        raise HTTPException(status_code=409, detail="Interview is already finished")
    evaluations = db.execute(select(Feedback, Answer, InterviewQuestion).join(Answer, Feedback.answer_id == Answer.id).join(InterviewQuestion, Answer.question_id == InterviewQuestion.id).where(InterviewQuestion.interview_id == interview.id)).all()
    resume = db.get(Resume, interview.resume_id) if interview.resume_id else None
    job = db.get(Job, interview.job_id) if interview.job_id else None
    interview_context = f"Role: {job.title if job else 'Target role'}\nInterview type: {interview.interview_type}\nDifficulty: {interview.difficulty}\nCandidate profile: {(resume.parsed_profile_json if resume else {})}\nJob analysis: {(job.parsed_analysis_json if job else {})}"
    evaluation_payload = json.dumps([{"question": question.question_text, "answer": answer.answer_text, "feedback": feedback.ai_feedback, "scores": {"technical": feedback.technical_score, "communication": feedback.communication_score, "relevance": feedback.relevance_score, "clarity": feedback.clarity_score, "confidence": feedback.confidence_score}} for feedback, answer, question in evaluations])
    try:
        final_feedback, final_result = await get_structured_llm_service().generate_final_feedback(interview_context, evaluation_payload)
    except (ValueError, LLMProviderError) as exc:
        raise HTTPException(status_code=502, detail="Final interview feedback is temporarily unavailable") from exc
    interview.ended_at = datetime.now(timezone.utc)
    interview.status = InterviewStatus.COMPLETED
    interview.final_feedback_json = final_feedback.model_dump()
    if interview.started_at:
        started_at = interview.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        interview.actual_duration_seconds = max(0, int((interview.ended_at - started_at).total_seconds()))
    interview.overall_score = final_feedback.overall_score
    db.commit()
    record_ai_usage(db, user_id=user.id, interview_id=interview.id, request_type="final_feedback", result=final_result)
    db.refresh(interview)
    return interview


@router.get("/{interview_id}/feedback", response_model=list[FeedbackResponse])
def interview_feedback(interview_id: UUID, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> list[Feedback]:
    owned_interview(interview_id, user.id, db)
    return list(db.scalars(select(Feedback).join(Answer, Feedback.answer_id == Answer.id).join(InterviewQuestion, Answer.question_id == InterviewQuestion.id).where(InterviewQuestion.interview_id == interview_id)))


@router.delete("/{interview_id}", status_code=204)
def delete_interview(interview_id: UUID, user: Annotated[User, Depends(current_user)], db: Annotated[Session, Depends(get_db)]) -> None:
    interview = owned_interview(interview_id, user.id, db)
    db.delete(interview)
    db.commit()
