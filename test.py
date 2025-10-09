import json
import os
import logging
import uvicorn
from litestar import Litestar, get, post
from logging.handlers import TimedRotatingFileHandler
from utils import extract_video_metadata
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee.storage_clients import MemoryStorageClient
from pydantic import BaseModel
import sys
import logging
import asyncio

def setup_logger():
    log_dir = os.getenv("LOG_DIR", "/app/logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, os.getenv("LOG_FILE", "app.log"))

    logger = logging.getLogger()  # root
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logger.addHandler(ch)

    # File (rotate daily, keep 7 days)
    fh = TimedRotatingFileHandler(log_file, when="midnight", backupCount=7, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logger.addHandler(fh)

    # Align common libraries
    for name in ["crawlee", "playwright", "uvicorn", "asyncio"]:
        logging.getLogger(name).setLevel(logger.level)

    logging.info(f"Logging initialized. File: {log_file}")
    return logger

logger = setup_logger()
class TikTokBody(BaseModel):
    url: str
    browser_type: str = "chromium"
    label: str = "newest"
    max_items: int = 30
    max_comments: int = 100

@post('/')
async def main(data: TikTokBody) -> str:
    """The crawler entry point that will be called when the HTTP endpoint is accessed."""
    # Disable writing storage data to the file system
    # storage_client = MemoryStorageClient()

    crawler = PlaywrightCrawler(
        headless=True,
        max_requests_per_crawl=10,
        browser_type='firefox',
        # storage_client=storage_client,
    )

    @crawler.router.default_handler
    async def default_handler(context: PlaywrightCrawlingContext) -> None:
        """Default request handler that processes each page during crawling."""
        context.log.info(f"Start profile crawl: {context.request.url}")

        # Hook browser console logs (giúp debug selector/JS)
        def _on_console(msg):
            try:
                logger.info("[page.console] %s: %s", msg.type, msg.text)
            except Exception:
                logger.exception("Console log parse error")
        context.page.on("console", _on_console)

        # Log response của API item_list
        def _on_response(resp):
            try:
                url = resp.url
                if "api/post/item_list" in url:
                    logger.info("[page.response] %s %s", resp.status, url)
            except Exception:
                logger.exception("Response log parse error")
        context.page.on("response", _on_response)
        # ========================================

        # Lấy giới hạn số video cần crawl
        limit = data.max_items
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError("`limit` must be a positive integer")

        try:
            await context.page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            logger.exception("wait_for_load_state failed")

        # Close modal if present
        try:
            skip_btn = await context.page.locator("div.TUXButton-label:has-text('Skip')").first
            await skip_btn.wait_for(timeout=5000)
            await skip_btn.click(timeout=1500)
            logger.info("Clicked 'Skip' modal successfully.")
        except Exception:
            logger.info("No 'Skip' modal or click failed; continuing.")

        # Đợi user-post xuất hiện
        try:
            await context.page.locator('[data-e2e="user-post-item"]').first.wait_for(timeout=5000)
        except Exception:
            logger.warning("No user-post item appeared within timeout; still continuing.")

        collected = {}
        retries = 0
        MAX_RETRIES = 3
        length_collected = 0

        while len(collected) < limit and retries < MAX_RETRIES:
            try:
                links = await extract_video_metadata(context.page)
                logger.info("extract_video_metadata returned %d items", len(links))
            except Exception:
                logger.exception("extract_video_metadata failed")
                links = []

            for item in links:
                try:
                    url = item["url"]
                    if url not in collected:
                        collected[url] = item.get("views")
                except Exception:
                    logger.exception("Bad item structure: %s", item)

            context.log.info(f"Found {len(collected)} video links so far...")

            if len(collected) >= limit:
                break

            # Scroll để load thêm
            try:
                await context.page.evaluate("window.scrollBy(0, window.innerHeight);")
            except Exception:
                logger.exception("Scroll evaluate failed")

            await asyncio.sleep(3)

            if len(collected) > length_collected:
                length_collected = len(collected)
                retries = 0
            else:
                retries += 1
                logger.info("No new items; retries=%d/%d", retries, MAX_RETRIES)

        final_links = [{"url": url, "views": views} for url, views in collected.items()]
        logger.info("Collected %d items (limit=%d).", len(final_links), limit)

        if not final_links:
            # Dump debug artifacts
            try:
                log_dir = os.getenv("LOG_DIR", "/app/logs")
                os.makedirs(log_dir, exist_ok=True)
                screenshot_path = os.path.join(log_dir, "last_error.png")
                html_path = os.path.join(log_dir, "last_error.html")
                await context.page.screenshot(path=screenshot_path, full_page=True)
                content = await context.page.content()
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.error("No video links found. Saved screenshot=%s and html=%s", screenshot_path, html_path)
            except Exception:
                logger.exception("Saving debug artifacts failed")

            raise RuntimeError("No video links found on profile page")

        await context.push_data(final_links[:limit])
        logger.info("Pushed %d items to dataset.", min(len(final_links), limit))

    # Run crawler
    try:
        await crawler.run([data.url])
    except Exception as e:
        logger.exception("Crawler run failed")
        raise e

    # Retrieve dataset items
    data = await crawler.get_data()
    items = getattr(data, "items", [])
    logger.info("Crawler finished. Dataset items=%d", len(items))

    # Persist last result to file for quick inspection
    try:
        log_dir = os.getenv("LOG_DIR", "/app/logs")
        os.makedirs(log_dir, exist_ok=True)
        out_json = os.path.join(log_dir, "last_results.json")
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        logger.info("Saved last_results.json to %s", out_json)
    except Exception:
        logger.exception("Failed to save last_results.json")

    return json.dumps(items, indent=4, ensure_ascii=False)


# Initialize the Litestar app with our route handler
app = Litestar(route_handlers=[main])

# Start the Uvicorn server using the `PORT` environment variable provided by GCP
# This is crucial - Cloud Run expects your app to listen on this specific port
uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '8080')))  # noqa: S104 # Use all interfaces in a container, safely