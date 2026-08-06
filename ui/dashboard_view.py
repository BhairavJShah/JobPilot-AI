import os
import csv
import json
import re
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
import core.state as state
from core.config_manager import CONFIG, CONFIG_PATH
from core.db_manager import log_message, recalculate_metrics, APPLIED_DB_PATH
from core.resume_parser import extract_resume_text
from automation.llm_evaluator import query_local_qwen
from automation.bot_runner import start_bot_thread, stop_bot
from ui.components import make_btn_interactive

class DashboardView(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        title_row = ttk.Frame(self)
        title_row.pack(fill='x', pady=(0, 15))
        lbl_title = ttk.Label(title_row, text="Control Dashboard", style='Heading.TLabel')
        lbl_title.pack(side='left')
        
        self.btn_toggle = tk.Button(title_row, text="Start Bot", font=('Segoe UI', 10, 'bold'), padx=20, pady=6)
        self.btn_toggle.pack(side='right')
        self.btn_toggle.config(command=self.toggle_bot_action)
        make_btn_interactive(self.btn_toggle, "#2563eb", "#1d4ed8", "white", "white")
        
        self.btn_pause = tk.Button(title_row, text="Pause", font=('Segoe UI', 10, 'bold'), padx=20, pady=6)
        self.btn_pause.pack(side='right', padx=5)
        self.btn_pause.config(command=self.toggle_pause_action)
        make_btn_interactive(self.btn_pause, "#d97706", "#b45309", "white", "white")
        
        metrics_frame = ttk.Frame(self)
        metrics_frame.pack(fill='x', pady=(0, 5))
        metrics_frame.columnconfigure((0, 1, 2, 3), weight=1, uniform="equal")
        
        self.applied_metric = self.create_metric_card(metrics_frame, "Applications Sent", "0", 0)
        self.skipped_metric = self.create_metric_card(metrics_frame, "Jobs Skipped", "0", 1)
        self.total_metric = self.create_metric_card(metrics_frame, "Total Evaluated", "0", 2)
        self.success_metric = self.create_metric_card(metrics_frame, "Success Rate", "0%", 3)
        
        self.session_stats_lbl = ttk.Label(self, text="Today: 0 evaluated, 0 matches", foreground="#94a3b8", font=('Segoe UI', 9))
        self.session_stats_lbl.pack(anchor='w', pady=(0, 15))
        
        workspace_frame = ttk.Frame(self)
        workspace_frame.pack(fill='both', expand=True)
        workspace_frame.columnconfigure(0, weight=1)
        workspace_frame.columnconfigure(1, weight=1)
        workspace_frame.rowconfigure(0, weight=1)
        workspace_frame.rowconfigure(1, weight=1)
        
        # Logs Card
        logs_card = ttk.Frame(workspace_frame, style='Card.TFrame', padding=15)
        logs_card.grid(row=0, column=0, sticky='nsew', padx=(0, 10), pady=(0, 10))
        
        log_top = ttk.Frame(logs_card)
        log_top.pack(fill='x', pady=(0, 5))
        lbl_log_title = ttk.Label(log_top, text="Operation Logs", style='CardHeading.TLabel')
        lbl_log_title.pack(side='left')
        
        self.log_search_var = tk.StringVar()
        log_search = tk.Entry(log_top, textvariable=self.log_search_var, bg="#080c14", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#1f2937", font=('Segoe UI', 9), width=20)
        log_search.pack(side='right')
        
        self.logs_box = scrolledtext.ScrolledText(logs_card, bg="#080c14", fg="#38bdf8", insertbackground="white", font=('Courier New', 9), bd=0, highlightthickness=1, highlightbackground="#1f2937")
        self.logs_box.pack(fill='both', expand=True)
        
        self.log_search_var.trace_add("write", lambda *args: self.update_logs_display())
        log_search.insert(0, "Search logs...")
        log_search.bind("<FocusIn>", lambda e: (log_search.delete(0, 'end') if log_search.get() == "Search logs..." else None, log_search.config(highlightbackground="#2563eb", highlightcolor="#2563eb")))
        log_search.bind("<FocusOut>", lambda e: (log_search.insert(0, "Search logs...") if not log_search.get() else None, log_search.config(highlightbackground="#1f2937", highlightcolor="#1f2937")))
        
        # Visual Analytics Card
        charts_card = ttk.Frame(workspace_frame, style='Card.TFrame', padding=15)
        charts_card.grid(row=1, column=0, sticky='nsew', padx=(0, 10), pady=(10, 0))
        lbl_charts_title = ttk.Label(charts_card, text="Visual Pipeline Analytics", style='CardHeading.TLabel')
        lbl_charts_title.pack(anchor='w', pady=(0, 5))
        
        self.chart_canvas = tk.Canvas(charts_card, bg="#1e293b", highlightthickness=0)
        self.chart_canvas.pack(fill='both', expand=True)
        
        # Chat Card
        chat_card = ttk.Frame(workspace_frame, style='Card.TFrame', padding=15)
        chat_card.grid(row=0, column=1, rowspan=2, sticky='nsew', padx=(10, 0))
        lbl_chat_title = ttk.Label(chat_card, text="Qwen RAG Assistant Chat", style='CardHeading.TLabel')
        lbl_chat_title.pack(anchor='w', pady=(0, 10))
        
        self.chat_history = scrolledtext.ScrolledText(chat_card, bg="#080c14", fg="#e2e8f0", insertbackground="white", font=('Segoe UI', 9), bd=0, state='disabled', wrap='word', highlightthickness=1, highlightbackground="#1f2937")
        self.chat_history.pack(fill='both', expand=True, pady=(0, 10))
        
        input_row = ttk.Frame(chat_card)
        input_row.pack(fill='x')
        self.chat_input = tk.Entry(input_row, bg="#080c14", fg="white", insertbackground="white", font=('Segoe UI', 10), bd=0, highlightthickness=1, highlightbackground="#1f2937")
        self.chat_input.pack(side='left', fill='x', expand=True, ipady=8, padx=(0, 5))
        self.chat_input.bind("<Return>", lambda e: self.send_chat_message())
        
        self.chat_input.bind("<FocusIn>", lambda e: self.chat_input.config(highlightbackground="#2563eb", highlightcolor="#2563eb"))
        self.chat_input.bind("<FocusOut>", lambda e: self.chat_input.config(highlightbackground="#1f2937", highlightcolor="#1f2937"))
        
        btn_send = tk.Button(input_row, text="Send", font=('Segoe UI', 9, 'bold'), padx=15)
        btn_send.pack(side='right')
        btn_send.config(command=self.send_chat_message)
        make_btn_interactive(btn_send, "#2563eb", "#1d4ed8", "white", "white")

    def create_metric_card(self, parent, label, val, col):
        card = ttk.Frame(parent, style='Card.TFrame', padding=12)
        card.grid(row=0, column=col, sticky='nsew', padx=5)
        
        lbl_lbl = ttk.Label(card, text=label, style='Card.TLabel')
        lbl_lbl.config(foreground='#94a3b8', font=('Segoe UI', 9, 'bold'))
        lbl_lbl.pack(anchor='w')
        lbl_val = tk.Label(card, text=val, bg='#1e293b', fg='#ffffff', font=('Segoe UI', 20, 'bold'))
        lbl_val.pack(anchor='w', pady=(5, 0))
        return lbl_val

    def toggle_bot_action(self):
        if state.BOT_RUNNING:
            stop_bot()
            self.btn_toggle.config(text="Start Bot")
            make_btn_interactive(self.btn_toggle, "#2563eb", "#1d4ed8", "white", "white")
        else:
            start_bot_thread()
            self.btn_toggle.config(text="Stop Bot")
            make_btn_interactive(self.btn_toggle, "#ef4444", "#dc2626", "white", "white")

    def toggle_pause_action(self):
        state.BOT_PAUSED = not state.BOT_PAUSED
        if state.BOT_PAUSED:
            self.btn_pause.config(text="Resume")
            make_btn_interactive(self.btn_pause, "#10b981", "#059669", "white", "white")
        else:
            self.btn_pause.config(text="Pause")
            make_btn_interactive(self.btn_pause, "#d97706", "#b45309", "white", "white")

    def update_logs_display(self):
        if not hasattr(self, 'logs_box'):
            return
        search_query = self.log_search_var.get().strip().lower()
        if search_query == "search logs...":
            search_query = ""
            
        self.logs_box.delete('1.0', 'end')
        for log in state.LOG_QUEUE:
            if not search_query or search_query in log.lower():
                self.logs_box.insert('end', log + "\n")
        self.logs_box.see('end')

    def update_dashboard_data(self):
        recalculate_metrics()
        applied = state.METRICS.get("applied", 0)
        skipped = state.METRICS.get("skipped", 0)
        total = applied + skipped + state.METRICS.get("suggested", 0)
        
        self.applied_metric.config(text=str(applied))
        self.skipped_metric.config(text=str(skipped))
        self.total_metric.config(text=str(total))
        
        success_rate = 0
        if applied + skipped > 0:
            success_rate = (applied / (applied + skipped)) * 100
        self.success_metric.config(text=f"{success_rate:.1f}%")
        
        today_eval = state.SESSION_STATS.get("evaluated", 0)
        today_match = state.SESSION_STATS.get("matches", 0)
        self.session_stats_lbl.config(text=f"Today: {today_eval} evaluated, {today_match} matches")
        
        if state.BOT_RUNNING:
            self.btn_toggle.config(text="Stop Bot")
            make_btn_interactive(self.btn_toggle, "#ef4444", "#dc2626", "white", "white")
        else:
            self.btn_toggle.config(text="Start Bot")
            make_btn_interactive(self.btn_toggle, "#2563eb", "#1d4ed8", "white", "white")
            
        self.update_logs_display()
        self.draw_vector_charts()

    def draw_vector_charts(self):
        self.chart_canvas.delete("all")
        
        applied = state.METRICS.get("applied", 0)
        skipped = state.METRICS.get("skipped", 0)
        suggested = state.METRICS.get("suggested", 0)
        total = applied + skipped + suggested
        
        cx, cy, r = 100, 80, 60
        if total == 0:
            self.chart_canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill="#334155", outline="#475569", width=2)
            self.chart_canvas.create_text(cx, cy, text="No Data", fill="#94a3b8", font=('Segoe UI', 9, 'bold'))
        else:
            angles = {
                "Applied": (applied / total) * 360,
                "Suggested": (suggested / total) * 360,
                "Skipped": (skipped / total) * 360
            }
            colors = {"Applied": "#10b981", "Suggested": "#3b82f6", "Skipped": "#ef4444"}
            
            start_angle = 0
            for label, angle in angles.items():
                if angle > 0:
                    self.chart_canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=start_angle, extent=angle, fill=colors[label], outline="#1e293b", width=1)
                    start_angle += angle
            ri = 38
            self.chart_canvas.create_oval(cx-ri, cy-ri, cx+ri, cy+ri, fill="#1e293b", outline="#1e293b")
            self.chart_canvas.create_text(cx, cy, text=f"{total}\nTotal", fill="#ffffff", font=('Segoe UI', 9, 'bold'))

        # Platforms Bar
        plats = {"Indeed": 0, "Naukri": 0, "LinkedIn": 0}
        if os.path.exists(APPLIED_DB_PATH):
            try:
                with open(APPLIED_DB_PATH, mode='r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if row and len(row) >= 5 and row[4] in ["Applied", "Manual Approval Apply"]:
                            p = row[3]
                            if p in plats: plats[p] += 1
            except Exception: pass
            
        max_val = max(list(plats.values()) + [1])
        bx, by, bw, bh = 220, 130, 45, 80
        idx = 0
        colors_plat = {"Indeed": "#3b82f6", "Naukri": "#f59e0b", "LinkedIn": "#0077b5"}
        for p, val in plats.items():
            bar_h = int((val / max_val) * bh)
            x0 = bx + idx * (bw + 20)
            y0 = by - bar_h
            x1 = x0 + bw
            y1 = by
            
            self.chart_canvas.create_rectangle(x0, y0, x1, y1, fill=colors_plat.get(p, "#cbd5e1"), outline="#1e293b", width=1)
            self.chart_canvas.create_text(x0 + bw/2, y0 - 8, text=str(val), fill="#ffffff", font=('Segoe UI', 8, 'bold'))
            self.chart_canvas.create_text(x0 + bw/2, by + 12, text=p, fill="#94a3b8", font=('Segoe UI', 8, 'bold'))
            idx += 1

    def send_chat_message(self):
        msg = self.chat_input.get().strip()
        if not msg: return
        
        self.chat_history.configure(state='normal')
        self.chat_history.insert('end', f"You: {msg}\n\n", "user")
        self.chat_history.tag_config("user", foreground="#60a5fa", font=('Segoe UI', 9, 'bold'))
        self.chat_history.configure(state='disabled')
        self.chat_history.see('end')
        self.chat_input.delete(0, 'end')
        
        def update_chat_ui(reply, command_data):
            self.chat_history.configure(state='normal')
            hist_content = self.chat_history.get('1.0', 'end')
            thinking_idx = hist_content.rfind("Qwen: Thinking...")
            if thinking_idx != -1:
                line_no = hist_content.count('\n', 0, thinking_idx) + 1
                self.chat_history.delete(f"{line_no}.0", 'end')
                
            self.chat_history.insert('end', f"Qwen: {reply}\n\n", "ai")
            self.chat_history.tag_config("ai", foreground="#f1f5f9")
            self.chat_history.configure(state='disabled')
            self.chat_history.see('end')
            
            if command_data:
                self.controller.execute_chat_command(command_data)

        def generate_response():
            self.after(0, lambda: self._show_thinking())
            
            # Using list(state.LOG_QUEUE) to be safe since it's a deque
            logs_list = list(state.LOG_QUEUE)
            logs_context = "\n".join(logs_list[-10:])
            cand_context = json.dumps(CONFIG["candidate"], indent=2)
            resume_text = extract_resume_text()
            
            history_text = ""
            if os.path.exists(APPLIED_DB_PATH):
                try:
                    with open(APPLIED_DB_PATH, mode='r', encoding='utf-8') as f:
                        lines = f.readlines()
                        if lines:
                            history_text = lines[0] + "".join(lines[-10:])
                except Exception: pass
            
            prompt = f"""
You are the Job Assistant AI agent. You have access to:
1. Candidate's PDF Resume content:
{resume_text[:3000]}

2. Stored Profile Configuration:
{cand_context}

3. Recent Applied Job History (from database):
{history_text}

4. Recent Operations Logs:
{logs_context}

User Question: {msg}

Instructions:
1. Answer the user's question accurately and politely using the resume content, applied database history, or profile configs above.
2. If they ask about their resume details or past job applications, retrieve it from the context fields.
3. If they ask to update settings (queries, skip_keywords, skills), append a [COMMAND: ...] tag:
[COMMAND: {{"type": "update_setting", "key": "queries", "value": ["role"]}}]
"""
            reply = query_local_qwen(prompt)
            
            command_data = None
            match_cmd = re.search(r'\[COMMAND:\s*(.*?)\]', reply, re.DOTALL)
            if match_cmd:
                try:
                    command_data = json.loads(match_cmd.group(1).strip())
                    reply = reply.replace(match_cmd.group(0), "").strip()
                except Exception: pass
            
            self.after(0, lambda: update_chat_ui(reply, command_data))
                
        threading.Thread(target=generate_response, daemon=True).start()

    def _show_thinking(self):
        self.chat_history.configure(state='normal')
        self.chat_history.insert('end', "Qwen: Thinking...\n", "thinking")
        self.chat_history.tag_config("thinking", foreground="#6b7280", font=('Segoe UI', 9, 'italic'))
        self.chat_history.configure(state='disabled')
        self.chat_history.see('end')
