from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models.domain import Credit, CreditTransaction


INITIAL_CREDIT_INTERVIEWS = 1
INITIAL_CREDIT_MINUTES = INITIAL_CREDIT_INTERVIEWS


def ensure_credit_account(db: Session, user_id) -> Credit:
    credit = db.scalar(select(Credit).where(Credit.user_id == user_id).with_for_update())
    if credit:
        return credit
    credit = Credit(user_id=user_id, balance_minutes=INITIAL_CREDIT_INTERVIEWS)
    db.add(credit)
    db.flush()
    db.add(CreditTransaction(user_id=user_id, amount_minutes=INITIAL_CREDIT_INTERVIEWS, transaction_type="GRANT"))
    return credit


def debit_interviews(db: Session, user_id, interviews: int, reference: str | None = None) -> Credit:
    if interviews <= 0:
        raise ValueError("Interview debit must be positive")
    credit = ensure_credit_account(db, user_id)
    updated = db.execute(
        update(Credit)
        .where(Credit.id == credit.id, Credit.balance_minutes >= interviews)
        .values(balance_minutes=Credit.balance_minutes - interviews)
    )
    if updated.rowcount != 1:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient interview credits")
    db.add(CreditTransaction(user_id=user_id, amount_minutes=-interviews, transaction_type="DEBIT", payment_reference=reference))
    db.flush()
    return credit


def debit_minutes(db: Session, user_id, minutes: int, reference: str | None = None) -> Credit:
    return debit_interviews(db, user_id, minutes, reference)


def grant_interviews(db: Session, user_id, interviews: int, reference: str, tx_type: str = "PURCHASE") -> Credit:
    if interviews <= 0:
        raise ValueError("Interview grant must be positive")
    credit = ensure_credit_account(db, user_id)
    db.execute(
        update(Credit)
        .where(Credit.id == credit.id)
        .values(balance_minutes=Credit.balance_minutes + interviews)
    )
    db.add(CreditTransaction(user_id=user_id, amount_minutes=interviews, transaction_type=tx_type, payment_reference=reference))
    db.flush()
    return credit


def grant_minutes(db: Session, user_id, minutes: int, reference: str, tx_type: str = "PURCHASE") -> Credit:
    return grant_interviews(db, user_id, minutes, reference, tx_type)