# Sử dụng Python bản nhẹ
FROM python:3.9-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Copy requirements trước để tận dụng Docker layer cache
COPY requirements.txt .

# Cài đặt các thư viện cần thiết
RUN pip install --no-cache-dir -r requirements.txt

# Copy phần còn lại của code
COPY . .

# Tạo thư mục static nếu chưa có
RUN mkdir -p static

# Cổng mặc định của Render/Cloud Run là 8080
ENV PORT=8080

# Chạy ứng dụng với gunicorn (production-ready)
CMD gunicorn --workers=1 --threads=4 --timeout=120 --bind=0.0.0.0:$PORT app:app
