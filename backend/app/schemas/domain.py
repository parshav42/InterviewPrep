from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.domain import InterviewStatus


class ResumeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    original_filename: str
    file_type: str
    file_size: int
    parsed_profile_json: dict
    uploaded_at: datetime


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    company_name: str | None = Field(default=None, max_length=180)
    job_description: str = Field(default="", max_length=30000)


class JobResponse(JobCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    created_at: datetime
    parsed_analysis_json: dict


class InterviewCreate(BaseModel):
    resume_id: UUID | None = None
    job_id: UUID | None = None
    interview_type: str = Field(min_length=2, max_length=50)
    difficulty: str = Field(min_length=2, max_length=30)
    duration_target_minutes: int = Field(ge=5, le=120)


class InterviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    resume_id: UUID | None
    job_id: UUID | None
    interview_type: str
    difficulty: str
    duration_target_minutes: int
    status: InterviewStatus
    started_at: datetime | None
    ended_at: datetime | None
    actual_duration_seconds: int | None
    overall_score: float | None
    final_feedback_json: dict | None
    created_at: datetime


class AnswerCreate(BaseModel):
    question_id: UUID
    answer_text: str = Field(min_length=1, max_length=30000)
    response_duration_seconds: int | None = Field(default=None, ge=0, le=3600)


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    answer_id: UUID
    technical_score: float
    communication_score: float
    relevance_score: float
    clarity_score: float
    confidence_score: float
    strengths: list
    weaknesses: list
    suggestions: list
    ai_feedback: str
    created_at: datetime


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    question_number: int
    question_text: str
    category: str
    difficulty: str


class AnswerResponse(FeedbackResponse):
    next_question: QuestionResponse | None = None
    is_complete: bool = False
    feedback_url: str | None = None
