import asyncio
from pydantic import BaseModel
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee.storage_clients import MemoryStorageClient
from utils import extract_video_metadata

class TikTokBody(BaseModel):
    url: str
    browser_type: str = "chromium"
    label: str = "newest"
    max_items: int = 30
    max_comments: int = 100

# @post('/tiktok/get_video_links_and_metadata')
async def tiktok_get_video_links_and_metadata(tiktok_url, browser_type, label, max_items, max_comments) -> dict:
    """The crawler entry point that will be called when the HTTP endpoint is accessed."""
    # Disable writing storage data to the file system
    storage_client = MemoryStorageClient()

    crawler = PlaywrightCrawler(
        headless=True,
        max_requests_per_crawl=10,
        browser_type=browser_type,
        storage_client=storage_client,
        browser_new_context_options={
            "viewport": {"width": 1280, "height": 900}
        },
        # launchOptions=["--no-sandbox", "--disable-setuid-sandbox"]
    )

    @crawler.router.default_handler
    async def request_handler(context: PlaywrightCrawlingContext) -> None:
        context.log.info(f'Start profile crawl: {context.request.url}')

        # Lấy giới hạn số video cần crawl
        limit = max_items
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
            [tiktok_url]
    )
    data = await crawler.get_data()
    import json
    return json.dumps(data.items, indent=4)


# # Initialize the Litestar app with our route handler
# app = Litestar(route_handlers=[tiktok_get_video_links_and_metadata])

# # Start the Uvicorn server using the `PORT` environment variable provided by GCP
# # This is crucial - Cloud Run expects your app to listen on this specific port
# uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '8080')))  # noqa: S104 # Use all interfaces in a container, safely
import sys
if __name__ == "__main__":
    tiktok_url = sys.argv[4].strip()
    web = sys.argv[1].strip() if len(sys.argv) > 2 else "chromium"
    label = sys.argv[2].strip() if len(sys.argv) > 3 else "newest"
    max_items = int(sys.argv[3].strip()) if len(sys.argv) > 4 else 30
    max_comments = int(sys.argv[5]) if len(sys.argv) > 5 else 100
    
    result = asyncio.run(tiktok_get_video_links_and_metadata(tiktok_url, web, label, max_items, max_comments))
    print("Result: ")
    print(result)