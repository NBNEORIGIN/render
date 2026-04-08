FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install --with-deps chromium

COPY . .

# 2 workers: allows downloads to proceed while publish is running.
# Job state is in-memory per worker — job list tab may show incomplete history
# across workers, but all publish/export operations write to DB immediately.
CMD gunicorn app:app --bind 0.0.0.0:5000 --workers 2 --timeout 180
