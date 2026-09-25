FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app app
COPY backend/migrations migrations
COPY backend/alembic.ini .
COPY index.html admin.html admin.js ./
COPY css css
# ... existing COPY lines ...
COPY backend/scripts scripts
COPY backend/start.sh .
# ... rest of Dockerfile ...
COPY js js
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8002"]
