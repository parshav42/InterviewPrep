from tests.test_resumes import auth_headers


def test_create_job_empty_title_returns_422(client):
    headers = auth_headers(client, "job-empty-title@example.com")
    response = client.post("/api/jobs", headers=headers, json={"title": "   ", "job_description": "Build software"})
    assert response.status_code == 422
    assert response.json()["detail"] == "Job title is required"


def test_create_job_valid_returns_201(client):
    headers = auth_headers(client, "job-valid@example.com")
    response = client.post("/api/jobs", headers=headers, json={"title": "ML Engineer", "job_description": "Build models"})
    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "ML Engineer"
    assert payload["job_description"] == "Build models"
