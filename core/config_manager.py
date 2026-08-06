import os
import json
import urllib.parse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

LOCATION_DATA = {
    "India": {
        "All States": ["All Cities"],
        "Karnataka": ["All Cities", "Bangalore", "Mysore", "Hubli", "Mangalore"],
        "Maharashtra": ["All Cities", "Mumbai", "Pune", "Nagpur", "Thane", "Navi Mumbai"],
        "Tamil Nadu": ["All Cities", "Chennai", "Coimbatore", "Madurai", "Trichy"],
        "Delhi NCR": ["All Cities", "Delhi", "New Delhi", "Noida", "Gurgaon"],
        "Telangana": ["All Cities", "Hyderabad", "Warangal", "Secunderabad"],
        "Gujarat": ["All Cities", "Ahmedabad", "Surat", "Vadodara", "Rajkot"]
    },
    "United States": {
        "All States": ["All Cities"],
        "California": ["All Cities", "San Francisco", "Los Angeles", "San Jose", "San Diego"],
        "New York": ["All Cities", "New York City", "Buffalo", "Rochester"],
        "Texas": ["All Cities", "Austin", "Houston", "Dallas", "San Antonio"],
        "Washington": ["All Cities", "Seattle", "Bellevue", "Spokane"]
    }
}

DEFAULT_CONFIG = {
    "candidate": {
        "name": "Your Full Name",
        "email": "your.email@example.com",
        "phone": "9999999999",
        "country_code": "+91",
        "linkedin": "https://www.linkedin.com/in/your-profile",
        "github": "https://github.com/your-username",
        "portfolio": "https://yourportfolio.com",
        "resume_path": "",
        "skills": ["React", "Node.js", "Python", "JavaScript", "Git"]
    },
    "settings": {
        "queries": ["Full Stack Developer", "Software Engineer", "Frontend Developer"],
        "min_score": 70,
        "skip_keywords": ["c++", "ruby", "COBOL"],
        "max_jobs_per_query": 10,
        "experience_level": "All",
        "job_type": "All",
        "location_type": "All",
        "location_scope": "Entire Country",
        "preferred_locations": ["Mumbai, Maharashtra, India", "Bangalore, Karnataka, India"],
        "target_platforms": ["Indeed", "Naukri", "LinkedIn"],
        "ollama_model": "qwen2.5:7b",
        "ai_provider": "local",
        "gemini_api_key": "",
        "gemini_model": "gemini-2.5-flash"
    },
    "accounts": {
        "indeed_email": "",
        "indeed_pass": "",
        "naukri_email": "",
        "naukri_pass": "",
        "linkedin_email": "",
        "linkedin_pass": ""
    },
    "smtp": {
        "server": "",
        "port": "",
        "email": "",
        "password": ""
    }
}

CONFIG = {}

def load_config():
    global CONFIG
    if not os.path.exists(CONFIG_PATH):
        CONFIG = dict(DEFAULT_CONFIG)
        save_config()
    else:
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                CONFIG = json.load(f)
                # Fill missing keys dynamically
                for category in ["candidate", "settings", "accounts", "smtp"]:
                    if category not in CONFIG:
                        CONFIG[category] = DEFAULT_CONFIG[category]
                    else:
                        for k, v in DEFAULT_CONFIG[category].items():
                            if k not in CONFIG[category]:
                                CONFIG[category][k] = v
        except Exception:
            CONFIG = dict(DEFAULT_CONFIG)
            save_config()
    return CONFIG

def save_config():
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(CONFIG, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

def get_model_name():
    """Get the configured Ollama model name, with fallback."""
    return CONFIG.get("settings", {}).get("ollama_model", "qwen2.5:7b")

def get_location_search_term(chip_text):
    parts = [p.strip() for p in chip_text.split(",") if p.strip()]
    if len(parts) == 3:
        city, state, country = parts[0], parts[1], parts[2]
        if city != "All Cities":
            return city
        elif state != "All States":
            return state
        else:
            return country
    return chip_text

def encode_query_for_url(query, platform="naukri"):
    """Safely encode search queries for platform-specific URLs."""
    if platform == "naukri":
        # Naukri uses dashed-lowercase slugs in URLs
        safe_q = query.strip().lower()
        safe_q = safe_q.replace("+", "plus").replace("#", "sharp").replace(".", "-dot-")
        safe_q = safe_q.replace(" ", "-")
        # Remove remaining unsafe URL chars
        safe_q = urllib.parse.quote(safe_q, safe="-")
        return safe_q
    elif platform == "indeed":
        return query.replace(" ", "+")
    elif platform == "linkedin":
        return urllib.parse.quote(query, safe="")
    return query

def get_installed_ollama_models():
    """Fetch list of installed models from local Ollama API."""
    import urllib.request
    try:
        response = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
        data = json.loads(response.read().decode('utf-8'))
        return [m['name'] for m in data.get("models", [])]
    except Exception:
        return []

def get_ai_provider():
    return CONFIG.get("settings", {}).get("ai_provider", "local")

def get_gemini_api_key():
    return CONFIG.get("settings", {}).get("gemini_api_key", "").strip()

def get_gemini_model():
    return CONFIG.get("settings", {}).get("gemini_model", "gemini-2.5-flash")

def get_active_model_display():
    provider = get_ai_provider()
    if provider == "gemini":
        g_model = get_gemini_model()
        return f"☁️ Gemini ({g_model})"
    else:
        l_model = get_model_name()
        return f"🤖 Local ({l_model})"

# Initial load
load_config()
