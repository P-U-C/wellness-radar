FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e ".[dev]"

COPY apps ./apps
COPY packages ./packages
COPY db ./db

RUN mkdir -p /app/raw
