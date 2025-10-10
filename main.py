import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import re
import json
import os
import sys

# Tính đường dẫn tuyệt đối của file hiện tại
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
print(BASE_DIR)
#Tạo FastAPI app
app = FastAPI()
env = os.environ.copy()

# Đảm bảo UTF-8 cho subprocess
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"


class TikTokBody(BaseModel):
    url: str
    browser_type: str = "firefox"
    label: str = "newest"
    max_items: int = 30
    max_comments: int = 100

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
        script_path = 'tiktok.get_list_videos'
        cmd = [sys.executable, "-m" ,script_path, browser_type, label, max_items, clean_url, max_comments]
        print(*cmd)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_b, stderr_b = await proc.communicate()
            out = stdout_b.decode("utf-8", "ignore")
            err = stderr_b.decode("utf-8", "ignore")

            if proc.returncode != 0:
                raise HTTPException(500, detail=f"Script exit {proc.returncode}:\n{err}")
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="⏱️ Quá thời gian xử lý")
            
        try:
            # Lấy phần output sau chữ "Result"
            result_start = out.find("Result:\n ")
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
