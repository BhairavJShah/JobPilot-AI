import json
import tkinter as tk
from tkinter import ttk, messagebox
from core.config_manager import CONFIG, CONFIG_PATH, LOCATION_DATA, get_installed_ollama_models
from core.db_manager import log_message, recalculate_metrics
from ui.components import TagChipContainer, add_form_input, make_btn_interactive, enable_canvas_mousewheel

class SettingsView(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        lbl_title = ttk.Label(self, text="Search Settings", style='Heading.TLabel')
        lbl_title.pack(anchor='w', pady=(0, 20))
        
        canvas = tk.Canvas(self, bg="#0f172a", bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        card = ttk.Frame(scrollable_frame, style='Card.TFrame', padding=25)
        card.pack(fill='both', expand=True, padx=5, pady=5)
        
        # AI Provider & Model Selector Block
        f_ai = ttk.Frame(card)
        f_ai.pack(fill='x', pady=10)
        ttk.Label(f_ai, text="AI Engine Provider & Intelligence Source", style='CardHeading.TLabel').pack(anchor='w', pady=(0, 6))
        
        f_prov = ttk.Frame(f_ai)
        f_prov.pack(fill='x', pady=4)
        
        provider_val = CONFIG["settings"].get("ai_provider", "local")
        if provider_val == "gemini": provider_val = "cloud"
        self.ai_provider_var = tk.StringVar(value=provider_val)
        
        rb_local = tk.Radiobutton(f_prov, text="🤖 Local Ollama (100% Private / Offline)", variable=self.ai_provider_var, value="local", command=self.on_provider_changed, bg='#1e293b', fg='white', selectcolor='#0f172a', font=('Segoe UI', 9, 'bold'))
        rb_local.pack(side='left', padx=(0, 20))
        
        rb_cloud = tk.Radiobutton(f_prov, text="☁️ Cloud AI / External API (OpenAI, DeepSeek, Groq, Google, Custom REST)", variable=self.ai_provider_var, value="cloud", command=self.on_provider_changed, bg='#1e293b', fg='white', selectcolor='#0f172a', font=('Segoe UI', 9, 'bold'))
        rb_cloud.pack(side='left')

        # Frame for Local Ollama Settings
        self.f_ollama_sub = ttk.Frame(f_ai)
        self.f_ollama_sub.pack(fill='x', pady=5)
        ttk.Label(self.f_ollama_sub, text="Local Ollama Model", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 4))
        
        model_row = ttk.Frame(self.f_ollama_sub)
        model_row.pack(fill='x')
        self.sel_model = ttk.Combobox(model_row, state="readonly")
        self.sel_model.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        btn_refresh_models = tk.Button(model_row, text="Refresh Models", font=('Segoe UI', 9, 'bold'), padx=10, pady=2)
        btn_refresh_models.pack(side='left')
        btn_refresh_models.config(command=self.refresh_models)
        make_btn_interactive(btn_refresh_models, "#3b82f6", "#2563eb", "white", "white")

        # Frame for Universal Cloud AI Settings
        self.f_cloud_sub = ttk.Frame(f_ai)
        self.f_cloud_sub.pack(fill='x', pady=5)
        
        # Preset Selector
        f_preset = ttk.Frame(self.f_cloud_sub)
        f_preset.pack(fill='x', pady=(0, 6))
        ttk.Label(f_preset, text="Cloud Provider Preset Quick-Select", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 4))
        
        self.sel_preset = ttk.Combobox(f_preset, values=["OpenAI / ChatGPT", "DeepSeek", "Groq", "Google AI", "Custom Endpoint"], state="readonly")
        self.sel_preset.pack(fill='x')
        self.sel_preset.set(CONFIG["settings"].get("cloud_ai_preset", "OpenAI / ChatGPT"))
        self.sel_preset.bind("<<ComboboxSelected>>", self.on_cloud_preset_selected)
        
        # Endpoint & Model Row
        cloud_grid = ttk.Frame(self.f_cloud_sub)
        cloud_grid.pack(fill='x', pady=4)
        cloud_grid.columnconfigure((0, 1), weight=1, uniform="equal")
        
        f_url = ttk.Frame(cloud_grid)
        f_url.grid(row=0, column=0, sticky='ew', padx=(0, 6))
        ttk.Label(f_url, text="Base API Endpoint URL", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 4))
        self.entry_cloud_url = tk.Entry(f_url, bg="#080c14", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#1f2937", font=('Segoe UI', 9))
        self.entry_cloud_url.pack(fill='x', ipady=5)
        self.entry_cloud_url.insert(0, CONFIG["settings"].get("cloud_ai_base_url", "https://api.openai.com/v1"))
        
        f_cmod = ttk.Frame(cloud_grid)
        f_cmod.grid(row=0, column=1, sticky='ew', padx=(6, 0))
        ttk.Label(f_cmod, text="Model Name / ID", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 4))
        self.entry_cloud_model = tk.Entry(f_cmod, bg="#080c14", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#1f2937", font=('Segoe UI', 9))
        self.entry_cloud_model.pack(fill='x', ipady=5)
        self.entry_cloud_model.insert(0, CONFIG["settings"].get("cloud_ai_model", "gpt-4o-mini"))
        
        # Authentication Selector (API Key vs Username/Password)
        f_auth_type = ttk.Frame(self.f_cloud_sub)
        f_auth_type.pack(fill='x', pady=(10, 4))
        ttk.Label(f_auth_type, text="Authentication Method", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 4))
        
        self.auth_type_var = tk.StringVar(value=CONFIG["settings"].get("cloud_ai_auth_type", "api_key"))
        
        rb_auth_key = tk.Radiobutton(f_auth_type, text="🔑 API Key / Bearer Token", variable=self.auth_type_var, value="api_key", command=self.on_auth_type_changed, bg='#1e293b', fg='white', selectcolor='#0f172a', font=('Segoe UI', 9))
        rb_auth_key.pack(side='left', padx=(0, 20))
        
        rb_auth_pass = tk.Radiobutton(f_auth_type, text="👤 Username & Password (Basic Auth)", variable=self.auth_type_var, value="user_pass", command=self.on_auth_type_changed, bg='#1e293b', fg='white', selectcolor='#0f172a', font=('Segoe UI', 9))
        rb_auth_pass.pack(side='left')

        # API Key Frame
        self.f_key_sub = ttk.Frame(self.f_cloud_sub)
        self.f_key_sub.pack(fill='x', pady=4)
        ttk.Label(self.f_key_sub, text="API Key / Token", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 4))
        self.entry_cloud_key = tk.Entry(self.f_key_sub, bg="#080c14", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#1f2937", font=('Segoe UI', 10), show="*")
        self.entry_cloud_key.pack(fill='x', ipady=5)
        self.entry_cloud_key.insert(0, CONFIG["settings"].get("cloud_ai_api_key", CONFIG["settings"].get("gemini_api_key", "")))

        # Username & Password Frame
        self.f_userpass_sub = ttk.Frame(self.f_cloud_sub)
        self.f_userpass_sub.pack(fill='x', pady=4)
        up_grid = ttk.Frame(self.f_userpass_sub)
        up_grid.pack(fill='x')
        up_grid.columnconfigure((0, 1), weight=1, uniform="equal")
        
        f_u = ttk.Frame(up_grid)
        f_u.grid(row=0, column=0, sticky='ew', padx=(0, 6))
        ttk.Label(f_u, text="API Username", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 4))
        self.entry_cloud_user = tk.Entry(f_u, bg="#080c14", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#1f2937", font=('Segoe UI', 9))
        self.entry_cloud_user.pack(fill='x', ipady=5)
        self.entry_cloud_user.insert(0, CONFIG["settings"].get("cloud_ai_username", ""))
        
        f_p = ttk.Frame(up_grid)
        f_p.grid(row=0, column=1, sticky='ew', padx=(6, 0))
        ttk.Label(f_p, text="API Password", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 4))
        self.entry_cloud_pass = tk.Entry(f_p, bg="#080c14", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#1f2937", font=('Segoe UI', 9), show="*")
        self.entry_cloud_pass.pack(fill='x', ipady=5)
        self.entry_cloud_pass.insert(0, CONFIG["settings"].get("cloud_ai_password", ""))
        
        btn_test_cloud = tk.Button(self.f_cloud_sub, text="⚡ Test Cloud AI Connection", font=('Segoe UI', 9, 'bold'), padx=12, pady=4)
        btn_test_cloud.pack(anchor='w', pady=(10, 0))
        btn_test_cloud.config(command=self.test_cloud_connection)
        make_btn_interactive(btn_test_cloud, "#10b981", "#059669", "white", "white")

        self.on_provider_changed()
        self.on_auth_type_changed()
        self.refresh_models()

        # Tag/Chip Containers for Queries & Skip Keywords
        self.settings_queries = TagChipContainer(card, CONFIG["settings"]["queries"], "Target Job Queries (Press Enter or Comma to add)", lambda val: self.update_config_list("queries", val))
        self.settings_queries.pack(fill='x', pady=5)
        
        self.settings_skip = TagChipContainer(card, CONFIG["settings"]["skip_keywords"], "Skip Keywords (Press Enter or Comma to add)", lambda val: self.update_config_list("skip_keywords", val))
        self.settings_skip.pack(fill='x', pady=5)

        # Geographic Search Scope
        f_scope = ttk.Frame(card)
        f_scope.pack(fill='x', pady=10)
        ttk.Label(f_scope, text="Geographic Location Scope", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 4))
        self.sel_scope = ttk.Combobox(f_scope, values=["Entire Country", "Custom Cities & States"], state="readonly")
        self.sel_scope.pack(fill='x')
        self.sel_scope.set(CONFIG["settings"].get("location_scope", "Entire Country"))
        self.sel_scope.bind("<<ComboboxSelected>>", self.on_scope_changed)

        # Hierarchical Dropdown Selection Frame
        self.f_hierarchical = ttk.Frame(card)
        self.f_hierarchical.pack(fill='x', pady=10)
        
        lbl_hier = ttk.Label(self.f_hierarchical, text="Location Hierarchy Selector", style='CardHeading.TLabel')
        lbl_hier.pack(anchor='w', pady=(0, 6))
        
        drop_grid = ttk.Frame(self.f_hierarchical)
        drop_grid.pack(fill='x')
        drop_grid.columnconfigure((0, 1, 2), weight=1, uniform="equal")
        
        fc = ttk.Frame(drop_grid)
        fc.grid(row=0, column=0, padx=4, sticky='ew')
        ttk.Label(fc, text="Country", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 2))
        self.sel_country = ttk.Combobox(fc, values=list(LOCATION_DATA.keys()), state="readonly")
        self.sel_country.pack(fill='x')
        self.sel_country.bind("<<ComboboxSelected>>", self.on_country_selected)
        
        fs = ttk.Frame(drop_grid)
        fs.grid(row=0, column=1, padx=4, sticky='ew')
        ttk.Label(fs, text="State", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 2))
        self.sel_state = ttk.Combobox(fs, state="readonly")
        self.sel_state.pack(fill='x')
        self.sel_state.bind("<<ComboboxSelected>>", self.on_state_selected)
        
        fcy = ttk.Frame(drop_grid)
        fcy.grid(row=0, column=2, padx=4, sticky='ew')
        ttk.Label(fcy, text="City", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 2))
        self.sel_city = ttk.Combobox(fcy, state="readonly")
        self.sel_city.pack(fill='x')
        
        self.sel_country.set("India")
        self.on_country_selected(None)
        
        btn_add_loc = tk.Button(self.f_hierarchical, text="Add Selected Location", font=('Segoe UI', 9, 'bold'), padx=15, pady=6)
        btn_add_loc.pack(anchor='w', pady=(10, 0))
        btn_add_loc.config(command=self.add_hierarchical_location)
        make_btn_interactive(btn_add_loc, "#10b981", "#059669", "white", "white")

        self.settings_locations = TagChipContainer(card, CONFIG["settings"].get("preferred_locations", []), "Selected Search Locations (Chips List)", lambda val: self.update_config_list("preferred_locations", val))
        self.settings_locations.pack(fill='x', pady=5)
        
        self.on_scope_changed(None)

        self.settings_min_score = add_form_input(card, "Minimum Match Score (%)")
        self.settings_max_jobs = add_form_input(card, "Max Jobs to Check Per Query")
        
        self.settings_min_score.insert(0, str(CONFIG["settings"]["min_score"]))
        self.settings_max_jobs.insert(0, str(CONFIG["settings"].get("max_jobs_per_query", 10)))
        
        # Filters dropdown selectors
        lbl_filters = ttk.Label(card, text="Job Search Filter Criteria", style='CardHeading.TLabel')
        lbl_filters.pack(anchor='w', pady=(20, 10))
        
        drop_frame = ttk.Frame(card)
        drop_frame.pack(fill='x', pady=5)
        drop_frame.columnconfigure((0, 1, 2), weight=1, uniform="equal")
        
        f_exp = ttk.Frame(drop_frame)
        f_exp.grid(row=0, column=0, padx=5, sticky='ew')
        ttk.Label(f_exp, text="Experience Level", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 4))
        self.sel_exp = ttk.Combobox(f_exp, values=["All", "Fresher", "Mid", "Senior"], state="readonly")
        self.sel_exp.pack(fill='x')
        self.sel_exp.set(CONFIG["settings"].get("experience_level", "All"))
        
        f_jt = ttk.Frame(drop_frame)
        f_jt.grid(row=0, column=1, padx=5, sticky='ew')
        ttk.Label(f_jt, text="Job Type", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 4))
        self.sel_jt = ttk.Combobox(f_jt, values=["All", "Full-time", "Internship", "Contract"], state="readonly")
        self.sel_jt.pack(fill='x')
        self.sel_jt.set(CONFIG["settings"].get("job_type", "All"))
        
        f_loc = ttk.Frame(drop_frame)
        f_loc.grid(row=0, column=2, padx=5, sticky='ew')
        ttk.Label(f_loc, text="Location Mode", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 4))
        self.sel_loc = ttk.Combobox(f_loc, values=["All", "Remote", "On-site", "Hybrid"], state="readonly")
        self.sel_loc.pack(fill='x')
        self.sel_loc.set(CONFIG["settings"].get("location_type", "All"))
        
        # Platforms Block
        lbl_plats = ttk.Label(card, text="Target Job Platforms", style='CardHeading.TLabel')
        lbl_plats.pack(anchor='w', pady=(20, 10))
        
        self.plat_vars = {}
        for plat in ["Indeed", "Naukri", "LinkedIn"]:
            self.plat_vars[plat] = tk.BooleanVar(value=plat in CONFIG["settings"].get("target_platforms", []))
            cb = tk.Checkbutton(card, text=plat, variable=self.plat_vars[plat], bg='#1e293b', fg='white', selectcolor='#0f172a', font=('Segoe UI', 9))
            cb.pack(anchor='w', pady=2)
            
        lbl_recom = ttk.Label(card, text="Additional Platforms Target (Recommended Extension)", style='Card.TLabel')
        lbl_recom.config(font=('Segoe UI', 9, 'italic'), foreground='#6b7280')
        lbl_recom.pack(anchor='w', pady=(15, 5))
        
        for plat in ["Hirist (Coming Soon)", "Foundit (Coming Soon)", "Wellfound (Coming Soon)"]:
            cb_mock = tk.Checkbutton(card, text=plat, state="disabled", bg='#1e293b', fg='#4b5563', selectcolor='#0f172a', font=('Segoe UI', 9))
            cb_mock.pack(anchor='w', pady=1)
        
        btn_save = tk.Button(card, text="Save Settings", font=('Segoe UI', 10, 'bold'), padx=25, pady=8)
        btn_save.pack(anchor='w', pady=(25, 0))
        btn_save.config(command=self.save_settings_action)
        make_btn_interactive(btn_save, "#2563eb", "#1d4ed8", "white", "white")

        enable_canvas_mousewheel(canvas)

    def on_provider_changed(self):
        prov = self.ai_provider_var.get()
        if prov == "cloud":
            self.f_ollama_sub.pack_forget()
            self.f_cloud_sub.pack(fill='x', pady=5)
        else:
            self.f_cloud_sub.pack_forget()
            self.f_ollama_sub.pack(fill='x', pady=5)

    def on_auth_type_changed(self):
        atype = self.auth_type_var.get()
        if atype == "user_pass":
            self.f_key_sub.pack_forget()
            self.f_userpass_sub.pack(fill='x', pady=4)
        else:
            self.f_userpass_sub.pack_forget()
            self.f_key_sub.pack(fill='x', pady=4)

    def on_cloud_preset_selected(self, event):
        preset = self.sel_preset.get()
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
        atype = self.auth_type_var.get()
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
                messagebox.showinfo("Success", f"Universal Cloud AI ({model}) connected successfully!")
        except Exception as e:
            messagebox.showerror("Connection Error", f"Cloud AI API connection test failed: {e}")

    def refresh_models(self):
        models = get_installed_ollama_models()
        self.sel_model.config(values=models)
        current_model = CONFIG["settings"].get("ollama_model", "qwen2.5:latest")
        if current_model in models:
            self.sel_model.set(current_model)
        elif models:
            self.sel_model.set(models[0])

    def on_country_selected(self, event):
        country = self.sel_country.get()
        states = list(LOCATION_DATA.get(country, {}).keys())
        self.sel_state.config(values=states)
        if states:
            self.sel_state.set(states[0])
            self.on_state_selected(None)
            
    def on_state_selected(self, event):
        country = self.sel_country.get()
        state = self.sel_state.get()
        cities = LOCATION_DATA.get(country, {}).get(state, ["All Cities"])
        self.sel_city.config(values=cities)
        if cities:
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

    def on_scope_changed(self, event):
        scope = self.sel_scope.get()
        if scope == "Entire Country":
            self.f_hierarchical.pack_forget()
            self.settings_locations.pack_forget()
        else:
            self.f_hierarchical.pack(fill='x', pady=10, after=self.sel_scope)
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
            for plat, var in self.plat_vars.items():
                if var.get(): plat_list.append(plat)
                
            CONFIG["settings"]["min_score"] = min_sc
            CONFIG["settings"]["max_jobs_per_query"] = max_jb
            CONFIG["settings"]["experience_level"] = self.sel_exp.get()
            CONFIG["settings"]["job_type"] = self.sel_jt.get()
            CONFIG["settings"]["location_type"] = self.sel_loc.get()
            CONFIG["settings"]["location_scope"] = self.sel_scope.get()
            CONFIG["settings"]["target_platforms"] = plat_list
            CONFIG["settings"]["ollama_model"] = self.sel_model.get()
            
            CONFIG["settings"]["ai_provider"] = self.ai_provider_var.get()
            CONFIG["settings"]["cloud_ai_preset"] = self.sel_preset.get()
            CONFIG["settings"]["cloud_ai_base_url"] = self.entry_cloud_url.get().strip()
            CONFIG["settings"]["cloud_ai_model"] = self.entry_cloud_model.get().strip()
            CONFIG["settings"]["cloud_ai_auth_type"] = self.auth_type_var.get()
            CONFIG["settings"]["cloud_ai_api_key"] = self.entry_cloud_key.get().strip()
            CONFIG["settings"]["cloud_ai_username"] = self.entry_cloud_user.get().strip()
            CONFIG["settings"]["cloud_ai_password"] = self.entry_cloud_pass.get().strip()
            
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(CONFIG, f, indent=4)
            messagebox.showinfo("Success", "Job search & Universal AI settings updated successfully!")
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
        self.ai_provider_var.set(prov_val)
        
        self.sel_preset.set(CONFIG["settings"].get("cloud_ai_preset", "OpenAI / ChatGPT"))
        self.entry_cloud_url.delete(0, 'end'); self.entry_cloud_url.insert(0, CONFIG["settings"].get("cloud_ai_base_url", "https://api.openai.com/v1"))
        self.entry_cloud_model.delete(0, 'end'); self.entry_cloud_model.insert(0, CONFIG["settings"].get("cloud_ai_model", "gpt-4o-mini"))
        
        self.auth_type_var.set(CONFIG["settings"].get("cloud_ai_auth_type", "api_key"))
        self.entry_cloud_key.delete(0, 'end'); self.entry_cloud_key.insert(0, CONFIG["settings"].get("cloud_ai_api_key", CONFIG["settings"].get("gemini_api_key", "")))
        self.entry_cloud_user.delete(0, 'end'); self.entry_cloud_user.insert(0, CONFIG["settings"].get("cloud_ai_username", ""))
        self.entry_cloud_pass.delete(0, 'end'); self.entry_cloud_pass.insert(0, CONFIG["settings"].get("cloud_ai_password", ""))
        
        self.on_provider_changed()
        self.on_auth_type_changed()
        
        self.sel_exp.set(CONFIG["settings"].get("experience_level", "All"))
        self.sel_jt.set(CONFIG["settings"].get("job_type", "All"))
        self.sel_loc.set(CONFIG["settings"].get("location_type", "All"))
        self.sel_scope.set(CONFIG["settings"].get("location_scope", "Entire Country"))
        self.on_scope_changed(None)
        
        self.settings_skip.update_items(CONFIG["settings"]["skip_keywords"])
        self.settings_locations.update_items(CONFIG["settings"].get("preferred_locations", []))
        self.refresh_models()
