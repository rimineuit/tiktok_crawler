# # 1️⃣ Base image: dùng bản slim cho nhẹ
# FROM python:3.11

# # 2️⃣ ENV + Working dir
# WORKDIR /app

# # 4️⃣ Cài Python packages
# RUN pip install --upgrade pip

# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt && \
#     pip install 'crawlee[playwright]' && \
#     playwright install
# # 7️⃣ Copy mã nguồn vào container
# # Tạo user thường và cho quyền
# # RUN useradd -m -u 10001 appuser \
# # && mkdir -p /ms-playwright /app \
# # && chown -R appuser:appuser /ms-playwright /app

# # # Playwright browsers path (ổn định quyền cho user mới)
# # ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# # USER appuser
# COPY . /app
# # 9️⃣ Mở port cho FastAPI
# # EXPOSE 8000

# # 🔟 Lệnh chạy app (Uvicorn)
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]



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
#    Đổi "main.py" thành tên file của bạn nếu khác.
CMD ["python", "app.py"]
