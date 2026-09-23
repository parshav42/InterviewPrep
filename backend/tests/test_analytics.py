from app.db.database import SessionLocal
from app.db.models.domain import AnalyticsEvent


def test_analytics_strips_sensitive_metadata_before_persistence(client):
    registered = client.post("/api/auth/register", json={"email": "analytics@example.com", "password": "correct horse battery", "full_name": "Analytics User"})
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    response = client.post("/api/analytics/events", headers=headers, json={
        "event_name": "interview_opened",
        "metadata": {
            "token": "redacted",
            "password": "redacted",
            "authorization": "redacted",
            "screen": "interview",
        },
    })
    assert response.status_code == 202
    with SessionLocal() as db:
        event = db.query(AnalyticsEvent).one()
        assert event.metadata_json == {"screen": "interview"}