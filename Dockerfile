FROM python:3.12-slim

WORKDIR /app

# System dependencies for psycopg2, Pillow, bidi
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-railway.txt .
RUN pip install --no-cache-dir -r requirements-railway.txt

COPY . .

CMD ["sh", "-c", "uvicorn bot_app:app --host 0.0.0.0 --port ${PORT:-8080}"]
