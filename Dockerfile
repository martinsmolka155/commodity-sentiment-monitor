FROM python:3.12-slim AS base

# Install only the minimal ffmpeg (avoid full libavcodec deps)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-install-project

COPY src/ src/
COPY fixtures/ fixtures/
COPY docs/ docs/
COPY tests/ tests/
RUN uv sync --no-dev

RUN mkdir -p /tmp/chunks

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "python", "-m", "app.main"]
