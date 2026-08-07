import re
import json
import urllib.request
import urllib.parse
from core.config_manager import CONFIG
from core.db_manager import log_message

def fast_scrape_jobs(query="Software Engineer", location="", limit=20):
    """
    Rapidly fetches job postings across multiple platforms using API/HTTP search endpoints.
    Returns list of dicts: [{"title": ..., "company": ..., "location": ..., "platform": ..., "url": ..., "description": ...}]
    """
    results = []
    log_message(f"⚡ FAST SCRAPER: Searching '{query}' in '{location if location else 'All'}'...")
    
    # 1. Scrape via JobSpy if available
    try:
        from jobspy import scrape_jobs
        loc_str = location if location else "India"
        site_names = ["linkedin", "indeed"]
        
        jobs_df = scrape_jobs(
            site_name=site_names,
            search_term=query,
            location=loc_str,
            results_wanted=min(limit, 20),
            hours_old=72,
            country_indeed='india' if 'india' in loc_str.lower() or 'chennai' in loc_str.lower() or 'bangalore' in loc_str.lower() else 'usa'
        )
        
        if not jobs_df.empty:
            for _, row in jobs_df.iterrows():
                results.append({
                    "title": str(row.get("title", "")),
                    "company": str(row.get("company", "")),
                    "location": str(row.get("location", "")),
                    "platform": str(row.get("site", "")).capitalize(),
                    "url": str(row.get("job_url", "")),
                    "description": str(row.get("description", ""))
                })
            log_message(f"⚡ JobSpy Scraper: Discovered {len(results)} jobs!")
            return results
    except Exception as e:
        log_message(f"JobSpy direct scraper notice (using fallback): {e}")

    # 2. Fallback Direct Search Scraper (LinkedIn Public Guest API)
    try:
        q_enc = urllib.parse.quote(query)
        loc_enc = urllib.parse.quote(location) if location else "India"
        api_url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={q_enc}&location={loc_enc}&start=0"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            
            # Simple regex parser for LinkedIn guest job cards
            titles = re.findall(r'<h3 class="base-search-card__title">\s*(.*?)\s*</h3>', html, re.DOTALL)
            companies = re.findall(r'<h4 class="base-search-card__subtitle">\s*<a[^>]*>\s*(.*?)\s*</a>', html, re.DOTALL)
            links = re.findall(r'<a class="base-card__full-link[^"]*" href="([^"?]*)', html)
            
            for i in range(min(len(titles), len(companies), len(links))):
                results.append({
                    "title": titles[i].strip(),
                    "company": companies[i].strip(),
                    "location": location if location else "India",
                    "platform": "LinkedIn",
                    "url": links[i].strip(),
                    "description": f"Role: {titles[i].strip()} at {companies[i].strip()}."
                })
            log_message(f"⚡ Direct Scraper: Found {len(results)} fast LinkedIn job listings!")
    except Exception as e:
        log_message(f"Fast scraper fallback error: {e}")
        
    return results
