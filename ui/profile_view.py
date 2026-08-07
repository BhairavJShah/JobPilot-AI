import json
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from core.config_manager import CONFIG, CONFIG_PATH
from core.db_manager import log_message, recalculate_metrics
from ui.components import C, F, TagChipContainer, add_grid_input, create_action_btn, add_section_divider

class ProfileView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # ── Header ──
        lbl_title = ctk.CTkLabel(self, text="Candidate Profile", font=F["h1"], text_color=C["text"], anchor="w")
        lbl_title.pack(anchor='w', pady=(0, 14))
        
        # ── Scrollable Card ──
        card = ctk.CTkScrollableFrame(self, fg_color=C["card"], corner_radius=12)
        card.pack(fill='both', expand=True)
        
        # ── Personal Information ──
        add_section_divider(card, "Personal Information")
        
        grid_frame = ctk.CTkFrame(card, fg_color="transparent")
        grid_frame.pack(fill='x', padx=16, pady=4)
        grid_frame.columnconfigure((0, 1), weight=1, uniform="equal")
        
        self.prof_name = add_grid_input(grid_frame, "Full Name", 0, 0)
        self.prof_email = add_grid_input(grid_frame, "Email Address", 0, 1)
        self.prof_phone = add_grid_input(grid_frame, "Phone Number", 1, 0)
        self.prof_country = add_grid_input(grid_frame, "Country Code", 1, 1)
        
        # ── Online Presence ──
        add_section_divider(card, "Online Presence")
        
        grid_frame2 = ctk.CTkFrame(card, fg_color="transparent")
        grid_frame2.pack(fill='x', padx=16, pady=4)
        grid_frame2.columnconfigure((0, 1), weight=1, uniform="equal")
        
        self.prof_linkedin = add_grid_input(grid_frame2, "LinkedIn URL", 0, 0)
        self.prof_github = add_grid_input(grid_frame2, "GitHub URL", 0, 1)
        self.prof_portfolio = add_grid_input(grid_frame2, "Portfolio Website", 1, 0)
        self.prof_resume = add_grid_input(grid_frame2, "Resume Local Path (PDF)", 1, 1)
        
        # ── Candidate QA Vault (ATS Form Memory) ──
        add_section_divider(card, "Candidate QA Vault (Smart Form Memory)")
        
        grid_qa = ctk.CTkFrame(card, fg_color="transparent")
        grid_qa.pack(fill='x', padx=16, pady=4)
        grid_qa.columnconfigure((0, 1), weight=1, uniform="equal")
        
        self.qa_exp = add_grid_input(grid_qa, "Experience (Years)", 0, 0)
        self.qa_notice = add_grid_input(grid_qa, "Notice Period", 0, 1)
        self.qa_cctc = add_grid_input(grid_qa, "Current Salary / CTC", 1, 0)
        self.qa_ectc = add_grid_input(grid_qa, "Expected Salary / CTC", 1, 1)
        self.qa_auth = add_grid_input(grid_qa, "Authorized to Work? (Yes/No)", 2, 0)
        self.qa_reloc = add_grid_input(grid_qa, "Willing to Relocate? (Yes/No)", 2, 1)
        
        # ── Technical Skills ──
        add_section_divider(card, "Technical Skills")
        
        self.prof_skills = TagChipContainer(card, CONFIG["candidate"].get("skills", []), "Skill Badges (Press Enter or Comma to add)", lambda val: self.update_candidate_list("skills", val))
        self.prof_skills.pack(fill='x', pady=6)
        
        self.reload_profile_fields()
        
        # ── Save Button ──
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(anchor='w', padx=16, pady=(20, 16))
        btn_save = create_action_btn(btn_frame, "Save Profile", self.save_profile_action, "primary", "large")
        btn_save.pack(side='left')

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
        
        qa = CONFIG["candidate"].get("qa_vault", {})
        self.qa_exp.delete(0, 'end'); self.qa_exp.insert(0, qa.get("experience_years", "1"))
        self.qa_notice.delete(0, 'end'); self.qa_notice.insert(0, qa.get("notice_period", "Immediate"))
        self.qa_cctc.delete(0, 'end'); self.qa_cctc.insert(0, qa.get("current_ctc", "0"))
        self.qa_ectc.delete(0, 'end'); self.qa_ectc.insert(0, qa.get("expected_ctc", "Negotiable"))
        self.qa_auth.delete(0, 'end'); self.qa_auth.insert(0, qa.get("work_authorization", "Yes"))
        self.qa_reloc.delete(0, 'end'); self.qa_reloc.insert(0, qa.get("willing_to_relocate", "Yes"))
        
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
            
            if "qa_vault" not in CONFIG["candidate"]: CONFIG["candidate"]["qa_vault"] = {}
            CONFIG["candidate"]["qa_vault"]["experience_years"] = self.qa_exp.get().strip()
            CONFIG["candidate"]["qa_vault"]["notice_period"] = self.qa_notice.get().strip()
            CONFIG["candidate"]["qa_vault"]["current_ctc"] = self.qa_cctc.get().strip()
            CONFIG["candidate"]["qa_vault"]["expected_ctc"] = self.qa_ectc.get().strip()
            CONFIG["candidate"]["qa_vault"]["work_authorization"] = self.qa_auth.get().strip()
            CONFIG["candidate"]["qa_vault"]["willing_to_relocate"] = self.qa_reloc.get().strip()
            
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(CONFIG, f, indent=4)
            messagebox.showinfo("Success", "Candidate profile & ATS QA Vault updated successfully!")
            log_message("Candidate Profile & QA Vault saved via Desktop GUI.")
            recalculate_metrics()
            self.controller.refresh_nav_buttons()
        except Exception as e:
            messagebox.showerror("Error", f"Could not save profile: {e}")
