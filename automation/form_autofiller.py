import os
from core.config_manager import CONFIG
from core.db_manager import log_message

async def auto_fill_playwright_form(page):
    try:
        log_message("Attempting to auto-fill common application fields...")
        name = CONFIG["candidate"]["name"]
        email = CONFIG["candidate"]["email"]
        phone = CONFIG["candidate"]["phone"]
        resume = CONFIG["candidate"]["resume_path"]
        
        # Fill Name fields
        for selector in ["input[name*='name']", "input[id*='name']", "input[placeholder*='Name']", "input[placeholder*='name']"]:
            try:
                if await page.locator(selector).count() > 0:
                    await page.locator(selector).first.fill(name)
                    log_message(f"Auto-filled name using selector: {selector}")
            except Exception as e: 
                log_message(f"Error filling name ({selector}): {e}")
            
        # Fill Email fields
        for selector in ["input[type='email']", "input[name*='email']", "input[id*='email']", "input[placeholder*='email']"]:
            try:
                if await page.locator(selector).count() > 0:
                    await page.locator(selector).first.fill(email)
                    log_message(f"Auto-filled email using selector: {selector}")
            except Exception as e: 
                log_message(f"Error filling email ({selector}): {e}")
            
        # Fill Phone fields
        for selector in ["input[type='tel']", "input[name*='phone']", "input[id*='phone']", "input[placeholder*='phone']", "input[placeholder*='Phone']"]:
            try:
                if await page.locator(selector).count() > 0:
                    await page.locator(selector).first.fill(phone)
                    log_message(f"Auto-filled phone using selector: {selector}")
            except Exception as e: 
                log_message(f"Error filling phone ({selector}): {e}")
            
        # Handle Resume upload fields
        for selector in ["input[type='file']", "input[id*='resume']", "input[name*='resume']"]:
            try:
                if await page.locator(selector).count() > 0 and os.path.exists(resume):
                    await page.locator(selector).first.set_input_files(resume)
                    log_message(f"Auto-filled resume file: {os.path.basename(resume)} using selector: {selector}")
            except Exception as e: 
                log_message(f"Error uploading resume ({selector}): {e}")
    except Exception as e:
        log_message(f"Critical error during form auto-fill: {e}")
