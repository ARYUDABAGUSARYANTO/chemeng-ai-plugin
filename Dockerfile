FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY chemeng_ai_mcp_server.py .
COPY test_chemeng_ai.py .
COPY chemeng_ai_openapi.json .

# Jalankan unit test otomatis saat build untuk memastikan kualitas (Tahap 7 QA)
RUN python3 test_chemeng_ai.py

EXPOSE 8000

CMD ["sh", "-c", "uvicorn chemeng_ai_mcp_server:app --host 0.0.0.0 --port ${PORT:-8000}"]
