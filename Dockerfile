FROM node:24-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=10000
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/sentiment-model.json ./backend/sentiment-model.json
COPY scripts/download_sentiment_model.py ./scripts/download_sentiment_model.py
RUN python scripts/download_sentiment_model.py
COPY docs/model-license.txt ./models/sentiment/LICENSE
COPY docs/sentiment.md ./models/sentiment/MODEL-NOTES.md
COPY backend/ ./backend/
COPY --from=frontend /build/dist/ ./frontend/dist/
RUN useradd --create-home wall && mkdir -p /app/data && chown wall:wall /app/data
USER wall
EXPOSE 10000
CMD ["sh", "-c", "exec python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --proxy-headers"]
