FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/index.html frontend/vite.config.js ./
COPY frontend/src ./src
RUN npm run build

FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 WEB_PUBLIC_MODE=true WEB_LIVE_ENABLED=false
WORKDIR /app
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY backend ./backend
COPY data/examples ./data/examples
COPY docs/evidence/phase2-clean.json docs/evidence/phase2-flawed.json docs/evidence/phase2-adversarial.json ./docs/evidence/
COPY scripts/serve.py ./scripts/serve.py
COPY scripts/container_start.py ./scripts/container_start.py
COPY --from=frontend /build/dist ./frontend/dist
RUN useradd --user-group --uid 10001 --create-home lumen && mkdir -p /app/runtime && chown -R lumen:lumen /app
EXPOSE 8000
CMD ["python", "scripts/container_start.py"]
