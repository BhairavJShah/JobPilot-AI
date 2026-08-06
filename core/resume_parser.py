import os
from core.config_manager import CONFIG

def extract_resume_text():
    path = CONFIG["candidate"].get("resume_path", "")
    if not path or not os.path.exists(path):
        return "Resume file not found at local path."
    try:
        import pypdf
        reader = pypdf.PdfReader(path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except ImportError:
        return "pypdf library not installed. RAG resume parsing is currently disabled."
    except Exception as e:
        return f"Error reading resume PDF: {e}"
