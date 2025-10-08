import sys, asyncio
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass
    
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from tiktok_crawler.crawler import crawl_links_tiktok   # Import hàm async đã có
import shutil
app = FastAPI()

class TikTokBody(BaseModel):
    url: str
    browser_type: str = "chromium"
    label: str = "newest"
    max_items: int = 30
    max_comments: int = 100

@app.post("/tiktok/get_video_links_and_metadata")
async def tiktok_get_video_links_and_metadata(body: TikTokBody):
    try:
        # Gọi crawler trực tiếp bằng await
        await crawl_links_tiktok(
            url=body.url.strip(),
            browser_type=body.browser_type.strip().lower(),
            label=body.label.strip().lower(),
            max_items=body.max_items,
            max_comments=body.max_comments
        )

        # Sau khi chạy xong, đọc file results.json
        import json, os
        if not os.path.exists("results.json"):
            raise HTTPException(status_code=500, detail="Không tìm thấy file results.json")

        with open("results.json", "r", encoding="utf-8") as f:
            result = json.load(f)
        # Xoá file sau khi đọc
        import os, shutil

        # Xóa file (nếu tồn tại)
        if os.path.exists("results.json"):
            os.remove("results.json")

        # Xóa folder (nếu tồn tại)
        if os.path.exists("storage"):
            shutil.rmtree("storage")

        return {"status": "success", "data": result}

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="⏱️ Quá thời gian xử lý")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi crawler: {e}")
