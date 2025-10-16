from playwright.async_api import async_playwright
import json
import gc
import time
import sys
from urllib.parse import unquote, urljoin

BASE_URL = "https://www.tiktok.com/music/"

def extract_song_info(audio_url):
    """Trích xuất song_name (chữ) và song_id (số cuối) từ audio_url."""
    try:
        part = audio_url.split("song/", 1)[1].split("?", 1)[0]
    except IndexError:
        return None, None

    decoded = unquote(part)  # decode % -> ký tự thật
    parts = decoded.rsplit("-", 1)

    if len(parts) == 2 and parts[1].isdigit():
        song_name_only = parts[0]
        song_id = parts[1]
    else:
        song_name_only = decoded
        song_id = None

    return song_name_only, song_id


# ===== Constants =====
TIKTOK_URL = "https://ads.tiktok.com/business/creativecenter/inspiration/popular/music/pc/vi"
BLOCKED_TYPES = {"image", "font", "stylesheet", "media"}
BLOCKED_KEYWORDS = {"analytics", "tracking", "collect", "adsbygoogle"}

# ===== Logging =====
def log(msg, level="INFO"):
    print(f"[{level}] {msg}")

# ===== Dropdown Helper =====
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
async def crawl_tiktok_trend_audio(url=TIKTOK_URL, limit=100, period='7'):
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
            if request.resource_type in BLOCKED_TYPES or any(k in request.url.lower() for k in BLOCKED_KEYWORDS):
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

            await page.wait_for_selector('#soundPeriodSelect > span > div > div', timeout=10000)

            period_button = await page.query_selector('#soundPeriodSelect > span > div > div')
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
            
            try:
                await page.wait_for_selector('a.index-mobile_goToDetailBtnWrapper__puubr', timeout=10000)
                log("Video elements loaded.")
            except:
                log("Video elements not found. Exiting.", "ERROR")
                return []

            collected = []
            seen_ids = set()
            empty_attempts = 0

            while len(collected) < limit:
                video_elements = await page.query_selector_all('a.index-mobile_goToDetailBtnWrapper__puubr')
                new_found = 0

                for el in video_elements[-20:]:  # Only scan the most recent ones
                    audio_url = await el.get_attribute("href")
                    if audio_url and audio_url not in seen_ids:
                        song_name, song_id = extract_song_info(audio_url)
                        key = song_id or song_name
                        if key in seen_ids:
                            continue
                        seen_ids.add(key)

                        if song_id:
                            full_url = f"{BASE_URL}-{song_id}"
                        else:
                            full_url = None

                        collected.append({
                            "audio_url": full_url,    # URL TikTok public dạng /music/tên-bài-ID
                            "song_name": song_name,   # chỉ chữ
                            "song_id": song_id
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

                view_more = await page.query_selector('#ccContentContainer > div.BannerLayout_listWrapper__2FJA_ > div > div:nth-child(2) > div.InduceLogin_induceLogin__pN61i > div > div.ViewMoreBtn_viewMoreBtn__fOkv2 > div')
                if view_more:
                    await view_more.scroll_into_view_if_needed()
                    await page.wait_for_timeout(500)
                    await view_more.click()
                    log("Clicked 'View More' button.")
                    try:
                        await page.wait_for_function(
                            f'#ccContentContainer > div.BannerLayout_listWrapper__2FJA_ > div > div:nth-child(2) > div.CommonDataList_listWrap__4ejAT.index-mobile_listWrap__INNh7.SoundList_soundListWrapper__Ab_az > div:nth-child(1) > div > div > a.length > {len(seen_ids)}',
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
            
import asyncio
# ===== CLI Runner =====
if __name__ == "__main__":
    try:
        limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10
        period = sys.argv[2] if len(sys.argv) > 2 else "7"
        result = asyncio.run(crawl_tiktok_trend_audio(limit=limit, period = period))

        log("Result:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        log(f"Unexpected error: {e}", "FATAL")
        sys.exit(1)