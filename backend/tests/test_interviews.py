from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.db.database import SessionLocal
from app.db.models.domain import AIUsage, Credit, CreditTransaction, Interview, InterviewStatus


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


def test_end_interview_succeeds_first_time(client):
    owner = auth_headers(client, "end-success@example.com")
    resume = client.post("/api/resumes/upload", headers=owner, files={"file": ("resume.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")}).json()
    interview = client.post("/api/interviews", headers=owner, json={"resume_id": resume["id"], "interview_type": "Technical", "difficulty": "Intermediate", "duration_target_minutes": 30}).json()
    assert client.post(f"/api/interviews/{interview['id']}/start", headers=owner).status_code == 200

    response = client.post(f"/api/interviews/{interview['id']}/end", headers=owner)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "COMPLETED"
    assert payload["ended_at"]
    assert payload["actual_duration_seconds"] is not None


def test_end_interview_twice_returns_200(client):
    owner = auth_headers(client, "end-twice@example.com")
    resume = client.post("/api/resumes/upload", headers=owner, files={"file": ("resume.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")}).json()
    interview = client.post("/api/interviews", headers=owner, json={"resume_id": resume["id"], "interview_type": "Technical", "difficulty": "Intermediate", "duration_target_minutes": 30}).json()
    assert client.post(f"/api/interviews/{interview['id']}/start", headers=owner).status_code == 200

    first = client.post(f"/api/interviews/{interview['id']}/end", headers=owner)
    assert first.status_code == 200
    second = client.post(f"/api/interviews/{interview['id']}/end", headers=owner)
    assert second.status_code == 200
    assert second.json()["status"] == "COMPLETED"


def test_end_interview_unknown_id_returns_404(client):
    owner = auth_headers(client, "end-missing@example.com")
    unknown_id = UUID("11111111-1111-4111-8111-111111111111")
    response = client.post(f"/api/interviews/{unknown_id}/end", headers=owner)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_end_interview_null_started_at_no_crash(client):
    owner = auth_headers(client, "end-null-started@example.com")
    resume = client.post("/api/resumes/upload", headers=owner, files={"file": ("resume.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")}).json()
    interview = client.post("/api/interviews", headers=owner, json={"resume_id": resume["id"], "interview_type": "Technical", "difficulty": "Intermediate", "duration_target_minutes": 30}).json()
    with SessionLocal() as db:
        row = db.get(Interview, UUID(interview["id"]))
        row.status = InterviewStatus.IN_PROGRESS
        row.started_at = None
        db.commit()

    response = client.post(f"/api/interviews/{interview['id']}/end", headers=owner)
    assert response.status_code == 200
    assert response.json()["actual_duration_seconds"] is None


def test_end_interview_other_user_returns_404(client):
    owner = auth_headers(client, "end-owner@example.com")
    other = auth_headers(client, "end-other@example.com")
    resume = client.post("/api/resumes/upload", headers=owner, files={"file": ("resume.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")}).json()
    interview = client.post("/api/interviews", headers=owner, json={"resume_id": resume["id"], "interview_type": "Technical", "difficulty": "Intermediate", "duration_target_minutes": 30}).json()

    response = client.post(f"/api/interviews/{interview['id']}/end", headers=other)
    assert response.status_code == 404


def test_admin_routes_require_role(client):
    user = auth_headers(client, "user@example.com")
    assert client.get("/api/admin/dashboard", headers=user).status_code == 403


def test_admin_user_detail_includes_profile_resume_and_media(client):
    from uuid import UUID

    from app.core.security import hash_password
    from app.db.database import SessionLocal
    from app.db.models.domain import InterviewMedia
    from app.db.models.user import User, UserRole

    with SessionLocal() as db:
        admin_user = User(email="admin@example.com", password_hash=hash_password("correct horse battery"), full_name="Site Admin", role=UserRole.ADMIN, email_verified=True)
        db.add(admin_user)
        db.commit()

    owner = auth_headers(client, "detail-user@example.com")
    valid_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    resume = client.post("/api/resumes/upload", headers=owner, files={"file": ("resume.pdf", valid_pdf, "application/pdf")}).json()
    interview = client.post("/api/interviews", headers=owner, json={"resume_id": resume["id"], "interview_type": "Technical", "difficulty": "Intermediate", "duration_target_minutes": 30}).json()
    user_id = UUID(client.get("/api/user/profile", headers=owner).json()["id"])
    interview_id = UUID(interview["id"])
    with SessionLocal() as db:
        db.add(InterviewMedia(user_id=user_id, interview_id=interview_id, media_type="photo", storage_key="uploads/demo/capture.jpg", original_filename="capture.jpg", file_size=1024, content_type="image/jpeg", metadata_json={"camera": "front", "resolution": "1280x720"}))
        db.commit()

    admin_login = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "correct horse battery"})
    assert admin_login.status_code == 200, admin_login.text
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    response = client.get(f"/api/admin/users/{user_id}", headers=admin_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["resume"]["filename"] == "resume.pdf"
    assert len(payload["interviews"]) >= 1
    assert len(payload["media"]) == 1
    assert payload["media"][0]["metadata"]["camera"] == "front"


def test_admin_user_download_all_bundle_includes_resume_and_media(client):
    from uuid import UUID

    from app.core.security import hash_password
    from app.db.database import SessionLocal
    from app.db.models.domain import InterviewMedia
    from app.db.models.user import User, UserRole

    with SessionLocal() as db:
        db.add(User(email="admin@example.com", password_hash=hash_password("correct horse battery"), full_name="Site Admin", role=UserRole.ADMIN, email_verified=True))
        db.commit()

    owner = auth_headers(client, "bundle-user@example.com")
    valid_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    resume = client.post("/api/resumes/upload", headers=owner, files={"file": ("resume.pdf", valid_pdf, "application/pdf")}).json()
    interview = client.post("/api/interviews", headers=owner, json={"resume_id": resume["id"], "interview_type": "Technical", "difficulty": "Intermediate", "duration_target_minutes": 30}).json()
    user_id = UUID(client.get("/api/user/profile", headers=owner).json()["id"])
    interview_id = UUID(interview["id"])
    with SessionLocal() as db:
        db.add(InterviewMedia(user_id=user_id, interview_id=interview_id, media_type="photo", storage_key="uploads/demo/capture.jpg", original_filename="capture.jpg", file_size=1024, content_type="image/jpeg", metadata_json={"camera": "front", "resolution": "1280x720"}))
        db.commit()

    admin_login = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "correct horse battery"})
    assert admin_login.status_code == 200, admin_login.text
    headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    response = client.get(f"/api/admin/users/{user_id}/download-all", headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/zip")
    payload = response.content
    assert b"resume.pdf" in payload
    assert b"capture.jpg" in payload


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


def test_start_interview_without_credits_returns_no_credits_payload(client):
    owner = auth_headers(client, "no-credits@example.com")
    user_id = UUID(client.get("/api/user/profile", headers=owner).json()["id"])
    resume = client.post("/api/resumes/upload", headers=owner, files={"file": ("resume.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")}).json()
    interview = client.post("/api/interviews", headers=owner, json={"resume_id": resume["id"], "interview_type": "Technical", "difficulty": "Intermediate", "duration_target_minutes": 30}).json()

    with SessionLocal() as db:
        credit = db.query(Credit).filter(Credit.user_id == user_id).one()
        credit.balance_minutes = 0
        db.commit()

    response = client.post(f"/api/interviews/{interview['id']}/start", headers=owner)
    assert response.status_code == 402
    payload = response.json()
    assert payload["detail"] == "no_credits"
    assert payload["message"] == "You've used all your interviews. Buy more to continue."


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
    from app.api.interviews import classify_answer, classify_answer_quality

    assert classify_answer("I don't know") == "give_up"
    assert classify_answer("next question") == "skip"
    assert classify_answer("") == "empty"
    assert classify_answer_quality("I don't know") == "vague"
    assert classify_answer_quality("I would explain the design and share the measurable outcome.") == "strong"
    assert classify_answer_quality("sorry this feels bad") == "emotional"
    assert classify_answer_quality("three words only") == "short"
    assert classify_answer_quality("I am not sure") == "vague"


def test_weak_answers_and_skip_commands_move_forward(client):
    owner = auth_headers(client, "weak-answers@example.com")
    resume = client.post("/api/resumes/upload", headers=owner, files={"file": ("resume.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")}).json()
    interview = client.post("/api/interviews", headers=owner, json={"resume_id": resume["id"], "interview_type": "Technical", "difficulty": "Intermediate", "duration_target_minutes": 30}).json()
    interview_id = interview["id"]
    assert client.post(f"/api/interviews/{interview_id}/start", headers=owner).status_code == 200
    current = client.get(f"/api/interviews/{interview_id}/questions/current", headers=owner).json()

    give_up = client.post(f"/api/interviews/{interview_id}/answer", headers=owner, json={"question_id": current["id"], "answer_text": "I don't know"})
    assert give_up.status_code == 200, give_up.text
    assert give_up.json()["next_question"]["question_text"] != current["question_text"]

    next_question = client.get(f"/api/interviews/{interview_id}/questions/current", headers=owner).json()
    skip = client.post(f"/api/interviews/{interview_id}/answer", headers=owner, json={"question_id": next_question["id"], "answer_text": "next question"})
    assert skip.status_code == 200, skip.text
    assert skip.json()["next_question"] is not None


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
