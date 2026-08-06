import os
import csv
import json
import tkinter as tk
from tkinter import ttk
import core.state as state
from core.config_manager import CONFIG, CONFIG_PATH, get_model_name, get_active_model_display
from core.db_manager import APPLIED_DB_PATH, recalculate_metrics
from ui.dashboard_view import DashboardView
from ui.history_view import HistoryView
from ui.suggestions_view import SuggestionsView
from ui.approvals_view import ApprovalsView
from ui.settings_view import SettingsView
from ui.profile_view import ProfileView
from ui.accounts_view import AccountsView

class AppWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI Job Bot Desktop Assistant")
        self.geometry("1150x760")
        self.configure(bg="#0f172a")
        
        self.current_view = "dashboard"
        
        # Style definition
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.style.layout('Vertical.TScrollbar', [
            ('Vertical.Scrollbar.trough', {'children': [
                ('Vertical.Scrollbar.thumb', {'expand': '1', 'sticky': 'nswe'})
            ], 'sticky': 'ns'})
        ])
        self.style.configure('Vertical.TScrollbar', troughcolor='#0f172a', background='#334155', bordercolor='#0f172a', arrowcolor='#94a3b8')
        
        self.style.configure('TFrame', background='#0f172a')
        self.style.configure('Card.TFrame', background='#1e293b', borderwidth=1, relief='solid', bordercolor='#1f2937')
        self.style.configure('Sidebar.TFrame', background='#0b0f19')
        self.style.configure('TLabel', background='#0f172a', foreground='#f1f5f9', font=('Segoe UI', 10))
        self.style.configure('Card.TLabel', background='#1e293b', foreground='#f1f5f9', font=('Segoe UI', 10))
        self.style.configure('Heading.TLabel', background='#0f172a', foreground='#ffffff', font=('Segoe UI', 15, 'bold'))
        self.style.configure('CardHeading.TLabel', background='#1e293b', foreground='#ffffff', font=('Segoe UI', 11, 'bold'))
        
        self.style.configure("Treeview", background="#0b0f19", foreground="#f1f5f9", fieldbackground="#0b0f19", rowheight=32, borderwidth=0, font=('Segoe UI', 9))
        self.style.configure("Treeview.Heading", background="#1e293b", foreground="#ffffff", font=('Segoe UI', 9, 'bold'), relief='flat')
        self.style.map("Treeview", background=[('selected', '#2563eb')])
        
        # Sidebar Frame
        self.sidebar = ttk.Frame(self, style='Sidebar.TFrame', width=240)
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)
        
        header_f = tk.Frame(self.sidebar, bg="#0b0f19")
        header_f.pack(pady=30, padx=20, anchor='w', fill='x')
        logo_label = tk.Label(header_f, text="✦ Job AI Agent", bg="#0b0f19", fg="#3b82f6", font=('Segoe UI', 14, 'bold'))
        logo_label.pack(side='left')
        
        # Navigation buttons
        self.nav_btns = {}
        for name in ['dashboard', 'history', 'suggestions', 'approvals', 'settings', 'profile', 'accounts']:
            btn = tk.Button(self.sidebar, bg="#0b0f19", fg="#94a3b8", activebackground="#1e293b", activeforeground="#ffffff", font=('Segoe UI', 10, 'bold'), relief='flat', bd=0, anchor='w', padx=15, height=2, command=lambda n=name: self.show_view(n))
            btn.pack(fill='x', padx=15, pady=2)
            self.nav_btns[name] = btn
            
        self.status_var = tk.StringVar(value="Status: Idle")
        status_lbl = tk.Label(self.sidebar, textvariable=self.status_var, bg="#0b0f19", fg="#10b981", font=('Segoe UI', 9, 'bold'))
        status_lbl.pack(side='bottom', pady=20, padx=20, anchor='w')
        
        self.container = ttk.Frame(self)
        self.container.pack(side='right', fill='both', expand=True, padx=25, pady=25)
        
        self.create_top_navbar()
        
        # Instantiate views inside main window container
        self.views = {}
        self.views['dashboard'] = DashboardView(self.container, self)
        self.views['history'] = HistoryView(self.container, self)
        self.views['suggestions'] = SuggestionsView(self.container, self)
        self.views['approvals'] = ApprovalsView(self.container, self)
        self.views['settings'] = SettingsView(self.container, self)
        self.views['profile'] = ProfileView(self.container, self)
        self.views['accounts'] = AccountsView(self.container, self)
        
        self.show_view('dashboard')
        self.update_gui_loop()
        
    def create_top_navbar(self):
        self.top_bar = tk.Frame(self.container, bg="#1e293b", height=50, highlightthickness=1, highlightbackground="#1f2937")
        self.top_bar.pack(fill='x', pady=(0, 20))
        self.top_bar.pack_propagate(False)
        
        status_f = tk.Frame(self.top_bar, bg="#1e293b")
        status_f.pack(side='left', padx=15, fill='y')
        
        active_disp = get_active_model_display()
        self.ind_qwen = tk.Label(status_f, text=f"● {active_disp}: Ready", bg="#1e293b", fg="#10b981", font=('Segoe UI', 8, 'bold'), cursor="hand2")
        self.ind_qwen.pack(side='left', padx=10)
        self.ind_qwen.bind("<Button-1>", lambda e: self.show_view('settings'))
        
        self.ind_edge = tk.Label(status_f, text="● Edge Driver: Connected", bg="#1e293b", fg="#94a3b8", font=('Segoe UI', 8, 'bold'))
        self.ind_edge.pack(side='left', padx=10)
        
        self.ind_db = tk.Label(status_f, text="● Local DB: active", bg="#1e293b", fg="#3b82f6", font=('Segoe UI', 8, 'bold'))
        self.ind_db.pack(side='left', padx=10)
        
    def show_view(self, name):
        self.current_view = name
        for v in self.views.values():
            v.pack_forget()
        self.views[name].pack(fill='both', expand=True)
        self.refresh_nav_buttons()
        
        # Trigger dynamic tree view reloads on focus
        if name == 'history':
            self.views['history'].load_history_table()
        elif name == 'suggestions':
            self.views['suggestions'].load_suggestions_table()
        elif name == 'approvals':
            self.views['approvals'].load_approvals_table()

    def refresh_nav_buttons(self):
        doubt_count = len(state.DOUBT_QUEUE)
        sug_count = 0
        if os.path.exists(APPLIED_DB_PATH):
            try:
                with open(APPLIED_DB_PATH, mode='r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if row and len(row) >= 5 and row[4] == "Suggested":
                            sug_count += 1
            except Exception: pass

        for name, btn in self.nav_btns.items():
            if name == 'approvals' and doubt_count > 0:
                text = f"Doubt Approvals  ● {doubt_count}"
                fg_color = "#ef4444"
                fg_hover = "#f87171"
            elif name == 'suggestions' and sug_count > 0:
                text = f"Job Suggestions  ● {sug_count}"
                fg_color = "#3b82f6"
                fg_hover = "#60a5fa"
            else:
                if name == 'dashboard': text = "Dashboard"
                elif name == 'history': text = "Applied History"
                elif name == 'suggestions': text = "Job Suggestions"
                elif name == 'approvals': text = "Doubt Approvals"
                elif name == 'settings': text = "Search Settings"
                elif name == 'profile': text = "Candidate Profile"
                elif name == 'accounts': text = "Logins & SMTP"
                
                fg_color = "#ffffff" if self.current_view == name else "#94a3b8"
                fg_hover = "#ffffff"

            bg_color = "#1e293b" if self.current_view == name else "#0b0f19"
            bg_hover = "#1e293b"
            
            btn.config(text=text, bg=bg_color, fg=fg_color)
            btn.bind("<Enter>", lambda e, b=btn, bh=bg_hover, fh=fg_hover: b.config(bg=bh, fg=fh))
            btn.bind("<Leave>", lambda e, b=btn, bc=bg_color, fc=fg_color: b.config(bg=bc, fg=fc))

    def execute_chat_command(self, cmd):
        c_type = cmd.get("type")
        key = cmd.get("key")
        val = cmd.get("value")
        
        try:
            if c_type == "update_setting":
                CONFIG["settings"][key] = val
            elif c_type == "update_candidate":
                CONFIG["candidate"][key] = val
                
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(CONFIG, f, indent=4)
                
            self.after(10, self.reload_all_views)
        except Exception as e:
            print(f"Error executing chat command: {e}")

    def reload_all_views(self):
        self.views['settings'].reload_view_data()
        self.views['profile'].reload_profile_fields()
        
        self.ind_qwen.config(text=f"● {get_active_model_display()}: Ready")
        
        recalculate_metrics()
        self.refresh_nav_buttons()

    def update_gui_loop(self):
        recalculate_metrics()
        
        # Dynamic dispatch refresh updates
        self.views['dashboard'].update_dashboard_data()
        
        if state.BOT_PAUSED:
            self.status_var.set("Status: Paused")
            self.ind_edge.config(text="● Edge Driver: Paused", fg="#d97706")
        elif state.BOT_RUNNING:
            self.status_var.set(f"Status: {state.CURRENT_STATUS}")
            self.ind_edge.config(text="● Edge Driver: Automated Loop Active", fg="#10b981")
        else:
            self.status_var.set("Status: Idle")
            self.ind_edge.config(text="● Edge Driver: Connected (Idle)", fg="#94a3b8")
            
        self.refresh_nav_buttons()
        self.after(1000, self.update_gui_loop)
