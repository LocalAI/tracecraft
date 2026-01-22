# Development container for AgentTrace
FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install additional system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    make \
    && rm -rf /var/lib/apt/lists/*

# Configure uv
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# Set working directory
WORKDIR /workspace

# Create and configure virtual environment directory
RUN mkdir -p /workspace/.venv && chown vscode:vscode /workspace/.venv

# Switch to non-root user
USER vscode

# Configure shell for uv
RUN echo 'eval "$(uv generate-shell-completion bash)"' >> ~/.bashrc

# Default command
CMD ["sleep", "infinity"]
