from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import subprocess
import sys
import os
from utils import load_all_json_data
app = FastAPI()
env = os.environ.copy()

env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"

class TikTokBody(BaseModel):
    url: str  # Danh sách các URL TikTok
    browser_type: str = "chromium"  # Mặc định là Firefox
    label: str = "newest"  # Nhãn mặc định
    max_items: int = 30  # Số lượng video tối đa mỗi trang
    get_comments: str = "False"  # Mặc định không lấy bình luận
    max_comments: int = 100  # Số lượng bình luận tối đa mỗi video

@app.post("/tiktok/get_video_links_and_metadata")
async def tiktok_get_video_links_and_metadata(body: TikTokBody):
    label = body.label.strip().lower()
    browser_type = body.browser_type.strip().lower()
    max_comments = str(body.max_comments)
    # Nối các URL thành một chuỗi cách nhau bởi dấu cách
    clean_url = body.url.strip()
    max_items = str(body.max_items).strip()
    script_path = "tiktok_crawler/crawler.py"
    get_comments = body.get_comments
    cmd = [sys.executable, script_path, browser_type, label, max_items, get_comments, clean_url, max_comments]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=900,
            encoding="utf-8",
            env=env
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="⏱️ Quá thời gian xử lý")
    
    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi chạy script:\n{proc.stderr}"
        )
    
    try:
        result = load_all_json_data()

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi parse JSON từ output: {e}\n\n--- STDOUT ---\n{proc.stdout}"
        )
    return result