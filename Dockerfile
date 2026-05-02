# Use a lightweight Python base image
FROM python:3.10-slim AS builder

WORKDIR /app/

# Install uv (Fast dependency management)
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/
ENV PATH="/app/.venv/bin:$PATH"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Step 1️⃣: Create Virtual Environment & Install pip
RUN python -m venv .venv && \
    /app/.venv/bin/python -m ensurepip --default-pip && \
    /app/.venv/bin/python -m pip install --upgrade pip setuptools wheel

# Step 2️⃣: Copy Dependencies and Source Code (needed for uv sync)
COPY pyproject.toml uv.lock /app/
COPY swx_core /app/swx_core
COPY swx_app /app/swx_app

# Step 3️⃣: Install Dependencies with `uv`
# Note: uv sync needs source code to resolve the package
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv .venv && \
    (uv sync --frozen --no-install-project 2>&1 || uv pip install -e ".[dev]")

# Step 4️⃣: Reinstall pip AFTER uv (because uv wipes pip)
RUN /app/.venv/bin/python -m ensurepip --default-pip && \
    /app/.venv/bin/python -m pip install --upgrade pip setuptools wheel

# Step 5️⃣: Install SwX-API as a Package
RUN /app/.venv/bin/python -m pip install .

# Stage 2: Final lightweight image
FROM python:3.10-slim

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app/

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Ensure `.venv` activation
ENV PATH="/app/.venv/bin:$PATH"

# Copy application files & dependencies to the final stage
COPY  swx_core /app/swx_core
COPY  swx_app /app/swx_app
COPY  alembic.ini /app/alembic.ini
COPY  migrations /app/migrations

COPY  scripts /app/scripts

COPY .env /app/.env

# ✅ Fix: Copy `pyproject.toml` to the final stage
COPY pyproject.toml /app/

# ✅ Correct Installation: Use `pip install .`
RUN /app/.venv/bin/python -m pip install .

# Expose FastAPI port
EXPOSE 8000


# Default command (Users can override this in Docker Compose)
CMD ["/app/.venv/bin/uvicorn", "swx_core.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
