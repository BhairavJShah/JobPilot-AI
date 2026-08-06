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
        
        self.ai_provider_var = tk.StringVar(value=CONFIG["settings"].get("ai_provider", "local"))
        
        rb_local = tk.Radiobutton(f_prov, text="🤖 Local Ollama (100% Private / Offline)", variable=self.ai_provider_var, value="local", command=self.on_provider_changed, bg='#1e293b', fg='white', selectcolor='#0f172a', font=('Segoe UI', 9, 'bold'))
        rb_local.pack(side='left', padx=(0, 20))
        
        rb_gemini = tk.Radiobutton(f_prov, text="☁️ Google Gemini (Cloud AI / Ultra-Fast 0.5s)", variable=self.ai_provider_var, value="gemini", command=self.on_provider_changed, bg='#1e293b', fg='white', selectcolor='#0f172a', font=('Segoe UI', 9, 'bold'))
        rb_gemini.pack(side='left')

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

        # Frame for Google Gemini Cloud Settings
        self.f_gemini_sub = ttk.Frame(f_ai)
        self.f_gemini_sub.pack(fill='x', pady=5)
        
        gem_grid = ttk.Frame(self.f_gemini_sub)
        gem_grid.pack(fill='x')
        gem_grid.columnconfigure(0, weight=2)
        gem_grid.columnconfigure(1, weight=1)
        
        f_key = ttk.Frame(gem_grid)
        f_key.grid(row=0, column=0, sticky='ew', padx=(0, 10))
        ttk.Label(f_key, text="Google Gemini API Key (from Google AI Studio)", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 4))
        self.entry_gemini_key = tk.Entry(f_key, bg="#080c14", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#1f2937", font=('Segoe UI', 10), show="*")
        self.entry_gemini_key.pack(fill='x', ipady=6)
        self.entry_gemini_key.insert(0, CONFIG["settings"].get("gemini_api_key", ""))
        
        f_gmod = ttk.Frame(gem_grid)
        f_gmod.grid(row=0, column=1, sticky='ew')
        ttk.Label(f_gmod, text="Gemini Model", font=('Segoe UI', 9, 'bold'), foreground='#94a3b8').pack(anchor='w', pady=(0, 4))
        self.sel_gemini_model = ttk.Combobox(f_gmod, values=["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"], state="readonly")
        self.sel_gemini_model.pack(fill='x')
        self.sel_gemini_model.set(CONFIG["settings"].get("gemini_model", "gemini-2.5-flash"))
        
        btn_test_gemini = tk.Button(self.f_gemini_sub, text="⚡ Test Gemini Key", font=('Segoe UI', 9, 'bold'), padx=12, pady=4)
        btn_test_gemini.pack(anchor='w', pady=(8, 0))
        btn_test_gemini.config(command=self.test_gemini_key)
        make_btn_interactive(btn_test_gemini, "#10b981", "#059669", "white", "white")

        self.on_provider_changed()
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
        if prov == "gemini":
            self.f_ollama_sub.pack_forget()
            self.f_gemini_sub.pack(fill='x', pady=5)
        else:
            self.f_gemini_sub.pack_forget()
            self.f_ollama_sub.pack(fill='x', pady=5)

    def test_gemini_key(self):
        key = self.entry_gemini_key.get().strip()
        if not key:
            messagebox.showerror("Error", "Please enter a Google Gemini API Key.")
            return
        g_model = self.sel_gemini_model.get()
        import urllib.request
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": "Hello, respond with 'Connected'"}]}]}
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                messagebox.showinfo("Success", f"Google Gemini ({g_model}) connected successfully!")
        except Exception as e:
            messagebox.showerror("Connection Error", f"Gemini API test failed: {e}")

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
            CONFIG["settings"]["gemini_api_key"] = self.entry_gemini_key.get().strip()
            CONFIG["settings"]["gemini_model"] = self.sel_gemini_model.get()
            
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(CONFIG, f, indent=4)
            messagebox.showinfo("Success", "Job search & AI settings updated successfully!")
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
        
        self.ai_provider_var.set(CONFIG["settings"].get("ai_provider", "local"))
        self.entry_gemini_key.delete(0, 'end')
        self.entry_gemini_key.insert(0, CONFIG["settings"].get("gemini_api_key", ""))
        self.sel_gemini_model.set(CONFIG["settings"].get("gemini_model", "gemini-2.5-flash"))
        self.on_provider_changed()
        
        self.sel_exp.set(CONFIG["settings"].get("experience_level", "All"))
        self.sel_jt.set(CONFIG["settings"].get("job_type", "All"))
        self.sel_loc.set(CONFIG["settings"].get("location_type", "All"))
        self.sel_scope.set(CONFIG["settings"].get("location_scope", "Entire Country"))
        self.on_scope_changed(None)
        
        self.settings_skip.update_items(CONFIG["settings"]["skip_keywords"])
        self.settings_locations.update_items(CONFIG["settings"].get("preferred_locations", []))
        self.refresh_models()
