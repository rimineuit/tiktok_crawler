# main.py
from datetime import timedelta

import asyncio
from utils import extract_video_metadata
from crawlee import Request
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee.storage_clients import MemoryStorageClient
import json

async def crawl_links_tiktok(url: str, browser_type: str, label: str, max_items: int, max_comments: int) -> None:
    
    """The crawler entry point."""
    storage_client = MemoryStorageClient()
    crawler = PlaywrightCrawler(
        headless=True,
        max_requests_per_crawl=3,
        request_handler_timeout=timedelta(seconds=1500),
        browser_type=browser_type,
        browser_new_context_options={
            "viewport": {"width": 1280, "height": 720},
            'permissions': []
        },
        storage_client=storage_client
    )
    
    # --- Handler mặc định: crawl trang profile để lấy link video ---
    @crawler.router.default_handler
    async def request_handler(context: PlaywrightCrawlingContext) -> None:
        url = context.request.url
        context.log.info(f'Start profile crawl: {url}')

        # Lấy giới hạn số video cần crawl
        limit = context.request.user_data.get('limit', 10)
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError('`limit` must be a positive integer')
        await context.page.wait_for_load_state("networkidle", timeout=30000)
        try:
            skip_btn = await context.page.locator("div.TUXButton-label:has-text('Skip')").first
            # Đợi tối đa 5s cho đến khi nút hiển thị
            await skip_btn.wait_for(timeout=5000)
            await skip_btn.click(timeout=1500)
        except Exception:
            pass
        # Đợi user-post hoặc nút load-more hiển thị
        await context.page.locator('[data-e2e="user-post-item"]').first.wait_for(timeout=3000)

        collected = {}
        retries = 0
        MAX_RETRIES = 3
        length_collected = 0
        while len(collected) < limit and retries < MAX_RETRIES:
            links = await extract_video_metadata(context.page)
            for item in links:
                url = item['url']
                if url not in collected:
                    collected[url] = item['views']
            
            context.log.info(f'Found {len(collected)} video links so far...')

            if len(collected) >= limit:
                break

            # Scroll xuống và chờ load thêm nội dung
            await context.page.evaluate('window.scrollBy(0, window.innerHeight);')
            await asyncio.sleep(3)  # Chờ nội dung load xong
            if len(collected) > length_collected:
                length_collected = len(collected)
                retries = 0  # reset retries if new items found
            else: 
                retries += 1

        # Tạo danh sách link video và lượt xem từ collected
        final_links = [{'url': url, 'views': views} for url, views in collected.items()]

        if not final_links:
            raise RuntimeError('No video links found on profile page')
        context.log.info(f'Queued {len(final_links)} video requests')
        # Trả về danh sách link video và lượt xem
        await context.push_data(final_links[:limit])
        
        
    # Run the crawler to collect data from several user pages
    await crawler.run(
            [Request.from_url(url, user_data={'limit': max_items, 'max_comments': max_comments}, label=label)]
    )
    data = await crawler.get_data()
    
    return json.dumps(data.items)
     
# import sys
# if __name__ == '__main__':
#     if len(sys.argv) < 4:    
#         sys.exit("Usage: python get_tiktok_video_links_and_metadata.py <browser_type> <label> <max_items> <TikTok_URL>")
    
#     tiktok_url = sys.argv[5].strip()
#     web = sys.argv[1].strip() if len(sys.argv) > 2 else "firefox"
#     label = sys.argv[2].strip() if len(sys.argv) > 3 else "newest"
#     max_items = int(sys.argv[3].strip()) if len(sys.argv) > 4 else 30
#     get_comments = sys.argv[4]
#     max_comments = int(sys.argv[6]) if len(sys.argv) > 5 else 100
#     asyncio.run(crawl_links_tiktok(tiktok_url, web, label, max_items, max_comments))