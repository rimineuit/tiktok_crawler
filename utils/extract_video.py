from crawlee.crawlers import PlaywrightCrawlingContext
from crawlee.router import Router
from datetime import datetime, timezone
import pytz

def convert_timestamp_to_vn_time(timestamp: int) -> str:
    # Khởi tạo timezone
    vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    
    # Dùng timezone-aware UTC datetime (chuẩn mới)
    dt_utc = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    
    # Chuyển sang Asia/Ho_Chi_Minh
    dt_vn = dt_utc.astimezone(vn_tz)
    
    return dt_vn.strftime("%Y-%m-%d %H:%M:%S")


router = Router[PlaywrightCrawlingContext]()

import re

def normalize_views(view_str: str) -> int:
    """
    Chuyển chuỗi lượt xem (vd: '1.2M', '15K', '732') thành số nguyên.
    """
    view_str = view_str.strip().upper().replace(",", "")  # '1.2m' → '1.2M'

    match = re.match(r'^([\d\.]+)([MK]?)$', view_str)
    if not match:
        return 0

    number_str, suffix = match.groups()
    number = float(number_str)

    if suffix == 'M':
        return int(number * 1_000_000)
    elif suffix == 'K':
        return int(number * 1_000)
    else:
        return int(number)

async def extract_video_metadata(page) -> list[dict]:
    """
    Trích xuất danh sách video với URL và lượt xem (đã chuẩn hóa).
    Trả về dạng: [{'url': ..., 'views': int}, ...]
    """
    results = []
    video_items = await page.query_selector_all('[data-e2e="user-post-item"]')

    for item in video_items:
        link_el = await item.query_selector('a[href*="/video/"]')
        href = await link_el.get_attribute('href') if link_el else None

        views_el = await item.query_selector('[data-e2e="video-views"]')
        views_text = await views_el.inner_text() if views_el else None

        if href and views_text:
            results.append({
                'url': href,
                'views': normalize_views(views_text)
            })

    return results
