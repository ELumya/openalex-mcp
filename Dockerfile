FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml ./

# Install dependencies (no dev deps, no editable install)
RUN uv sync --no-dev

# Copy source
COPY src/ ./src/

# Run the MCP server in HTTP mode
ENV MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

EXPOSE 8000

CMD ["uv", "run", "python", "src/server.py"]
