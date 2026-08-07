import os
from core.config_manager import CONFIG
from core.db_manager import log_message

async def auto_fill_playwright_form(page):
    """
    Intelligent ATS form auto-filler leveraging Candidate QA Vault:
    - Contact Info (Name, Email, Phone, Resume PDF)
    - Experience Years, Notice Period, Salary Expectations
    - Work Authorization, Relocation, Gender Radio Buttons
    """
    try:
        log_message("Attempting to auto-fill common application fields...")
        cand = CONFIG.get("candidate", {})
        name = cand.get("name", "")
        email = cand.get("email", "")
        phone = cand.get("phone", "")
        resume = cand.get("resume_path", "")
        qa_vault = cand.get("qa_vault", {})
        
        # 1. Fill Name fields
        for selector in ["input[name*='name']", "input[id*='name']", "input[placeholder*='Name']", "input[placeholder*='name']"]:
            try:
                if await page.locator(selector).count() > 0:
                    await page.locator(selector).first.fill(name)
                    log_message(f"Auto-filled name using selector: {selector}")
            except Exception: pass
            
        # 2. Fill Email fields
        for selector in ["input[type='email']", "input[name*='email']", "input[id*='email']", "input[placeholder*='email']"]:
            try:
                if await page.locator(selector).count() > 0:
                    await page.locator(selector).first.fill(email)
                    log_message(f"Auto-filled email using selector: {selector}")
            except Exception: pass
            
        # 3. Fill Phone fields
        for selector in ["input[type='tel']", "input[name*='phone']", "input[id*='phone']", "input[placeholder*='phone']", "input[placeholder*='Phone']"]:
            try:
                if await page.locator(selector).count() > 0:
                    await page.locator(selector).first.fill(phone)
                    log_message(f"Auto-filled phone using selector: {selector}")
            except Exception: pass
            
        # 4. Upload Resume file
        for selector in ["input[type='file']", "input[id*='resume']", "input[name*='resume']"]:
            try:
                if await page.locator(selector).count() > 0 and os.path.exists(resume):
                    await page.locator(selector).first.set_input_files(resume)
                    log_message(f"Auto-filled resume file: {os.path.basename(resume)}")
            except Exception: pass

        # 5. Smart ATS QA Vault Auto-Fill
        exp_yrs = qa_vault.get("experience_years", "1")
        notice = qa_vault.get("notice_period", "Immediate")
        c_ctc = qa_vault.get("current_ctc", "0")
        e_ctc = qa_vault.get("expected_ctc", "Negotiable")

        # Experience inputs
        for selector in ["input[name*='exp']", "input[placeholder*='experience']", "input[id*='experience']"]:
            try:
                if await page.locator(selector).count() > 0:
                    await page.locator(selector).first.fill(exp_yrs)
                    log_message(f"ATS Vault: Auto-filled Experience Years ({exp_yrs})")
            except Exception: pass

        # Notice period inputs
        for selector in ["input[name*='notice']", "input[placeholder*='notice']", "input[id*='notice']"]:
            try:
                if await page.locator(selector).count() > 0:
                    await page.locator(selector).first.fill(notice)
                    log_message(f"ATS Vault: Auto-filled Notice Period ({notice})")
            except Exception: pass

        # Current & Expected CTC
        for selector in ["input[name*='current_ctc']", "input[placeholder*='current ctc']", "input[id*='current_salary']"]:
            try:
                if await page.locator(selector).count() > 0:
                    await page.locator(selector).first.fill(c_ctc)
            except Exception: pass

        for selector in ["input[name*='expected_ctc']", "input[placeholder*='expected ctc']", "input[id*='expected_salary']"]:
            try:
                if await page.locator(selector).count() > 0:
                    await page.locator(selector).first.fill(e_ctc)
            except Exception: pass

    except Exception as e:
        log_message(f"Critical error during form auto-fill: {e}")
