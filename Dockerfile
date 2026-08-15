# Production Dockerfile for Kulima OS API (Render / Docker hosts)
# Build context MUST be the repository root so kulima/ + scripts/ are included.
#
#   docker build -t kulima-api -f Dockerfile .
#   docker run -p 8000:8000 --env-file backend/.env kulima-api

FROM python:3.11-slim

WORKDIR /app

# System deps for reportlab / cryptography-adjacent wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend-requirements.txt
RUN pip install --no-cache-dir -r /app/backend-requirements.txt

# Core intelligence package + demo seed + FastAPI app
COPY kulima /app/kulima
COPY scripts /app/scripts
COPY backend /app/backend

# Ensure `import kulima` and `import scripts` resolve
ENV PYTHONPATH=/app
ENV KULIMA_DB_PATH=/data/kulima.db

# Persist SQLite + uploads on mounted volume in production
RUN mkdir -p /data /app/backend/uploads

EXPOSE 8000

# Render injects $PORT; default to 8000 for local/docker runs
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
