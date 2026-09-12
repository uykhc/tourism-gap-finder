# Railway production image for the FastAPI service.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# The HTTP API and the analysis packages it calls.  Analysis *jobs* still run
# elsewhere; what ships here is the library code plus the region tables and the
# sample artifacts that live under apps/api/app/data.
COPY pyproject.toml README.md ./
COPY apps/api ./apps/api
COPY data/analysis/calculation ./data/analysis/calculation
COPY data/analysis/evaluation ./data/analysis/evaluation
# Only the similarity package's own sources; its data/, results/ and tests/ are
# large and are excluded by .dockerignore.
COPY data/analysis/similarity/pyproject.toml ./data/analysis/similarity/
COPY data/analysis/similarity/src ./data/analysis/similarity/src
# Install order matters: evaluation imports hankkeut_calculation, which is a
# local package and so cannot be declared as a resolvable dependency.
RUN python -m pip install --upgrade pip \
    && python -m pip install '.[api]' \
        ./data/analysis/calculation \
        ./data/analysis/evaluation \
        ./data/analysis/similarity

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Railway injects PORT at runtime.  8000 remains useful for `docker run`.
CMD ["sh", "-c", "uvicorn apps.api.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
