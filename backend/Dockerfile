FROM python:3.12-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.20 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --gid 10001 pulse && useradd --uid 10001 --gid pulse --create-home pulse
WORKDIR /app
COPY --from=builder --chown=pulse:pulse /app/.venv /app/.venv
COPY --chown=pulse:pulse alembic.ini ./
COPY --chown=pulse:pulse migrations ./migrations
USER pulse
EXPOSE 8000
CMD ["uvicorn", "pulse.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
