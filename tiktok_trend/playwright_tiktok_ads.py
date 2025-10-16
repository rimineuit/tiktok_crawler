from playwright.async_api import async_playwright
import gc

# ===== Constants =====
TIKTOK_URL = "https://ads.tiktok.com/business/creativecenter/inspiration/popular/pc/vi"
# Block resource types - giữ những cần thiết cho scraping
BLOCKED_TYPES = {
    "image", 
    "font", 
    "stylesheet", 
    "media",
    "websocket",  # real-time connections không cần
    "manifest",   # app manifests
    "texttrack",  # video captions/subtitles
    "eventsource" # server-sent events
}

# Block URLs chứa keywords này
BLOCKED_KEYWORDS = {
    # Analytics & Tracking
    "analytics", "tracking", "collect", "adsbygoogle",
    "googletagmanager", "gtag", "facebook.com/tr", "pixel",
    "doubleclick", "googlesyndication", "googleadservices",
    
    # Social widgets & embeds (không cần cho scraping)
    "widget", "embed", "share-button", "social",
    
    # Ads & Marketing
    "adsystem", "advertising", "marketing", "campaign",
    
    # Monitoring & Error reporting
    "sentry", "bugsnag", "rollbar", "logrocket", "hotjar",
    
    # CDN assets không cần thiết
    "webfont", "woff", "woff2", "ttf", "eot",
    
    # Video/Audio (nếu không cần preview)
    "mp4", "webm", "ogg", "mp3", "wav",  # uncomment nếu muốn block media files
}

# Optional: Block specific domains hoàn toàn
BLOCKED_DOMAINS = {
    "google-analytics.com",
    "googletagmanager.com", 
    "doubleclick.net",
    "facebook.com",
    "connect.facebook.net",
    "analytics.tiktok.com",  # TikTok's own analytics
}

# ===== Logging =====
def log(msg, level="INFO"):
    print(f"[{level}] {msg}")

# ===== Dropdown Helper =====
"""
Chọn quốc gia là việt nam để thu thập đúng dữ liệu
"""
async def select_dropdown_option(page, placeholder_text, value, option_selector):
    try:
        input_field = await page.wait_for_selector(f'input[placeholder="{placeholder_text}"]', timeout=5000)
        await input_field.fill(value)
        await page.wait_for_timeout(1000)
        dropdown_item = await page.wait_for_selector(option_selector, timeout=5000)
        await dropdown_item.click()
        await page.wait_for_timeout(1000)
        log("Dropdown option selected successfully.")
        return True
    except Exception as e:
        log(f"Dropdown selection failed: {e}", "ERROR")
        return False

# ===== Main Crawler =====
async def crawl_tiktok_trend_videos(url=TIKTOK_URL, limit=500, period="7"):
    async with async_playwright() as p:
        browser = await p.firefox.launch(
            headless=True
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            bypass_csp=True,
            java_script_enabled=True
        )

        async def route_filter(route, request):
            url = request.url.lower()
            
            # Block by resource type
            if request.resource_type in BLOCKED_TYPES:
                return await route.abort()
            
            # Block by keywords in URL
            if any(keyword in url for keyword in BLOCKED_KEYWORDS):
                return await route.abort()
            
            # Block by domain (optional)
            if any(domain in url for domain in BLOCKED_DOMAINS):
                return await route.abort()
            
            return await route.continue_()

        await context.route("**/*", route_filter)
        page = await context.new_page()

        try:
            await page.goto(url)
            await page.wait_for_load_state("domcontentloaded")
            log(f"Navigated to {url}")

            # Close banner if present
            try:
                banner = await page.wait_for_selector("#ccModuleBannerWrap div div div div", timeout=5000)
                await banner.click()
                await page.wait_for_timeout(1000)
                log("Banner clicked.")
            except:
                log("Banner not found or clickable.")

            # Set language to Vietnamese
            await select_dropdown_option(
                page,
                "Nhập/chọn từ danh sách",
                "việt nam",
                'div.byted-select-popover-panel-inner span.byted-high-light:has-text("Việt Nam")'
            )
            
            # ===== Kiểm tra đã chọn ngôn ngữ là "Việt Nam" =====
            try:
                lang_selector = await page.wait_for_selector(
                    "#ccModuleBannerWrap div div div div span span span span div span:nth-child(1)",
                    timeout=5000
                )
                current_lang = (await lang_selector.inner_text()).strip()
                if current_lang != "Việt Nam":
                    raise ValueError(f"Ngôn ngữ hiện tại là '{current_lang}', không phải 'Việt Nam'")
                log("Đã xác nhận ngôn ngữ là 'Việt Nam'.")
            except Exception as e:
                log(f"Lỗi khi kiểm tra ngôn ngữ: {e}", "ERROR")
                return []
            
            
            # 1) Mở dropdown (không gán .wait_for() vào biến)
            dropdown = page.locator('#ccContentContainer > div.BannerLayout_listWrapper__2FJA_ > div > div.PopularList_listSearcher__Bko2l.index-mobile_listSearcher__rKZAb > div.ListFilter_container__DwDsk.index-mobile_container__3wl4i.PopularList_sorter__N_G9_.index-mobile_filters__LxraM > div:nth-child(1) > div.ListFilter_RightSearchWrap__UyaKk > div > span.byted-select.byted-select-size-md.byted-select-single.byted-can-input-grouped.CcRimlessSelect_ccRimSelector__m4xdd.index-mobile_ccRimSelector__S2lLr.index-mobile_sortWrapSelect__2Yw1N > span > span > span > div')
            await dropdown.click()  # click tự đợi visible + enabled
            
            # 2) Chọn period
            await page.wait_for_selector('#tiktokPeriodSelect > span > div > div', timeout=10000)
            period_button = await page.query_selector('#tiktokPeriodSelect > span > div > div')
            if period_button:
                await period_button.click()
                await page.wait_for_selector(f"div.creative-component-single-line:has-text('{period} ngày qua')", timeout=5000)

                month_period = await page.query_selector(f"div.creative-component-single-line:has-text('{period} ngày qua')")
                if month_period:
                    await month_period.click()
                    log(f"Đã chọn khoảng thời gian '{period}'.")
            else:
                log("Không tìm thấy nút chọn khoảng thời gian.", "ERROR")
                return []
            
            await page.wait_for_timeout(10000)

            try:
                await page.wait_for_selector('blockquote[data-video-id]', timeout=10000)
                log("Video elements loaded.")
            except:
                log("Video elements not found. Exiting.", "ERROR")
                return []

            collected = []
            seen_ids = set()
            empty_attempts = 0

            while len(collected) < limit:
                video_elements = await page.query_selector_all('blockquote[data-video-id]')
                new_found = 0

                for el in video_elements[-20:]:  # Only scan the most recent ones
                    video_id = await el.get_attribute("data-video-id")
                    if video_id and video_id not in seen_ids:
                        seen_ids.add(video_id)
                        collected.append({
                            'video_id': video_id,
                            'url': f"https://www.tiktok.com/@_/video/{video_id}"
                        })
                        new_found += 1

                if new_found == 0:
                    empty_attempts += 1
                    log(f"No new videos found. Attempt {empty_attempts}/3")
                    if empty_attempts >= 3:
                        log("No new videos for 3 consecutive attempts. Stopping.")
                        break
                else:
                    empty_attempts = 0

                log(f"Collected {len(collected)} / {limit} videos...")

                if len(collected) >= limit:
                    break
                
                view_more = await page.query_selector('div[data-testid="cc_contentArea_viewmore_btn"]')
                if view_more:
                    await view_more.scroll_into_view_if_needed()
                    await page.wait_for_timeout(500)
                    await view_more.click()
                    log("Clicked 'View More' button.")
                    try:
                        await page.wait_for_function(
                            f'document.querySelectorAll("blockquote[data-video-id]").length > {len(seen_ids)}',
                            timeout=10000
                        )
                    except:
                        await page.wait_for_timeout(2000)
                else:
                    log("No 'View More' button found. Stopping.")
                    break

                gc.collect()

            return collected[:limit]

        finally:
            await context.close()
            await browser.close()
            
# import asyncio
# import json, sys
# # ===== CLI Runner =====
# if __name__ == "__main__":
#     try:
#         limit = int(sys.argv[1]) if len(sys.argv) > 1 else 500
#         period = str(sys.argv[2]) if len(sys.argv) > 2 else "7"
#         result = asyncio.run(crawl_tiktok_trend_videos(TIKTOK_URL, limit=limit, period=period))
#         for idx, item in enumerate(result, start=1):
#             item["ranking"] = idx

#         log("Result:")
#         print(json.dumps(result, indent=2, ensure_ascii=False))
#     except Exception as e:
#         log(f"Unexpected error: {e}", "FATAL")
#         sys.exit(1)