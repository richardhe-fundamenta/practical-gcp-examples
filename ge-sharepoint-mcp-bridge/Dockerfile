FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app
WORKDIR /app

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev && chown -R app:app /app

USER app
ENV PYTHONUNBUFFERED=1 PORT=8080
EXPOSE 8080
CMD ["uv", "run", "--no-dev", "sharepoint-mcp-bridge"]
