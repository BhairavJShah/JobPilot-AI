import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import core.state as state
from core.db_manager import save_to_db, recalculate_metrics
from automation.bot_runner import apply_single_job_async
from ui.components import make_btn_interactive

class ApprovalsView(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        title_row = ttk.Frame(self)
        title_row.pack(fill='x', pady=(0, 20))
        lbl_title = ttk.Label(title_row, text="Doubt Queue Approvals", style='Heading.TLabel')
        lbl_title.pack(side='left')
        
        card_split = ttk.Frame(self)
        card_split.pack(fill='both', expand=True)
        card_split.columnconfigure(0, weight=1)
        card_split.columnconfigure(1, weight=1)
        card_split.rowconfigure(0, weight=1)
        
        left_card = ttk.Frame(card_split, style='Card.TFrame', padding=10)
        left_card.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        
        columns = ('company', 'role', 'score')
        self.appr_tree = ttk.Treeview(left_card, columns=columns, show='headings')
        self.appr_tree.heading('company', text='Company')
        self.appr_tree.heading('role', text='Role')
        self.appr_tree.heading('score', text='Score')
        self.appr_tree.column('company', width=120)
        self.appr_tree.column('role', width=150)
        self.appr_tree.column('score', width=70)
        
        self.appr_tree.bind("<<TreeviewSelect>>", self.on_approval_select)
        self.appr_tree.pack(fill='both', expand=True)
        
        right_card = ttk.Frame(card_split, style='Card.TFrame', padding=15)
        right_card.grid(row=0, column=1, sticky='nsew', padx=(10, 0))
        
        lbl_detail_lbl = ttk.Label(right_card, text="Job Details Preview", style='CardHeading.TLabel')
        lbl_detail_lbl.pack(anchor='w', pady=(0, 10))
        
        self.appr_desc = scrolledtext.ScrolledText(right_card, bg="#080c14", fg="#cbd5e1", font=('Segoe UI', 9), wrap='word', bd=0)
        self.appr_desc.pack(fill='both', expand=True, pady=(0, 10))
        
        btn_row = ttk.Frame(right_card)
        btn_row.pack(fill='x')
        
        btn_appr = tk.Button(btn_row, text="Approve & Apply", font=('Segoe UI', 9, 'bold'), padx=20, pady=7)
        btn_appr.pack(side='left', padx=5)
        btn_appr.config(command=self.approve_and_apply_job)
        make_btn_interactive(btn_appr, "#10b981", "#059669", "white", "white")
        
        btn_rej = tk.Button(btn_row, text="Reject & Skip", font=('Segoe UI', 9, 'bold'), padx=20, pady=7)
        btn_rej.pack(side='left', padx=5)
        btn_rej.config(command=self.reject_and_skip_job)
        make_btn_interactive(btn_rej, "#ef4444", "#dc2626", "white", "white")
        
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
        
        save_to_db(job.get("url", ""), job.get("title", ""), job.get("company", ""), job.get("platform", ""), "Manual User Disapproval", "Manual User Disapproval")
        self.load_approvals_table()
        self.appr_desc.delete('1.0', 'end')
        messagebox.showinfo("Skipped", "Job rejected and removed from queue.")
        recalculate_metrics()
        self.controller.refresh_nav_buttons()
