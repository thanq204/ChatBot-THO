# ---- Stage 1: Build the React frontend ----
FROM node:22-slim AS frontend

WORKDIR /frontend

# Copy the manifests first so npm ci is cached until dependencies actually change.
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Build Python dependencies ----
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Stage 3: Production ----
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Security: run as non-root user
RUN useradd -m appuser

# Backend and model-only pipeline, then the compiled SPA served by FastAPI.
COPY backend/ ./backend/
COPY src/ai_models/ ./src/ai_models/
COPY --from=frontend /frontend/dist ./frontend/dist

# Create data directory with correct ownership
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:' + os.getenv('PORT', '8000') + '/health')" || exit 1

# Railway and similar platforms inject PORT at runtime. Keep 8000 as the
# local Docker default while binding the public server to the assigned port.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
