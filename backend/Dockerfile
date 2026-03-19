FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Install Chromium + system deps (required by scrapling/playwright)
RUN uv run playwright install chromium --with-deps

COPY backend/ ./backend/

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
