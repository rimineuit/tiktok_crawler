# 1️⃣ Base image: dùng bản slim cho nhẹ
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

# 2️⃣ ENV + Working dir
WORKDIR /app
RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser \
    && mkdir -p /home/appuser/.cache \
    && chown -R appuser:appuser /home/appuser/.cache
# 4️⃣ Cài Python packages
RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
    # playwright install --with-deps chromium
# 7️⃣ Copy mã nguồn vào container
COPY . /app
RUN mkdir -p /app/storage
RUN chown -R appuser:appuser /app
USER appuser
# 9️⃣ Mở port cho FastAPI
EXPOSE 8000

# 🔟 Lệnh chạy app (Uvicorn)
CMD ["python", "app.py"]