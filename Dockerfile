# Budget — web UI + API in one container.
#   docker compose up -d        (see docker-compose.yml)
# Data (database, backups, the generated admin password) lives in /data.

# ── Build the web interface ──────────────────────────────────────────────
FROM node:22-alpine AS ui
WORKDIR /app/web-ui
COPY web-ui/package.json web-ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web-ui/ ./
RUN npm run build

# ── Python runtime ───────────────────────────────────────────────────────
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BUDGET_HOST=0.0.0.0 \
    BUDGET_PORT=4000 \
    BUDGET_DATA_DIR=/data

# tzdata so TZ works: bill dates, backups and the morning digest use local time
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv export --frozen --no-dev --no-emit-project --no-hashes -o /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && pip uninstall -y uv && rm /tmp/requirements.txt

COPY api_server.py ./
COPY models ./models
COPY --from=ui /app/web-ui/dist ./web-ui/dist

RUN useradd --system --uid 1000 --no-create-home budget \
    && mkdir -p /data && chown budget:budget /data
USER budget
VOLUME /data
EXPOSE 4000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"BUDGET_PORT\"]}/health', timeout=4)"

CMD ["python", "api_server.py"]
