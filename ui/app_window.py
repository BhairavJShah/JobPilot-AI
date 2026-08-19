import os
import csv
import json
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import core.state as state
from core.config_manager import CONFIG, CONFIG_PATH, get_model_name, get_active_model_display
from core.db_manager import APPLIED_DB_PATH, recalculate_metrics
from automation.llm_evaluator import check_live_ai_status
from ui.components import C, F, configure_treeview_style
from ui.dashboard_view import DashboardView
from ui.history_view import HistoryView
from ui.suggestions_view import SuggestionsView
from ui.approvals_view import ApprovalsView
from ui.settings_view import SettingsView
from ui.profile_view import ProfileView
from ui.accounts_view import AccountsView
from ui.contacts_view import ContactsView

class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("JobPilot-AI — Autonomous Job Search & Outreach Assistant")
        self.geometry("1220x800")
        self.minsize(1050, 680)
        self.configure(fg_color=C["bg"])
        
        self.current_view = "dashboard"
        configure_treeview_style()
        
        # ── Sidebar ──
        self.sidebar = ctk.CTkFrame(self, fg_color=C["sidebar"], corner_radius=0, width=240)
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)
        
        # Logo
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(pady=(24, 12), padx=20, anchor='w', fill='x')
        
        logo_icon = ctk.CTkLabel(logo_frame, text="◆", font=("Segoe UI", 20, "bold"), text_color=C["accent"])
        logo_icon.pack(side='left')
        logo_text = ctk.CTkLabel(logo_frame, text=" JobPilot-AI", font=F["logo"], text_color=C["text"])
        logo_text.pack(side='left')
        
        # Separator
        sep = ctk.CTkFrame(self.sidebar, fg_color=C["border"], height=1, corner_radius=0)
        sep.pack(fill='x', padx=20, pady=(8, 16))
        
        # Navigation Buttons
        nav_items = [
            ('dashboard',   '⊞', 'Dashboard'),
            ('history',     '☰', 'Applied History'),
            ('suggestions', '✉', 'Suggestions'),
            ('approvals',   '⚑', 'Approvals'),
            ('contacts',    '📇', 'Recruiter Contacts'),
            ('settings',    '⚙', 'AI & Search'),
            ('profile',     '◉', 'My Profile'),
            ('accounts',    '🔒', 'Credentials'),
        ]
        
        self.nav_btns = {}
        for name, icon, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=f"  {icon}   {label}",
                anchor="w",
                font=F["nav"],
                fg_color="transparent",
                hover_color=C["card_hover"],
                text_color=C["muted"],
                corner_radius=10,
                height=42,
                command=lambda n=name: self.show_view(n)
            )
            btn.pack(fill='x', padx=12, pady=2)
            self.nav_btns[name] = btn
            
        # Status Card at Sidebar Bottom
        status_card = ctk.CTkFrame(self.sidebar, fg_color=C["card"], corner_radius=12)
        status_card.pack(side='bottom', fill='x', padx=16, pady=20)
        
        self.status_dot = ctk.CTkLabel(status_card, text="●", font=F["xs_b"], text_color=C["green"], width=16)
        self.status_dot.pack(side='left', padx=(12, 0), pady=10)
        
        self.status_var = tk.StringVar(value="Status: Idle")
        self.status_lbl = ctk.CTkLabel(status_card, textvariable=self.status_var, font=F["xs_b"], text_color=C["muted"], anchor="w")
        self.status_lbl.pack(side='left', padx=(4, 12), pady=10)
        
        # ── Main Content Container ──
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(side='right', fill='both', expand=True, padx=(0, 20), pady=20)
        
        self.create_top_navbar()
        
        # Views
        self.views = {}
        self.views['dashboard'] = DashboardView(self.container, self)
        self.views['history'] = HistoryView(self.container, self)
        self.views['suggestions'] = SuggestionsView(self.container, self)
        self.views['approvals'] = ApprovalsView(self.container, self)
        self.views['contacts'] = ContactsView(self.container, self)
        self.views['settings'] = SettingsView(self.container, self)
        self.views['profile'] = ProfileView(self.container, self)
        self.views['accounts'] = AccountsView(self.container, self)
        
        self.show_view('dashboard')
        self.update_gui_loop()
        
    def _update_ai_status_async(self):
        def _check():
            try:
                status_text, is_online = check_live_ai_status()
                self._pending_ai_status = (status_text, is_online)
            except Exception:
                self._pending_ai_status = ("Offline", False)
        threading.Thread(target=_check, daemon=True).start()

    def _apply_ai_status(self, status_text, is_online):
        if hasattr(self, 'ind_qwen'):
            ind_color = C["green"] if is_online else C["red"]
            self.ind_qwen.configure(text=f"● {status_text}", text_color=ind_color)

    def create_top_navbar(self):
        self.top_bar = ctk.CTkFrame(self.container, fg_color=C["card"], corner_radius=12, height=48)
        self.top_bar.pack(fill='x', pady=(0, 16))
        self.top_bar.pack_propagate(False)
        
        status_f = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        status_f.pack(side='left', padx=16, fill='y')
        
        status_str = "Checking AI..."
        ind_color = C["dim"]
        self.ind_qwen = ctk.CTkLabel(status_f, text=f"● {status_str}",
                                     font=F["xs_b"], text_color=ind_color, cursor="hand2")
        self.ind_qwen.pack(side='left', padx=(0, 16), pady=12)
        self.ind_qwen.bind("<Button-1>", lambda e: self.show_view('settings'))
        
        self._update_ai_status_async()
        
        self.ind_edge = ctk.CTkLabel(status_f, text="● Edge: Connected",
                                    font=F["xs_b"], text_color=C["dim"])
        self.ind_edge.pack(side='left', padx=(0, 16), pady=12)
        
        self.ind_db = ctk.CTkLabel(status_f, text="● DB: Active",
                                  font=F["xs_b"], text_color=C["blue"])
        self.ind_db.pack(side='left', pady=12)
        
    def show_view(self, name):
        self.current_view = name
        for v in self.views.values():
            v.pack_forget()
        self.views[name].pack(fill='both', expand=True)
        self.refresh_nav_buttons()
        
        if name == 'history':
            self.views['history'].load_history_table()
        elif name == 'suggestions':
            self.views['suggestions'].load_suggestions_table()
        elif name == 'approvals':
            self.views['approvals'].load_approvals_table()
        elif name == 'contacts':
            self.views['contacts'].load_contacts_table()

    def refresh_nav_buttons(self):
        doubt_count = len(state.DOUBT_QUEUE)
        sug_count = getattr(state, 'SUGGESTION_COUNT', 0)

        nav_labels = {
            'dashboard':   ('⊞', 'Dashboard'),
            'history':     ('☰', 'Applied History'),
            'suggestions': ('✉', 'Suggestions'),
            'approvals':   ('⚑', 'Approvals'),
            'contacts':    ('📇', 'Recruiter Contacts'),
            'settings':    ('⚙', 'AI & Search'),
            'profile':     ('◉', 'My Profile'),
            'accounts':    ('🔒', 'Credentials'),
        }

        for name, btn in self.nav_btns.items():
            is_active = self.current_view == name
            icon, label = nav_labels[name]
            
            if name == 'approvals' and doubt_count > 0:
                text = f"  {icon}   Approvals  ● {doubt_count}"
                fg_color = C["card_hover"] if is_active else "transparent"
                text_color = C["red"]
            elif name == 'suggestions' and sug_count > 0:
                text = f"  {icon}   Suggestions  ● {sug_count}"
                fg_color = C["card_hover"] if is_active else "transparent"
                text_color = C["blue"]
            else:
                text = f"  {icon}   {label}"
                fg_color = C["card_hover"] if is_active else "transparent"
                text_color = C["text"] if is_active else C["muted"]

            font = F["nav_a"] if is_active else F["nav"]
            btn.configure(text=text, fg_color=fg_color, text_color=text_color, font=font)

    def execute_chat_command(self, cmd):
        c_type = cmd.get("type")
        key = cmd.get("key")
        val = cmd.get("value")
        
        try:
            if c_type == "append_query":
                existing = CONFIG["settings"].get("queries", [])
                if isinstance(val, list):
                    for v in val:
                        if v and v not in existing: existing.append(v)
                elif isinstance(val, str) and val not in existing:
                    existing.append(val)
                CONFIG["settings"]["queries"] = existing
            elif c_type == "update_setting":
                CONFIG["settings"][key] = val
            elif c_type == "update_candidate":
                CONFIG["candidate"][key] = val
            elif c_type == "update_qa_vault":
                if "qa_vault" not in CONFIG["candidate"]: CONFIG["candidate"]["qa_vault"] = {}
                CONFIG["candidate"]["qa_vault"][key] = str(val)
                
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(CONFIG, f, indent=4)
                
            self.after(10, self.reload_all_views)
        except Exception as e:
            from core.db_manager import log_message
            log_message(f"Error executing chat command: {e}")

    def reload_all_views(self):
        self.views['settings'].reload_view_data()
        self.views['profile'].reload_profile_fields()
        self._update_ai_status_async()
        recalculate_metrics()
        self.refresh_nav_buttons()

    def update_gui_loop(self):
        if hasattr(self, '_pending_ai_status') and self._pending_ai_status is not None:
            status_text, is_online = self._pending_ai_status
            self._pending_ai_status = None
            self._apply_ai_status(status_text, is_online)

        recalculate_metrics()
        self.views['dashboard'].update_dashboard_data()
        
        if state.BOT_PAUSED:
            self.status_var.set("Status: Paused")
            self.status_dot.configure(text_color=C["amber"])
            self.ind_edge.configure(text="● Edge: Paused", text_color=C["amber"])
        elif state.BOT_RUNNING:
            self.status_var.set(f"Status: {state.CURRENT_STATUS}")
            self.status_dot.configure(text_color=C["green"])
            self.ind_edge.configure(text="● Edge: Active", text_color=C["green"])
        else:
            self.status_var.set("Status: Idle")
            self.status_dot.configure(text_color=C["dim"])
            self.ind_edge.configure(text="● Edge: Idle", text_color=C["dim"])
            
        self.refresh_nav_buttons()
        self.after(1000, self.update_gui_loop)
