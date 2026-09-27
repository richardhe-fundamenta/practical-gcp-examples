# Deterministic build for Cloud Run. Cloud Run injects $PORT (8080);
# main.ts honors it and binds 0.0.0.0, so no port config is needed here.
FROM node:22-slim
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build          # vite -> dist/mcp-app.html (read at runtime by server.ts)

ENV NODE_ENV=production
CMD ["npx", "tsx", "main.ts"]
