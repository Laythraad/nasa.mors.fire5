FROM python:3.12-slim@sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54 AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PATH="/opt/venv/bin:$PATH"
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM builder AS test
WORKDIR /app
COPY requirements-dev.txt .
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY ruff.toml .
COPY app ./app
COPY tests ./tests
ENV AEGIS_DB_PATH=/tmp/aegis-tests.db PYTHONPATH=/app
CMD ["pytest", "-q", "tests"]

FROM python:3.12-slim@sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH" AEGIS_DB_PATH=/app/data/aegis.db
WORKDIR /app
RUN groupadd --system aegis && useradd --system --gid aegis --home-dir /app aegis && mkdir -p /app/data
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
RUN chown -R aegis:aegis /app
USER aegis
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
