# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Inherit build arguments for labels
ARG GRAPHITI_VERSION
ARG BUILD_DATE
ARG VCS_REF

# OCI image annotations
LABEL org.opencontainers.image.title="Graphiti FastAPI Server"
LABEL org.opencontainers.image.description="FastAPI server for Graphiti temporal knowledge graphs"

# Install uv using the installer script
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin:$PATH"

# Configure uv for runtime
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Set up the server application
WORKDIR /app
COPY ./server/pyproject.toml ./server/README.md ./server/uv.lock ./
COPY ./server/graph_service ./graph_service

# Install server dependencies
ARG INSTALL_FALKORDB=false
RUN uv sync --frozen --no-dev && \
    if [ -n "$GRAPHITI_VERSION" ]; then \
        if [ "$INSTALL_FALKORDB" = "true" ]; then \
            uv pip install --system --upgrade "graphiti-core[falkordb]==$GRAPHITI_VERSION"; \
        else \
            uv pip install --system --upgrade "graphiti-core==$GRAPHITI_VERSION"; \
        fi; \
    else \
        if [ "$INSTALL_FALKORDB" = "true" ]; then \
            uv pip install --system --upgrade "graphiti-core[falkordb]"; \
        else \
            uv pip install --system --upgrade graphiti-core; \
        fi; \
    fi

# Set environment variables - add venv to PATH
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Set port
ENV PORT=8000
EXPOSE $PORT

# Use venv's uvicorn directly instead of uv run
CMD ["/app/.venv/bin/uvicorn", "graph_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
