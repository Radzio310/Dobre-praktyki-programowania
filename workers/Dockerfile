FROM python:3.11-slim

WORKDIR /app

# OpenCV headless + numpy wymagają paru bibliotek systemowych
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY analyze_worker.py /app/analyze_worker.py
COPY result_dispatcher.py /app/result_dispatcher.py
COPY image_detection.py /app/image_detection.py

ENV PYTHONPATH=/app
