# Railway production image for the FastAPI service.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Analysis jobs and their generated artifacts are deployed separately; this
# image contains only the HTTP API and its dependencies.
COPY pyproject.toml README.md ./
COPY apps/api ./apps/api
RUN python -m pip install --upgrade pip && python -m pip install '.[api]'

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Railway injects PORT at runtime.  8000 remains useful for `docker run`.
CMD ["sh", "-c", "uvicorn apps.api.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
