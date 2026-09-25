#!/bin/sh
python -m alembic upgrade head
python scripts/seed.py
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002