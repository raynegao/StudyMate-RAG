ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.10.9

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:${PYTHON_VERSION}-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=uv /uv /usr/local/bin/uv
COPY backend/requirements.txt /tmp/requirements.txt

RUN uv venv /opt/venv --python /usr/local/bin/python \
    && uv pip sync --python /opt/venv/bin/python --torch-backend cpu /tmp/requirements.txt

FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false \
    PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app/backend \
    HOME=/home/studymate \
    HF_HOME=/home/studymate/.cache/huggingface \
    STUDYMATE_UPLOAD_DIR=/app/data/uploads \
    STUDYMATE_CHROMA_DIR=/app/data/chroma_db

RUN groupadd --gid 10001 studymate \
    && useradd --uid 10001 --gid studymate --create-home --shell /usr/sbin/nologin studymate

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=studymate:studymate backend ./backend
COPY --chown=studymate:studymate frontend ./frontend
COPY --chown=studymate:studymate scripts ./scripts

RUN install -d -o studymate -g studymate \
        /app/data/uploads \
        /app/data/chroma_db \
        /home/studymate/.cache/huggingface \
    && chmod +x scripts/*.sh

USER studymate

EXPOSE 8000 8501

CMD ["scripts/run_backend.sh"]
