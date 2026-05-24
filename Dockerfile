FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY templates/ ./templates/
COPY data/ ./data/

ENV PYTHONPATH=/app
ENV DATA_PATH=/app/data/properties.json

# Run once and exit (use host cron to schedule)
CMD ["python", "-m", "src.main"]
