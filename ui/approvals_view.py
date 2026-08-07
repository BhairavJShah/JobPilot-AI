import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import core.state as state
from core.db_manager import save_to_db, recalculate_metrics, update_job_status_in_csv
from automation.bot_runner import apply_single_job_async
from ui.components import C, F, create_action_btn

class ApprovalsView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # ── Header ──
        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.pack(fill='x', pady=(0, 14))
        lbl_title = ctk.CTkLabel(title_row, text="Doubt Queue Approvals", font=F["h1"], text_color=C["text"])
        lbl_title.pack(side='left')
        
        # ── Split Layout ──
        card_split = ctk.CTkFrame(self, fg_color="transparent")
        card_split.pack(fill='both', expand=True)
        card_split.columnconfigure(0, weight=1)
        card_split.columnconfigure(1, weight=1)
        card_split.rowconfigure(0, weight=1)
        
        left_card = ctk.CTkFrame(card_split, fg_color=C["card"], corner_radius=12)
        left_card.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        
        columns = ('company', 'role', 'score')
        self.appr_tree = ttk.Treeview(left_card, columns=columns, show='headings', style="Dark.Treeview")
        self.appr_tree.heading('company', text='Company')
        self.appr_tree.heading('role', text='Role')
        self.appr_tree.heading('score', text='Score')
        self.appr_tree.column('company', width=120)
        self.appr_tree.column('role', width=150)
        self.appr_tree.column('score', width=70)
        
        self.appr_tree.bind("<<TreeviewSelect>>", self.on_approval_select)
        self.appr_tree.pack(fill='both', expand=True, padx=10, pady=10)
        
        right_card = ctk.CTkFrame(card_split, fg_color=C["card"], corner_radius=12)
        right_card.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        
        lbl_detail_lbl = ctk.CTkLabel(right_card, text="Job Details Preview", font=F["h3"], text_color=C["text"])
        lbl_detail_lbl.pack(anchor='w', padx=14, pady=(12, 8))
        
        desc_inner = ctk.CTkFrame(right_card, fg_color=C["input"], corner_radius=8)
        desc_inner.pack(fill='both', expand=True, padx=14, pady=(0, 10))
        
        self.appr_desc = scrolledtext.ScrolledText(desc_inner,
            bg=C["input"], fg=C["text"],
            font=F["sm"], wrap='word', bd=0, highlightthickness=0)
        self.appr_desc.pack(fill='both', expand=True, padx=6, pady=6)
        
        btn_row = ctk.CTkFrame(right_card, fg_color="transparent")
        btn_row.pack(fill='x', padx=14, pady=(0, 14))
        
        btn_appr = create_action_btn(btn_row, "✓  Approve & Apply", self.approve_and_apply_job, "success", "normal")
        btn_appr.pack(side='left', padx=(0, 8))
        
        btn_rej = create_action_btn(btn_row, "✕  Reject & Skip", self.reject_and_skip_job, "danger", "normal")
        btn_rej.pack(side='left')
        
        self.load_approvals_table()

    def load_approvals_table(self):
        for item in self.appr_tree.get_children():
            self.appr_tree.delete(item)
        with state.DOUBT_LOCK:
            for job in state.DOUBT_QUEUE:
                self.appr_tree.insert('', 'end', iid=job.get('url', ''), values=(job.get("company", ""), job.get("title", ""), f"{job.get('score', 0)}%"))

    def on_approval_select(self, event):
        selected = self.appr_tree.selection()
        if not selected: return
        url_iid = selected[0]
        
        job = None
        with state.DOUBT_LOCK:
            for j in state.DOUBT_QUEUE:
                if j.get("url") == url_iid:
                    job = j
                    break
                    
        if not job: return
        
        self.appr_desc.delete('1.0', 'end')
        details = f"COMPANY: {job.get('company', '')}\nROLE: {job.get('title', '')}\nMATCH SCORE: {job.get('score', '')}%\nSOURCE: {job.get('platform', '')}\nURL: {job.get('url', '')}\nREASON: {job.get('reason', '')}\n\nDESCRIPTION:\n{job.get('description', '')}"
        self.appr_desc.insert('end', details)

    def approve_and_apply_job(self):
        selected = self.appr_tree.selection()
        if not selected: return
        url_iid = selected[0]
        
        job = None
        with state.DOUBT_LOCK:
            for idx, j in enumerate(state.DOUBT_QUEUE):
                if j.get("url") == url_iid:
                    job = state.DOUBT_QUEUE.pop(idx)
                    break
                    
        if not job: return
        
        apply_single_job_async(job)
        self.load_approvals_table()
        self.appr_desc.delete('1.0', 'end')
        messagebox.showinfo("Success", "Applying to approved job in background...")
        recalculate_metrics()
        self.controller.refresh_nav_buttons()

    def reject_and_skip_job(self):
        selected = self.appr_tree.selection()
        if not selected: return
        url_iid = selected[0]
        
        job = None
        with state.DOUBT_LOCK:
            for idx, j in enumerate(state.DOUBT_QUEUE):
                if j.get("url") == url_iid:
                    job = state.DOUBT_QUEUE.pop(idx)
                    break
                    
        if not job: return
        
        updated = update_job_status_in_csv(job.get("url", ""), "Approval Needed", "Manual User Disapproval", "Manual User Disapproval")
        if not updated:
            save_to_db(job.get("url", ""), job.get("title", ""), job.get("company", ""), job.get("platform", ""), "Manual User Disapproval", "Manual User Disapproval")
            
        self.load_approvals_table()
        self.appr_desc.delete('1.0', 'end')
        messagebox.showinfo("Skipped", "Job rejected and marked as Manual User Disapproval.")
        recalculate_metrics()
        self.controller.refresh_nav_buttons()
