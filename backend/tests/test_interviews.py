def auth_headers(client, email):
    response = client.post("/api/auth/register", json={"email": email, "password": "correct horse battery", "full_name": email.split("@")[0]})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_interview_ownership_and_flow(client):
    owner = auth_headers(client, "owner@example.com")
    other = auth_headers(client, "other@example.com")
    job = client.post("/api/jobs", headers=owner, json={"title": "ML Engineer", "job_description": "Build models"}).json()
    assert client.get(f"/api/jobs/{job['id']}", headers=other).status_code == 404
    interview = client.post("/api/interviews", headers=owner, json={"job_id": job["id"], "interview_type": "Technical", "difficulty": "Intermediate", "duration_target_minutes": 30}).json()
    assert client.get(f"/api/interviews/{interview['id']}", headers=other).status_code == 404
    started = client.post(f"/api/interviews/{interview['id']}/start", headers=owner)
    assert started.status_code == 200
    questions = client.get(f"/api/interviews/{interview['id']}/questions/current", headers=owner)
    assert questions.status_code == 200
    feedback = client.post(f"/api/interviews/{interview['id']}/answer", headers=owner, json={"question_id": questions.json()["id"], "answer_text": "I would explain the design and measure the outcome."})
    assert feedback.status_code == 200
    assert feedback.json()["overall_score"] if "overall_score" in feedback.json() else feedback.json()["technical_score"]
    assert client.get(f"/api/interviews/{interview['id']}", headers=owner).status_code == 200


def test_admin_routes_require_role(client):
    user = auth_headers(client, "user@example.com")
    assert client.get("/api/admin/dashboard", headers=user).status_code == 403
