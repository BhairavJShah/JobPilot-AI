import os
import re
import json
import webbrowser
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from core.config_manager import CONFIG
from core.db_manager import load_recruiter_contacts, log_message
from core.resume_parser import extract_resume_text
from core.email_smtp import send_smtp_email
from automation.llm_evaluator import query_local_qwen
from ui.components import C, F, create_action_btn

class ContactsView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.contacts_data = []
        
        # ── Header Row ──
        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.pack(fill='x', pady=(0, 14))
        lbl_title = ctk.CTkLabel(title_row, text="Recruiter Contacts & Outreach", font=F["h1"], text_color=C["text"])
        lbl_title.pack(side='left')
        
        # Search Entry
        self.search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(title_row, textvariable=self.search_var,
                                   placeholder_text="Search by company, role, email or phone...",
                                   fg_color=C["input"], border_color=C["border"],
                                   text_color=C["text"], font=F["sm"], width=280, height=36, corner_radius=8)
        search_entry.pack(side='right', padx=(10, 0))
        self.search_var.trace_add("write", lambda *args: self.filter_contacts())

        btn_refresh = create_action_btn(title_row, "Refresh", self.load_contacts_table, "ghost", "small")
        btn_refresh.pack(side='right')
        
        # ── Split Layout ──
        card_split = ctk.CTkFrame(self, fg_color="transparent")
        card_split.pack(fill='both', expand=True)
        card_split.columnconfigure(0, weight=1)
        card_split.columnconfigure(1, weight=1)
        card_split.rowconfigure(0, weight=1)
        
        # Left Panel - Table
        left_card = ctk.CTkFrame(card_split, fg_color=C["card"], corner_radius=12)
        left_card.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        
        columns = ('company', 'role', 'hr_name', 'email', 'phone')
        self.contacts_tree = ttk.Treeview(left_card, columns=columns, show='headings', style="Dark.Treeview")
        self.contacts_tree.heading('company', text='Company')
        self.contacts_tree.heading('role', text='Role')
        self.contacts_tree.heading('hr_name', text='HR / Recruiter')
        self.contacts_tree.heading('email', text='Email')
        self.contacts_tree.heading('phone', text='Phone / WhatsApp')
        
        self.contacts_tree.column('company', width=110)
        self.contacts_tree.column('role', width=120)
        self.contacts_tree.column('hr_name', width=100)
        self.contacts_tree.column('email', width=140)
        self.contacts_tree.column('phone', width=120)
        
        self.contacts_tree.bind("<<TreeviewSelect>>", self.on_contact_select)
        
        scrollbar = ttk.Scrollbar(left_card, orient="vertical", command=self.contacts_tree.yview, style="Dark.Vertical.TScrollbar")
        self.contacts_tree.configure(yscrollcommand=scrollbar.set)
        
        self.contacts_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        scrollbar.pack(side='right', fill='y', pady=10, padx=(0, 4))
        
        # Right Panel - Recruiter Outreach Card
        self.right_card = ctk.CTkScrollableFrame(card_split, fg_color=C["card"], corner_radius=12)
        self.right_card.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        
        # Selected Contact Details Display
        self.lbl_company_role = ctk.CTkLabel(self.right_card, text="Select a Recruiter Contact", font=F["h2"], text_color=C["text"], anchor="w")
        self.lbl_company_role.pack(anchor='w', padx=14, pady=(12, 4))
        
        self.lbl_hr_name = ctk.CTkLabel(self.right_card, text="Discovered via automated scan", font=F["sm"], text_color=C["muted"], anchor="w")
        self.lbl_hr_name.pack(anchor='w', padx=14, pady=(0, 12))
        
        # Action Buttons Box (WhatsApp & Call)
        self.action_box = ctk.CTkFrame(self.right_card, fg_color=C["input"], corner_radius=10)
        self.action_box.pack(fill='x', padx=14, pady=(0, 12))
        
        self.lbl_phone_val = ctk.CTkLabel(self.action_box, text="Phone / WhatsApp: N/A", font=F["sm_b"], text_color=C["text"], anchor="w")
        self.lbl_phone_val.pack(anchor='w', padx=12, pady=(10, 6))
        
        btn_phone_row = ctk.CTkFrame(self.action_box, fg_color="transparent")
        btn_phone_row.pack(fill='x', padx=12, pady=(0, 10))
        
        self.btn_whatsapp = create_action_btn(btn_phone_row, "💬 Open WhatsApp Chat", self.open_whatsapp, "success", "small")
        self.btn_whatsapp.pack(side='left', padx=(0, 8))
        
        self.btn_copy_phone = create_action_btn(btn_phone_row, "📞 Copy Number", self.copy_phone, "ghost", "small")
        self.btn_copy_phone.pack(side='left')

        # Email & Cover Letter Section
        self.email_box = ctk.CTkFrame(self.right_card, fg_color=C["input"], corner_radius=10)
        self.email_box.pack(fill='x', padx=14, pady=(0, 12))
        
        self.lbl_email_val = ctk.CTkLabel(self.email_box, text="Email: N/A", font=F["sm_b"], text_color=C["text"], anchor="w")
        self.lbl_email_val.pack(anchor='w', padx=12, pady=(10, 6))
        
        btn_email_row = ctk.CTkFrame(self.email_box, fg_color="transparent")
        btn_email_row.pack(fill='x', padx=12, pady=(0, 10))
        
        self.btn_send_smtp = create_action_btn(btn_email_row, "✉️ Send Direct Email", self.send_direct_email, "primary", "small")
        self.btn_send_smtp.pack(side='left', padx=(0, 8))
        
        self.btn_copy_email = create_action_btn(btn_email_row, "📋 Copy Email", self.copy_email, "ghost", "small")
        self.btn_copy_email.pack(side='left')

        # Cover Letter Preview Box
        lbl_draft_title = ctk.CTkLabel(self.right_card, text="Tailored Cold Email / Outreach Pitch", font=F["h3"], text_color=C["text"], anchor="w")
        lbl_draft_title.pack(anchor='w', padx=14, pady=(8, 6))
        
        draft_inner = ctk.CTkFrame(self.right_card, fg_color=C["input"], corner_radius=8)
        draft_inner.pack(fill='x', padx=14, pady=(0, 12))
        
        self.draft_preview = scrolledtext.ScrolledText(draft_inner,
            bg=C["input"], fg=C["text"],
            font=F["sm"], wrap='word', bd=0, height=10, highlightthickness=0)
        self.draft_preview.pack(fill='both', expand=True, padx=6, pady=6)
        
        self.selected_contact = None
        self.load_contacts_table()

    def load_contacts_table(self):
        for item in self.contacts_tree.get_children():
            self.contacts_tree.delete(item)
            
        self.contacts_data = load_recruiter_contacts()
        self.filter_contacts()

    def filter_contacts(self):
        for item in self.contacts_tree.get_children():
            self.contacts_tree.delete(item)
            
        query = self.search_var.get().strip().lower()
        for idx, c in enumerate(reversed(self.contacts_data)):
            comp = c.get("company", "")
            role = c.get("role", "")
            hr = c.get("recruiter_name", "")
            email = c.get("email", "")
            phone = c.get("phone", "")
            
            if not query or any(query in val.lower() for val in [comp, role, hr, email, phone]):
                self.contacts_tree.insert('', 'end', iid=str(idx), values=(comp, role, hr, email, phone))

    def on_contact_select(self, event):
        selected = self.contacts_tree.selection()
        if not selected: return
        
        idx = int(selected[0])
        # Reversed list lookup
        rev_data = list(reversed(self.contacts_data))
        if idx >= len(rev_data): return
        
        c = rev_data[idx]
        self.selected_contact = c
        
        comp = c.get("company", "Company")
        role = c.get("role", "Role")
        hr = c.get("recruiter_name", "Hiring Manager")
        email = c.get("email", "N/A")
        phone = c.get("phone", "N/A")
        
        self.lbl_company_role.configure(text=f"{role} @ {comp}")
        self.lbl_hr_name.configure(text=f"Recruiter: {hr} • Platform: {c.get('platform', '')}")
        self.lbl_phone_val.configure(text=f"Phone / WhatsApp: {phone if phone else 'N/A'}")
        self.lbl_email_val.configure(text=f"Email Address: {email if email else 'N/A'}")
        
        # Generate custom outreach pitch
        self.draft_preview.delete('1.0', 'end')
        self.draft_preview.insert('end', f"Generating personalized pitch for {hr} at {comp}...\n")
        
        def update_draft(reply):
            self.draft_preview.delete('1.0', 'end')
            self.draft_preview.insert('end', reply)

        def generate_pitch():
            try:
                resume_context = extract_resume_text()
                prompt = f"""
Write a 3-paragraph direct cold outreach message/email to the hiring recruiter.
Recruiter Name: {hr}
Job Role: {role}
Company Name: {comp}
Candidate Details:
{json.dumps(CONFIG["candidate"], indent=2)}
Resume Summary:
{resume_context[:2000]}

Keep it professional, engaging, and ready to send over Email or LinkedIn/WhatsApp.
"""
                reply = query_local_qwen(prompt)
                self.after(0, lambda: update_draft(reply))
            except Exception as e:
                self.after(0, lambda: update_draft(f"Error generating pitch: {e}"))
                
        threading.Thread(target=generate_pitch, daemon=True).start()

    def open_whatsapp(self):
        if not self.selected_contact or not self.selected_contact.get("phone"):
            messagebox.showinfo("WhatsApp", "No phone number recorded for this contact.")
            return
        phone = self.selected_contact.get("phone")
        digits = re.sub(r'\D', '', phone)
        if len(digits) == 10:
            digits = "91" + digits  # Default India country code if 10 digits
        webbrowser.open(f"https://wa.me/{digits}")

    def copy_phone(self):
        if not self.selected_contact or not self.selected_contact.get("phone"):
            return
        self.clipboard_clear()
        self.clipboard_append(self.selected_contact.get("phone"))
        messagebox.showinfo("Copied", "Phone number copied to clipboard!")

    def copy_email(self):
        if not self.selected_contact or not self.selected_contact.get("email"):
            return
        self.clipboard_clear()
        self.clipboard_append(self.selected_contact.get("email"))
        messagebox.showinfo("Copied", "Email address copied to clipboard!")

    def send_direct_email(self):
        if not self.selected_contact or not self.selected_contact.get("email"):
            messagebox.showerror("Error", "No email address found for this contact.")
            return
        to_email = self.selected_contact.get("email")
        role = self.selected_contact.get("role", "Job Role")
        draft = self.draft_preview.get('1.0', 'end').strip()
        subject = f"Application for {role} - {CONFIG['candidate']['name']}"
        resume = CONFIG["candidate"]["resume_path"]
        
        def send_task():
            log_message(f"SMTP: Sending recruiter outreach to {to_email}...")
            try:
                send_smtp_email(to_email, subject, draft, resume)
                log_message(f"SMTP: Successfully sent email to recruiter at {to_email}!")
                self.after(10, lambda: messagebox.showinfo("Success", f"Direct email sent to {to_email}!"))
            except Exception as e:
                log_message(f"SMTP ERROR: Failed to send email to {to_email}: {e}")
                self.after(10, lambda: messagebox.showerror("SMTP Error", f"Email send failed: {e}"))
                
        threading.Thread(target=send_task, daemon=True).start()
