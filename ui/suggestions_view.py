import os
import csv
import re
import json
import webbrowser
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from core.config_manager import CONFIG
from core.db_manager import APPLIED_DB_PATH, log_message, recalculate_metrics, update_job_status_in_csv
from core.resume_parser import extract_resume_text
from core.email_smtp import send_smtp_email
from automation.llm_evaluator import query_local_qwen
from ui.components import C, F, create_action_btn

class SuggestionsView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # ── Header ──
        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.pack(fill='x', pady=(0, 14))
        lbl_title = ctk.CTkLabel(title_row, text="Career Suggestions", font=F["h1"], text_color=C["text"])
        lbl_title.pack(side='left')
        
        # ── Split Layout ──
        card_split = ctk.CTkFrame(self, fg_color="transparent")
        card_split.pack(fill='both', expand=True)
        card_split.columnconfigure(0, weight=1)
        card_split.columnconfigure(1, weight=1)
        card_split.rowconfigure(0, weight=1)
        
        left_card = ctk.CTkFrame(card_split, fg_color=C["card"], corner_radius=12)
        left_card.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        
        columns = ('company', 'role', 'detail')
        self.sug_tree = ttk.Treeview(left_card, columns=columns, show='headings', style="Dark.Treeview")
        self.sug_tree.heading('company', text='Company')
        self.sug_tree.heading('role', text='Role')
        self.sug_tree.heading('detail', text='Target Email/URL')
        
        self.sug_tree.column('company', width=100)
        self.sug_tree.column('role', width=130)
        self.sug_tree.column('detail', width=180)
        self.sug_tree.bind("<<TreeviewSelect>>", self.on_suggestion_select)
        self.sug_tree.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.right_card = ctk.CTkFrame(card_split, fg_color=C["card"], corner_radius=12)
        self.right_card.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        
        preview_header = ctk.CTkFrame(self.right_card, fg_color="transparent")
        preview_header.pack(fill='x', padx=14, pady=(12, 8))
        lbl_preview = ctk.CTkLabel(preview_header, text="AI Cover Letter Draft", font=F["h3"], text_color=C["text"])
        lbl_preview.pack(side='left')
        
        ai_badge = ctk.CTkLabel(preview_header, text="AUTO", fg_color=C["purple"], text_color="white",
                                font=F["xs_b"], corner_radius=6, width=48, height=20)
        ai_badge.pack(side='left', padx=(8, 0))
        
        preview_inner = ctk.CTkFrame(self.right_card, fg_color=C["input"], corner_radius=8)
        preview_inner.pack(fill='both', expand=True, padx=14, pady=(0, 10))
        
        self.sug_preview = scrolledtext.ScrolledText(preview_inner,
            bg=C["input"], fg=C["text"],
            insertbackground="white", font=F["sm"],
            wrap='word', bd=0, highlightthickness=0)
        self.sug_preview.pack(fill='both', expand=True, padx=6, pady=6)
        
        btn_row = ctk.CTkFrame(self.right_card, fg_color="transparent")
        btn_row.pack(fill='x', padx=14, pady=(0, 14))
        
        self.btn_copy_draft = create_action_btn(btn_row, "Copy Draft", self.copy_draft_to_clipboard, "primary", "small")
        self.btn_copy_draft.pack(side='left', padx=(0, 6))
        
        self.btn_gen_pdf = create_action_btn(btn_row, "📄 Tailor Resume PDF", self.generate_pdf_action, "warning", "small")
        self.btn_gen_pdf.pack(side='left', padx=(0, 6))
        
        self.btn_open_target = create_action_btn(btn_row, "Open URL", self.open_suggestion_link, "success", "small")
        self.btn_open_target.pack(side='left', padx=(0, 6))

        self.btn_mark_applied = create_action_btn(btn_row, "✓ Mark Done", self.mark_suggestion_as_applied, "outline", "small")
        self.btn_mark_applied.pack(side='left')
        
        self.load_suggestions_table()

    def load_suggestions_table(self):
        for item in self.sug_tree.get_children():
            self.sug_tree.delete(item)
        if not os.path.exists(APPLIED_DB_PATH): return
        try:
            with open(APPLIED_DB_PATH, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if row and len(row) >= 6 and row[4] == "Suggested":
                        self.sug_tree.insert('', 'end', iid=row[0], values=(row[2], row[1], row[5]))
        except Exception as e:
            log_message(f"Suggestions load error: {e}")

    def on_suggestion_select(self, event):
        selected = self.sug_tree.selection()
        if not selected: return
        item = self.sug_tree.item(selected[0], 'values')
        company, role, detail = item[0], item[1], item[2]
        
        self.sug_preview.delete('1.0', 'end')
        self.sug_preview.insert('end', "Generating customized email draft cover letter...\n")
        
        def update_ui(reply):
            self.sug_preview.delete('1.0', 'end')
            self.sug_preview.insert('end', reply)

        def generate_mail():
            try:
                resume_context = extract_resume_text()
                prompt = f"""
Write a professional, highly engaging cold outreach email (cover letter) applying for the role.
Job Role: {role}
Company Name: {company}
Candidate Profile details:
{json.dumps(CONFIG["candidate"], indent=2)}
Candidate Resume Summary:
{resume_context[:2000]}

Draft a clear Subject line and Body. Use paragraph breaks. Keep it short, direct, and professional.
Do not include any placeholders like [Date], write the letter ready to send.
"""
                reply = query_local_qwen(prompt)
                self.after(0, lambda: update_ui(reply))
            except Exception as e:
                self.after(0, lambda: update_ui(f"Error generating email: {e}"))
            
        threading.Thread(target=generate_mail, daemon=True).start()

    def send_direct_smtp_email_action(self):
        selected = self.sug_tree.selection()
        if not selected: return
        url_iid = selected[0]
        item = self.sug_tree.item(url_iid, 'values')
        company, role, detail = item[0], item[1], item[2]
        
        email_matches = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', detail)
        if not email_matches:
            messagebox.showerror("Error", "No email recipient address found in suggestion target.")
            return
        to_email = email_matches[0]
        
        draft = self.sug_preview.get('1.0', 'end').strip()
        subject = f"Application for {role} - {CONFIG['candidate']['name']}"
        resume = CONFIG["candidate"]["resume_path"]
        
        def send_task():
            log_message(f"SMTP: Sending cover letter to {to_email}...")
            try:
                send_smtp_email(to_email, subject, draft, resume)
                log_message(f"SMTP: Successfully sent email application to {to_email}!")
                self.after(10, lambda: self.finish_smtp_applied(url_iid))
            except Exception as e:
                log_message(f"SMTP ERROR: Failed to send email to {to_email}: {e}")
                self.after(10, lambda: messagebox.showerror("SMTP Error", f"Email send failed: {e}"))
                
        threading.Thread(target=send_task, daemon=True).start()

    def finish_smtp_applied(self, url_iid):
        updated = update_job_status_in_csv(url_iid, "Suggested", "Applied", "Directly sent cover letter via SMTP Outreach Engine")
        if updated:
            messagebox.showinfo("Success", "Email outreach sent! Job moved to Applied History.")
            self.load_suggestions_table()
            self.sug_preview.delete('1.0', 'end')
            self.controller.refresh_nav_buttons()

    def mark_suggestion_as_applied(self):
        selected = self.sug_tree.selection()
        if not selected: return
        url = selected[0]
        
        updated = update_job_status_in_csv(url, "Suggested", "Applied", "Manually applied and marked done via checklist")
        if updated:
            messagebox.showinfo("Applied", "Job marked as Applied and moved to History!")
            self.load_suggestions_table()
            self.sug_preview.delete('1.0', 'end')
            self.controller.refresh_nav_buttons()
        else:
            messagebox.showerror("Error", "Could not find matching suggested record to update.")

    def copy_draft_to_clipboard(self):
        draft = self.sug_preview.get('1.0', 'end').strip()
        self.clipboard_clear()
        self.clipboard_append(draft)
        messagebox.showinfo("Success", "Cover letter draft copied to clipboard!")

    def open_suggestion_link(self):
        selected = self.sug_tree.selection()
        if not selected: return
        item = self.sug_tree.item(selected[0], 'values')
        detail = item[2]
        
        if "Email resume to:" in detail:
            email_addr = detail.replace("Email resume to:", "").strip()
            webbrowser.open(f"mailto:{email_addr}")
        elif "Career Page:" in detail:
            url_addr = detail.replace("Career Page:", "").strip()
            webbrowser.open(url_addr)
        else:
            if detail.startswith("http"):
                webbrowser.open(detail)

    def generate_pdf_action(self):
        selected = self.sug_tree.selection()
        if not selected:
            messagebox.showinfo("Select Job", "Please select a job suggestion from the list first.")
            return
        item = self.sug_tree.item(selected[0], 'values')
        company, role = item[0], item[1]
        
        def bg_generate():
            from core.resume_exporter import generate_tailored_resume_pdf
            try:
                pdf_path = generate_tailored_resume_pdf(role, company, "")
                self.after(10, lambda: messagebox.showinfo("Resume PDF Created", f"Tailored PDF resume generated at:\n{pdf_path}"))
                webbrowser.open(os.path.dirname(pdf_path))
            except Exception as e:
                self.after(10, lambda: messagebox.showerror("PDF Error", f"Could not generate PDF: {e}"))
                
        threading.Thread(target=bg_generate, daemon=True).start()
