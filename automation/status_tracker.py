import os
import asyncio
import threading
from playwright.async_api import async_playwright
from core.db_manager import log_message, load_applied_urls, update_job_status_in_csv
import core.state as state

TRACKER_RUNNING = False
TRACKER_LOCK = threading.Lock()

def get_edge_executable_path():
    possible_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe")
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

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
                edge_exe = get_edge_executable_path()
                launch_kwargs = {
                    "user_data_dir": user_data_dir,
                    "headless": False
                }
                if edge_exe:
                    launch_kwargs["executable_path"] = edge_exe

                browser = await p.chromium.launch_persistent_context(**launch_kwargs)
                page = await browser.new_page()
                
                # 1. Scrape Indeed Applied Portal
                log_message("TRACKER: Scanning Indeed applied jobs portal...")
                try:
                    await page.goto("https://in.indeed.com/myjobs/applied", wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(4)
                    
                    job_cards = page.locator("[data-gnav-element-name='myjobs_applied_job'], .css-1q2s2g4, .css-kyg84b")
                    card_count = await job_cards.count()
                    log_message(f"TRACKER: Found {card_count} applied jobs on Indeed portal.")
                    
                    for i in range(card_count):
                        try:
                            card = job_cards.nth(i)
                            card_text = await card.inner_text()
                            card_lower = card_text.lower()
                            
                            # Determine status update
                            status_update = None
                            if "interview" in card_lower or "shortlist" in card_lower:
                                status_update = "Interviewing"
                            elif "not selected" in card_lower or "rejected" in card_lower or "declined" in card_lower:
                                status_update = "Not Selected"
                            elif "offer" in card_lower:
                                status_update = "Offer Received"
                                
                            if status_update:
                                links = card.locator("a")
                                if await links.count() > 0:
                                    href = await links.first.get_attribute("href")
                                    if href:
                                        full_url = "https://in.indeed.com" + href if href.startswith("/") else href
                                        update_job_status_in_csv(full_url, "Applied", status_update, "Updated via Indeed portal sync")
                        except Exception:
                            continue
                except Exception as e:
                    log_message(f"TRACKER: Indeed portal scan notice: {e}")
                
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
