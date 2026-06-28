# Stage 1: build the frontend (oven/bun image, bun's own documented pattern:
# frozen-lockfile install then build) - produces frontend/dist.
FROM oven/bun:1 AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ ./
RUN bun run build

# Stage 2: backend + the built frontend, served from one process/port.
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# ffmpeg/ffprobe aren't pip packages - same as the host setup in CLAUDE.md.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# uv's documented caching pattern: install deps from the lockfile before
# copying the rest of the source, so source-only changes don't bust this layer.
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project

COPY backend/ ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# Bakes the voice model into the image at build time (same model CLAUDE.md's
# one-time host setup downloads) so the final image is fully self-contained -
# no runtime download step needed to render.
RUN uv run python -m piper.download_voices en_US-lessac-low --download-dir assets/voices

COPY --from=frontend-builder /app/frontend/dist /app/frontend_dist

ENV PATH="/app/backend/.venv/bin:$PATH"
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
