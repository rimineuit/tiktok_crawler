import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import re
import json
import os
app = FastAPI()
env = os.environ.copy()

env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"

class TikTokBody(BaseModel):
    url: str
    browser_type: str = "chromium"
    label: str = "newest"
    max_items: int = 30
    max_comments: int = 100

import sys
@app.post("/tiktok/get_video_links_and_metadata")
async def tiktok_get_video_links_and_metadata(body: TikTokBody):
    try:
        # Gọi crawler trực tiếp bằng await
        label = body.label.strip().lower()
        browser_type = body.browser_type.strip().lower()
        max_comments = str(body.max_comments)
        # Nối các URL thành một chuỗi cách nhau bởi dấu cách
        clean_url = body.url.strip()
        max_items = str(body.max_items).strip()
        script_path = "get_list_videos.py"
        cmd = [sys.executable, script_path, browser_type, label, max_items, clean_url, max_comments]
        print(cmd)
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
            
        try:
            # Lấy phần output sau chữ "Result"
            result_start = proc.stdout.find("Result:\n ")
            if result_start == -1:
                raise ValueError("Không tìm thấy đoạn 'Result' trong stdout")

            json_part = proc.stdout[result_start:]  # phần sau "Result"
            # Tìm JSON mảng đầu tiên bắt đầu bằng [ và kết thúc bằng ]
            json_match = re.search(r"\[\s*{[\s\S]*?}\s*\]", json_part)
            
            if not json_match:
                raise ValueError("Không tìm thấy JSON hợp lệ trong stdout")

            json_text = json_match.group(0).replace("\n", "")
            result_json = json.loads(json_text)

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi parse JSON từ output: {e}\n\n--- STDOUT ---\n{proc.stdout}"
            )
            
        return result_json

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="⏱️ Quá thời gian xử lý")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi crawler: {e}")
