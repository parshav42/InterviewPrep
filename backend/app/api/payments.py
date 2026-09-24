import hashlib
import hmac
import json
import time
from typing import Annotated, Literal

import razorpay
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import current_user
from app.core.config import get_settings
from app.db.database import get_db
from app.db.models.domain import Credit, PaymentOrder
from app.db.models.user import User
from app.services.credit_service import grant_minutes


router = APIRouter()
settings = get_settings()
PLANS = {
    "starter": {"interviews": 1, "amount_paise": 0},
    "pro": {"interviews": 10, "amount_paise": 49900},
}


class CreateOrderRequest(BaseModel):
    plan: Literal["starter", "pro"]


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


def _client() -> razorpay.Client:
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def _signature_matches(secret: str, payload: bytes, signature: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _balance(db: Session, user_id) -> int:
    credit = db.scalar(select(Credit).where(Credit.user_id == user_id))
    return credit.balance_minutes if credit else 0


def _fulfill_order(db: Session, order: PaymentOrder, payment_id: str | None) -> int:
    if order.status == "PAID":
        return _balance(db, order.user_id)
    order.status = "PAID"
    if payment_id:
        order.razorpay_payment_id = payment_id
    credit = grant_minutes(db, order.user_id, order.credits_minutes, order.razorpay_order_id, tx_type="PURCHASE")
    db.commit()
    return credit.balance_minutes


@router.post("/create-order")
def create_order(
    payload: CreateOrderRequest,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    plan = PLANS[payload.plan]
    if payload.plan == "starter":
        credit = grant_minutes(db, user.id, plan["interviews"], "starter", tx_type="PURCHASE")
        db.commit()
        return {"free": True, "credits_added": plan["interviews"], "interviews_added": plan["interviews"], "balance_minutes": credit.balance_minutes, "balance_interviews": credit.balance_minutes}

    razorpay_order = _client().order.create({
        "amount": plan["amount_paise"],
        "currency": "INR",
        "receipt": f"{user.id}-{int(time.time())}",
        "notes": {"user_id": str(user.id), "credits_minutes": str(plan["interviews"])},
    })
    order = PaymentOrder(
        user_id=user.id,
        razorpay_order_id=razorpay_order["id"],
        amount_paise=plan["amount_paise"],
        credits_minutes=plan["interviews"],
        status="CREATED",
    )
    db.add(order)
    db.commit()
    return {
        "order_id": order.razorpay_order_id,
        "amount_paise": order.amount_paise,
        "key_id": settings.razorpay_key_id,
        "credits": order.credits_minutes,
        "interviews": order.credits_minutes,
    }


@router.post("/verify")
def verify_payment(
    payload: VerifyPaymentRequest,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    signed_payload = f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}".encode()
    if not _signature_matches(settings.razorpay_key_secret, signed_payload, payload.razorpay_signature):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payment signature")
    order = db.scalar(
        select(PaymentOrder)
        .where(PaymentOrder.razorpay_order_id == payload.razorpay_order_id, PaymentOrder.user_id == user.id)
        .with_for_update()
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment order not found")
    balance = _fulfill_order(db, order, payload.razorpay_payment_id)
    return {"status": "paid", "balance_minutes": balance, "balance_interviews": balance}


@router.post("/webhook")
async def payment_webhook(
    request: Request,
    x_razorpay_signature: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    raw_body = await request.body()
    if not x_razorpay_signature or not _signature_matches(settings.razorpay_webhook_secret, raw_body, x_razorpay_signature):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")
    try:
        event = json.loads(raw_body)
    except json.JSONDecodeError:
        return {"status": "ignored"}
    if event.get("event") != "payment.captured":
        return {"status": "ignored"}
    payment = event.get("payload", {}).get("payment", {}).get("entity", {})
    razorpay_order_id = payment.get("order_id")
    if not razorpay_order_id:
        return {"status": "ignored"}
    order = db.scalar(select(PaymentOrder).where(PaymentOrder.razorpay_order_id == razorpay_order_id).with_for_update())
    if not order:
        return {"status": "ignored"}
    _fulfill_order(db, order, payment.get("id"))
    return {"status": "processed"}
