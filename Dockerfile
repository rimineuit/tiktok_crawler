# 1) Base image đã có đầy đủ Playwright + sandbox deps
FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

# 2) Làm việc trong /app
WORKDIR /app

# 3) Cài Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4) Cài browser cần thiết (Firefox). Có thể bỏ nếu muốn giữ mặc định là cài cả 3.
RUN pip install 'crawlee[playwright]' && \
    playwright install --with-deps firefox

# 5) Copy mã nguồn
COPY . /app

# 6) Expose cổng (Cloud Run sẽ map PORT)
ENV PORT=8000
EXPOSE 8000

# 7) Chạy app (bạn đã uvicorn.run(...) trong code nên chỉ cần python file chính)
CMD ["python", "app.py"]
