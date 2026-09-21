# ==============================================================================
# HomeCartel Marketing AI Content Automation - Production Container
# All-in-One: React UI Control Dashboard + Flask API + Python AI Pipelines
# ==============================================================================

FROM python:3.11-slim

# Avoid prompts during apt installs
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 1. Install critical Linux C & system libraries required by OpenCV (YOLO),
#    FFmpeg (video compilation), and Librosa (audio beat analysis)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsndfile1 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-cache YOLO-World model weights during Docker build so it never delays runtime
RUN python -c "from ultralytics import YOLO; YOLO('yolov8s-worldv2.pt')" || true

# 3. Copy application codebase, assets, fonts, and model weights
COPY . .

# Ensure working output directories exist
RUN mkdir -p /app/output /app/output/logs /app/output/content

# Default Port (Railway injects $PORT at runtime)
ENV PORT=5200
EXPOSE 5200

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT}/api/health || exit 1

# 4. Start the All-in-One Marketing Studio server via Gunicorn (production WSGI)
#    --timeout 600 accommodates long-running AI pipeline phases
#    Railway injects $PORT at runtime; default to 5200
CMD ["sh", "-c", "cd 'UI Control' && exec gunicorn --bind 0.0.0.0:${PORT:-5200} --workers 2 --threads 4 --timeout 600 api_server:app"]
