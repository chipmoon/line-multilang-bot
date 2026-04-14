# Sử dụng Python bản nhẹ
FROM python:3.11-slim

# Install system dependencies (ffmpeg for audio conversion)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

# Yêu cầu của Hugging Face: Chạy với user có UID 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Copy requirements trước để tận dụng Docker layer cache
COPY --chown=user requirements.txt .

# Cài đặt các thư viện cần thiết
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy phần còn lại của code với quyền của user
COPY --chown=user . .

# Tạo thư mục static và đảm bảo quyền ghi
RUN mkdir -p static

# Hugging Face mặc định dùng cổng 7860
ENV PORT=7860

# Chạy ứng dụng với gunicorn
CMD gunicorn --workers=1 --threads=4 --timeout=120 --bind=0.0.0.0:$PORT app:app
