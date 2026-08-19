import os
import csv
import threading
from datetime import datetime
import core.state as state

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPLIED_DB_PATH = os.path.join(BASE_DIR, "applied_jobs.csv")
RECRUITER_DB_PATH = os.path.join(BASE_DIR, "recruiter_contacts.csv")
LOG_FILE_PATH = os.path.join(BASE_DIR, "bot_logs.txt")

DB_LOCK = threading.Lock()
RECRUITER_CACHE_SET = set()

def _init_recruiter_cache():
    if not RECRUITER_CACHE_SET and os.path.exists(RECRUITER_DB_PATH):
        try:
            with open(RECRUITER_DB_PATH, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if row and len(row) >= 7:
                        c_comp, c_email, c_url = row[0], row[3], row[6]
                        if c_url:
                            RECRUITER_CACHE_SET.add(f"url:{c_url}")
                        if c_comp and c_email:
                            RECRUITER_CACHE_SET.add(f"comp:{c_comp}:email:{c_email}")
        except Exception:
            pass

def save_recruiter_contact(company, role, recruiter_name, email, phone, platform, url):
    """Save extracted recruiter contact details to recruiter_contacts.csv."""
    if not (email or phone or recruiter_name):
        return
    
    with DB_LOCK:
        _init_recruiter_cache()
        cache_key_url = f"url:{url}" if url else None
        cache_key_comp_email = f"comp:{company}:email:{email}" if company and email else None
        
        if (cache_key_url and cache_key_url in RECRUITER_CACHE_SET) or \
           (cache_key_comp_email and cache_key_comp_email in RECRUITER_CACHE_SET):
            return

        file_exists = os.path.exists(RECRUITER_DB_PATH)
        try:
            with open(RECRUITER_DB_PATH, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Company", "Role", "Recruiter_Name", "Email", "Phone", "Platform", "URL", "Timestamp"])
                writer.writerow([company, role, recruiter_name, email, phone, platform, url, datetime.now().isoformat()])
            if cache_key_url:
                RECRUITER_CACHE_SET.add(cache_key_url)
            if cache_key_comp_email:
                RECRUITER_CACHE_SET.add(cache_key_comp_email)
            log_message(f"📇 RECRUITER CONTACT FOUND: {company} ({role}) -> Email: '{email}', Phone: '{phone}'")
        except Exception as e:
            log_message(f"Error saving recruiter contact: {e}")

def load_recruiter_contacts():
    """Load all recruiter contacts from CSV database."""
    with DB_LOCK:
        if not os.path.exists(RECRUITER_DB_PATH):
            return []
        contacts = []
        try:
            with open(RECRUITER_DB_PATH, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if row and len(row) >= 7:
                        contacts.append({
                            "company": row[0],
                            "role": row[1],
                            "recruiter_name": row[2],
                            "email": row[3],
                            "phone": row[4],
                            "platform": row[5],
                            "url": row[6],
                            "timestamp": row[7] if len(row) > 7 else ""
                        })
        except Exception as e:
            log_message(f"Error loading recruiter contacts: {e}")
        return contacts

# Shared in-memory set of applied URLs, updated live to prevent duplicates across concurrent loops
APPLIED_URLS_SET = set()

def init_applied_urls():
    """Load all applied URLs from CSV into the shared in-memory set."""
    global APPLIED_URLS_SET
    APPLIED_URLS_SET = load_applied_urls()

def log_message(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    state.LOG_QUEUE.append(full_msg)
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(full_msg + "\n")
    except Exception as e:
        print(f"Error writing log file: {e}")

def save_to_db(url, title, company, platform, status, detail=""):
    with DB_LOCK:
        file_exists = os.path.exists(APPLIED_DB_PATH)
        try:
            with open(APPLIED_DB_PATH, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["URL", "Title", "Company", "Platform", "Status", "Detail", "Timestamp"])
                writer.writerow([url, title, company, platform, status, detail, datetime.now().isoformat()])
            # Update the shared in-memory set so concurrent loops see this URL immediately
            APPLIED_URLS_SET.add(url)
            # Increment daily session counter for safety cap enforcement
            if status in ["Applied", "Manual Approval Apply"]:
                state.SESSION_STATS["applied_today"] = state.SESSION_STATS.get("applied_today", 0) + 1
            if status == "Suggested":
                state.SUGGESTION_COUNT += 1
            recalculate_metrics_unlocked()
        except Exception as e:
            log_message(f"Error saving to DB: {e}")

def update_job_status_in_csv(url_key, old_status, new_status, new_detail=""):
    """Helper to update a job's status in the CSV database. Returns True if updated."""
    rows = []
    updated = False
    with DB_LOCK:
        try:
            with open(APPLIED_DB_PATH, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header:
                    rows.append(header)
                for row in reader:
                    if row:
                        if row[0] == url_key and row[4] == old_status:
                            row[4] = new_status
                            if new_detail:
                                row[5] = new_detail
                            updated = True
                        rows.append(row)
            if updated:
                with open(APPLIED_DB_PATH, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
                recalculate_metrics_unlocked()
        except Exception as e:
            log_message(f"Error updating CSV status: {e}")
    return updated

def recalculate_metrics_unlocked():
    applied = 0
    skipped = 0
    suggested = 0
    platforms = {"Indeed": 0, "Naukri": 0, "LinkedIn": 0}
    if os.path.exists(APPLIED_DB_PATH):
        try:
            with open(APPLIED_DB_PATH, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None) # Skip header
                for row in reader:
                    if row and len(row) >= 5:
                        platform = row[3] if len(row) > 3 else ""
                        status = row[4]
                        if status in ["Applied", "Manual Approval Apply"]:
                            applied += 1
                        elif status in ["Skipped", "Rejected", "Manual User Disapproval"]:
                            skipped += 1
                        elif status == "Suggested":
                            suggested += 1
                        # Count platform breakdown
                        if platform in platforms:
                            platforms[platform] += 1
        except Exception:
            pass
    state.METRICS["applied"] = applied
    state.METRICS["skipped"] = skipped
    state.METRICS["suggested"] = suggested
    state.METRICS["platforms"] = platforms
    state.SUGGESTION_COUNT = suggested

def recalculate_metrics():
    with DB_LOCK:
        recalculate_metrics_unlocked()

def load_applied_urls():
    if not os.path.exists(APPLIED_DB_PATH):
        return set()
    urls = set()
    try:
        with DB_LOCK:
            with open(APPLIED_DB_PATH, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if row:
                        urls.add(row[0])
    except Exception as e:
        log_message(f"Error loading applied DB: {e}")
    return urls
