import fitz


def auth_headers(client, email):
    response = client.post("/api/auth/register", json={"email": email, "password": "correct horse battery", "full_name": email.split("@")[0]})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def pdf_bytes():
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Candidate Python FastAPI experience")
    content = document.tobytes()
    document.close()
    return content


def test_resume_upload_list_get_delete_and_isolation(client):
    owner = auth_headers(client, "resume-owner@example.com")
    other = auth_headers(client, "resume-other@example.com")
    response = client.post("/api/resumes/upload", headers=owner, files={"file": ("resume.pdf", pdf_bytes(), "application/pdf")})
    assert response.status_code == 201
    resume_id = response.json()["id"]
    assert client.get("/api/resumes", headers=owner).json()[0]["id"] == resume_id
    assert client.get(f"/api/resumes/{resume_id}", headers=owner).status_code == 200
    assert client.get(f"/api/resumes/{resume_id}", headers=other).status_code == 404
    assert client.delete(f"/api/resumes/{resume_id}", headers=owner).status_code == 204
    assert client.get(f"/api/resumes/{resume_id}", headers=owner).status_code == 404


def test_resume_rejects_invalid_and_oversized_files(client):
    headers = auth_headers(client, "resume-validation@example.com")
    invalid = client.post("/api/resumes/upload", headers=headers, files={"file": ("resume.pdf", b"not a pdf", "application/pdf")})
    assert invalid.status_code == 422
    oversized = client.post("/api/resumes/upload", headers=headers, files={"file": ("resume.pdf", b"x" * (10 * 1024 * 1024 + 1), "application/pdf")})
    assert oversized.status_code == 413


def test_upload_returns_extracted_text(client):
    headers = auth_headers(client, "resume-preview@example.com")
    response = client.post("/api/resumes/upload", headers=headers, files={"file": ("resume.pdf", pdf_bytes(), "application/pdf")})
    assert response.status_code == 201
    payload = response.json()
    assert payload["extracted_text_preview"]
    assert "Candidate Python FastAPI experience" in payload["extracted_text_preview"]
    assert payload["parsed"]["skills"]
    assert payload["parsed"]["summary"]


def test_upload_invalid_returns_error(client):
    headers = auth_headers(client, "resume-invalid@example.com")
    response = client.post("/api/resumes/upload", headers=headers, files={"file": ("resume.txt", b"hello world", "text/plain")})
    assert response.status_code == 415
    assert "Only PDF and DOCX resumes" in response.json()["detail"]


def test_upload_scanned_pdf_returns_warning(client):
    headers = auth_headers(client, "resume-scanned@example.com")
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), " ")
    payload = document.tobytes()
    document.close()
    response = client.post("/api/resumes/upload", headers=headers, files={"file": ("scan.pdf", payload, "application/pdf")})
    assert response.status_code == 422
    assert "Could not extract text from this PDF" in response.json()["detail"]