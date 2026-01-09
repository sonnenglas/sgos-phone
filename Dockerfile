# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# Stage 2: Python runtime
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies and dotenvx
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && curl -sfS https://dotenvx.sh | sh \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/
COPY .env .

# Copy built frontend
COPY --from=frontend-build /frontend/dist /app/static

# Create data directory
RUN mkdir -p /app/data/voicemails

EXPOSE 8000

# dotenvx decrypts .env using DOTENV_PRIVATE_KEY env var
CMD ["sh", "-c", "dotenvx run -- sh -c 'alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000'"]
