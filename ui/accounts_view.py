import json
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from core.config_manager import CONFIG, CONFIG_PATH
from core.db_manager import log_message, recalculate_metrics
from core.credential_store import get_credential, store_credential
from ui.components import C, F, add_grid_input, create_action_btn, add_section_divider

class AccountsView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # ── Header ──
        lbl_title = ctk.CTkLabel(self, text="Credentials & SMTP", font=F["h1"], text_color=C["text"], anchor="w")
        lbl_title.pack(anchor='w', pady=(0, 14))
        
        # ── Scrollable Card ──
        card = ctk.CTkScrollableFrame(self, fg_color=C["card"], corner_radius=12)
        card.pack(fill='both', expand=True)
        
        # ── Job Board Logins ──
        add_section_divider(card, "Job Board Session Logins")
        
        grid_frame = ctk.CTkFrame(card, fg_color="transparent")
        grid_frame.pack(fill='x', padx=16, pady=4)
        grid_frame.columnconfigure((0, 1), weight=1, uniform="equal")
        
        self.indeed_user = add_grid_input(grid_frame, "Indeed Username / Email", 0, 0)
        self.indeed_pass = add_grid_input(grid_frame, "Indeed Password", 0, 1)
        self.indeed_pass.configure(show="*")
        
        self.naukri_user = add_grid_input(grid_frame, "Naukri Username / Email", 1, 0)
        self.naukri_pass = add_grid_input(grid_frame, "Naukri Password", 1, 1)
        self.naukri_pass.configure(show="*")

        self.linkedin_user = add_grid_input(grid_frame, "LinkedIn Username / Email", 2, 0)
        self.linkedin_pass = add_grid_input(grid_frame, "LinkedIn Password", 2, 1)
        self.linkedin_pass.configure(show="*")
        
        # ── SMTP Mail Server ──
        add_section_divider(card, "SMTP Outreach Mail Server")
        
        smtp_frame = ctk.CTkFrame(card, fg_color="transparent")
        smtp_frame.pack(fill='x', padx=16, pady=4)
        smtp_frame.columnconfigure((0, 1), weight=1, uniform="equal")
        
        self.smtp_server = add_grid_input(smtp_frame, "SMTP Host (e.g. smtp.gmail.com)", 0, 0)
        self.smtp_port = add_grid_input(smtp_frame, "SMTP Port (default 587)", 0, 1)
        self.smtp_email = add_grid_input(smtp_frame, "Sender Email Address", 1, 0)
        self.smtp_password = add_grid_input(smtp_frame, "Email App Password", 1, 1)
        self.smtp_password.configure(show="*")
        
        # Populate
        self.indeed_user.insert(0, CONFIG["accounts"].get("indeed_email", ""))
        self.indeed_pass.insert(0, get_credential("accounts.indeed_pass"))
        self.naukri_user.insert(0, CONFIG["accounts"].get("naukri_email", ""))
        self.naukri_pass.insert(0, get_credential("accounts.naukri_pass"))
        self.linkedin_user.insert(0, CONFIG["accounts"].get("linkedin_email", ""))
        self.linkedin_pass.insert(0, get_credential("accounts.linkedin_pass"))
        
        self.smtp_server.insert(0, CONFIG.get("smtp", {}).get("server", ""))
        self.smtp_port.insert(0, CONFIG.get("smtp", {}).get("port", ""))
        self.smtp_email.insert(0, CONFIG.get("smtp", {}).get("email", ""))
        self.smtp_password.insert(0, get_credential("smtp.password"))
        
        # ── Save Button ──
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(anchor='w', padx=16, pady=(20, 16))
        btn_save = create_action_btn(btn_frame, "Save Credentials", self.save_accounts_action, "primary", "large")
        btn_save.pack(side='left')
        
    def save_accounts_action(self):
        try:
            CONFIG["accounts"]["indeed_email"] = self.indeed_user.get().strip()
            CONFIG["accounts"]["naukri_email"] = self.naukri_user.get().strip()
            CONFIG["accounts"]["linkedin_email"] = self.linkedin_user.get().strip()
            # Store passwords in secure OS keyring, NOT in config.json
            store_credential("accounts.indeed_pass", self.indeed_pass.get().strip())
            store_credential("accounts.naukri_pass", self.naukri_pass.get().strip())
            store_credential("accounts.linkedin_pass", self.linkedin_pass.get().strip())
            # Blank out passwords in config dict (they live in keyring now)
            CONFIG["accounts"]["indeed_pass"] = ""
            CONFIG["accounts"]["naukri_pass"] = ""
            CONFIG["accounts"]["linkedin_pass"] = ""
            
            if "smtp" not in CONFIG: CONFIG["smtp"] = {}
            CONFIG["smtp"]["server"] = self.smtp_server.get().strip()
            CONFIG["smtp"]["port"] = self.smtp_port.get().strip()
            CONFIG["smtp"]["email"] = self.smtp_email.get().strip()
            store_credential("smtp.password", self.smtp_password.get().strip())
            CONFIG["smtp"]["password"] = ""  # Blank out in config
            
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(CONFIG, f, indent=4)
            messagebox.showinfo("Success", "Account credentials & SMTP server saved securely!")
            log_message("Credentials saved to secure store & SMTP settings saved via Desktop GUI.")
            recalculate_metrics()
            self.controller.refresh_nav_buttons()
        except Exception as e:
            messagebox.showerror("Error", f"Could not save accounts: {e}")
