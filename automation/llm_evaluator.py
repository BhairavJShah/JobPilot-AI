import re
import json
import urllib.request
from core.config_manager import CONFIG, get_model_name, get_ai_provider, get_gemini_api_key, get_gemini_model
from core.db_manager import log_message

MAX_RETRIES = 2

def query_local_qwen(prompt):
    """Query the local Ollama LLM with automatic retry on transient failures."""
    url = "http://127.0.0.1:11434/api/generate"
    model = get_model_name()
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    req_data = json.dumps(data).encode('utf-8')
    
    for attempt in range(MAX_RETRIES + 1):
        req = urllib.request.Request(
            url, 
            data=req_data, 
            headers={'Content-Type': 'application/json'}
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                res = json.loads(response.read().decode('utf-8'))
                return res.get("response", "").strip()
        except Exception as e:
            if attempt < MAX_RETRIES:
                import time
                time.sleep(2 * (attempt + 1))  # Exponential backoff: 2s, 4s
                continue
            log_message(f"Local {model} API error after {MAX_RETRIES + 1} attempts: {e}")
            return f"Ollama model '{model}' is unavailable or took too long to respond."

def query_google_gemini(prompt):
    """Query the Google Gemini API (Cloud AI)."""
    api_key = get_gemini_api_key()
    if not api_key:
        log_message("Gemini API Key missing. Falling back to local Ollama...")
        return query_local_qwen(prompt)
        
    g_model = get_gemini_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }
    req_data = json.dumps(payload).encode('utf-8')
    
    for attempt in range(MAX_RETRIES + 1):
        req = urllib.request.Request(
            url, 
            data=req_data, 
            headers={'Content-Type': 'application/json'}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                res = json.loads(response.read().decode('utf-8'))
                candidates = res.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
                return ""
        except Exception as e:
            if attempt < MAX_RETRIES:
                import time
                time.sleep(1.5 * (attempt + 1))
                continue
            log_message(f"Google Gemini API error ({g_model}): {e}. Falling back to local Ollama...")
            return query_local_qwen(prompt)

def query_ai_model(prompt):
    """Query either Local Ollama or Google Gemini based on user setting."""
    provider = get_ai_provider()
    if provider == "gemini" and get_gemini_api_key():
        return query_google_gemini(prompt)
    else:
        return query_local_qwen(prompt)

def evaluate_job_with_qwen(title, description):
    import core.state as state
    
    prompt = f"""
You are a technical recruiter assistant. Your job is to strictly evaluate if the candidate matches the job description.
Candidate Technical Profile:
- Skills: {', '.join(CONFIG['candidate'].get('skills', []))}.

Evaluate the following job:
Job Title: {title}
Job Description:
{description}

Rules:
1. Skip/Reject the job ONLY if it requires explicit forbidden keywords: {', '.join(CONFIG['settings']['skip_keywords'])}.
2. Calculate a percentage match score (from 0 to 100) based on candidate skills and transferable technical qualifications.
3. If the role matches candidate qualifications OR if the candidate has transferable skills to do the job (even if the title or exact keywords differ), set "is_match": true.
4. Set "should_approve": true for ANY job where title keywords differ from exact candidate search titles, or if candidate has general qualifications for the role, or if there is any doubt — so the user can review and approve it in the Approvals queue!
5. DO NOT reject jobs that the candidate is qualified to do. When in doubt, mark "is_match": true and "should_approve": true.

Respond ONLY in the following JSON format:
{{
  "is_match": true/false,
  "score": 85,
  "reason": "Explain briefly why it matches, what skills apply, or why user approval is requested",
  "should_approve": true/false
}}
"""
    res_text = query_ai_model(prompt)
    
    # Track session evaluation count
    state.SESSION_STATS["evaluated_today"] = state.SESSION_STATS.get("evaluated_today", 0) + 1
    
    try:
        match = re.search(r'\{.*\}', res_text, re.DOTALL)
        if match:
            result = json.loads(match.group(0))
            if result.get("is_match"):
                state.SESSION_STATS["matches_today"] = state.SESSION_STATS.get("matches_today", 0) + 1
            return result
    except Exception:
        pass
    
    # Fallback: keyword-based scoring
    score = 0
    skills = [s.lower() for s in CONFIG['candidate'].get('skills', [])]
    desc_l = description.lower()
    for s in skills:
        if s in desc_l:
            score += 10
    return {"is_match": score >= CONFIG['settings']['min_score'], "score": min(score, 100), "reason": "Fallback match based on keywords", "should_approve": False}
