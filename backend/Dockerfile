# Backend Dockerfile (legacy / backend-only context)
#
# Prefer the repository-root Dockerfile for Render:
#   docker build -t kulima-api -f Dockerfile .
#
# This file remains for local backend-only experiments, but it CANNOT serve
# production alone — kulima/ and scripts/ must be on PYTHONPATH.

FROM python:3.11-slim
WORKDIR /app
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
