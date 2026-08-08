import os
import random
import re
import asyncio
import threading
import urllib.parse
from playwright.async_api import async_playwright
import core.state as state
from core.config_manager import CONFIG, get_location_search_term, encode_query_for_url, SCREENSHOTS_DIR
from core.db_manager import log_message, save_to_db, load_applied_urls, recalculate_metrics, APPLIED_URLS_SET, init_applied_urls, update_job_status_in_csv, save_recruiter_contact
from core.contact_extractor import extract_recruiter_contacts
from automation.llm_evaluator import evaluate_job_with_qwen
from automation.form_autofiller import auto_fill_playwright_form

# Pause helper
async def check_pause():
    while state.BOT_PAUSED and state.BOT_RUNNING:
        await asyncio.sleep(1)

async def check_safety_limit():
    safe_mode = CONFIG.get("settings", {}).get("safe_mode", True)
    daily_cap = CONFIG.get("settings", {}).get("daily_apply_cap", 25)
    applied_count = state.METRICS.get("applied", 0)
    
    if safe_mode and applied_count >= daily_cap:
        log_message(f"🛡️ SAFETY LIMIT REACHED: Reached daily application cap ({applied_count}/{daily_cap}). Pausing bot to protect your platform account.")
        state.BOT_PAUSED = True
        return True
    return False

async def human_delay():
    min_d = CONFIG.get("settings", {}).get("min_delay_seconds", 10)
    max_d = CONFIG.get("settings", {}).get("max_delay_seconds", 30)
    delay = random.randint(min_d, max_d)
    log_message(f"⏳ Human Emulation: Pausing {delay}s to simulate realistic human browsing...")
    await asyncio.sleep(delay)

# Retry logic for page.goto
async def goto_with_retry(page, url, retries=2, delay=3, wait_until="domcontentloaded", timeout=30000):
    for attempt in range(retries + 1):
        try:
            await page.goto(url, wait_until=wait_until, timeout=timeout)
            return True
        except Exception as e:
            if attempt < retries:
                log_message(f"Navigation to {url} failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
            else:
                log_message(f"Navigation to {url} failed after {retries} retries: {e}")
                raise e

# Pre-run login flow checking
async def verify_indeed_auth(page):
    try:
        log_message("Checking Indeed login status...")
        await goto_with_retry(page, "https://in.indeed.com/")
        await asyncio.sleep(3)
        
        signin_btn = page.locator("a:has-text('Sign in')")
        if await signin_btn.count() > 0:
            log_message("ACTION REQUIRED: Please sign in to Indeed in the Edge window (Google, OTP Email, or Password).")
            log_message("The bot will pause and wait for you to complete your sign-in...")
            while state.BOT_RUNNING:
                try:
                    if "secure.indeed.com" in page.url:
                        await asyncio.sleep(2)
                        continue
                    if await page.locator("a:has-text('Sign in')").count() > 0:
                        await asyncio.sleep(2)
                        continue
                    break
                except Exception:
                    if page.is_closed():
                        break
                    await asyncio.sleep(2)
            if state.BOT_RUNNING:
                log_message("Indeed login detected! Continuing...")
        else:
            log_message("Already logged in to Indeed.")
    except Exception as e:
        log_message(f"Indeed auth verification failed: {e}")

async def verify_naukri_auth(page):
    try:
        log_message("Checking Naukri login status...")
        await goto_with_retry(page, "https://www.naukri.com/")
        await asyncio.sleep(3)
        
        login_btn = page.locator("a#login_Layer")
        if await login_btn.count() > 0:
            email = CONFIG.get("accounts", {}).get("naukri_email", "")
            password = CONFIG.get("accounts", {}).get("naukri_pass", "")
            if email and password:
                log_message("Attempting automatic login to Naukri...")
                try:
                    await login_btn.click()
                    await asyncio.sleep(2)
                    await page.locator("input[placeholder='Enter your active Email ID / Username']").fill(email)
                    await page.locator("input[placeholder='Enter your password']").fill(password)
                    await page.locator("button[type='submit']").click()
                    await asyncio.sleep(5)
                except Exception as e:
                    log_message(f"Auto-login failed: {e}")
                    
            # Robust verification check: wait until they are off the login URL and the login button is gone
            login_btn = page.locator("a#login_Layer")
            if await login_btn.count() > 0:
                log_message("ACTION REQUIRED: Please log in to Naukri in the Edge window.")
                log_message("The bot will pause and wait for you to complete your sign-in...")
                while state.BOT_RUNNING:
                    try:
                        if "nlogin/login" in page.url:
                            await asyncio.sleep(2)
                            continue
                        if await page.locator("a#login_Layer").count() > 0:
                            await asyncio.sleep(2)
                            continue
                        break
                    except Exception:
                        if page.is_closed():
                            break
                        await asyncio.sleep(2)
                if state.BOT_RUNNING:
                    log_message("Naukri login detected! Continuing...")
        else:
            log_message("Already logged in to Naukri.")
    except Exception as e:
        log_message(f"Naukri auth verification failed: {e}")

async def verify_linkedin_auth(page):
    try:
        log_message("Checking LinkedIn login status...")
        await goto_with_retry(page, "https://www.linkedin.com/feed/")
        await asyncio.sleep(3)
        
        if "feed" not in page.url:
            email = CONFIG.get("accounts", {}).get("linkedin_email", "")
            password = CONFIG.get("accounts", {}).get("linkedin_pass", "")
            if email and password:
                log_message("Attempting automatic login to LinkedIn...")
                try:
                    await goto_with_retry(page, "https://www.linkedin.com/login")
                    await asyncio.sleep(2)
                    
                    # Check for either #username or #session_key
                    user_input = None
                    for selector in ["#username", "#session_key"]:
                        if await page.locator(selector).count() > 0:
                            user_input = page.locator(selector)
                            break
                    
                    pass_input = None
                    for selector in ["#password", "#session_password"]:
                        if await page.locator(selector).count() > 0:
                            pass_input = page.locator(selector)
                            break
                            
                    if user_input and pass_input:
                        await user_input.fill(email)
                        await pass_input.fill(password)
                        submit_btn = page.locator("button[type='submit'], button:has-text('Sign in')")
                        await submit_btn.first.click()
                        await asyncio.sleep(5)
                    else:
                        log_message("LinkedIn login input fields not found.")
                except Exception as e:
                    log_message(f"Auto-login failed: {e}")
                    
            if "feed" not in page.url:
                log_message("ACTION REQUIRED: Please log in to LinkedIn in the Edge window.")
                log_message("The bot will pause and wait for you to complete your sign-in...")
                while state.BOT_RUNNING:
                    try:
                        if "feed" not in page.url:
                            await asyncio.sleep(2)
                        else:
                            break
                    except Exception:
                        if page.is_closed():
                            break
                        await asyncio.sleep(2)
                if state.BOT_RUNNING:
                    log_message("LinkedIn login detected! Continuing...")
        else:
            log_message("Already logged in to LinkedIn.")
    except Exception as e:
        log_message(f"LinkedIn auth verification failed: {e}")


async def wait_for_manual_submission(page):
    log_message("Waiting up to 60s for manual form completion (checking every 3s)...")
    try:
        for _ in range(20):
            if not state.BOT_RUNNING: break
            if page.is_closed(): break
            await asyncio.sleep(3)
    except Exception:
        pass


async def process_job_evaluation(title, company, href, desc_text, platform, desc_page, browser):
    """
    Helper function that handles the shared LLM evaluation, scoring, doubt queue,
    DB save, and screenshot pattern.
    Returns True if applied/suggested, False if skipped.
    """
    # Safety check: enforce daily application cap
    if await check_safety_limit():
        return False
    
    contacts = extract_recruiter_contacts(desc_text)
    email_matches = contacts["emails"]
    phone_matches = contacts["phones"]
    hr_matches = contacts["hr_names"]
    
    # Save recruiter contact to dedicated DB if any info found
    if email_matches or phone_matches or hr_matches:
        e_str = email_matches[0] if email_matches else ""
        p_str = phone_matches[0] if phone_matches else ""
        hr_str = hr_matches[0] if hr_matches else "Hiring Manager"
        save_recruiter_contact(company, title, hr_str, e_str, p_str, platform, href)
        
    try:
        eval_res = evaluate_job_with_qwen(title, desc_text)
        if eval_res is None:
            eval_res = {}
    except Exception as e:
        log_message(f"LLM evaluation error for '{title}': {e}")
        eval_res = {}
    score = eval_res.get("score", 0)
    is_match = eval_res.get("is_match", False)
    reason = eval_res.get("reason", "")
    should_approve = eval_res.get("should_approve", False)
    
    if is_match:
        if should_approve:
            log_message(f"DOUBT DETECTED ({score}%): Queueing '{title}' at '{company}' in Approvals.")
            with state.DOUBT_LOCK:
                state.DOUBT_QUEUE.append({
                    "title": title, "company": company, "url": href, 
                    "platform": platform, "score": score, "reason": reason, "description": desc_text
                })
            save_to_db(href, title, company, platform, "Approval Needed", reason)
            return True
            
        sc_path = os.path.join(SCREENSHOTS_DIR, f"{platform.lower()}_match_{random.randint(1000, 9999)}.png")
        try:
            await desc_page.screenshot(path=sc_path)
        except Exception as e:
            log_message(f"Could not take screenshot: {e}")
            
        if platform == "Indeed":
            apply_btn = desc_page.locator("button:has-text('Apply now'), button:has-text('Apply with Indeed')")
            external_apply = desc_page.locator("a:has-text('Apply on company site')")
            
            if await apply_btn.count() > 0:
                log_message(f"Indeed MATCH FOUND ({score}%): {title} at {company}. Initiating Easy Apply...")
                await apply_btn.first.click()
                await asyncio.sleep(3)
                try:
                    await auto_fill_playwright_form(desc_page)
                except Exception as e:
                    log_message(f"Auto-fill error: {e}")
                await wait_for_manual_submission(desc_page)
                save_to_db(href, title, company, "Indeed", "Applied")
            elif await external_apply.count() > 0:
                career_url = await external_apply.first.get_attribute("href")
                log_message(f"SUGGESTED: External Career Page for {title} at {company}: {career_url}")
                save_to_db(href, title, company, "Indeed", "Suggested", f"Career Page: {career_url}")
            elif email_matches:
                company_email = email_matches[0]
                log_message(f"SUGGESTED: Email Application for {title} at {company}: {company_email}")
                save_to_db(href, title, company, "Indeed", "Suggested", f"Email resume to: {company_email}")
            else:
                save_to_db(href, title, company, "Indeed", "Suggested", "Apply manually")
                
        elif platform == "Naukri":
            apply_btn = desc_page.locator("button:has-text('Apply'), button#apply-button, .apply-button")
            if await apply_btn.count() > 0:
                log_message(f"Naukri MATCH FOUND ({score}%): {title} at {company}. Clicking Apply...")
                
                async def click_and_detect():
                    async with desc_page.context.expect_page(timeout=5000) as new_page_info:
                        await apply_btn.first.click()
                    new_p = await new_page_info.value
                    return new_p
                    
                try:
                    new_tab = await click_and_detect()
                    await asyncio.sleep(2)
                    redirect_url = new_tab.url
                    log_message(f"SUGGESTED: Naukri click opened external company site: {redirect_url}")
                    save_to_db(href, title, company, "Naukri", "Suggested", f"Career Page: {redirect_url}")
                    await new_tab.close()
                except Exception:
                    # Fallback if no new page opens (inline redirection or standard modal)
                    await asyncio.sleep(3)
                    try:
                        current_url = desc_page.url
                        if "naukri.com" not in current_url:
                            log_message(f"SUGGESTED: Naukri redirected page to external career site: {current_url}")
                            save_to_db(href, title, company, "Naukri", "Suggested", f"Career Page: {current_url}")
                        else:
                            try:
                                await auto_fill_playwright_form(desc_page)
                            except Exception as e:
                                log_message(f"Auto-fill error: {e}")
                            await wait_for_manual_submission(desc_page)
                            save_to_db(href, title, company, "Naukri", "Applied")
                    except Exception:
                        pass
            elif email_matches:
                company_email = email_matches[0]
                log_message(f"SUGGESTED: Email Application for {title} at {company}: {company_email}")
                save_to_db(href, title, company, "Naukri", "Suggested", f"Email resume to: {company_email}")
            else:
                save_to_db(href, title, company, "Naukri", "Suggested", "Apply manually")
                
        elif platform == "LinkedIn":
            easy_apply_btn = desc_page.locator("button.jobs-apply-button:has-text('Easy Apply')")
            apply_btn = desc_page.locator("button.jobs-apply-button")
            
            if await easy_apply_btn.count() > 0:
                log_message(f"LinkedIn MATCH FOUND ({score}%): {title} at {company}. Clicking Easy Apply...")
                await easy_apply_btn.first.click()
                await asyncio.sleep(3)
                try:
                    await auto_fill_playwright_form(desc_page)
                except Exception as e:
                    log_message(f"Auto-fill error: {e}")
                await wait_for_manual_submission(desc_page)
                save_to_db(href, title, company, "LinkedIn", "Applied")
            elif await apply_btn.count() > 0:
                # Click standard apply and capture redirect
                async def click_and_detect():
                    async with desc_page.context.expect_page(timeout=5000) as new_page_info:
                        await apply_btn.first.click()
                    new_p = await new_page_info.value
                    return new_p
                try:
                    new_tab = await click_and_detect()
                    await asyncio.sleep(2)
                    redirect_url = new_tab.url
                    log_message(f"SUGGESTED: LinkedIn apply opened career link: {redirect_url}")
                    save_to_db(href, title, company, "LinkedIn", "Suggested", f"Career Page: {redirect_url}")
                    await new_tab.close()
                except Exception:
                    log_message(f"SUGGESTED: External Apply for {title} at {company}")
                    save_to_db(href, title, company, "LinkedIn", "Suggested", f"Career Link: {href}")
            elif email_matches:
                company_email = email_matches[0]
                log_message(f"SUGGESTED: Email Application for {title} at {company}: {company_email}")
                save_to_db(href, title, company, "LinkedIn", "Suggested", f"Email resume to: {company_email}")
            else:
                save_to_db(href, title, company, "LinkedIn", "Suggested", "Apply manually")
        return True
    else:
        log_message(f"{platform} skipped ({score}%): {reason}")
        save_to_db(href, title, company, platform, "Skipped", reason)
        return False


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

async def run_bot_async():
    global CURRENT_STATUS
    log_message("Starting Local Job Bot Loop...")
    init_applied_urls()
    
    async with async_playwright() as p:
        try:
            user_data_dir = os.path.join(os.path.expanduser("~"), "edge-debug-profile")
            log_message("Launching Edge Browser...")
            edge_exe = get_edge_executable_path()
            launch_kwargs = {
                "user_data_dir": user_data_dir,
                "headless": False,
                "args": [
                    "--remote-debugging-port=9222", 
                    "--disable-blink-features=AutomationControlled"
                ],
                "ignore_default_args": ["--enable-automation"]
            }
            if edge_exe:
                launch_kwargs["executable_path"] = edge_exe
                
            browser = await p.chromium.launch_persistent_context(**launch_kwargs)
            
            state.ACTIVE_BROWSER_CONTEXT = browser
            state.ACTIVE_EVENT_LOOP = asyncio.get_running_loop()
            
            target_platforms = CONFIG["settings"].get("target_platforms", ["Indeed", "Naukri", "LinkedIn"])
            pages = {}
            
            if "Indeed" in target_platforms:
                try:
                    page_indeed = browser.pages[0] if browser.pages else await browser.new_page()
                    state.CURRENT_STATUS = "Indeed Auth Check"
                    await verify_indeed_auth(page_indeed)
                    if state.BOT_RUNNING:
                        pages["Indeed"] = page_indeed
                except Exception as e:
                    log_message(f"Indeed Auth Check failed: {e}. Skipping Indeed.")
                
            if "Naukri" in target_platforms:
                try:
                    page_naukri = await browser.new_page() if len(pages) > 0 else (browser.pages[0] if browser.pages else await browser.new_page())
                    state.CURRENT_STATUS = "Naukri Auth Check"
                    await verify_naukri_auth(page_naukri)
                    if state.BOT_RUNNING:
                        pages["Naukri"] = page_naukri
                except Exception as e:
                    log_message(f"Naukri Auth Check failed: {e}. Skipping Naukri.")

            if "LinkedIn" in target_platforms:
                try:
                    page_linkedin = await browser.new_page() if len(pages) > 0 else (browser.pages[0] if browser.pages else await browser.new_page())
                    state.CURRENT_STATUS = "LinkedIn Auth Check"
                    await verify_linkedin_auth(page_linkedin)
                    if state.BOT_RUNNING:
                        pages["LinkedIn"] = page_linkedin
                except Exception as e:
                    log_message(f"LinkedIn Auth Check failed: {e}. Skipping LinkedIn.")
            
            queries = CONFIG["settings"]["queries"]
            max_jobs_cfg = CONFIG["settings"].get("max_jobs_per_query", 9999)
            max_jobs = 999999 if (max_jobs_cfg >= 9999 or max_jobs_cfg <= 0) else max_jobs_cfg
            preferred_locs = CONFIG["settings"].get("preferred_locations", [])
            location_scope = CONFIG["settings"].get("location_scope", "Entire Country")
            
            # Filters
            exp_lvl = CONFIG["settings"].get("experience_level", "All")
            j_type = CONFIG["settings"].get("job_type", "All")
            loc_type = CONFIG["settings"].get("location_type", "All")
            
            tasks = []
            
            # Indeed automation loop task
            async def run_indeed_loop(page):
                for query in queries:
                    locations = [""] if location_scope == "Entire Country" else (preferred_locs if preferred_locs else [""])
                    for loc in locations:
                        await check_pause()
                        if not state.BOT_RUNNING: break
                        
                        search_query = query
                        if loc_type == "Remote": search_query += " remote"
                        elif loc_type == "Hybrid": search_query += " hybrid"
                        elif loc_type == "On-site": search_query += " onsite"
                        
                        q_encoded = encode_query_for_url(search_query, 'indeed')
                        
                        # Pagination up to 3 pages
                        for page_num in range(3):
                            if not state.BOT_RUNNING: break
                            await check_pause()
                            
                            url = f"https://in.indeed.com/jobs?q={q_encoded}&iafilter=1"
                            if loc:
                                url += f"&l={get_location_search_term(loc).replace(' ', '+')}"
                            url += "&fromage=1"
                            
                            params = []
                            if exp_lvl == "Fresher": params.append("explvl=ENTRY_LEVEL")
                            elif exp_lvl == "Mid": params.append("explvl=MID_LEVEL")
                            elif exp_lvl == "Senior": params.append("explvl=SENIOR_LEVEL")
                            
                            if j_type == "Full-time": params.append("jt=fulltime")
                            elif j_type == "Internship": params.append("jt=internship")
                            elif j_type == "Contract": params.append("jt=contract")
                            
                            if page_num > 0:
                                params.append(f"start={page_num * 10}")
                                
                            if params:
                                url += "&" + "&".join(params)
                                
                            log_message(f"Indeed: Searching '{search_query}' in '{get_location_search_term(loc) if loc else 'Entire Country'}' (Page {page_num+1})...")
                            try:
                                await goto_with_retry(page, url)
                                await asyncio.sleep(5)
                            except Exception as e:
                                log_message(f"Indeed: Search page navigation failed: {e}")
                                break
                            
                            cards = await page.locator("div.job_seen_beacon").all()
                            log_message(f"Indeed: Found {len(cards)} listings for '{search_query}' on page {page_num+1}.")
                            
                            if len(cards) == 0:
                                break # No more jobs
                                
                            jobs_processed = 0
                            for card in cards:
                                await check_pause()
                                if not state.BOT_RUNNING: break
                                if jobs_processed >= max_jobs: break
                                
                                title_el = card.locator("a.jcs-JobTitle")
                                if await title_el.count() == 0: continue
                                title = await title_el.inner_text()
                                href = await title_el.get_attribute("href")
                                if href and href.startswith("/"):
                                    href = "https://in.indeed.com" + href
                                    
                                if href in APPLIED_URLS_SET: continue
                                jobs_processed += 1
                                
                                comp_el = card.locator("[data-testid='company-name']")
                                company = await comp_el.inner_text() if await comp_el.count() > 0 else "Unknown Company"
                                
                                log_message(f"Indeed: Inspecting {title} at {company}")
                                
                                desc_page = await browser.new_page()
                                try:
                                    await goto_with_retry(desc_page, href)
                                    await asyncio.sleep(3)
                                    
                                    desc_text = ""
                                    desc_el = desc_page.locator("#jobDescriptionText")
                                    if await desc_el.count() > 0:
                                        desc_text = await desc_el.inner_text()
                                        
                                    await process_job_evaluation(title, company, href, desc_text, "Indeed", desc_page, browser)
                                except Exception as e:
                                    log_message(f"Indeed check error: {e}")
                                finally:
                                    await desc_page.close()
                                await human_delay()
                            if jobs_processed == 0:
                                break # No jobs found on this page, stop paginating

            # Naukri automation loop task
            async def run_naukri_loop(page):
                for query in queries:
                    locations = [""]
                    if location_scope == "Custom Cities & States" and preferred_locs:
                        locations = [get_location_search_term(loc) for loc in preferred_locs]
                        
                    for loc in locations:
                        await check_pause()
                        if not state.BOT_RUNNING: break
                        
                        q_encoded = encode_query_for_url(query, 'naukri')
                        url = f"https://www.naukri.com/{q_encoded}-jobs"
                        if loc:
                            url += f"-in-{loc.lower().replace(' ', '-')}"
                        url += "?src=discovery"
                        
                        n_params = []
                        if exp_lvl == "Fresher": n_params.append("experience=0")
                        elif exp_lvl == "Mid": n_params.append("experience=3")
                        elif exp_lvl == "Senior": n_params.append("experience=7")
                        
                        if loc_type == "Remote": n_params.append("workMode=3")
                        elif loc_type == "Hybrid": n_params.append("workMode=2")
                        
                        if n_params:
                            url += "&" + "&".join(n_params)
                            
                        log_message(f"Naukri: Searching '{query}' in '{loc if loc else 'Entire Country'}'...")
                        try:
                            await goto_with_retry(page, url)
                            await asyncio.sleep(5)
                        except Exception as e:
                            log_message(f"Naukri: Search page navigation failed: {e}")
                            continue
                        
                        cards = await page.locator("div.srp-jobtuple, article.jobTuple, div.cust-job-tuple").all()
                        log_message(f"Naukri: Found {len(cards)} listings for '{query}' in '{loc if loc else 'Entire Country'}'.")
                        
                        for card in cards[:max_jobs]:
                            await check_pause()
                            if not state.BOT_RUNNING: break
                            
                            title_el = card.locator("a.title, a.job-title")
                            if await title_el.count() == 0: continue
                            title = await title_el.inner_text()
                            href = await title_el.get_attribute("href")
                            
                            if not href or href in APPLIED_URLS_SET: continue
                            
                            comp_el = card.locator("a.comp-name, .companyName")
                            company = await comp_el.inner_text() if await comp_el.count() > 0 else "Unknown Company"
                            
                            log_message(f"Naukri: Inspecting {title} at {company}")
                            
                            desc_page = await browser.new_page()
                            try:
                                await goto_with_retry(desc_page, href)
                                await asyncio.sleep(3)
                                
                                desc_text = ""
                                desc_el = desc_page.locator(".job-desc, .jd-header-title, #jobDescriptionText")
                                if await desc_el.count() > 0:
                                    desc_text = await desc_el.inner_text()
                                    
                                await process_job_evaluation(title, company, href, desc_text, "Naukri", desc_page, browser)
                            except Exception as e:
                                log_message(f"Naukri check error: {e}")
                            finally:
                                await desc_page.close()
                            await asyncio.sleep(random.uniform(3.0, 7.0))

            # LinkedIn automation loop task
            async def run_linkedin_loop(page):
                for query in queries:
                    locations = [""] if location_scope == "Entire Country" else (preferred_locs if preferred_locs else [""])
                    for loc in locations:
                        await check_pause()
                        if not state.BOT_RUNNING: break
                        
                        q_encoded = encode_query_for_url(query, 'linkedin')
                        url = f"https://www.linkedin.com/jobs/search/?keywords={q_encoded}&f_AL=true"
                        if loc:
                            url += f"&location={get_location_search_term(loc).replace(' ', '%20')}"
                        else:
                            url += "&location=India"
                            
                        # Past 24h
                        url += "&f_TPR=r86400"
                        
                        if exp_lvl == "Fresher": url += "&f_E=1%2C2"
                        elif exp_lvl == "Mid": url += "&f_E=3"
                        elif exp_lvl == "Senior": url += "&f_E=4%2C5"
                        
                        if j_type == "Full-time": url += "&f_JT=F"
                        elif j_type == "Internship": url += "&f_JT=I"
                        elif j_type == "Contract": url += "&f_JT=C"
                        
                        if loc_type == "Remote": url += "&f_WT=2"
                        elif loc_type == "Hybrid": url += "&f_WT=3"
                        elif loc_type == "On-site": url += "&f_WT=1"
                        
                        log_message(f"LinkedIn: Searching '{query}' in '{loc if loc else 'India'}'...")
                        try:
                            await goto_with_retry(page, url)
                            await asyncio.sleep(5)
                        except Exception as e:
                            log_message(f"LinkedIn: Search page navigation failed: {e}")
                            continue
                        
                        try:
                            # Scroll down the listings frame on the left to trigger lazy loading
                            await page.evaluate("document.querySelector('.jobs-search-results-list')?.scrollTo(0, 1000)")
                            await asyncio.sleep(2)
                        except Exception:
                            pass
                            
                        cards = await page.locator("li.jobs-search-results__list-item, div.job-card-container").all()
                        log_message(f"LinkedIn: Found {len(cards)} listings for '{query}'.")
                        
                        for card in cards[:max_jobs]:
                            await check_pause()
                            if not state.BOT_RUNNING: break
                            
                            try:
                                # Click job card to display details in panel or open in new tab
                                await card.click()
                                await asyncio.sleep(3)
                                
                                title_el = card.locator("a.job-card-list__title, .artdeco-entity-lockup__title a")
                                if await title_el.count() == 0: continue
                                title = await title_el.first.inner_text()
                                href = await title_el.first.get_attribute("href")
                                if not href: continue
                                if href.startswith("/"):
                                    href = "https://www.linkedin.com" + href
                                href = href.split("?")[0] # Clean params
                                    
                                if href in APPLIED_URLS_SET: continue
                                
                                comp_el = card.locator(".job-card-container__primary-description, .artdeco-entity-lockup__subtitle")
                                company = await comp_el.first.inner_text() if await comp_el.count() > 0 else "Unknown Company"
                                company = company.strip().split("\n")[0]
                                
                                log_message(f"LinkedIn: Inspecting {title} at {company}")
                                
                                # FIX for LinkedIn loop: Open job in a separate tab to avoid losing search context on navigation
                                desc_page = await browser.new_page()
                                try:
                                    await goto_with_retry(desc_page, href)
                                    await asyncio.sleep(3)
                                    
                                    desc_text = ""
                                    desc_el = desc_page.locator(".jobs-description__content, .jobs-box__html-content, #job-details")
                                    if await desc_el.count() > 0:
                                        desc_text = await desc_el.first.inner_text()
                                        
                                    await process_job_evaluation(title, company, href, desc_text, "LinkedIn", desc_page, browser)
                                except Exception as e:
                                    log_message(f"LinkedIn check error: {e}")
                                finally:
                                    await desc_page.close()
                            except Exception as e:
                                log_message(f"LinkedIn card processing error: {e}")
                            await asyncio.sleep(random.uniform(3.0, 5.0))
            
            # Web-Wide Internet Career Page Scanner task
            async def run_internet_scanner_loop(browser):
                page = await browser.new_page()
                log_message("Web Scanner: Initializing Web-Wide Internet Career Page Scanner...")
                for query in queries:
                    await check_pause()
                    if not state.BOT_RUNNING: break
                    
                    ats_sites = ["site:greenhouse.io", "site:lever.co", "site:jobs.ashbyhq.com", "site:workday.com"]
                    for site in ats_sites:
                        await check_pause()
                        if not state.BOT_RUNNING: break
                        
                        search_term = f"{query} {site} India"
                        encoded_search = urllib.parse.quote(search_term)
                        search_url = f"https://html.duckduckgo.com/html/?q={encoded_search}"
                        
                        log_message(f"Web Scanner: Searching broader web for '{search_term}'...")
                        try:
                            await goto_with_retry(page, search_url)
                            await asyncio.sleep(4)
                            
                            links = await page.locator("a.result__url").all()
                            log_message(f"Web Scanner: Found {len(links)} web career results for '{search_term}'.")
                            
                            for link_el in links[:5]:
                                await check_pause()
                                if not state.BOT_RUNNING: break
                                
                                href = await link_el.get_attribute("href")
                                if not href: continue
                                
                                if "duckduckgo.com/l/?" in href:
                                    match = re.search(r'uddg=([^&]+)', href)
                                    if match:
                                        href = urllib.parse.unquote(match.group(1))
                                        
                                if href in APPLIED_URLS_SET: continue
                                
                                log_message(f"Web Scanner: Inspecting web career page: {href}")
                                web_page = await browser.new_page()
                                try:
                                    await goto_with_retry(web_page, href, timeout=20000)
                                    await asyncio.sleep(3)
                                    
                                    web_title = await web_page.title()
                                    desc_el = web_page.locator("body")
                                    desc_text = await desc_el.inner_text() if await desc_el.count() > 0 else web_title
                                    
                                    company_match = re.search(r'at\s+([A-Z][A-Za-z0-9\s]+)', web_title)
                                    company_name = company_match.group(1).strip() if company_match else "Web Hiring Portal"
                                    
                                    await process_job_evaluation(web_title, company_name, href, desc_text[:3000], "Web Search", web_page, browser)
                                except Exception as e:
                                    log_message(f"Web Scanner error on {href}: {e}")
                                finally:
                                    await web_page.close()
                                await asyncio.sleep(2)
                        except Exception as e:
                            log_message(f"Web Scanner search error for '{search_term}': {e}")
                await page.close()

            # Setup parallel tab gathers
            if "Indeed" in pages:
                tasks.append(run_indeed_loop(pages["Indeed"]))
            if "Naukri" in pages:
                tasks.append(run_naukri_loop(pages["Naukri"]))
            if "LinkedIn" in pages:
                tasks.append(run_linkedin_loop(pages["LinkedIn"]))
            
            # Always run Web-Wide Internet Career Page Scanner
            tasks.append(run_internet_scanner_loop(browser))
                
            state.CURRENT_STATUS = "Applying (Concurrently)"
            await asyncio.gather(*tasks)
            
            await browser.close()
        except Exception as e:
            log_message(f"Fatal error in browser loop: {e}")
        finally:
            state.ACTIVE_BROWSER_CONTEXT = None
            state.ACTIVE_EVENT_LOOP = None
            state.BOT_RUNNING = False
            state.CURRENT_STATUS = "Idle"
            log_message("Job Bot Stopped.")

def start_bot_thread():
    if state.BOT_RUNNING: return
    state.BOT_RUNNING = True
    
    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_bot_async())
        loop.close()
        
    threading.Thread(target=run_loop, daemon=True).start()

def stop_bot():
    state.BOT_RUNNING = False
    log_message("Stop command triggered.")

def apply_single_job_async(job):
    async def process_apply_page(page, job):
        log_message(f"APPLYING APPROVED JOB: {job['title']} at {job['company']}")
        await goto_with_retry(page, job["url"])
        await asyncio.sleep(3)
        
        # Verify platform auth if login wall/button appears
        platform = job.get("platform", "")
        if platform == "Naukri":
            if await page.locator("a#login_Layer").count() > 0 or "nlogin/login" in page.url:
                await verify_naukri_auth(page)
        elif platform == "Indeed":
            if await page.locator("a:has-text('Sign in')").count() > 0 or "secure.indeed.com" in page.url:
                await verify_indeed_auth(page)
        elif platform == "LinkedIn":
            if "feed" not in page.url and await page.locator("#username, #session_key").count() > 0:
                await verify_linkedin_auth(page)
                
        apply_btn = page.locator("button:has-text('Apply now'), button:has-text('Apply with Indeed'), button:has-text('Apply'), button#apply-button, button.jobs-apply-button:has-text('Easy Apply')")
        if await apply_btn.count() > 0:
            log_message(f"Found apply button for {job['title']}. Clicking Apply...")
            await apply_btn.first.click()
            await asyncio.sleep(3)
            try:
                await auto_fill_playwright_form(page)
            except Exception as e:
                log_message(f"Auto-fill error: {e}")
            updated = update_job_status_in_csv(job["url"], "Approval Needed", "Applied", "Manual Approval Apply")
            if not updated:
                save_to_db(job["url"], job["title"], job["company"], platform, "Applied", "Manual Approval Apply")
        else:
            log_message("Apply button not found on page. Please apply manually in the opened tab.")
            await asyncio.sleep(30)

    def apply_thread():
        # Case 1: Main bot is running — reuse active logged-in browser context!
        if state.ACTIVE_BROWSER_CONTEXT and state.ACTIVE_EVENT_LOOP:
            try:
                async def apply_in_active_context():
                    page = await state.ACTIVE_BROWSER_CONTEXT.new_page()
                    try:
                        await process_apply_page(page, job)
                    finally:
                        await page.close()
                
                future = asyncio.run_coroutine_threadsafe(apply_in_active_context(), state.ACTIVE_EVENT_LOOP)
                future.result()
                return
            except Exception as e:
                log_message(f"Active context apply error: {e}. Falling back to standalone persistent session...")

        # Case 2: Main bot is idle — launch persistent Edge profile context containing user login cookies!
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def standalone_playwright_task():
            async with async_playwright() as p:
                browser = None
                try:
                    user_data_dir = os.path.join(os.path.expanduser("~"), "edge-debug-profile")
                    browser = await p.chromium.launch_persistent_context(
                        user_data_dir,
                        executable_path=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                        headless=False
                    )
                    page = browser.pages[0] if browser.pages else await browser.new_page()
                    await process_apply_page(page, job)
                except Exception as e:
                    log_message(f"Error in persistent single job apply: {e}")
                finally:
                    if browser:
                        await browser.close()
                
        loop.run_until_complete(standalone_playwright_task())
        loop.close()
        
    threading.Thread(target=apply_thread, daemon=True).start()
