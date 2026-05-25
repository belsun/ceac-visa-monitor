FROM python:3.11-slim

# System deps for ddddocr (OpenCV) and general use
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ceac_monitor.py .

# State directory (will be mounted as volume)
RUN mkdir -p /app/state

CMD ["python", "ceac_monitor.py", "--loop", "--state-dir", "/app/state"]
