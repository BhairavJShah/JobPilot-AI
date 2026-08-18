import os
import json
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from core.config_manager import CONFIG, BASE_DIR
from core.resume_parser import extract_resume_text
from automation.llm_evaluator import query_ai_model
from core.db_manager import log_message
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os as _os

# Try to register a Unicode-capable font
_UNICODE_FONT = 'Helvetica'  # fallback
try:
    # Try common Windows fonts
    for _font_path in [
        _os.path.join(_os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'arial.ttf'),
        _os.path.join(_os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'segoeui.ttf'),
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
    ]:
        if _os.path.exists(_font_path):
            pdfmetrics.registerFont(TTFont('UnicodeFont', _font_path))
            _UNICODE_FONT = 'UnicodeFont'
            break
except Exception:
    pass

def _extract_json(text):
    start = text.find('{')
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    return None
    return None

RESUMES_OUTPUT_DIR = os.path.join(BASE_DIR, "tailored_resumes")
os.makedirs(RESUMES_OUTPUT_DIR, exist_ok=True)

def generate_tailored_resume_pdf(job_title="Software Engineer", company_name="Target Company", job_description=""):
    """
    Uses AI to tailor candidate's resume content for a target job description
    and compiles a modern professional PDF resume file.
    Returns absolute path of the generated PDF.
    """
    log_message(f"PDF RESUME GENERATOR: Tailoring resume for {job_title} at {company_name}...")
    
    cand = CONFIG.get("candidate", {})
    cand_name = cand.get("name", "Candidate Name")
    cand_email = cand.get("email", "candidate@email.com")
    cand_phone = cand.get("phone", "+91 9999999999")
    cand_linkedin = cand.get("linkedin", "")
    cand_github = cand.get("github", "")
    cand_skills = ", ".join(cand.get("skills", []))
    
    base_resume = extract_resume_text()
    
    prompt = f"""
You are an expert resume writer and ATS specialist. Tailor the candidate's resume for the target job role.

Candidate Profile:
- Name: {cand_name}
- Technical Skills: {cand_skills}
- Base Resume Summary:
{base_resume[:2000]}

Target Job:
- Title: {job_title}
- Company: {company_name}
- Description: {job_description[:2000]}

Instructions:
Generate a clean, structured JSON object with tailored resume content:
1. "summary": A compelling 3-sentence professional summary tailored to {job_title}.
2. "tailored_skills": A list of 8-12 top technical & soft skills matching the job.
3. "bullet_points": A list of 4-5 high-impact achievement bullet points relevant to this role.

Respond ONLY with JSON format:
{{
  "summary": "...",
  "tailored_skills": ["Skill1", "Skill2"],
  "bullet_points": ["Achievement 1...", "Achievement 2..."]
}}
"""
    reply = query_ai_model(prompt)
    
    summary = f"Dedicated {job_title} with strong technical foundation in {cand_skills}. Experienced in software development, problem solving, and building scalable applications."
    skills_list = cand.get("skills", [])
    bullets = [
        f"Developed and deployed high-performance software applications matching industry best practices.",
        f"Collaborated with cross-functional teams to design, test, and implement user-centric solutions.",
        f"Optimized database queries and API endpoints to improve application responsiveness by 35%.",
        f"Demonstrated proficiency in rapid learning and adapting to modern software frameworks."
    ]
    
    try:
        parsed = _extract_json(reply)
        if parsed:
            summary = parsed.get("summary", summary)
            skills_list = parsed.get("tailored_skills", skills_list)
            bullets = parsed.get("bullet_points", bullets)
    except Exception as e:
        log_message(f"AI JSON parse notice (using fallback): {e}")

    # Build PDF with ReportLab
    safe_company = "".join(c for c in company_name if c.isalnum() or c in (' ', '_')).rstrip().replace(" ", "_")
    safe_title = "".join(c for c in job_title if c.isalnum() or c in (' ', '_')).rstrip().replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"Resume_{safe_company}_{safe_title}_{timestamp}.pdf"
    pdf_path = os.path.join(RESUMES_OUTPUT_DIR, pdf_filename)
    
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('NameTitle', parent=styles['Heading1'], fontSize=22, leading=26, textColor=colors.HexColor('#0f172a'), fontName=_UNICODE_FONT)
    contact_style = ParagraphStyle('ContactInfo', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor('#475569'), fontName=_UNICODE_FONT)
    heading_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=12, leading=16, textColor=colors.HexColor('#2563eb'), fontName=_UNICODE_FONT, spaceBefore=12, spaceAfter=4)
    body_style = ParagraphStyle('BodyTextCustom', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor('#1e293b'), fontName=_UNICODE_FONT)
    bullet_style = ParagraphStyle('BulletCustom', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor('#334155'), leftIndent=12, firstLineIndent=-8, spaceAfter=4, fontName=_UNICODE_FONT)
    
    elements = []
    
    # Header Name
    elements.append(Paragraph(f"<b>{cand_name}</b>", title_style))
    contact_str = f"Email: {cand_email}  |  Phone: {cand_phone}"
    if cand_linkedin: contact_str += f"  |  LinkedIn: {cand_linkedin}"
    if cand_github: contact_str += f"  |  GitHub: {cand_github}"
    elements.append(Paragraph(contact_str, contact_style))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563eb'), spaceAfter=10))
    
    # Professional Summary
    elements.append(Paragraph("<b>PROFESSIONAL SUMMARY</b>", heading_style))
    elements.append(Paragraph(summary, body_style))
    elements.append(Spacer(1, 8))
    
    # Technical Skills
    elements.append(Paragraph("<b>TECHNICAL SKILLS</b>", heading_style))
    skills_str = ", ".join(skills_list)
    elements.append(Paragraph(skills_str, body_style))
    elements.append(Spacer(1, 8))
    
    # Key Achievements & Experience Highlights
    elements.append(Paragraph(f"<b>KEY HIGHLIGHTS ({job_title.upper()})</b>", heading_style))
    for b in bullets:
        elements.append(Paragraph(f"•  {b}", bullet_style))
        
    doc.build(elements)
    log_message(f"📄 TAILORED RESUME CREATED: {pdf_path}")
    return pdf_path
