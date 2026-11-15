FROM node:20-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEMO_MODE=true
ENV PRICES_ONLINE=false
COPY pyproject.toml README.md LICENSE ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY sample-data ./sample-data
RUN pip install --no-cache-dir .
COPY --from=web /web/dist ./web/dist
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
