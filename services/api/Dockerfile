# API image. Build context = repo root (needs services/data for exports/clash/validate/drawings).
# Mirrors the repo layout so routers' relative paths to ../data/src resolve.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/services/api/src:/app/services/data/src

# system libs some wheels (ifcopenshell, shapely) expect, + a toolchain so any
# source-only dep (meson/cmake builds) can compile instead of failing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY services/api/requirements.txt /app/services/api/requirements.txt
COPY services/data/requirements.txt /app/services/data/requirements.txt
# resilient to slow/flaky PyPI: longer timeout + retries (heavy scientific wheels)
ENV PIP_DEFAULT_TIMEOUT=180 PIP_RETRIES=8 PIP_NO_CACHE_DIR=1
RUN pip install -r /app/services/api/requirements.txt psycopg[binary] \
    && pip install -r /app/services/data/requirements.txt

COPY services/api/src /app/services/api/src
COPY services/data/src /app/services/data/src

EXPOSE 8000
CMD ["uvicorn", "aec_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
