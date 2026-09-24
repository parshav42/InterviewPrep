import hashlib
import hmac
import json

from app.db.database import SessionLocal
from app.db.models.domain import Credit, CreditTransaction, PaymentOrder
from app.api import payments


class FakeRazorpayOrder:
    def create(self, payload):
        assert payload["amount"] == 49900
        assert payload["currency"] == "INR"
        return {"id": "order_test_123"}


class FakeRazorpayClient:
    order = FakeRazorpayOrder()


def auth_headers(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "payments@example.com", "password": "correct horse battery", "full_name": "Payment User"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def sign(secret, payload):
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def test_create_order_for_starter_grants_credits(client):
    headers = auth_headers(client)
    response = client.post("/api/payments/create-order", headers=headers, json={"plan": "starter"})
    assert response.status_code == 200
    assert response.json()["free"] is True
    assert response.json()["credits_added"] == 1
    with SessionLocal() as db:
        credit = db.query(Credit).one()
        assert credit.balance_minutes == 2
        assert db.query(CreditTransaction).filter_by(transaction_type="PURCHASE").one().amount_minutes == 1


def test_create_order_for_pro_uses_server_catalog(client, monkeypatch):
    monkeypatch.setattr(payments, "_client", lambda: FakeRazorpayClient())
    headers = auth_headers(client)
    response = client.post("/api/payments/create-order", headers=headers, json={"plan": "pro"})
    assert response.status_code == 200
    assert response.json()["order_id"] == "order_test_123"
    assert response.json()["amount_paise"] == 49900
    with SessionLocal() as db:
        order = db.query(PaymentOrder).one()
        assert order.status == "CREATED"
        assert order.credits_minutes == 10


def test_verify_valid_signature_grants_once(client, monkeypatch):
    monkeypatch.setattr(payments.settings, "razorpay_key_secret", "payment-secret")
    monkeypatch.setattr(payments, "_client", lambda: FakeRazorpayClient())
    headers = auth_headers(client)
    client.post("/api/payments/create-order", headers=headers, json={"plan": "pro"})
    payload = {"razorpay_order_id": "order_test_123", "razorpay_payment_id": "pay_test_123"}
    payload["razorpay_signature"] = sign("payment-secret", f"{payload['razorpay_order_id']}|{payload['razorpay_payment_id']}".encode())
    first = client.post("/api/payments/verify", headers=headers, json=payload)
    second = client.post("/api/payments/verify", headers=headers, json=payload)
    assert first.json()["balance_minutes"] == 11
    assert second.json()["balance_minutes"] == 11
    with SessionLocal() as db:
        assert db.query(CreditTransaction).filter_by(transaction_type="PURCHASE").count() == 1


def test_verify_invalid_signature_returns_400(client, monkeypatch):
    monkeypatch.setattr(payments, "_client", lambda: FakeRazorpayClient())
    headers = auth_headers(client)
    client.post("/api/payments/create-order", headers=headers, json={"plan": "pro"})
    response = client.post("/api/payments/verify", headers=headers, json={
        "razorpay_order_id": "order_test_123",
        "razorpay_payment_id": "pay_test_123",
        "razorpay_signature": "invalid",
    })
    assert response.status_code == 400


def test_webhook_processes_and_replays_idempotently(client, monkeypatch):
    monkeypatch.setattr(payments.settings, "razorpay_key_secret", "payment-secret")
    monkeypatch.setattr(payments.settings, "razorpay_webhook_secret", "webhook-secret")
    monkeypatch.setattr(payments, "_client", lambda: FakeRazorpayClient())
    headers = auth_headers(client)
    client.post("/api/payments/create-order", headers=headers, json={"plan": "pro"})
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_webhook_123", "order_id": "order_test_123"}}}}).encode()
    webhook_headers = {"X-Razorpay-Signature": sign("webhook-secret", body)}
    first = client.post("/api/payments/webhook", content=body, headers=webhook_headers)
    second = client.post("/api/payments/webhook", content=body, headers=webhook_headers)
    assert first.status_code == 200
    assert second.status_code == 200
    with SessionLocal() as db:
        assert db.query(PaymentOrder).one().status == "PAID"
        assert db.query(CreditTransaction).filter_by(transaction_type="PURCHASE").count() == 1


def test_webhook_invalid_signature_returns_400(client, monkeypatch):
    monkeypatch.setattr(payments.settings, "razorpay_webhook_secret", "webhook-secret")
    response = client.post("/api/payments/webhook", content=b"{}", headers={"X-Razorpay-Signature": "invalid"})
    assert response.status_code == 400


def test_create_order_requires_authentication(client):
    response = client.post("/api/payments/create-order", json={"plan": "starter"})
    assert response.status_code == 401
