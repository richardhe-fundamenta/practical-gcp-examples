# Router image, built with uv.
FROM python:3.14-slim

# uv binary from the official distroless image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies from the locked manifest (reproducible, no dev deps).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY sandbox_router.py .

# Change ownership of the /app directory to the non-root user 1000.
RUN chown -R 1000:1000 /app
USER 1000

# Expose the port that the Uvicorn server will run on.
# This must match the port in the CMD instruction below.
EXPOSE 8080

# Run uvicorn directly from the venv uv built — avoids invoking `uv` at runtime
# (uv would try to init a cache under HOME, which fails for the non-root UID).
# --port must match the container port / service targetPort.
CMD ["/app/.venv/bin/uvicorn", "sandbox_router:app", "--host", "0.0.0.0", "--port", "8080"]
