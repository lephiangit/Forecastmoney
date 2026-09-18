FROM python:3.11-slim

WORKDIR /app

# Mặc định của image là PRODUCTION. Nếu không đặt, config.py coi đây là môi trường
# dev: /docs mở công khai và validate_for_production() thoát sớm, nên toàn bộ cổng
# kiểm tra secret mặc định + CORS bị bỏ qua và app vẫn khởi động bình thường.
ENV ENVIRONMENT=production

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/
# Copy shared model files
COPY models/ ./models/
RUN mkdir -p data/

# Expose port
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
