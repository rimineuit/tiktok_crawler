# 1️⃣ Base image: dùng bản slim cho nhẹ
FROM python:3.11 AS app

# 2️⃣ ENV + Working dir
WORKDIR /app

# 4️⃣ Cài Python packages
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    playwright install --with-deps chromium
# 7️⃣ Copy mã nguồn vào container
COPY . /app

# 9️⃣ Mở port cho FastAPI
EXPOSE 8000

# 🔟 Lệnh chạy app (Uvicorn)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]