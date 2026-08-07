import re

def extract_recruiter_contacts(text):
    """
    Parses job descriptions or page content to extract recruiter contact info:
    - Email addresses
    - Phone / Mobile / WhatsApp numbers
    - Contact Person / HR names
    """
    if not text:
        return {"emails": [], "phones": [], "hr_names": []}
        
    # 1. Email Extraction
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = list(dict.fromkeys(re.findall(email_pattern, text)))  # Preserve order, unique
    
    # Filter out dummy/generic system emails if any
    filtered_emails = []
    for e in emails:
        e_lower = e.lower()
        if not any(dummy in e_lower for dummy in ["example.com", "schema.org", "sentry.io", "w3.org", "domain.com"]):
            filtered_emails.append(e)
            
    # 2. Phone / Mobile / WhatsApp Number Extraction
    # Matches Indian numbers (+91 9876543210, 9876543210, 09876543210) & International formats
    phone_pattern = r'(?:(?:\+?\d{1,3}[\s-]?)?\(?\d{3,5}\)?[\s-]?\d{3,5}[\s-]?\d{3,5})'
    raw_phones = re.findall(phone_pattern, text)
    
    valid_phones = []
    for p in raw_phones:
        digits = re.sub(r'\D', '', p)
        # Check digit length suitable for mobile/landline numbers (10 to 13 digits)
        if 10 <= len(digits) <= 13:
            # Avoid matching timestamps, dates, zip codes or large numbers
            if not digits.startswith(('202', '201', '200', '199', '198')):
                formatted_phone = p.strip()
                if formatted_phone not in valid_phones:
                    valid_phones.append(formatted_phone)
                    
    # Look for explicit WhatsApp / Phone keywords
    contact_keywords_pattern = r'(?:hr|recruiter|contact|call|whatsapp|ph|phone|mobile|reach us at|connect with)[\s\:\-]*([+\d\s\-\(\)]{10,18})'
    keyword_matches = re.findall(contact_keywords_pattern, text, re.IGNORECASE)
    for km in keyword_matches:
        digits = re.sub(r'\D', '', km)
        if 10 <= len(digits) <= 13 and km.strip() not in valid_phones:
            valid_phones.append(km.strip())

    # 3. HR / Recruiter Name Extraction
    hr_names = []
    hr_patterns = [
        r'(?:hr|recruiter|hiring manager|contact person)[\s\:\-]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
        r'reach out to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
        r'posted by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})'
    ]
    for pattern in hr_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            if m.strip() not in hr_names and len(m.strip()) > 3:
                hr_names.append(m.strip())

    return {
        "emails": filtered_emails,
        "phones": valid_phones,
        "hr_names": hr_names
    }
