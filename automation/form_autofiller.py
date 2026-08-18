import os
import re
import asyncio
import core.state as state
from core.config_manager import CONFIG
from core.db_manager import log_message
from automation.llm_evaluator import query_ai_model

# ── Mapping of common ATS field patterns to QA Vault keys ──
# Each entry: (list_of_field_hint_patterns, config_key_path, fallback_value)
VAULT_FIELD_MAP = [
    # Contact info
    (["full name", "your name", "candidate name", "applicant name", "first name", "last name"],
     ("candidate", "name"), ""),
    (["email", "e-mail", "mail address"],
     ("candidate", "email"), ""),
    (["phone", "mobile", "contact number", "cell"],
     ("candidate", "phone"), ""),
    (["linkedin", "linked in"],
     ("candidate", "linkedin"), ""),
    (["github"],
     ("candidate", "github"), ""),
    (["portfolio", "website", "personal site"],
     ("candidate", "portfolio"), ""),
    # QA Vault fields
    (["experience", "years of experience", "total experience", "work experience", "exp in years"],
     ("candidate", "qa_vault", "experience_years"), "1"),
    (["notice period", "notice_period", "joining time"],
     ("candidate", "qa_vault", "notice_period"), "Immediate"),
    (["current ctc", "current salary", "current compensation", "present ctc", "present salary"],
     ("candidate", "qa_vault", "current_ctc"), "0"),
    (["expected ctc", "expected salary", "expected compensation", "desired salary", "desired ctc"],
     ("candidate", "qa_vault", "expected_ctc"), "Negotiable"),
    (["gender", "sex"],
     ("candidate", "qa_vault", "gender"), "Decline to state"),
    (["relocat", "willing to relocate", "open to relocation"],
     ("candidate", "qa_vault", "willing_to_relocate"), "Yes"),
    (["work authorization", "authorized to work", "legally authorized", "visa", "sponsorship"],
     ("candidate", "qa_vault", "work_authorization"), "Yes"),
    (["require sponsorship", "need sponsorship", "visa sponsorship"],
     ("candidate", "qa_vault", "require_sponsorship"), "No"),
]


def _get_config_value(key_path):
    """Traverse CONFIG dict using a tuple key path like ('candidate', 'qa_vault', 'experience_years')."""
    obj = CONFIG
    for k in key_path:
        if isinstance(obj, dict):
            obj = obj.get(k, None)
        else:
            return None
    return obj


def _match_vault(label_text):
    """Try to match a form field label to a QA vault entry. Returns value or None."""
    label_lower = label_text.lower().strip()
    for patterns, key_path, fallback in VAULT_FIELD_MAP:
        for pattern in patterns:
            if pattern in label_lower:
                val = _get_config_value(key_path)
                return val if val else fallback
    return None


async def _get_field_label(field, page):
    """Try to determine the label/question text for a form field element."""
    label_text = ""
    try:
        # Method 1: aria-label attribute
        aria = await field.get_attribute("aria-label")
        if aria and len(aria.strip()) > 2:
            return aria.strip()

        # Method 2: placeholder attribute
        placeholder = await field.get_attribute("placeholder")
        if placeholder and len(placeholder.strip()) > 2:
            return placeholder.strip()

        # Method 3: Associated <label> via 'for' attribute
        field_id = await field.get_attribute("id")
        if field_id:
            label_el = page.locator(f"label[for='{field_id}']")
            if await label_el.count() > 0:
                lt = await label_el.first.inner_text()
                if lt.strip():
                    return lt.strip()

        # Method 4: Find nearest preceding label/span/legend text
        # Use the field's parent container to look for label-like text
        field_name = await field.get_attribute("name") or ""
        if field_name:
            label_text = field_name.replace("_", " ").replace("-", " ").strip()
            if len(label_text) > 2:
                return label_text

        # Method 5: Title attribute
        title = await field.get_attribute("title")
        if title and len(title.strip()) > 2:
            return title.strip()

    except Exception:
        pass
    return label_text


async def _ai_answer_question(question_text, job_title="", company=""):
    """Use the AI model to answer an application form question based on candidate profile."""
    cand = CONFIG.get("candidate", {})
    skills = ", ".join(cand.get("skills", []))
    qa_vault = cand.get("qa_vault", {})

    prompt = f"""You are an expert job application assistant. Answer the following job application form question 
for the candidate. Give ONLY the answer text, nothing else. Be concise and professional.

Candidate Profile:
- Name: {cand.get('name', '')}
- Skills: {skills}
- Experience: {qa_vault.get('experience_years', '1')} years
- Notice Period: {qa_vault.get('notice_period', 'Immediate')}
- Current CTC: {qa_vault.get('current_ctc', '0')} LPA
- Expected CTC: {qa_vault.get('expected_ctc', 'Negotiable')} LPA
- Work Authorization: {qa_vault.get('work_authorization', 'Yes')}
- Willing to Relocate: {qa_vault.get('willing_to_relocate', 'Yes')}

Job: {job_title} at {company}

Form Question: "{question_text}"

Rules:
1. If the question asks for a number (years, salary, etc.), respond with ONLY the number.
2. If the question is yes/no, respond with ONLY "Yes" or "No".
3. If it's a city/location question, respond with the candidate's likely city or "Open to relocation".
4. If you truly cannot determine the answer from the profile, respond with exactly: UNSURE
5. Never respond with placeholder text like "N/A" or "Not applicable" - give a real answer or say UNSURE.

Answer:"""

    try:
        reply = query_ai_model(prompt)
        answer = reply.strip().split("\n")[0].strip()  # Take first line only
        if answer and answer.upper() != "UNSURE":
            return answer
    except Exception as e:
        log_message(f"AI form answer error: {e}")
    return None


async def _add_to_form_doubt_queue(question_text, field_info, job_title, company, job_url, platform):
    """Add an unanswered form question to the doubt queue for user input."""
    with state.DOUBT_LOCK:
        state.DOUBT_QUEUE.append({
            "title": job_title,
            "company": company,
            "url": job_url,
            "platform": platform,
            "score": "—",
            "reason": f"FORM QUESTION: {question_text}",
            "description": f"The application form for '{job_title}' at '{company}' asked a question the bot could not answer automatically.\n\nQuestion: {question_text}\n\nPlease answer this in the portal window, then approve the job from the Doubt Queue to continue.",
            "type": "form_question"
        })
    log_message(f"FORM DOUBT: Cannot auto-answer '{question_text}' for {job_title} at {company}. Added to Doubt Queue - please answer in the browser window.")


async def auto_fill_playwright_form(page, job_title="", company="", job_url="", platform=""):
    """
    Intelligent ATS form auto-filler with multi-layer answering:
    Layer 1: QA Vault pattern matching (instant, offline)
    Layer 2: AI-powered answer generation (for unknown questions)
    Layer 3: Doubt Queue pause (for truly uncertain questions)
    
    Also handles LinkedIn multi-step "Next" button forms.
    """
    try:
        log_message("Smart Auto-Filler: Scanning form fields...")
        filled_count = 0
        doubt_count = 0
        max_steps = 5  # LinkedIn can have up to 5 steps

        for step in range(max_steps):
            # ── 1. Fill all visible text input fields ──
            text_inputs = await page.locator(
                "input[type='text']:visible, input[type='email']:visible, "
                "input[type='tel']:visible, input[type='number']:visible, "
                "input[type='url']:visible, input:not([type]):visible"
            ).all()

            for field in text_inputs:
                try:
                    # Skip fields that already have a value
                    current_val = await field.input_value()
                    if current_val and len(current_val.strip()) > 0:
                        continue

                    label = await _get_field_label(field, page)
                    if not label:
                        continue

                    # Layer 1: Try QA Vault match
                    vault_answer = _match_vault(label)
                    if vault_answer:
                        await field.fill(str(vault_answer))
                        log_message(f"Auto-filled '{label}' from QA Vault")
                        filled_count += 1
                        continue

                    # Layer 2: Try AI answer
                    ai_answer = await _ai_answer_question(label, job_title, company)
                    if ai_answer:
                        await field.fill(ai_answer)
                        log_message(f"AI-filled '{label}' -> '{ai_answer}'")
                        filled_count += 1
                        continue

                    # Layer 3: Add to doubt queue
                    await _add_to_form_doubt_queue(label, {}, job_title, company, job_url, platform)
                    doubt_count += 1

                except Exception:
                    pass

            # ── 2. Fill textarea fields ──
            textareas = await page.locator("textarea:visible").all()
            for ta in textareas:
                try:
                    current_val = await ta.input_value()
                    if current_val and len(current_val.strip()) > 0:
                        continue

                    label = await _get_field_label(ta, page)
                    if not label:
                        continue

                    ai_answer = await _ai_answer_question(label, job_title, company)
                    if ai_answer:
                        await ta.fill(ai_answer)
                        log_message(f"AI-filled textarea '{label}'")
                        filled_count += 1
                    else:
                        await _add_to_form_doubt_queue(label, {}, job_title, company, job_url, platform)
                        doubt_count += 1
                except Exception:
                    pass

            # ── 3. Handle select/dropdown fields ──
            selects = await page.locator("select:visible").all()
            for sel in selects:
                try:
                    label = await _get_field_label(sel, page)
                    if not label:
                        continue

                    # Get all options
                    options = await sel.locator("option").all()
                    option_texts = []
                    for opt in options:
                        opt_text = await opt.inner_text()
                        opt_val = await opt.get_attribute("value")
                        if opt_val and opt_text.strip():
                            option_texts.append(opt_text.strip())

                    if not option_texts:
                        continue

                    # Try vault match first
                    vault_answer = _match_vault(label)
                    if vault_answer:
                        # Find best matching option
                        vault_lower = vault_answer.lower()
                        for opt_text in option_texts:
                            if vault_lower in opt_text.lower() or opt_text.lower() in vault_lower:
                                await sel.select_option(label=opt_text)
                                log_message(f"Auto-selected '{opt_text}' for '{label}'")
                                filled_count += 1
                                break
                        continue

                    # AI-select: ask AI which option to pick
                    options_str = ", ".join(option_texts[:15])
                    ai_prompt = f"For the dropdown question '{label}', which option should I select? Options: [{options_str}]. Reply with ONLY the exact option text."
                    ai_answer = await _ai_answer_question(ai_prompt, job_title, company)
                    if ai_answer:
                        for opt_text in option_texts:
                            if ai_answer.lower().strip() in opt_text.lower() or opt_text.lower() in ai_answer.lower().strip():
                                await sel.select_option(label=opt_text)
                                log_message(f"AI-selected '{opt_text}' for '{label}'")
                                filled_count += 1
                                break

                except Exception:
                    pass

            # ── 4. Handle radio buttons and checkboxes ──
            radio_groups = await page.locator("fieldset:visible, div[role='radiogroup']:visible, div[role='group']:visible").all()
            for group in radio_groups:
                try:
                    # Get the group question/legend
                    legend = group.locator("legend, label, span[class*='label']")
                    if await legend.count() == 0:
                        continue
                    question_text = await legend.first.inner_text()
                    if not question_text.strip():
                        continue

                    # Get radio/checkbox options
                    options = await group.locator("input[type='radio'], input[type='checkbox']").all()
                    if not options:
                        continue

                    # Collect option labels
                    option_labels = []
                    for opt in options:
                        opt_label = await _get_field_label(opt, page)
                        if not opt_label:
                            # Try sibling label text
                            try:
                                parent = opt.locator("xpath=..")
                                parent_text = await parent.inner_text()
                                opt_label = parent_text.strip()
                            except Exception:
                                pass
                        option_labels.append(opt_label or "Unknown")

                    # Try vault match
                    vault_answer = _match_vault(question_text)
                    if vault_answer:
                        vault_lower = vault_answer.lower()
                        for i, lbl in enumerate(option_labels):
                            if vault_lower in lbl.lower() or lbl.lower() in vault_lower:
                                await options[i].click()
                                log_message(f"Auto-selected radio '{lbl}' for '{question_text}'")
                                filled_count += 1
                                break
                        continue

                    # AI answer
                    labels_str = ", ".join(option_labels[:10])
                    ai_answer = await _ai_answer_question(
                        f"{question_text} Options: [{labels_str}]", job_title, company
                    )
                    if ai_answer:
                        ai_lower = ai_answer.lower().strip()
                        for i, lbl in enumerate(option_labels):
                            if ai_lower in lbl.lower() or lbl.lower() in ai_lower:
                                await options[i].click()
                                log_message(f"AI-selected radio '{lbl}' for '{question_text}'")
                                filled_count += 1
                                break

                except Exception:
                    pass

            # ── 5. Upload resume if file input found ──
            resume_path = CONFIG.get("candidate", {}).get("resume_path", "")
            if resume_path and os.path.exists(resume_path):
                file_inputs = await page.locator("input[type='file']:visible").all()
                for fi in file_inputs:
                    try:
                        await fi.set_input_files(resume_path)
                        log_message(f"Uploaded resume: {os.path.basename(resume_path)}")
                        filled_count += 1
                    except Exception:
                        pass

            # ── 6. Handle LinkedIn / multi-step "Next" button ──
            next_btn = page.locator(
                "button:has-text('Next'), button:has-text('Continue'), "
                "button[aria-label='Continue to next step'], "
                "button[aria-label='Next']"
            )
            # Don't click "Submit" buttons here — that's handled separately
            submit_btn = page.locator(
                "button:has-text('Submit application'), button:has-text('Submit'), "
                "button[aria-label='Submit application'], button:has-text('Send application')"
            )

            if await submit_btn.count() > 0:
                # We've reached the final step — try to submit
                if doubt_count == 0:
                    log_message(f"Smart Auto-Filler: All fields answered! Submitting application...")
                    try:
                        await submit_btn.first.click()
                        await asyncio.sleep(3)
                        log_message("Application submitted successfully!")
                    except Exception as e:
                        log_message(f"Submit click error: {e}")
                else:
                    log_message(f"Smart Auto-Filler: {doubt_count} question(s) need your input. Check the Doubt Queue tab or answer in the browser window.")
                break

            elif await next_btn.count() > 0:
                log_message(f"Multi-step form: Clicking Next (step {step + 1})...")
                try:
                    await next_btn.first.click()
                    await asyncio.sleep(2)
                except Exception:
                    break
            else:
                # No Next or Submit button found — single page form, we're done
                break

        log_message(f"Smart Auto-Filler complete: {filled_count} fields filled, {doubt_count} questions need manual input.")

        # If there are doubt questions, wait longer for user to answer them in the browser
        if doubt_count > 0:
            log_message(f"Waiting for you to answer {doubt_count} question(s) in the browser window...")

    except Exception as e:
        log_message(f"Critical error during smart form auto-fill: {e}")
