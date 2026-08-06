import json
import tkinter as tk
from tkinter import ttk, messagebox
from core.config_manager import CONFIG, CONFIG_PATH
from core.db_manager import log_message, recalculate_metrics
from ui.components import add_grid_input, make_btn_interactive, enable_canvas_mousewheel

class AccountsView(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        lbl_title = ttk.Label(self, text="Job Board Logins & SMTP Configuration (Stored locally)", style='Heading.TLabel')
        lbl_title.pack(anchor='w', pady=(0, 20))
        
        canvas = tk.Canvas(self, bg="#0f172a", bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def on_canvas_configure(e):
            canvas.itemconfig(canvas_window, width=e.width)
            canvas.configure(scrollregion=canvas.bbox("all"))
            
        canvas.bind("<Configure>", on_canvas_configure)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        card = ttk.Frame(scrollable_frame, style='Card.TFrame', padding=20)
        card.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 1. Job Board Logins
        lbl_jobs_hdr = ttk.Label(card, text="Job Board Session Logins", style='CardHeading.TLabel')
        lbl_jobs_hdr.pack(anchor='w', pady=(0, 10))
        
        grid_frame = ttk.Frame(card)
        grid_frame.pack(fill='x', pady=10)
        grid_frame.columnconfigure((0, 1), weight=1, uniform="equal")
        
        self.indeed_user = add_grid_input(grid_frame, "Indeed Username / Email", 0, 0)
        self.indeed_pass = add_grid_input(grid_frame, "Indeed Password", 0, 1)
        self.indeed_pass.config(show="*")
        
        self.naukri_user = add_grid_input(grid_frame, "Naukri Username / Email", 1, 0)
        self.naukri_pass = add_grid_input(grid_frame, "Naukri Password", 1, 1)
        self.naukri_pass.config(show="*")

        self.linkedin_user = add_grid_input(grid_frame, "LinkedIn Username / Email", 2, 0)
        self.linkedin_pass = add_grid_input(grid_frame, "LinkedIn Password", 2, 1)
        self.linkedin_pass.config(show="*")
        
        # 2. SMTP Mail Server Configurations
        lbl_smtp_hdr = ttk.Label(card, text="SMTP Outreach Mail Server Configuration (Gmail App Passwords recommended)", style='CardHeading.TLabel')
        lbl_smtp_hdr.pack(anchor='w', pady=(20, 10))
        
        smtp_frame = ttk.Frame(card)
        smtp_frame.pack(fill='x', pady=10)
        smtp_frame.columnconfigure((0, 1), weight=1, uniform="equal")
        
        self.smtp_server = add_grid_input(smtp_frame, "SMTP Host Server (e.g. smtp.gmail.com)", 0, 0)
        self.smtp_port = add_grid_input(smtp_frame, "SMTP Server Port (default 587)", 0, 1)
        self.smtp_email = add_grid_input(smtp_frame, "Outbox Sender Email address", 1, 0)
        self.smtp_password = add_grid_input(smtp_frame, "Outbox Email App Password", 1, 1)
        self.smtp_password.config(show="*")
        
        # Populate
        self.indeed_user.insert(0, CONFIG["accounts"].get("indeed_email", ""))
        self.indeed_pass.insert(0, CONFIG["accounts"].get("indeed_pass", ""))
        self.naukri_user.insert(0, CONFIG["accounts"].get("naukri_email", ""))
        self.naukri_pass.insert(0, CONFIG["accounts"].get("naukri_pass", ""))
        self.linkedin_user.insert(0, CONFIG["accounts"].get("linkedin_email", ""))
        self.linkedin_pass.insert(0, CONFIG["accounts"].get("linkedin_pass", ""))
        
        self.smtp_server.insert(0, CONFIG.get("smtp", {}).get("server", ""))
        self.smtp_port.insert(0, CONFIG.get("smtp", {}).get("port", ""))
        self.smtp_email.insert(0, CONFIG.get("smtp", {}).get("email", ""))
        self.smtp_password.insert(0, CONFIG.get("smtp", {}).get("password", ""))
        
        btn_save = tk.Button(card, text="Save Credentials", font=('Segoe UI', 10, 'bold'), padx=25, pady=8)
        btn_save.pack(anchor='w', pady=(25, 0))
        btn_save.config(command=self.save_accounts_action)
        make_btn_interactive(btn_save, "#2563eb", "#1d4ed8", "white", "white")

        enable_canvas_mousewheel(canvas)
        
    def save_accounts_action(self):
        try:
            CONFIG["accounts"]["indeed_email"] = self.indeed_user.get().strip()
            CONFIG["accounts"]["indeed_pass"] = self.indeed_pass.get().strip()
            CONFIG["accounts"]["naukri_email"] = self.naukri_user.get().strip()
            CONFIG["accounts"]["naukri_pass"] = self.naukri_pass.get().strip()
            CONFIG["accounts"]["linkedin_email"] = self.linkedin_user.get().strip()
            CONFIG["accounts"]["linkedin_pass"] = self.linkedin_pass.get().strip()
            
            if "smtp" not in CONFIG: CONFIG["smtp"] = {}
            CONFIG["smtp"]["server"] = self.smtp_server.get().strip()
            CONFIG["smtp"]["port"] = self.smtp_port.get().strip()
            CONFIG["smtp"]["email"] = self.smtp_email.get().strip()
            CONFIG["smtp"]["password"] = self.smtp_password.get().strip()
            
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(CONFIG, f, indent=4)
            messagebox.showinfo("Success", "Account credentials & SMTP server saved locally!")
            log_message("Credentials & SMTP settings saved via Desktop GUI.")
            recalculate_metrics()
            self.controller.refresh_nav_buttons()
        except Exception as e:
            messagebox.showerror("Error", f"Could not save accounts: {e}")
