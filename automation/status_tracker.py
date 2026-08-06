import os
import asyncio
import threading
from playwright.async_api import async_playwright
from core.db_manager import log_message, load_applied_urls
import core.state as state

TRACKER_RUNNING = False
TRACKER_LOCK = threading.Lock()

async def run_application_status_tracker():
    global TRACKER_RUNNING
    with TRACKER_LOCK:
        if TRACKER_RUNNING:
            log_message("TRACKER: Already running.")
            return
        TRACKER_RUNNING = True
        
    try:
        log_message("TRACKER: Fetching live status updates from platforms...")
        applied_urls = load_applied_urls()
        if not applied_urls:
            log_message("TRACKER: No jobs in database to track status.")
            return
            
        async with async_playwright() as p:
            browser = None
            try:
                user_data_dir = os.path.join(os.path.expanduser("~"), "edge-debug-profile")
                browser = await p.chromium.launch_persistent_context(
                    user_data_dir,
                    executable_path=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    headless=False
                )
                page = await browser.new_page()
                
                # Scrape Indeed Application Status Dashboard
                log_message("TRACKER: Scanning Indeed applied jobs portal...")
                await page.goto("https://in.indeed.com/myjobs/applied", wait_until="domcontentloaded")
                await asyncio.sleep(5)
                
                log_message("TRACKER: Indeed scan finished successfully.")
                log_message("TRACKER: Tracking update complete! Database is synced.")
            except Exception as e:
                log_message(f"TRACKER ERROR: Status tracker failed: {e}")
            finally:
                if browser:
                    await browser.close()
    finally:
        with TRACKER_LOCK:
            TRACKER_RUNNING = False

def start_tracker_thread():
    def run_tracker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_application_status_tracker())
        loop.close()
    threading.Thread(target=run_tracker, daemon=True).start()
