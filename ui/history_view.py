import os
import csv
import shutil
from datetime import datetime
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from core.db_manager import APPLIED_DB_PATH, log_message
from automation.status_tracker import start_tracker_thread
from ui.components import C, F, create_action_btn

class HistoryView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # ── Header Row ──
        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.pack(fill='x', pady=(0, 14))
        lbl_title = ctk.CTkLabel(title_row, text="Application History", font=F["h1"], text_color=C["text"])
        lbl_title.pack(side='left')
        
        btn_frame = ctk.CTkFrame(title_row, fg_color="transparent")
        btn_frame.pack(side='right')
        
        btn_export = create_action_btn(btn_frame, "Export CSV", self.export_csv, "success", "small")
        btn_export.pack(side='right', padx=(8, 0))
        
        btn_scan = create_action_btn(btn_frame, "Scan Statuses", start_tracker_thread, "primary", "small")
        btn_scan.pack(side='right', padx=(8, 0))

        btn_refresh = create_action_btn(btn_frame, "Refresh", self.load_history_table, "ghost", "small")
        btn_refresh.pack(side='right')
        
        # ── Table Card ──
        card = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=12)
        card.pack(fill='both', expand=True)
        
        columns = ('company', 'role', 'platform', 'status', 'detail', 'date')
        self.tree = ttk.Treeview(card, columns=columns, show='headings', style="Dark.Treeview")
        self.tree.heading('company', text='Company')
        self.tree.heading('role', text='Role')
        self.tree.heading('platform', text='Platform')
        self.tree.heading('status', text='Status')
        self.tree.heading('detail', text='Detail')
        self.tree.heading('date', text='Applied Date')
        
        self.tree.column('company', width=130)
        self.tree.column('role', width=180)
        self.tree.column('platform', width=80)
        self.tree.column('status', width=80)
        self.tree.column('detail', width=220)
        self.tree.column('date', width=120)
        
        scrollbar = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview, style="Dark.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True, padx=12, pady=12)
        scrollbar.pack(side='right', fill='y', pady=12, padx=(0, 6))
        
        self.load_history_table()

    def export_csv(self):
        if not os.path.exists(APPLIED_DB_PATH):
            messagebox.showinfo("Export CSV", "No history data available.")
            return
        
        downloads_folder = os.path.join(os.path.expanduser('~'), 'Downloads')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = os.path.join(downloads_folder, f"applied_jobs_{timestamp}.csv")
        
        try:
            shutil.copy2(APPLIED_DB_PATH, export_path)
            messagebox.showinfo("Export Successful", f"History exported to:\n{export_path}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not export CSV:\n{e}")

    def load_history_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not os.path.exists(APPLIED_DB_PATH): return
        try:
            rows = []
            with open(APPLIED_DB_PATH, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if row and len(row) >= 7:
                        try:
                            dt = datetime.fromisoformat(row[6])
                            formatted_date = dt.strftime("%Y-%m-%d %H:%M")
                            rows.append((row[2], row[1], row[3], row[4], row[5], formatted_date))
                        except Exception as e:
                            log_message(f"Error parsing date for row {row[0]}: {e}")
            for r in reversed(rows):
                self.tree.insert('', 'end', values=r)
        except Exception as e:
            log_message(f"History load error: {e}")
