FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
COPY backend backend
COPY ml ml
COPY optimization optimization
COPY iot iot
COPY scripts scripts
COPY alembic.ini .
# Trained model artifacts (ml/models/*.joblib) are committed; the dataset is regenerated reproducibly:
RUN python scripts/generate_data.py
EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
