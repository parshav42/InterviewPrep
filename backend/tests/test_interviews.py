from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.db.database import SessionLocal
from app.db.models.domain import AIUsage, Credit, CreditTransaction


def auth_headers(client, email):
    response = client.post("/api/auth/register", json={"email": email, "password": "correct horse battery", "full_name": email.split("@")[0]})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_interview_ownership_and_flow(client):
    owner = auth_headers(client, "owner@example.com")
    other = auth_headers(client, "other@example.com")
    resume = client.post("/api/resumes/upload", headers=owner, files={"file": ("resume.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")}).json()
    job = client.post("/api/jobs", headers=owner, json={"title": "ML Engineer", "job_description": "Build models"}).json()
    assert client.get(f"/api/jobs/{job['id']}", headers=other).status_code == 404
    interview = client.post("/api/interviews", headers=owner, json={"job_id": job["id"], "resume_id": resume["id"], "interview_type": "Technical", "difficulty": "Intermediate", "duration_target_minutes": 30}).json()
    assert client.get(f"/api/interviews/{interview['id']}", headers=other).status_code == 404
    started = client.post(f"/api/interviews/{interview['id']}/start", headers=owner)
    assert started.status_code == 200
    questions = client.get(f"/api/interviews/{interview['id']}/questions/current", headers=owner)
    assert questions.status_code == 200
    question_text = questions.json()["question_text"]
    assert client.post(f"/api/interviews/{interview['id']}/answer", headers=owner, json={"question_id": questions.json()["id"], "answer_text": question_text}).status_code == 422
    feedback = client.post(f"/api/interviews/{interview['id']}/answer", headers=owner, json={"question_id": questions.json()["id"], "answer_text": "I would explain the design and measure the outcome."})
    assert feedback.status_code == 200
    assert feedback.json()["overall_score"] if "overall_score" in feedback.json() else feedback.json()["technical_score"]
    assert client.get(f"/api/interviews/{interview['id']}", headers=owner).status_code == 200


def test_admin_routes_require_role(client):
    user = auth_headers(client, "user@example.com")
    assert client.get("/api/admin/dashboard", headers=user).status_code == 403


def test_question_cap_completes_interview_and_persists_final_feedback(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "max_interview_questions", 3)
    owner = auth_headers(client, "cap@example.com")
    resume = client.post("/api/resumes/upload", headers=owner, files={"file": ("resume.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")}).json()
    interview = client.post("/api/interviews", headers=owner, json={"resume_id": resume["id"], "interview_type": "Technical", "difficulty": "Intermediate", "duration_target_minutes": 30}).json()
    interview_id = interview["id"]
    assert client.post(f"/api/interviews/{interview_id}/start", headers=owner).status_code == 200

    for answer_number in range(3):
        question = client.get(f"/api/interviews/{interview_id}/questions/current", headers=owner).json()
        response = client.post(f"/api/interviews/{interview_id}/answer", headers=owner, json={"question_id": question["id"], "answer_text": f"A detailed answer {answer_number + 1} with evidence"})
        assert response.status_code == 200

    completed = client.get(f"/api/interviews/{interview_id}", headers=owner).json()
    assert completed["status"] == "COMPLETED"
    assert completed["final_feedback_json"]["summary"]
    assert client.get(f"/api/interviews/{interview_id}/questions/current", headers=owner).status_code == 204
    assert len(client.get(f"/api/interviews/{interview_id}/feedback", headers=owner).json()) == 3


def test_interview_asks_multiple_questions(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_interview_questions", 3)
    owner = auth_headers(client, "multiple-questions@example.com")
    resume = client.post("/api/resumes/upload", headers=owner, files={"file": ("resume.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")}).json()
    interview = client.post(f"/api/interviews", headers=owner, json={"resume_id": resume["id"], "interview_type": "Technical", "difficulty": "Intermediate", "duration_target_minutes": 30}).json()
    interview_id = interview["id"]
    assert client.post(f"/api/interviews/{interview_id}/start", headers=owner).status_code == 200

    question_numbers = []
    for answer_number in range(3):
        question = client.get(f"/api/interviews/{interview_id}/questions/current", headers=owner).json()
        question_numbers.append(question["question_number"])
        if answer_number == 0:
            assert question["question_text"].startswith("Hi Candidate, welcome")
        if answer_number == 1:
            assert question["question_text"].startswith("Thanks for sharing that")
        response = client.post(f"/api/interviews/{interview_id}/answer", headers=owner, json={"question_id": question["id"], "answer_text": f"A detailed answer with evidence {answer_number + 1}"})
        assert response.status_code == 200
        payload = response.json()
        if answer_number < 2:
            assert payload["next_question"]["question_number"] == answer_number + 2
            assert payload["is_complete"] is False
        else:
            assert payload["next_question"] is None
            assert payload["is_complete"] is True

    assert question_numbers == [1, 2, 3]


def test_llm_followup_failure_uses_deterministic_question_fallback(client, monkeypatch):
    from app.services.llm.service import get_llm_service
    from app.services.llm.qwen_provider import LLMProviderError

    service = get_llm_service()
    original_generate = service.provider.generate
    calls = {"questions": 0}

    async def fail_followup(messages, **kwargs):
        if "Generate one personalized" in messages[0]["content"]:
            calls["questions"] += 1
            if calls["questions"] == 2:
                raise LLMProviderError("provider unavailable", error_type="provider_unavailable")
        return await original_generate(messages, **kwargs)

    monkeypatch.setattr(service.provider, "generate", fail_followup)
    owner = auth_headers(client, "fallback@example.com")
    resume = client.post("/api/resumes/upload", headers=owner, files={"file": ("resume.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")}).json()
    interview = client.post("/api/interviews", headers=owner, json={"resume_id": resume["id"], "interview_type": "Technical", "difficulty": "Intermediate", "duration_target_minutes": 30}).json()
    interview_id = interview["id"]
    assert client.post(f"/api/interviews/{interview_id}/start", headers=owner).status_code == 200
    question = client.get(f"/api/interviews/{interview_id}/questions/current", headers=owner).json()
    assert client.post(f"/api/interviews/{interview_id}/answer", headers=owner, json={"question_id": question["id"], "answer_text": "A measurable answer"}).status_code == 200
    next_question = client.get(f"/api/interviews/{interview_id}/questions/current", headers=owner).json()
    assert next_question["question_number"] == 2
    assert next_question["question_text"] == "What would you improve or do differently based on that experience?"


def test_credit_concurrency_allows_only_one_debit(client):
    owner = auth_headers(client, "credits@example.com")
    user_id = UUID(client.get("/api/user/profile", headers=owner).json()["id"])
    with SessionLocal() as db:
        db.query(Credit).filter(Credit.user_id == user_id).update({"balance_minutes": 30})
        db.commit()

    def debit():
        with SessionLocal() as db:
            try:
                from app.services.credit_service import debit_minutes
                debit_minutes(db, user_id, 30, "parallel-test")
                db.commit()
                return "success"
            except HTTPException as error:
                db.rollback()
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: debit(), range(2)))
    assert sorted(outcomes, key=str) == [402, "success"]
    with SessionLocal() as db:
        credit = db.query(Credit).filter(Credit.user_id == user_id).one()
        debits = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id, CreditTransaction.transaction_type == "DEBIT").all()
        assert credit.balance_minutes == 0
        assert len(debits) == 1


def test_llm_rate_limit_allows_under_rejects_over_and_resets(client, monkeypatch):
    import app.middleware.llm_rate_limit as limiter

    monkeypatch.setattr(limiter, "MAX_REQUESTS_PER_MINUTE", 2)
    owner = auth_headers(client, "rate@example.com")
    user_id = UUID(client.get("/api/user/profile", headers=owner).json()["id"])
    from app.middleware.llm_rate_limit import check_llm_rate_limit
    from app.db.models.user import User

    with SessionLocal() as db:
        user = db.get(User, user_id)
        check_llm_rate_limit(user, db)
        db.add_all([AIUsage(user_id=user_id, provider="test", model="test", request_type="test", created_at=datetime.now(timezone.utc)) for _ in range(2)])
        db.commit()
        with pytest.raises(HTTPException) as error:
            check_llm_rate_limit(user, db)
        assert error.value.status_code == 429
        assert error.value.headers["Retry-After"] == "60"
        db.query(AIUsage).update({"created_at": datetime.now(timezone.utc) - timedelta(minutes=2)})
        db.commit()
        check_llm_rate_limit(user, db)


def test_answer_quality_signal_classification():
    from app.api.interviews import classify_answer_quality

    assert classify_answer_quality("I don't know") == "vague"
    assert classify_answer_quality("I would explain the design and share the measurable outcome.") == "strong"
    assert classify_answer_quality("sorry this feels bad") == "emotional"
    assert classify_answer_quality("three words only") == "short"
    assert classify_answer_quality("I am not sure") == "vague"


def test_remove_user_data_deletes_resources(client):
    owner = auth_headers(client, "cleanup@example.com")
    resume = client.post("/api/resumes/upload", headers=owner, files={"file": ("resume.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")}).json()
    job = client.post("/api/jobs", headers=owner, json={"title": "ML Engineer", "job_description": "Build models"}).json()
    interview = client.post("/api/interviews", headers=owner, json={"job_id": job["id"], "resume_id": resume["id"], "interview_type": "Technical", "difficulty": "Intermediate", "duration_target_minutes": 30}).json()
    question = client.post(f"/api/interviews/{interview['id']}/start", headers=owner)
    assert question.status_code == 200
    current = client.get(f"/api/interviews/{interview['id']}/questions/current", headers=owner).json()
    client.post(f"/api/interviews/{interview['id']}/answer", headers=owner, json={"question_id": current["id"], "answer_text": "I built a recommendation system and improved accuracy by 12 percent."})

    with SessionLocal() as db:
        user_id = UUID(client.get("/api/user/profile", headers=owner).json()["id"])
        from app.db.models.domain import AnalyticsEvent
        db.add(AnalyticsEvent(user_id=user_id, event_name="interview_started", interview_id=UUID(interview["id"]), metadata_json={"source": "test"}))
        db.commit()

    response = client.delete("/api/user/data", headers=owner)
    assert response.status_code == 200
    payload = response.json()
    assert payload["removed"]["resumes"] >= 1
    assert payload["removed"]["jobs"] >= 1
    assert payload["removed"]["interviews"] >= 1
    assert client.get("/api/user/profile", headers=owner).status_code == 200
    assert client.get("/api/interviews", headers=owner).json() == []


def test_history_returns_real_score_and_duration(client):
    owner = auth_headers(client, "history@example.com")
    resume = client.post("/api/resumes/upload", headers=owner, files={"file": ("resume.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")}).json()
    interview = client.post("/api/interviews", headers=owner, json={"resume_id": resume["id"], "interview_type": "Technical", "difficulty": "Intermediate", "duration_target_minutes": 30}).json()
    with SessionLocal() as db:
        from app.db.models.domain import Interview
        row = db.get(Interview, UUID(interview["id"]))
        row.started_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        row.ended_at = datetime.now(timezone.utc)
        row.actual_duration_seconds = 300
        row.overall_score = 86.5
        row.status = "COMPLETED"
        db.commit()

    history = client.get("/api/interviews", headers=owner).json()
    assert len(history) == 1
    assert history[0]["duration_seconds"] == 300
    assert history[0]["score"] == 86.5
    assert "status" not in history[0]


def test_interview_prompt_includes_last_answer_quality(client, monkeypatch):
    owner = auth_headers(client, "prompt@example.com")
    resume = client.post("/api/resumes/upload", headers=owner, files={"file": ("resume.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")}).json()
    interview = client.post("/api/interviews", headers=owner, json={"resume_id": resume["id"], "interview_type": "Technical", "difficulty": "Intermediate", "duration_target_minutes": 30}).json()
    start = client.post(f"/api/interviews/{interview['id']}/start", headers=owner)
    assert start.status_code == 200
    first_question = client.get(f"/api/interviews/{interview['id']}/questions/current", headers=owner).json()

    from app.services.llm.structured_service import StructuredLLMService
    original = StructuredLLMService.generate_question
    captured = {}

    async def capture(self, context):
        captured["context"] = context
        return await original(self, context)

    monkeypatch.setattr(StructuredLLMService, "generate_question", capture)
    response = client.post(f"/api/interviews/{interview['id']}/answer", headers=owner, json={"question_id": first_question["id"], "answer_text": "I don't know"})
    assert response.status_code == 200
    assert "Last answer quality: vague" in captured["context"]
