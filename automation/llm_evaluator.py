import re
import json
import urllib.request
import base64
from core.config_manager import CONFIG, get_model_name, get_ai_provider, get_cloud_ai_config
from core.db_manager import log_message

MAX_RETRIES = 2

def check_live_ai_status():
    """
    Empirically pings the active AI model (Ollama local endpoint or Cloud REST API)
    and returns a tuple: (status_text, is_online_bool)
    """
    provider = get_ai_provider()
    if provider == "cloud":
        cfg = get_cloud_ai_config()
        m_name = cfg.get("model") or cfg.get("preset", "Cloud")
        key = cfg.get("api_key") or cfg.get("password")
        if not key and cfg.get("auth_type") == "api_key":
            return (f"☁️ Cloud ({m_name}): Key Missing", False)
        return (f"☁️ Cloud ({m_name}): Ready", True)
    else:
        l_model = get_model_name()
        try:
            url = "http://127.0.0.1:11434/api/tags"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    models = [m.get("name") for m in data.get("models", [])]
                    base_m = l_model.split(":")[0]
                    found = any(base_m in m for m in models)
                    if found:
                        return (f"🤖 Local ({l_model}): Ready", True)
                    else:
                        return (f"🤖 Local ({l_model}): Model Not Pulled", False)
        except Exception:
            return (f"🤖 Local ({l_model}): Ollama Offline", False)
        return (f"🤖 Local ({l_model}): Ready", True)

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
    base_url = (cfg.get("base_url") or "https://api.openai.com/v1").strip().rstrip('/')
    model = (cfg.get("model") or "gpt-4o-mini").strip()
    auth_type = cfg.get("auth_type", "api_key")
    api_key = (cfg.get("api_key") or "").strip()
    username = (cfg.get("username") or "").strip()
    password = (cfg.get("password") or "").strip()
    
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
        else:
            headers['Authorization'] = f"Bearer {api_key}"

    # 2. Build Endpoint URL & Request Payload
    if "generativelanguage.googleapis.com" in base_url:
        endpoint = f"{base_url}/models/{model}:generateContent"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
    elif "anthropic.com" in base_url:
        endpoint = f"{base_url}/v1/messages"
        payload = {
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}]
        }
    else:
        # Standard OpenAI / v1 format
        if not base_url.endswith("/chat/completions") and not base_url.endswith("/generate"):
            endpoint = f"{base_url}/chat/completions"
        else:
            endpoint = base_url
            
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }

    req_data = json.dumps(payload).encode('utf-8')

    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(endpoint, data=req_data, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                res = json.loads(response.read().decode('utf-8'))
                
                # Parse response according to provider schema
                if "choices" in res and len(res["choices"]) > 0:
                    msg = res["choices"][0].get("message", {})
                    return msg.get("content", "").strip()
                elif "candidates" in res and len(res["candidates"]) > 0:
                    parts = res["candidates"][0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
                elif "content" in res and isinstance(res["content"], list):
                    return res["content"][0].get("text", "").strip()
                else:
                    return str(res)
        except Exception as e:
            if attempt < MAX_RETRIES:
                import time
                time.sleep(2 * (attempt + 1))
                continue
            log_message(f"Cloud AI Error ({endpoint}): {e}")
            return f"Cloud AI Service Error: {e}"

def query_ai_model(prompt):
    """Unified entry point for AI evaluations."""
    provider = get_ai_provider()
    if provider == "cloud":
        return query_cloud_ai(prompt)
    else:
        return query_local_qwen(prompt)

def evaluate_job_with_qwen(job_title, job_description):
    """
    Evaluates job relevance using the active AI provider (Local Ollama or Cloud REST API).
    Returns JSON dictionary with match score (0-100), reasoning, and approval flag.
    """
    cand_obj = CONFIG.get('candidate', {}) if isinstance(CONFIG.get('candidate'), dict) else {}
    set_obj = CONFIG.get('settings', {}) if isinstance(CONFIG.get('settings'), dict) else {}
    
    cand_skills = cand_obj.get('skills', []) if isinstance(cand_obj.get('skills'), list) else []
    target_queries = set_obj.get('queries', []) if isinstance(set_obj.get('queries'), list) else []
    skip_kw = set_obj.get('skip_keywords', []) if isinstance(set_obj.get('skip_keywords'), list) else []
    min_score_val = set_obj.get('min_score', 70)

    skills_str = ", ".join([str(s) for s in cand_skills])
    queries_str = ", ".join([str(q) for q in target_queries])
    skip_str = ", ".join([str(k) for k in skip_kw])

    prompt = f"""
You are an expert HR recruiter and AI job matching system.

Evaluate if this job listing matches the candidate's target profile:
Job Title: {job_title}
Job Description Snippet:
{job_description[:2000]}

Candidate Skills: {skills_str}
Candidate Target Roles: {queries_str}
Skip Keywords (Reject if present): {skip_str}

Instructions:
1. Return a JSON object with keys:
   - "score": Integer score from 0 to 100 representing job match fit.
   - "is_match": True if score >= {min_score_val}, else False.
   - "reason": Brief 1-2 sentence explanation of why this job matches or fails.
   - "should_approve": True if job title is borderline, non-standard, or salary is unusually high/low requiring human approval.

Respond ONLY with valid JSON.
"""
    reply = query_ai_model(prompt)
    
    try:
        match = re.search(r'\{.*\}', reply, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        log_message(f"Error parsing AI response JSON: {e}")
        
    return {
        "score": 50,
        "is_match": False,
        "reason": "Could not parse structured evaluation from AI model.",
        "should_approve": True
    }
