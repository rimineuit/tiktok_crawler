# 1️⃣ Base image: dùng bản slim cho nhẹ
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

# 2️⃣ ENV + Working dir
WORKDIR /app

# 4️⃣ Cài Python packages
RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m pip install 'crawlee[all]'
    # playwright install --with-deps chromium
# 7️⃣ Copy mã nguồn vào container
# Tạo user thường và cho quyền
# RUN useradd -m -u 10001 appuser \
# && mkdir -p /ms-playwright /app \
# && chown -R appuser:appuser /ms-playwright /app

# # Playwright browsers path (ổn định quyền cho user mới)
# ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# USER appuser
COPY . /app
# 9️⃣ Mở port cho FastAPI
# EXPOSE 8000

# 🔟 Lệnh chạy app (Uvicorn)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]