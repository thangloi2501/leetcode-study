FROM python:3.14-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (no project, just deps)
RUN uv sync --frozen --no-install-project --no-dev

# Copy application source
COPY *.py ./

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080

CMD ["uv", "run", "gunicorn", "main:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "60"]
