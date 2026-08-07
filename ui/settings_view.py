import json
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from core.config_manager import CONFIG, CONFIG_PATH, LOCATION_DATA, get_installed_ollama_models
from core.db_manager import log_message, recalculate_metrics
from ui.components import C, F, TagChipContainer, add_form_input, create_action_btn, add_section_divider

class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # ── Header ──
        lbl_title = ctk.CTkLabel(self, text="AI & Search Settings", font=F["h1"], text_color=C["text"], anchor="w")
        lbl_title.pack(anchor='w', pady=(0, 14))
        
        # ── Scrollable Card ──
        card = ctk.CTkScrollableFrame(self, fg_color=C["card"], corner_radius=12)
        card.pack(fill='both', expand=True)
        
        # ═══════════════════════════════════════════════════
        # AI Provider & Model Selector Block
        # ═══════════════════════════════════════════════════
        add_section_divider(card, "AI Engine Provider")
        
        f_ai = ctk.CTkFrame(card, fg_color="transparent")
        f_ai.pack(fill='x', padx=16, pady=6)
        
        provider_val = CONFIG["settings"].get("ai_provider", "local")
        if provider_val == "gemini": provider_val = "cloud"
        
        self.seg_provider = ctk.CTkSegmentedButton(
            f_ai,
            values=["Local Ollama (Offline)", "Cloud AI / REST API"],
            command=self.on_provider_changed,
            selected_color=C["accent"],
            selected_hover_color=C["accent_d"],
            unselected_color=C["input"],
            unselected_hover_color=C["card_hover"],
            text_color=C["text"],
            font=F["sm_b"],
            corner_radius=10,
            height=38
        )
        self.seg_provider.pack(fill='x', pady=(0, 10))
        self.seg_provider.set("Cloud AI / REST API" if provider_val == "cloud" else "Local Ollama (Offline)")

        # Frame for Local Ollama Settings
        self.f_ollama_sub = ctk.CTkFrame(f_ai, fg_color="transparent")
        self.f_ollama_sub.pack(fill='x', pady=5)
        
        lbl_ollama = ctk.CTkLabel(self.f_ollama_sub, text="Local Ollama Model", font=F["sm_b"], text_color=C["muted"], anchor="w")
        lbl_ollama.pack(anchor='w', pady=(0, 4))
        
        model_row = ctk.CTkFrame(self.f_ollama_sub, fg_color="transparent")
        model_row.pack(fill='x')
        
        self.sel_model = ctk.CTkOptionMenu(model_row, fg_color=C["input"], button_color=C["card_hover"],
                                          button_hover_color=C["border"], text_color=C["text"],
                                          dropdown_fg_color=C["card"], font=F["sm"], corner_radius=8, height=36)
        self.sel_model.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        btn_refresh_models = create_action_btn(model_row, "Refresh Models", self.refresh_models, "outline", "small")
        btn_refresh_models.pack(side='left')

        # Frame for Universal Cloud AI Settings
        self.f_cloud_sub = ctk.CTkFrame(f_ai, fg_color="transparent")
        self.f_cloud_sub.pack(fill='x', pady=5)
        
        # Preset Selector
        f_preset = ctk.CTkFrame(self.f_cloud_sub, fg_color="transparent")
        f_preset.pack(fill='x', pady=(0, 8))
        
        lbl_preset = ctk.CTkLabel(f_preset, text="Cloud Provider Preset", font=F["sm_b"], text_color=C["muted"], anchor="w")
        lbl_preset.pack(anchor='w', pady=(0, 4))
        
        self.sel_preset = ctk.CTkOptionMenu(f_preset, values=["OpenAI / ChatGPT", "DeepSeek", "Groq", "Google AI", "Custom Endpoint"],
                                           command=self.on_cloud_preset_selected,
                                           fg_color=C["input"], button_color=C["card_hover"],
                                           button_hover_color=C["border"], text_color=C["text"],
                                           dropdown_fg_color=C["card"], font=F["sm"], corner_radius=8, height=36)
        self.sel_preset.pack(fill='x')
        self.sel_preset.set(CONFIG["settings"].get("cloud_ai_preset", "OpenAI / ChatGPT"))
        
        # Endpoint & Model Row
        cloud_grid = ctk.CTkFrame(self.f_cloud_sub, fg_color="transparent")
        cloud_grid.pack(fill='x', pady=4)
        cloud_grid.columnconfigure((0, 1), weight=1, uniform="equal")
        
        f_url = ctk.CTkFrame(cloud_grid, fg_color="transparent")
        f_url.grid(row=0, column=0, sticky='ew', padx=(0, 6))
        ctk.CTkLabel(f_url, text="Base API Endpoint URL", font=F["sm_b"], text_color=C["muted"], anchor="w").pack(anchor='w', pady=(0, 4))
        
        self.entry_cloud_url = ctk.CTkEntry(f_url, fg_color=C["input"], border_color=C["border"],
                                           text_color=C["text"], font=F["xs"], corner_radius=8, height=36)
        self.entry_cloud_url.pack(fill='x')
        self.entry_cloud_url.insert(0, CONFIG["settings"].get("cloud_ai_base_url", "https://api.openai.com/v1"))
        
        f_cmod = ctk.CTkFrame(cloud_grid, fg_color="transparent")
        f_cmod.grid(row=0, column=1, sticky='ew', padx=(6, 0))
        ctk.CTkLabel(f_cmod, text="Model Name / ID", font=F["sm_b"], text_color=C["muted"], anchor="w").pack(anchor='w', pady=(0, 4))
        
        self.entry_cloud_model = ctk.CTkEntry(f_cmod, fg_color=C["input"], border_color=C["border"],
                                             text_color=C["text"], font=F["xs"], corner_radius=8, height=36)
        self.entry_cloud_model.pack(fill='x')
        self.entry_cloud_model.insert(0, CONFIG["settings"].get("cloud_ai_model", "gpt-4o-mini"))
        
        # Authentication Segmented Control
        f_auth_type = ctk.CTkFrame(self.f_cloud_sub, fg_color="transparent")
        f_auth_type.pack(fill='x', pady=(10, 4))
        ctk.CTkLabel(f_auth_type, text="Authentication Method", font=F["sm_b"], text_color=C["muted"], anchor="w").pack(anchor='w', pady=(0, 4))
        
        current_auth = CONFIG["settings"].get("cloud_ai_auth_type", "api_key")
        self.seg_auth = ctk.CTkSegmentedButton(
            f_auth_type,
            values=["API Key / Bearer Token", "Username & Password (Basic Auth)"],
            command=self.on_auth_type_changed,
            selected_color=C["accent"],
            selected_hover_color=C["accent_d"],
            unselected_color=C["input"],
            unselected_hover_color=C["card_hover"],
            text_color=C["text"],
            font=F["xs_b"],
            corner_radius=8,
            height=34
        )
        self.seg_auth.pack(fill='x')
        self.seg_auth.set("Username & Password (Basic Auth)" if current_auth == "user_pass" else "API Key / Bearer Token")

        # API Key Frame
        self.f_key_sub = ctk.CTkFrame(self.f_cloud_sub, fg_color="transparent")
        self.f_key_sub.pack(fill='x', pady=4)
        ctk.CTkLabel(self.f_key_sub, text="API Key / Token", font=F["sm_b"], text_color=C["muted"], anchor="w").pack(anchor='w', pady=(0, 4))
        self.entry_cloud_key = ctk.CTkEntry(self.f_key_sub, fg_color=C["input"], border_color=C["border"],
                                           text_color=C["text"], font=F["sm"], corner_radius=8, height=36, show="*")
        self.entry_cloud_key.pack(fill='x')
        self.entry_cloud_key.insert(0, CONFIG["settings"].get("cloud_ai_api_key", CONFIG["settings"].get("gemini_api_key", "")))

        # Username & Password Frame
        self.f_userpass_sub = ctk.CTkFrame(self.f_cloud_sub, fg_color="transparent")
        self.f_userpass_sub.pack(fill='x', pady=4)
        up_grid = ctk.CTkFrame(self.f_userpass_sub, fg_color="transparent")
        up_grid.pack(fill='x')
        up_grid.columnconfigure((0, 1), weight=1, uniform="equal")
        
        f_u = ctk.CTkFrame(up_grid, fg_color="transparent")
        f_u.grid(row=0, column=0, sticky='ew', padx=(0, 6))
        ctk.CTkLabel(f_u, text="API Username", font=F["sm_b"], text_color=C["muted"], anchor="w").pack(anchor='w', pady=(0, 4))
        self.entry_cloud_user = ctk.CTkEntry(f_u, fg_color=C["input"], border_color=C["border"],
                                            text_color=C["text"], font=F["xs"], corner_radius=8, height=36)
        self.entry_cloud_user.pack(fill='x')
        self.entry_cloud_user.insert(0, CONFIG["settings"].get("cloud_ai_username", ""))
        
        f_p = ctk.CTkFrame(up_grid, fg_color="transparent")
        f_p.grid(row=0, column=1, sticky='ew', padx=(6, 0))
        ctk.CTkLabel(f_p, text="API Password", font=F["sm_b"], text_color=C["muted"], anchor="w").pack(anchor='w', pady=(0, 4))
        self.entry_cloud_pass = ctk.CTkEntry(f_p, fg_color=C["input"], border_color=C["border"],
                                            text_color=C["text"], font=F["xs"], corner_radius=8, height=36, show="*")
        self.entry_cloud_pass.pack(fill='x')
        self.entry_cloud_pass.insert(0, CONFIG["settings"].get("cloud_ai_password", ""))
        
        btn_test_cloud = create_action_btn(self.f_cloud_sub, "⚡ Test Connection", self.test_cloud_connection, "success", "small")
        btn_test_cloud.pack(anchor='w', pady=(10, 0))

        self.on_provider_changed(self.seg_provider.get())
        self.on_auth_type_changed(self.seg_auth.get())
        self.refresh_models()

        # ═══════════════════════════════════════════════════
        # Job Search Configuration
        # ═══════════════════════════════════════════════════
        add_section_divider(card, "Job Search Queries")

        self.settings_queries = TagChipContainer(card, CONFIG["settings"]["queries"], "Target Job Queries (Press Enter or Comma to add)", lambda val: self.update_config_list("queries", val))
        self.settings_queries.pack(fill='x', pady=5)
        
        self.settings_skip = TagChipContainer(card, CONFIG["settings"]["skip_keywords"], "Skip Keywords (Press Enter or Comma to add)", lambda val: self.update_config_list("skip_keywords", val))
        self.settings_skip.pack(fill='x', pady=5)

        # ═══════════════════════════════════════════════════
        # Geographic Settings
        # ═══════════════════════════════════════════════════
        add_section_divider(card, "Geographic Location")

        f_scope = ctk.CTkFrame(card, fg_color="transparent")
        f_scope.pack(fill='x', padx=16, pady=6)
        ctk.CTkLabel(f_scope, text="Location Scope", font=F["sm_b"], text_color=C["muted"], anchor="w").pack(anchor='w', pady=(0, 4))
        
        self.sel_scope = ctk.CTkOptionMenu(f_scope, values=["Entire Country", "Custom Cities & States"],
                                          command=self.on_scope_changed,
                                          fg_color=C["input"], button_color=C["card_hover"],
                                          button_hover_color=C["border"], text_color=C["text"],
                                          dropdown_fg_color=C["card"], font=F["sm"], corner_radius=8, height=36)
        self.sel_scope.pack(fill='x')
        self.sel_scope.set(CONFIG["settings"].get("location_scope", "Entire Country"))

        # Hierarchical Location Selection
        self.f_hierarchical = ctk.CTkFrame(card, fg_color="transparent")
        self.f_hierarchical.pack(fill='x', padx=16, pady=10)
        
        ctk.CTkLabel(self.f_hierarchical, text="Location Hierarchy Selector", font=F["h3"], text_color=C["text"]).pack(anchor='w', pady=(0, 6))
        
        drop_grid = ctk.CTkFrame(self.f_hierarchical, fg_color="transparent")
        drop_grid.pack(fill='x')
        drop_grid.columnconfigure((0, 1, 2), weight=1, uniform="equal")
        
        fc = ctk.CTkFrame(drop_grid, fg_color="transparent")
        fc.grid(row=0, column=0, padx=4, sticky='ew')
        ctk.CTkLabel(fc, text="Country", font=F["sm_b"], text_color=C["muted"], anchor="w").pack(anchor='w', pady=(0, 2))
        self.sel_country = ctk.CTkOptionMenu(fc, values=list(LOCATION_DATA.keys()), command=self.on_country_selected,
                                             fg_color=C["input"], button_color=C["card_hover"], text_color=C["text"], dropdown_fg_color=C["card"], font=F["xs"], corner_radius=8, height=34)
        self.sel_country.pack(fill='x')
        
        fs = ctk.CTkFrame(drop_grid, fg_color="transparent")
        fs.grid(row=0, column=1, padx=4, sticky='ew')
        ctk.CTkLabel(fs, text="State", font=F["sm_b"], text_color=C["muted"], anchor="w").pack(anchor='w', pady=(0, 2))
        self.sel_state = ctk.CTkOptionMenu(fs, values=["Select State"], command=self.on_state_selected,
                                           fg_color=C["input"], button_color=C["card_hover"], text_color=C["text"], dropdown_fg_color=C["card"], font=F["xs"], corner_radius=8, height=34)
        self.sel_state.pack(fill='x')
        
        fcy = ctk.CTkFrame(drop_grid, fg_color="transparent")
        fcy.grid(row=0, column=2, padx=4, sticky='ew')
        ctk.CTkLabel(fcy, text="City", font=F["sm_b"], text_color=C["muted"], anchor="w").pack(anchor='w', pady=(0, 2))
        self.sel_city = ctk.CTkOptionMenu(fcy, values=["Select City"],
                                          fg_color=C["input"], button_color=C["card_hover"], text_color=C["text"], dropdown_fg_color=C["card"], font=F["xs"], corner_radius=8, height=34)
        self.sel_city.pack(fill='x')
        
        self.sel_country.set("India")
        self.on_country_selected("India")
        
        btn_add_loc = create_action_btn(self.f_hierarchical, "Add Location", self.add_hierarchical_location, "success", "small")
        btn_add_loc.pack(anchor='w', pady=(10, 0))

        self.settings_locations = TagChipContainer(card, CONFIG["settings"].get("preferred_locations", []), "Selected Search Locations", lambda val: self.update_config_list("preferred_locations", val))
        self.settings_locations.pack(fill='x', pady=5)
        
        self.on_scope_changed(self.sel_scope.get())

        # ═══════════════════════════════════════════════════
        # Account Safety & Anti-Bot Rate Limiter
        # ═══════════════════════════════════════════════════
        add_section_divider(card, "Account Safety & Anti-Bot Protection")
        
        safe_frame = ctk.CTkFrame(card, fg_color="transparent")
        safe_frame.pack(fill='x', padx=16, pady=5)
        
        self.sw_safe_mode = ctk.CTkSwitch(safe_frame, text="  Enable Account Safety Mode (Daily Cap & Human Emulation Delays)",
                                         progress_color=C["accent"], button_color=C["text"],
                                         button_hover_color=C["accent_h"], text_color=C["text"], font=F["sm_b"])
        self.sw_safe_mode.pack(anchor='w', pady=4)
        if CONFIG["settings"].get("safe_mode", True):
            self.sw_safe_mode.select()
        else:
            self.sw_safe_mode.deselect()

        self.settings_daily_cap = add_form_input(card, "Daily Application Safety Cap (Max per day)")
        self.settings_min_delay = add_form_input(card, "Minimum Delay Between Applications (Seconds)")
        self.settings_max_delay = add_form_input(card, "Maximum Delay Between Applications (Seconds)")
        
        self.settings_daily_cap.insert(0, str(CONFIG["settings"].get("daily_apply_cap", 25)))
        self.settings_min_delay.insert(0, str(CONFIG["settings"].get("min_delay_seconds", 15)))
        self.settings_max_delay.insert(0, str(CONFIG["settings"].get("max_delay_seconds", 45)))

        # ═══════════════════════════════════════════════════
        # Search Thresholds & Filters
        # ═══════════════════════════════════════════════════
        add_section_divider(card, "Search Thresholds")

        self.settings_min_score = add_form_input(card, "Minimum Match Score (%)")
        self.settings_max_jobs = add_form_input(card, "Max Jobs to Check Per Query")
        
        self.settings_min_score.insert(0, str(CONFIG["settings"]["min_score"]))
        self.settings_max_jobs.insert(0, str(CONFIG["settings"].get("max_jobs_per_query", 10)))
        
        # Filters
        add_section_divider(card, "Job Search Filters")
        
        drop_frame = ctk.CTkFrame(card, fg_color="transparent")
        drop_frame.pack(fill='x', padx=16, pady=5)
        drop_frame.columnconfigure((0, 1, 2), weight=1, uniform="equal")
        
        f_exp = ctk.CTkFrame(drop_frame, fg_color="transparent")
        f_exp.grid(row=0, column=0, padx=5, sticky='ew')
        ctk.CTkLabel(f_exp, text="Experience Level", font=F["sm_b"], text_color=C["muted"], anchor="w").pack(anchor='w', pady=(0, 4))
        self.sel_exp = ctk.CTkOptionMenu(f_exp, values=["All", "Fresher", "Mid", "Senior"],
                                        fg_color=C["input"], button_color=C["card_hover"], text_color=C["text"], dropdown_fg_color=C["card"], font=F["xs"], corner_radius=8, height=34)
        self.sel_exp.pack(fill='x')
        self.sel_exp.set(CONFIG["settings"].get("experience_level", "All"))
        
        f_jt = ctk.CTkFrame(drop_frame, fg_color="transparent")
        f_jt.grid(row=0, column=1, padx=5, sticky='ew')
        ctk.CTkLabel(f_jt, text="Job Type", font=F["sm_b"], text_color=C["muted"], anchor="w").pack(anchor='w', pady=(0, 4))
        self.sel_jt = ctk.CTkOptionMenu(f_jt, values=["All", "Full-time", "Internship", "Contract"],
                                       fg_color=C["input"], button_color=C["card_hover"], text_color=C["text"], dropdown_fg_color=C["card"], font=F["xs"], corner_radius=8, height=34)
        self.sel_jt.pack(fill='x')
        self.sel_jt.set(CONFIG["settings"].get("job_type", "All"))
        
        f_loc = ctk.CTkFrame(drop_frame, fg_color="transparent")
        f_loc.grid(row=0, column=2, padx=5, sticky='ew')
        ctk.CTkLabel(f_loc, text="Location Mode", font=F["sm_b"], text_color=C["muted"], anchor="w").pack(anchor='w', pady=(0, 4))
        self.sel_loc = ctk.CTkOptionMenu(f_loc, values=["All", "Remote", "On-site", "Hybrid"],
                                        fg_color=C["input"], button_color=C["card_hover"], text_color=C["text"], dropdown_fg_color=C["card"], font=F["xs"], corner_radius=8, height=34)
        self.sel_loc.pack(fill='x')
        self.sel_loc.set(CONFIG["settings"].get("location_type", "All"))
        
        # ═══════════════════════════════════════════════════
        # Target Platforms (with Switches!)
        # ═══════════════════════════════════════════════════
        add_section_divider(card, "Target Platforms")
        
        plat_frame = ctk.CTkFrame(card, fg_color="transparent")
        plat_frame.pack(fill='x', padx=16, pady=5)
        
        self.plat_switches = {}
        for plat in ["Indeed", "Naukri", "LinkedIn"]:
            is_on = plat in CONFIG["settings"].get("target_platforms", [])
            sw = ctk.CTkSwitch(plat_frame, text=f"  {plat}",
                               progress_color=C["accent"], button_color=C["text"],
                               button_hover_color=C["accent_h"], text_color=C["text"],
                               font=F["sm"])
            sw.pack(anchor='w', pady=4)
            if is_on: sw.select()
            else: sw.deselect()
            self.plat_switches[plat] = sw
            
        ctk.CTkLabel(card, text="Coming Soon: Hirist, Foundit, Wellfound", font=F["xs"],
                     text_color=C["dim"], anchor="w").pack(anchor='w', padx=16, pady=(8, 0))
        
        # ═══════════════════════════════════════════════════
        # Save Button
        # ═══════════════════════════════════════════════════
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(anchor='w', padx=16, pady=(24, 16))
        btn_save = create_action_btn(btn_frame, "Save All Settings", self.save_settings_action, "primary", "large")
        btn_save.pack(side='left')

    # ── Handler Methods ──
    def on_provider_changed(self, value):
        if "Cloud" in value:
            self.f_ollama_sub.pack_forget()
            self.f_cloud_sub.pack(fill='x', pady=5)
        else:
            self.f_cloud_sub.pack_forget()
            self.f_ollama_sub.pack(fill='x', pady=5)

    def on_auth_type_changed(self, value):
        if "Username" in value:
            self.f_key_sub.pack_forget()
            self.f_userpass_sub.pack(fill='x', pady=4)
        else:
            self.f_userpass_sub.pack_forget()
            self.f_key_sub.pack(fill='x', pady=4)

    def on_cloud_preset_selected(self, preset):
        if "OpenAI" in preset:
            self.entry_cloud_url.delete(0, 'end'); self.entry_cloud_url.insert(0, "https://api.openai.com/v1")
            self.entry_cloud_model.delete(0, 'end'); self.entry_cloud_model.insert(0, "gpt-4o-mini")
        elif "DeepSeek" in preset:
            self.entry_cloud_url.delete(0, 'end'); self.entry_cloud_url.insert(0, "https://api.deepseek.com/v1")
            self.entry_cloud_model.delete(0, 'end'); self.entry_cloud_model.insert(0, "deepseek-chat")
        elif "Groq" in preset:
            self.entry_cloud_url.delete(0, 'end'); self.entry_cloud_url.insert(0, "https://api.groq.com/openai/v1")
            self.entry_cloud_model.delete(0, 'end'); self.entry_cloud_model.insert(0, "llama-3.3-70b-versatile")
        elif "Google" in preset:
            self.entry_cloud_url.delete(0, 'end'); self.entry_cloud_url.insert(0, "https://generativelanguage.googleapis.com/v1beta")
            self.entry_cloud_model.delete(0, 'end'); self.entry_cloud_model.insert(0, "gemini-2.5-flash")

    def test_cloud_connection(self):
        url = self.entry_cloud_url.get().strip()
        model = self.entry_cloud_model.get().strip()
        atype = "user_pass" if "Username" in self.seg_auth.get() else "api_key"
        key = self.entry_cloud_key.get().strip()
        uname = self.entry_cloud_user.get().strip()
        passwd = self.entry_cloud_pass.get().strip()
        
        if atype == "user_pass" and (not uname or not passwd):
            messagebox.showerror("Error", "Please enter both API Username and Password.")
            return
        elif atype == "api_key" and not key:
            messagebox.showerror("Error", "Please enter an API Key / Token.")
            return
            
        import urllib.request
        import base64
        headers = {'Content-Type': 'application/json'}
        if atype == "user_pass" or (uname and passwd and not key):
            up = f"{uname}:{passwd}".encode('utf-8')
            headers['Authorization'] = f"Basic {base64.b64encode(up).decode('utf-8')}"
        elif key:
            if "generativelanguage.googleapis.com" in url:
                headers['x-goog-api-key'] = key
            else:
                headers['Authorization'] = f"Bearer {key}"
                
        endpoint = f"{url.rstrip('/')}/models/{model}:generateContent" if "generativelanguage.googleapis.com" in url else (f"{url.rstrip('/')}/chat/completions" if not url.endswith("/chat/completions") else url)
        payload = {"contents": [{"parts": [{"text": "Hello"}]}]} if "generativelanguage.googleapis.com" in url else {"model": model, "messages": [{"role": "user", "content": "Hello"}]}
        
        try:
            req = urllib.request.Request(endpoint, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                messagebox.showinfo("Success", f"Cloud AI ({model}) connected successfully!")
        except Exception as e:
            messagebox.showerror("Connection Error", f"Cloud AI test failed: {e}")

    def refresh_models(self):
        models = get_installed_ollama_models()
        if models:
            self.sel_model.configure(values=models)
            current_model = CONFIG["settings"].get("ollama_model", "qwen2.5:latest")
            if current_model in models:
                self.sel_model.set(current_model)
            else:
                self.sel_model.set(models[0])
        else:
            self.sel_model.configure(values=["qwen2.5:latest"])
            self.sel_model.set("qwen2.5:latest")

    def on_country_selected(self, country):
        states = list(LOCATION_DATA.get(country, {}).keys())
        if states:
            self.sel_state.configure(values=states)
            self.sel_state.set(states[0])
            self.on_state_selected(states[0])
            
    def on_state_selected(self, state):
        country = self.sel_country.get()
        cities = LOCATION_DATA.get(country, {}).get(state, ["All Cities"])
        if cities:
            self.sel_city.configure(values=cities)
            self.sel_city.set(cities[0])

    def add_hierarchical_location(self):
        country = self.sel_country.get()
        state = self.sel_state.get()
        city = self.sel_city.get()
        loc_str = f"{city}, {state}, {country}"
        
        current_items = self.settings_locations.items
        if loc_str not in current_items:
            current_items.append(loc_str)
            self.settings_locations.update_items(current_items)
            self.update_config_list("preferred_locations", current_items)
            self.controller.refresh_nav_buttons()

    def on_scope_changed(self, scope):
        if scope == "Entire Country":
            self.f_hierarchical.pack_forget()
            self.settings_locations.pack_forget()
        else:
            self.f_hierarchical.pack(fill='x', padx=16, pady=10, after=self.sel_scope.master)
            self.settings_locations.pack(fill='x', pady=5, after=self.f_hierarchical)

    def update_config_list(self, key, val):
        CONFIG["settings"][key] = val
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(CONFIG, f, indent=4)
        recalculate_metrics()
        self.controller.refresh_nav_buttons()

    def save_settings_action(self):
        try:
            min_sc = int(self.settings_min_score.get().strip())
            max_jb = int(self.settings_max_jobs.get().strip())
            
            plat_list = []
            for plat, sw in self.plat_switches.items():
                if sw.get(): plat_list.append(plat)
                
            CONFIG["settings"]["min_score"] = min_sc
            CONFIG["settings"]["max_jobs_per_query"] = max_jb
            CONFIG["settings"]["safe_mode"] = True if self.sw_safe_mode.get() else False
            CONFIG["settings"]["daily_apply_cap"] = int(self.settings_daily_cap.get().strip())
            CONFIG["settings"]["min_delay_seconds"] = int(self.settings_min_delay.get().strip())
            CONFIG["settings"]["max_delay_seconds"] = int(self.settings_max_delay.get().strip())
            CONFIG["settings"]["experience_level"] = self.sel_exp.get()
            CONFIG["settings"]["job_type"] = self.sel_jt.get()
            CONFIG["settings"]["location_type"] = self.sel_loc.get()
            CONFIG["settings"]["location_scope"] = self.sel_scope.get()
            CONFIG["settings"]["target_platforms"] = plat_list
            CONFIG["settings"]["ollama_model"] = self.sel_model.get()
            
            CONFIG["settings"]["ai_provider"] = "cloud" if "Cloud" in self.seg_provider.get() else "local"
            CONFIG["settings"]["cloud_ai_preset"] = self.sel_preset.get()
            CONFIG["settings"]["cloud_ai_base_url"] = self.entry_cloud_url.get().strip()
            CONFIG["settings"]["cloud_ai_model"] = self.entry_cloud_model.get().strip()
            CONFIG["settings"]["cloud_ai_auth_type"] = "user_pass" if "Username" in self.seg_auth.get() else "api_key"
            CONFIG["settings"]["cloud_ai_api_key"] = self.entry_cloud_key.get().strip()
            CONFIG["settings"]["cloud_ai_username"] = self.entry_cloud_user.get().strip()
            CONFIG["settings"]["cloud_ai_password"] = self.entry_cloud_pass.get().strip()
            
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(CONFIG, f, indent=4)
            messagebox.showinfo("Success", "All settings saved successfully!")
            log_message("Settings saved via Desktop GUI.")
            recalculate_metrics()
            self.controller.refresh_nav_buttons()
        except Exception as e:
            messagebox.showerror("Error", f"Could not save settings: {e}")
            
    def reload_view_data(self):
        self.settings_queries.update_items(CONFIG["settings"]["queries"])
        self.settings_min_score.delete(0, 'end')
        self.settings_min_score.insert(0, str(CONFIG["settings"]["min_score"]))
        self.settings_max_jobs.delete(0, 'end')
        self.settings_max_jobs.insert(0, str(CONFIG["settings"].get("max_jobs_per_query", 10)))
        
        prov_val = CONFIG["settings"].get("ai_provider", "local")
        if prov_val == "gemini": prov_val = "cloud"
        self.seg_provider.set("Cloud AI / REST API" if prov_val == "cloud" else "Local Ollama (Offline)")
        
        self.sel_preset.set(CONFIG["settings"].get("cloud_ai_preset", "OpenAI / ChatGPT"))
        self.entry_cloud_url.delete(0, 'end'); self.entry_cloud_url.insert(0, CONFIG["settings"].get("cloud_ai_base_url", "https://api.openai.com/v1"))
        self.entry_cloud_model.delete(0, 'end'); self.entry_cloud_model.insert(0, CONFIG["settings"].get("cloud_ai_model", "gpt-4o-mini"))
        
        auth_val = CONFIG["settings"].get("cloud_ai_auth_type", "api_key")
        self.seg_auth.set("Username & Password (Basic Auth)" if auth_val == "user_pass" else "API Key / Bearer Token")
        
        self.entry_cloud_key.delete(0, 'end'); self.entry_cloud_key.insert(0, CONFIG["settings"].get("cloud_ai_api_key", CONFIG["settings"].get("gemini_api_key", "")))
        self.entry_cloud_user.delete(0, 'end'); self.entry_cloud_user.insert(0, CONFIG["settings"].get("cloud_ai_username", ""))
        self.entry_cloud_pass.delete(0, 'end'); self.entry_cloud_pass.insert(0, CONFIG["settings"].get("cloud_ai_password", ""))
        
        self.on_provider_changed(self.seg_provider.get())
        self.on_auth_type_changed(self.seg_auth.get())
        
        self.sel_exp.set(CONFIG["settings"].get("experience_level", "All"))
        self.sel_jt.set(CONFIG["settings"].get("job_type", "All"))
        self.sel_loc.set(CONFIG["settings"].get("location_type", "All"))
        self.sel_scope.set(CONFIG["settings"].get("location_scope", "Entire Country"))
        self.on_scope_changed(self.sel_scope.get())
        
        self.settings_skip.update_items(CONFIG["settings"]["skip_keywords"])
        self.settings_locations.update_items(CONFIG["settings"].get("preferred_locations", []))
        self.refresh_models()
        
        # Reload safety settings
        if CONFIG["settings"].get("safe_mode", True):
            self.sw_safe_mode.select()
        else:
            self.sw_safe_mode.deselect()
        self.settings_daily_cap.delete(0, 'end'); self.settings_daily_cap.insert(0, str(CONFIG["settings"].get("daily_apply_cap", 25)))
        self.settings_min_delay.delete(0, 'end'); self.settings_min_delay.insert(0, str(CONFIG["settings"].get("min_delay_seconds", 15)))
        self.settings_max_delay.delete(0, 'end'); self.settings_max_delay.insert(0, str(CONFIG["settings"].get("max_delay_seconds", 45)))
