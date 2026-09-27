# Deterministic build for Cloud Run. Cloud Run injects $PORT (8080);
# main.ts honors it and binds 0.0.0.0. The server shells out to a Python
# PyMuPDF helper, so the image carries Python + uv alongside Node.
FROM node:22-slim
WORKDIR /app

# Python + uv for python/pdf_tool.py
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Python deps into /app/.venv (used at runtime by `uv run`)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Node deps + UI build
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build          # vite -> dist/app.html (read at runtime by server.ts)

ENV NODE_ENV=production
CMD ["npx", "tsx", "main.ts"]
