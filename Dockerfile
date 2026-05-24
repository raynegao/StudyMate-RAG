FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TOKENIZERS_PARALLELISM=false \
    PYTHONPATH=/app/backend \
    STUDYMATE_UPLOAD_DIR=/app/data/uploads \
    STUDYMATE_CHROMA_DIR=/app/data/chroma_db

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt

COPY . .

RUN chmod +x scripts/*.sh \
    && mkdir -p data/uploads data/chroma_db

EXPOSE 8000 8501

CMD ["scripts/run_backend.sh"]
