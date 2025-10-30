FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gcc && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app

RUN useradd -u 1000 -m appuser
RUN chown -R 1000:1000 /app

USER 1000:1000

HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
  CMD pgrep -f "python.*poller.py" || exit 1

CMD ["python", "-u", "poller.py"]