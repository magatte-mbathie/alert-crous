FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PYTHONPATH=/app/src \
	STATE_DB_PATH=/home/appuser/data/alert_crous.sqlite3

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py ./
COPY src ./src

RUN useradd --create-home appuser \
	&& mkdir -p /home/appuser/data \
	&& chown -R appuser:appuser /home/appuser/data

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
	CMD ["python", "-c", "import os; os.kill(1, 0)"]

CMD ["python", "main.py"]
