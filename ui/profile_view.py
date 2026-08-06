import json
import tkinter as tk
from tkinter import ttk, messagebox
from core.config_manager import CONFIG, CONFIG_PATH
from core.db_manager import log_message, recalculate_metrics
from ui.components import TagChipContainer, add_grid_input, make_btn_interactive, enable_canvas_mousewheel

class ProfileView(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        lbl_title = ttk.Label(self, text="Candidate Profile details", style='Heading.TLabel')
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
        
        card = ttk.Frame(scrollable_frame, style='Card.TFrame', padding=20)
        card.pack(fill='both', expand=True, padx=5, pady=5)
        
        grid_frame = ttk.Frame(card)
        grid_frame.pack(fill='x', pady=10)
        grid_frame.columnconfigure((0, 1), weight=1, uniform="equal")
        
        self.prof_name = add_grid_input(grid_frame, "Full Name", 0, 0)
        self.prof_email = add_grid_input(grid_frame, "Email Address", 0, 1)
        self.prof_phone = add_grid_input(grid_frame, "Phone Number", 1, 0)
        self.prof_country = add_grid_input(grid_frame, "Country Code", 1, 1)
        self.prof_linkedin = add_grid_input(grid_frame, "LinkedIn URL", 2, 0)
        self.prof_github = add_grid_input(grid_frame, "GitHub URL", 2, 1)
        self.prof_portfolio = add_grid_input(grid_frame, "Portfolio Website", 3, 0)
        self.prof_resume = add_grid_input(grid_frame, "Resume Local Path (PDF)", 3, 1)
        
        self.prof_skills = TagChipContainer(card, CONFIG["candidate"].get("skills", []), "Technical Skills Chip Badges (Press Enter or Comma to add)", lambda val: self.update_candidate_list("skills", val))
        self.prof_skills.pack(fill='x', pady=10)
        
        self.reload_profile_fields()
        
        btn_save = tk.Button(card, text="Save Profile Details", font=('Segoe UI', 10, 'bold'), padx=25, pady=8)
        btn_save.pack(anchor='w', pady=(25, 0))
        btn_save.config(command=self.save_profile_action)
        make_btn_interactive(btn_save, "#2563eb", "#1d4ed8", "white", "white")

        enable_canvas_mousewheel(canvas)

    def update_candidate_list(self, key, val):
        CONFIG["candidate"][key] = val
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(CONFIG, f, indent=4)
        recalculate_metrics()
        self.controller.refresh_nav_buttons()

    def reload_profile_fields(self):
        self.prof_name.delete(0, 'end')
        self.prof_name.insert(0, CONFIG["candidate"]["name"])
        self.prof_email.delete(0, 'end')
        self.prof_email.insert(0, CONFIG["candidate"]["email"])
        self.prof_phone.delete(0, 'end')
        self.prof_phone.insert(0, CONFIG["candidate"]["phone"])
        self.prof_country.delete(0, 'end')
        self.prof_country.insert(0, CONFIG["candidate"]["country_code"])
        self.prof_linkedin.delete(0, 'end')
        self.prof_linkedin.insert(0, CONFIG["candidate"]["linkedin"])
        self.prof_github.delete(0, 'end')
        self.prof_github.insert(0, CONFIG["candidate"]["github"])
        self.prof_portfolio.delete(0, 'end')
        self.prof_portfolio.insert(0, CONFIG["candidate"]["portfolio"])
        self.prof_resume.delete(0, 'end')
        self.prof_resume.insert(0, CONFIG["candidate"]["resume_path"])
        self.prof_skills.update_items(CONFIG["candidate"].get("skills", []))

    def save_profile_action(self):
        try:
            CONFIG["candidate"]["name"] = self.prof_name.get().strip()
            CONFIG["candidate"]["email"] = self.prof_email.get().strip()
            CONFIG["candidate"]["phone"] = self.prof_phone.get().strip()
            CONFIG["candidate"]["country_code"] = self.prof_country.get().strip()
            CONFIG["candidate"]["linkedin"] = self.prof_linkedin.get().strip()
            CONFIG["candidate"]["github"] = self.prof_github.get().strip()
            CONFIG["candidate"]["portfolio"] = self.prof_portfolio.get().strip()
            CONFIG["candidate"]["resume_path"] = self.prof_resume.get().strip()
            
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(CONFIG, f, indent=4)
            messagebox.showinfo("Success", "Candidate profile updated successfully!")
            log_message("Candidate Profile saved via Desktop GUI.")
            recalculate_metrics()
            self.controller.refresh_nav_buttons()
        except Exception as e:
            messagebox.showerror("Error", f"Could not save profile: {e}")
