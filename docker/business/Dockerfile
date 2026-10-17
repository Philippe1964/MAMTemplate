# ==============================================================================
# Stage 1: Builder (Python 3.14 Alpine + uv)
# ==============================================================================
FROM python:3.14-alpine AS builder

RUN apk update \
    && apk upgrade --no-cache \
    && apk add --no-cache build-base linux-headers

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY pyproject.toml README.md uv.lock* ./
RUN uv sync --frozen --no-install-project --no-dev || uv sync --no-install-project --no-dev

COPY src/ ./src/
RUN uv sync --frozen --no-dev || uv sync --no-dev

# ==============================================================================
# Stage 2: Runtime (Hardened Alpine, zero-CVE profile, non-root user)
# ==============================================================================
FROM python:3.14-alpine AS runtime

RUN apk update \
    && apk upgrade --no-cache \
    && apk add --no-cache curl libstdc++ \
    && rm -rf /var/cache/apk/* /usr/local/lib/python3.14/ensurepip \
    && pip uninstall -y pip setuptools 2>/dev/null || true \
    && addgroup -g 10001 -S appgroup \
    && adduser -u 10001 -S -G appgroup -h /home/appuser -s /sbin/nologin appuser

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appgroup /app/src /app/src

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "mamtemplate.presentation.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
