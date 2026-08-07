import re
import json
import urllib.request
import base64
from core.config_manager import CONFIG, get_model_name, get_ai_provider, get_cloud_ai_config
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

def query_cloud_ai(prompt):
    """Universal Cloud AI query supporting API Key, Bearer Token, Username/Password Auth, and Custom REST endpoints."""
    cfg = get_cloud_ai_config()
    base_url = cfg["base_url"].rstrip('/')
    model = cfg["model"]
    auth_type = cfg["auth_type"]
    api_key = cfg["api_key"]
    username = cfg["username"]
    password = cfg["password"]
    
    headers = {'Content-Type': 'application/json'}
    
    # 1. Setup Auth Headers (Bearer Token vs Username/Password Basic Auth)
    if auth_type == "user_pass" or (username and password and not api_key):
        userpass = f"{username}:{password}".encode('utf-8')
        b64_userpass = base64.b64encode(userpass).decode('utf-8')
        headers['Authorization'] = f"Basic {b64_userpass}"
    elif api_key:
        if "generativelanguage.googleapis.com" in base_url:
            headers['x-goog-api-key'] = api_key
        elif "anthropic.com" in base_url:
            headers['x-api-key'] = api_key
            headers['anthropic-version'] = '2023-06-01'
        else:
            headers['Authorization'] = f"Bearer {api_key}"
            
    # 2. Determine Endpoint & Payload format
    if "generativelanguage.googleapis.com" in base_url:
        endpoint = f"{base_url}/models/{model}:generateContent"
        if api_key and 'x-goog-api-key' not in headers:
            endpoint += f"?key={api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
    else:
        # Standard OpenAI / Custom REST Chat Completions API
        endpoint = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }

    req_data = json.dumps(payload).encode('utf-8')
    
    for attempt in range(MAX_RETRIES + 1):
        req = urllib.request.Request(
            endpoint, 
            data=req_data, 
            headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                res = json.loads(response.read().decode('utf-8'))
                
                # Parse OpenAI / Custom style choices
                if "choices" in res and len(res["choices"]) > 0:
                    choice = res["choices"][0]
                    if "message" in choice:
                        return choice["message"].get("content", "").strip()
                    elif "text" in choice:
                        return choice["text"].strip()
                # Parse Google style candidates
                elif "candidates" in res and len(res["candidates"]) > 0:
                    parts = res["candidates"][0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
                # Parse Anthropic style content list
                elif "content" in res and isinstance(res["content"], list) and len(res["content"]) > 0:
                    first_item = res["content"][0]
                    if isinstance(first_item, dict) and "text" in first_item:
                        return first_item["text"].strip()
                return json.dumps(res)
        except Exception as e:
            if attempt < MAX_RETRIES:
                import time
                time.sleep(1.5 * (attempt + 1))
                continue
            log_message(f"Universal Cloud AI error ({model} at {base_url}): {e}. Falling back to local Ollama...")
            return query_local_qwen(prompt)

def query_ai_model(prompt):
    """Query either Local Ollama or Universal Cloud AI based on user setting."""
    provider = get_ai_provider()
    if provider == "cloud":
        return query_cloud_ai(prompt)
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
