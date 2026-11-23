# PERSONAL OS — API (FastAPI)
# NOTE: written for Phase 10; Docker is not installed in the build sandbox,
# so this file is correct-by-construction but untested there (see docs/DEPLOYMENT.md).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app ./app

# Non-root user; /app/data holds the default SQLite database file
RUN useradd --create-home --uid 10001 personalos \
    && mkdir -p /app/data \
    && chown -R personalos:personalos /app
USER personalos

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
