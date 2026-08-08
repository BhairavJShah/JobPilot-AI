import os
import csv
import json
import re
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, scrolledtext
import core.state as state
from core.config_manager import CONFIG, CONFIG_PATH
from core.db_manager import log_message, recalculate_metrics, APPLIED_DB_PATH
from core.resume_parser import extract_resume_text
from automation.llm_evaluator import query_ai_model
from automation.job_scraper import fast_scrape_jobs
from automation.bot_runner import start_bot_thread, stop_bot
from ui.components import C, F, create_action_btn

class DashboardView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # ── Header Row ──
        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.pack(fill='x', pady=(0, 14))
        lbl_title = ctk.CTkLabel(title_row, text="Control Dashboard", font=F["h1"], text_color=C["text"])
        lbl_title.pack(side='left')
        
        btn_frame = ctk.CTkFrame(title_row, fg_color="transparent")
        btn_frame.pack(side='right')
        
        self.btn_pause = create_action_btn(btn_frame, "⏸  Pause", self.toggle_pause_action, "warning", "normal")
        self.btn_pause.pack(side='right', padx=(8, 0))
        
        self.btn_toggle = create_action_btn(btn_frame, "▶  Start Bot", self.toggle_bot_action, "primary", "normal")
        self.btn_toggle.pack(side='right')
        
        # ── Metric Cards Row ──
        metrics_frame = ctk.CTkFrame(self, fg_color="transparent")
        metrics_frame.pack(fill='x', pady=(0, 6))
        metrics_frame.columnconfigure((0, 1, 2, 3), weight=1, uniform="equal")
        
        self.applied_metric = self.create_metric_card(metrics_frame, "Applications Sent", "0", 0, C["green"])
        self.skipped_metric = self.create_metric_card(metrics_frame, "Jobs Skipped", "0", 1, C["red"])
        self.total_metric = self.create_metric_card(metrics_frame, "Total Evaluated", "0", 2, C["blue"])
        self.success_metric = self.create_metric_card(metrics_frame, "Success Rate", "0%", 3, C["purple"])
        
        self.session_stats_lbl = ctk.CTkLabel(self, text="Today: 0 evaluated, 0 matches",
                                              text_color=C["dim"], font=F["xs_b"], anchor="w")
        self.session_stats_lbl.pack(anchor='w', pady=(0, 12))
        
        # ── Workspace 2x2 Grid ──
        workspace_frame = ctk.CTkFrame(self, fg_color="transparent")
        workspace_frame.pack(fill='both', expand=True)
        workspace_frame.columnconfigure(0, weight=1)
        workspace_frame.columnconfigure(1, weight=1)
        workspace_frame.rowconfigure(0, weight=1)
        workspace_frame.rowconfigure(1, weight=1)
        
        # ── Logs Card ──
        logs_card = ctk.CTkFrame(workspace_frame, fg_color=C["card"], corner_radius=12)
        logs_card.grid(row=0, column=0, sticky='nsew', padx=(0, 8), pady=(0, 8))
        
        log_top = ctk.CTkFrame(logs_card, fg_color="transparent")
        log_top.pack(fill='x', padx=14, pady=(12, 6))
        lbl_log_title = ctk.CTkLabel(log_top, text="Operation Logs", font=F["h3"], text_color=C["text"])
        lbl_log_title.pack(side='left')
        
        self.log_search_var = tk.StringVar()
        log_search = ctk.CTkEntry(log_top, textvariable=self.log_search_var,
                                 placeholder_text="Search logs...",
                                 fg_color=C["input"], border_color=C["border"],
                                 text_color=C["text"], font=F["xs"], width=180, height=30, corner_radius=8)
        log_search.pack(side='right')
        
        logs_inner = ctk.CTkFrame(logs_card, fg_color=C["input"], corner_radius=8)
        logs_inner.pack(fill='both', expand=True, padx=14, pady=(0, 14))
        
        self.logs_box = scrolledtext.ScrolledText(logs_inner,
            bg=C["input"], fg=C["cyan"],
            insertbackground="white",
            font=F["mono"], bd=0, highlightthickness=0)
        self.logs_box.pack(fill='both', expand=True, padx=6, pady=6)
        
        self.log_search_var.trace_add("write", lambda *args: self.update_logs_display())
        
        # ── Analytics Card ──
        charts_card = ctk.CTkFrame(workspace_frame, fg_color=C["card"], corner_radius=12)
        charts_card.grid(row=1, column=0, sticky='nsew', padx=(0, 8), pady=(8, 0))
        
        lbl_charts_title = ctk.CTkLabel(charts_card, text="Pipeline Analytics", font=F["h3"], text_color=C["text"])
        lbl_charts_title.pack(anchor='w', padx=14, pady=(12, 6))
        
        self.chart_canvas = tk.Canvas(charts_card, bg=C["card"], highlightthickness=0, bd=0)
        self.chart_canvas.pack(fill='both', expand=True, padx=14, pady=(0, 14))
        
        # ── Chat Card ──
        chat_card = ctk.CTkFrame(workspace_frame, fg_color=C["card"], corner_radius=12)
        chat_card.grid(row=0, column=1, rowspan=2, sticky='nsew', padx=(8, 0))
        
        chat_header = ctk.CTkFrame(chat_card, fg_color="transparent")
        chat_header.pack(fill='x', padx=14, pady=(12, 8))
        lbl_chat_title = ctk.CTkLabel(chat_header, text="AI Assistant Chat", font=F["h3"], text_color=C["text"])
        lbl_chat_title.pack(side='left')
        
        chat_badge = ctk.CTkLabel(chat_header, text="RAG", fg_color=C["accent"], text_color="white",
                                 font=F["xs_b"], corner_radius=6, width=42, height=20)
        chat_badge.pack(side='left', padx=(8, 0))
        
        chat_inner = ctk.CTkFrame(chat_card, fg_color=C["input"], corner_radius=8)
        chat_inner.pack(fill='both', expand=True, padx=14, pady=(0, 10))
        
        self.chat_history = scrolledtext.ScrolledText(chat_inner,
            bg=C["input"], fg=C["text"],
            insertbackground="white", font=F["sm"],
            bd=0, state='disabled', wrap='word', highlightthickness=0)
        self.chat_history.pack(fill='both', expand=True, padx=6, pady=6)
        
        input_row = ctk.CTkFrame(chat_card, fg_color="transparent")
        input_row.pack(fill='x', padx=14, pady=(0, 14))
        
        self.chat_input = ctk.CTkEntry(input_row,
            placeholder_text="Ask about resume, jobs, or settings...",
            fg_color=C["input"], border_color=C["border"], text_color=C["text"],
            font=F["sm"], corner_radius=8, height=38)
        self.chat_input.pack(side='left', fill='x', expand=True, padx=(0, 8))
        self.chat_input.bind("<Return>", lambda e: self.send_chat_message())
        
        btn_send = create_action_btn(input_row, "Send", self.send_chat_message, "primary", "small")
        btn_send.pack(side='right')

    def create_metric_card(self, parent, label, val, col, accent_color):
        card = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=12)
        card.grid(row=0, column=col, sticky='nsew', padx=5, pady=2)
        
        accent_bar = ctk.CTkFrame(card, fg_color=accent_color, height=3, corner_radius=0)
        accent_bar.pack(fill='x', pady=(0, 10))
        
        lbl_lbl = ctk.CTkLabel(card, text=label, font=F["xs_b"], text_color=C["muted"], anchor="w")
        lbl_lbl.pack(anchor='w', padx=14)
        
        lbl_val = ctk.CTkLabel(card, text=val, font=F["metric"], text_color=accent_color, anchor="w")
        lbl_val.pack(anchor='w', padx=14, pady=(2, 10))
        return lbl_val

    def toggle_bot_action(self):
        if state.BOT_RUNNING:
            stop_bot()
            self.btn_toggle.configure(text="▶  Start Bot", fg_color=C["accent"], hover_color=C["accent_d"])
        else:
            start_bot_thread()
            self.btn_toggle.configure(text="■  Stop Bot", fg_color=C["red"], hover_color=C["red_h"])

    def toggle_pause_action(self):
        state.BOT_PAUSED = not state.BOT_PAUSED
        if state.BOT_PAUSED:
            self.btn_pause.configure(text="▶  Resume", fg_color=C["green"], hover_color=C["green_h"])
        else:
            self.btn_pause.configure(text="⏸  Pause", fg_color=C["amber"], hover_color=C["amber_h"])

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
        
        self.applied_metric.configure(text=str(applied))
        self.skipped_metric.configure(text=str(skipped))
        self.total_metric.configure(text=str(total))
        
        success_rate = 0
        if applied + skipped > 0:
            success_rate = (applied / (applied + skipped)) * 100
        self.success_metric.configure(text=f"{success_rate:.1f}%")
        
        today_eval = state.SESSION_STATS.get("evaluated_today", 0)
        today_match = state.SESSION_STATS.get("matches_today", 0)
        self.session_stats_lbl.configure(text=f"Today: {today_eval} evaluated, {today_match} matches")
        
        if state.BOT_RUNNING:
            self.btn_toggle.configure(text="■  Stop Bot", fg_color=C["red"], hover_color=C["red_h"])
        else:
            self.btn_toggle.configure(text="▶  Start Bot", fg_color=C["accent"], hover_color=C["accent_d"])
            
        self.update_logs_display()
        self.draw_vector_charts()

    def draw_vector_charts(self):
        self.chart_canvas.delete("all")
        
        applied = state.METRICS.get("applied", 0)
        skipped = state.METRICS.get("skipped", 0)
        suggested = state.METRICS.get("suggested", 0)
        total = applied + skipped + suggested
        
        cx, cy, r = 100, 75, 55
        if total == 0:
            self.chart_canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill=C["card_hover"], outline=C["border"], width=1)
            self.chart_canvas.create_text(cx, cy, text="No Data", fill=C["dim"], font=F["xs_b"])
        else:
            angles = {
                "Applied": (applied / total) * 360,
                "Suggested": (suggested / total) * 360,
                "Skipped": (skipped / total) * 360
            }
            colors = {"Applied": C["green"], "Suggested": C["blue"], "Skipped": C["red"]}
            
            start_angle = 0
            for label, angle in angles.items():
                if angle > 0:
                    self.chart_canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=start_angle, extent=angle, fill=colors[label], outline=C["card"], width=2)
                    start_angle += angle
            ri = 34
            self.chart_canvas.create_oval(cx-ri, cy-ri, cx+ri, cy+ri, fill=C["card"], outline=C["card"])
            self.chart_canvas.create_text(cx, cy, text=f"{total}\nTotal", fill=C["text"], font=F["xs_b"])

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
        bx, by, bw, bh = 220, 120, 42, 70
        idx = 0
        colors_plat = {"Indeed": C["blue"], "Naukri": C["amber"], "LinkedIn": "#0077b5"}
        for p, val in plats.items():
            bar_h = int((val / max_val) * bh)
            x0 = bx + idx * (bw + 18)
            y0 = by - bar_h
            x1 = x0 + bw
            y1 = by
            
            self.chart_canvas.create_rectangle(x0, y0, x1, y1, fill=colors_plat.get(p, C["dim"]), outline=C["card"], width=1)
            self.chart_canvas.create_text(x0 + bw/2, y0 - 8, text=str(val), fill=C["text"], font=F["xs_b"])
            self.chart_canvas.create_text(x0 + bw/2, by + 12, text=p, fill=C["muted"], font=F["xs_b"])
            idx += 1

    def send_chat_message(self):
        msg = self.chat_input.get().strip()
        if not msg: return
        
        self.chat_history.configure(state='normal')
        self.chat_history.insert('end', f"You: {msg}\n\n", "user")
        self.chat_history.tag_config("user", foreground=C["accent_h"], font=('Segoe UI', 9, 'bold'))
        self.chat_history.configure(state='disabled')
        self.chat_history.see('end')
        self.chat_input.delete(0, 'end')
        
        def update_chat_ui(reply, command_data):
            self.chat_history.configure(state='normal')
            hist_content = self.chat_history.get('1.0', 'end')
            thinking_idx = hist_content.rfind("AI: Thinking...")
            if thinking_idx != -1:
                line_no = hist_content.count('\n', 0, thinking_idx) + 1
                self.chat_history.delete(f"{line_no}.0", 'end')
                
            self.chat_history.insert('end', f"AI: {reply}\n\n", "ai")
            self.chat_history.tag_config("ai", foreground=C["text"])
            self.chat_history.configure(state='disabled')
            self.chat_history.see('end')
            
            if command_data:
                self.controller.execute_chat_command(command_data)

        def generate_response():
            self.after(0, lambda: self._show_thinking())
            
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
            
            # Web Search Integration: Check if user question requests live internet/job market data
            web_context = ""
            msg_lower = msg.lower()
            if any(k in msg_lower for k in ["search", "find", "job", "opening", "salary", "market", "latest", "company", "recruit"]):
                try:
                    q_term = CONFIG["settings"]["queries"][0] if CONFIG["settings"]["queries"] else "Software Engineer"
                    web_results = fast_scrape_jobs(query=q_term, limit=5)
                    if web_results:
                        formatted_jobs = [f"- {j['title']} at {j['company']} ({j['platform']}): {j['url']}" for j in web_results[:5]]
                        web_context = "5. Live Internet Job Market Data (Real-time Web Search):\n" + "\n".join(formatted_jobs) + "\n"
                except Exception as e:
                    web_context = f"5. Live Internet Search Notice: {e}\n"

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

{web_context}
User Question: {msg}

Instructions:
1. Answer the user's question accurately and politely using the resume content, applied database history, profile configs, or live internet job market data.
2. If they ask about their resume details or past job applications, retrieve it from the context fields.
3. If they ask to search or add a new job role (e.g. "look for Python Developer jobs" or "add React Native"), append a command tag:
[COMMAND: {{"type": "append_query", "value": "Python Developer"}}]
4. If they state a salary preference or expected CTC (e.g. "my expected CTC is 12 LPA"), append a command tag:
[COMMAND: {{"type": "update_qa_vault", "key": "expected_ctc", "value": "12"}}]
"""
            reply = query_ai_model(prompt)
            
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
        self.chat_history.insert('end', "AI: Thinking...\n", "thinking")
        self.chat_history.tag_config("thinking", foreground=C["dim"], font=('Segoe UI', 9, 'italic'))
        self.chat_history.configure(state='disabled')
        self.chat_history.see('end')
