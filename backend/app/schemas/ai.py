from typing import Any

from pydantic import BaseModel, Field, field_validator


def normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value.strip().lower() in {"", "not specified", "none", "n/a", "null"}:
        return []
    return [str(value)]


class CandidateProfile(BaseModel):
    name: str | None = None
    education: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    programming_languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    internships: list[str] = Field(default_factory=list)
    experience: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)

    _normalize_lists = field_validator("education", "skills", "programming_languages", "frameworks", "projects", "internships", "experience", "certifications", "achievements", mode="before")(normalize_list)


class JobAnalysis(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    technical_topics: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    experience_requirements: list[str] = Field(default_factory=list)
    interview_topics: list[str] = Field(default_factory=list)

    _normalize_lists = field_validator("required_skills", "preferred_skills", "technical_topics", "responsibilities", "experience_requirements", "interview_topics", mode="before")(normalize_list)


class QuestionOutput(BaseModel):
    question: str = Field(min_length=5, max_length=2000)
    category: str = Field(min_length=2, max_length=80)
    difficulty: str = Field(min_length=2, max_length=30)
    rationale: str = Field(default="", max_length=2000)


class AnswerEvaluation(BaseModel):
    technical_accuracy: float = Field(ge=0, le=100)
    communication: float = Field(ge=0, le=100)
    depth: float = Field(ge=0, le=100)
    relevance: float = Field(ge=0, le=100)
    problem_solving: float = Field(ge=0, le=100)
    overall_score: float = Field(ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    feedback: str = Field(max_length=5000)
    recommended_followup: str = Field(default="", max_length=2000)


class FinalFeedback(BaseModel):
    overall_score: float = Field(ge=0, le=100)
    summary: str = Field(min_length=1, max_length=5000)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommended_practice: list[str] = Field(default_factory=list)

    _normalize_lists = field_validator("strengths", "weaknesses", "recommended_practice", mode="before")(normalize_list)
