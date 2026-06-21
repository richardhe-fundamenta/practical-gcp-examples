# Analytics sandbox runtime: the upstream python-runtime-sandbox FastAPI server (main.py,
# Apache-2.0) + a data/analytics package stack, built with uv.
FROM python:3.12-slim

# libgomp1 is the OpenMP runtime scikit-learn / scipy wheels load at import.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# uv binary from the official distroless image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install into the SYSTEM python (no venv): /execute runs user code as `python3 main.py`
# (PATH's python), so the packages must live there — not in a venv.
COPY pyproject.toml .
RUN uv pip install --system --no-cache -r pyproject.toml

COPY main.py .

# matplotlib/altair need a writable cache/config dir when running as the non-root UID.
ENV MPLCONFIGDIR=/tmp/mpl XDG_CACHE_HOME=/tmp/cache

RUN chown -R 1000:1000 /app
USER 1000

EXPOSE 8888

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8888"]
