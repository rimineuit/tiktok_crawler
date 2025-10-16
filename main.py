import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Annotated, List, Any
import re
import json
import os
import sys


#Tạo FastAPI app
app = FastAPI(
    title="Crawler",
    description="""
    API nội bộ để crawl video và metadata từ TikTok.
    
    **Chức năng chính:**
    - Crawl video & metadata
    - Crawl comment
    - Lưu JSON kết quả
    
    **Lưu ý:** Chỉ dành cho mục đích nghiên cứu.
    """,
    version="1.0.0",
    contact={
        "name": "RIMINE",
        "email": "minh0974680144@gmail.com",
    },
)

env = os.environ.copy()

# Đảm bảo UTF-8 cho subprocess
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"


""" 
Thu thập danh sách video từ trang người dùng
"""

class TikTokUserPageCrawler(BaseModel):
    url: Annotated[str, Field(description="Đường dẫn tới trang cá nhân", examples=['https://www.tiktok.com/@suongvufamily'])]
    browser_type: Annotated[str, Field(default="firefox" ,description="Loại trình duyệt (hiện tại chỉ hỗ trợ 'firefox')", examples=["firefox", "chromium", "webkit"])]
    max_items: Annotated[int, Field(default=10, ge=1, le=200, description="Số lượng video tối đa cần crawl (1–200)")]

@app.post("/tiktok/get_video_links_on_user_page", tags=["TikTok Crawler"], summary="Lấy danh sách video trên trang cá nhân")
async def get_video_links_on_user_page(body: TikTokUserPageCrawler):
    try:
        browser_type = body.browser_type.strip().lower()
        clean_url = body.url.strip()
        max_items = str(body.max_items).strip()
        script_path = 'tiktok.get_list_videos'
        cmd = [sys.executable, "-m" ,script_path, browser_type, max_items, clean_url]
        
        # Gọi subprocess
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout_b, stderr_b = await proc.communicate()
        out = stdout_b.decode("utf-8", "ignore")
        err = stderr_b.decode("utf-8", "ignore")
            
        try:
            # Lấy phần output sau chữ "Result"
            result_start = out.find("Result:\n ")
            if result_start == -1:
                raise ValueError("Không tìm thấy đoạn 'Result' trong stdout")

            json_part = out[result_start:]
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

"""
Thu thập comments từ người dùng
"""
from tiktok import get_comments
class TikTokCrawlComments(BaseModel):
    id: Annotated[str, Field(description="ID của bài đăng trên tiktok", examples=['7516102298347506952'])]
    
@app.post("/tiktok/get_comments", tags=['TikTok Crawler'], summary="Lấy danh sách comments của 1 video")
async def get_comments_of_video(body: TikTokCrawlComments):
    id = str(body.id)
    try:
        comments = get_comments(id)
        return comments
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy bình luận: {e}")
    
"""
Thu thập bài viết từ trang tiktok trend
"""
from tiktok_trend.playwright_tiktok_ads import crawl_tiktok_trend_videos
class TikTokTrendCrawlPost(BaseModel):
    limit: Annotated[str, Field(description="Số lượng tối đa cần thu thập (max là 500)", examples=[500], default=500)]
    period: Annotated[str, Field(description="Period trong trang TikTokTrend", default="7", example=[7, 30, 120])]
    
@app.post("/tiktoktrend/crawl_post", tags=['TikTokTrend Crawler'], summary="Thu thập danh sách bài viết trên trang TikTokTrend")
async def crawl_posts_from_tiktoktrend(body: TikTokTrendCrawlPost):
    limit = int(body.limit)
    period = body.period
    try:
        result = await crawl_tiktok_trend_videos(limit=limit, period=period)
        for idx, r in enumerate(result, start=1):
            r['ranking'] = idx
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {e}")
        
    return result
    

"""
Thu thập danh sách link nhạc từ TikTokTrend
"""
from tiktok_trend.playwright_tiktok_audio import crawl_tiktok_trend_audio
class TikTokTrendCrawlAudio(BaseModel):
    limit: Annotated[str, Field(description="Số lượng tối đa cần thu thập (max là 100)", examples=[100], default=100)]
    period: Annotated[str, Field(description="Period trong trang TikTokTrend", default="7", example=[7, 30, 120])]

@app.post("/tiktoktrend/crawl_audio", tags=['TikTokTrend Crawler'], summary="Thu thập danh sách audio trên trang TikTokTrend")
async def crawl_audios_from_tiktoktrend(body: TikTokTrendCrawlAudio):
    limit = int(body.limit)
    period = body.period
    
    # cmd = [sys.executable, "-m", "tiktok_trend.playwright_tiktok_audio", limit, period]
    try:
        result = await crawl_tiktok_trend_audio(limit=limit, period=period)
        for idx, r in enumerate(result, start=1):
            r['period'] = period
            r['ranking'] = idx
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {e}")
    
    return result
        
"""
Lấy transcripts của video tiktok
"""
from utils.get_transcripts import download_transcript
class GetTranscriptsTikTok(BaseModel):
    url: Annotated[str, Field(default="https://www.tiktok.com/@cotuyenhoala/video/7527196260919512328", description="Lấy transcripts của một video tiktok", examples=["https://www.tiktok.com/@cotuyenhoala/video/7527196260919512328"])]
    
@app.post("/utils/get_transcripts", tags=['utils'])
async def get_transcripts(body: GetTranscriptsTikTok):
    url = body.url
    try:
        result = await download_transcript(url)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {e}")
    
"""
Lấy các từ giống nhau
"""
from analysis_tiktok_trend.groups_pruned import group_ngrams_from_lists
class GetPrunnedGroup(BaseModel):
    ids: Annotated[List[Any], Field(examples=[[1,2,3]], description="Danh sách các id")]
    transcripts: Annotated[List[str], Field(examples=['hi','hello','goodbye'], description="Danh sách các đoạn văn")]
    nmin: Annotated[int, Field(examples=[2], default=2, description="Độ dài đoạn nhỏ nhất được gom nhóm")]
    nmax: Annotated[int, Field(examples=[100], default=100, description="Độ dài đoạn lớn nhất được gom nhóm")]
    min_id_count: Annotated[int, Field(examples=[2], default=2, description="Số id nhỏ nhất trong một nhóm")]
@app.post("/utils/get_prunned_groups", tags=['utils'])
async def get_prunned_groups(body: GetPrunnedGroup):
    ids = body.ids
    transcripts = body.transcripts
    nmin = body.nmin
    nmax = body.nmax
    min_id_count = body.min_id_count
    try:
        result = group_ngrams_from_lists(ids,transcripts, nmin, nmax, min_id_count)
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {e}")
    