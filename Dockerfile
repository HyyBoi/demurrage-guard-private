# DemurrageGuard engine: FastAPI (REST) + MCP server, one container.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine ./engine
COPY samples ./samples

# Alternate Clouds: set PORT = 8000 in the Source tab (must match, or you get a 502).
EXPOSE 8000
CMD ["sh", "-c", "uvicorn engine.app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
