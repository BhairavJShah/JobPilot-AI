import customtkinter as ctk
from tkinter import ttk
import tkinter as tk

# ═══════════════════════════════════════════════════════════════
#  DESIGN SYSTEM v3.0 — Hybrid Premium Theme
#  CustomTkinter • Glassmorphism Depth • Minimal Layout • Soft Tactile
# ═══════════════════════════════════════════════════════════════

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Color Palette ──
C = {
    "bg":          "#0a0e1a",
    "sidebar":     "#080c16",
    "card":        "#111827",
    "card_hover":  "#1a2340",
    "input":       "#0c1220",
    "border":      "#1e293b",
    "focus":       "#6366f1",

    "accent":      "#6366f1",
    "accent_h":    "#818cf8",
    "accent_d":    "#4f46e5",
    "green":       "#10b981",
    "green_h":     "#34d399",
    "red":         "#ef4444",
    "red_h":       "#f87171",
    "amber":       "#f59e0b",
    "amber_h":     "#fbbf24",
    "blue":        "#3b82f6",
    "purple":      "#a855f7",
    "cyan":        "#22d3ee",

    "text":        "#f1f5f9",
    "muted":       "#94a3b8",
    "dim":         "#64748b",

    "chip":        "#312e81",
    "chip_text":   "#c7d2fe",
}

# ── Typography ──
F = {
    "h1":      ("Segoe UI", 18, "bold"),
    "h2":      ("Segoe UI", 14, "bold"),
    "h3":      ("Segoe UI", 12, "bold"),
    "body":    ("Segoe UI", 11),
    "body_b":  ("Segoe UI", 11, "bold"),
    "sm":      ("Segoe UI", 10),
    "sm_b":    ("Segoe UI", 10, "bold"),
    "xs":      ("Segoe UI", 9),
    "xs_b":    ("Segoe UI", 9, "bold"),
    "mono":    ("Consolas", 10),
    "logo":    ("Segoe UI", 16, "bold"),
    "metric":  ("Segoe UI", 24, "bold"),
    "nav":     ("Segoe UI", 11),
    "nav_a":   ("Segoe UI", 11, "bold"),
}

# ═══════════════════════════════════════════════════════════════
#  Treeview Styling (ttk widgets inside CTk app)
# ═══════════════════════════════════════════════════════════════
def configure_treeview_style():
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Dark.Treeview",
        background=C["input"], foreground=C["text"],
        fieldbackground=C["input"], rowheight=36,
        borderwidth=0, font=F["sm"])
    style.configure("Dark.Treeview.Heading",
        background=C["card"], foreground=C["muted"],
        font=F["sm_b"], relief="flat", borderwidth=0)
    style.map("Dark.Treeview",
        background=[("selected", C["accent"])],
        foreground=[("selected", "#ffffff")])
    style.layout("Dark.Treeview", [
        ("Treeview.treearea", {"sticky": "nswe"})
    ])
    # Scrollbar
    style.configure("Dark.Vertical.TScrollbar",
        troughcolor=C["bg"], background=C["dim"],
        bordercolor=C["bg"], arrowcolor=C["muted"], width=8)

# ═══════════════════════════════════════════════════════════════
#  Button Helpers
# ═══════════════════════════════════════════════════════════════
def make_btn_interactive(btn, bg_normal, bg_hover, fg_normal, fg_hover):
    """Legacy compat — works with both CTkButton and tk.Button"""
    try:
        btn.configure(fg_color=bg_normal, hover_color=bg_hover, text_color=fg_normal)
    except Exception:
        btn.config(bg=bg_normal, fg=fg_normal,
                   activebackground=bg_hover, activeforeground=fg_hover,
                   relief='flat', bd=0, cursor='hand2')
        btn.bind("<Enter>", lambda e: btn.config(bg=bg_hover, fg=fg_hover))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg_normal, fg=fg_normal))

def create_action_btn(parent, text, command, color="primary", size="normal"):
    color_map = {
        "primary":  (C["accent"],  C["accent_d"], "#ffffff"),
        "success":  (C["green"],   "#059669",     "#ffffff"),
        "danger":   (C["red"],     "#dc2626",     "#ffffff"),
        "warning":  (C["amber"],   "#d97706",     "#ffffff"),
        "ghost":    (C["card"],    C["card_hover"], C["muted"]),
        "outline":  ("transparent", C["card_hover"], C["accent"]),
    }
    fg, hover, tc = color_map.get(color, color_map["primary"])
    dim = {"small": (28, 10), "normal": (34, 12), "large": (38, 14)}
    h, cr = dim.get(size, dim["normal"])
    font = F["xs_b"] if size == "small" else F["sm_b"]
    border = 1 if color == "outline" else 0
    return ctk.CTkButton(parent, text=text, command=command,
        fg_color=fg, hover_color=hover, text_color=tc,
        font=font, corner_radius=cr, height=h,
        border_width=border, border_color=C["accent"] if border else None)

# ═══════════════════════════════════════════════════════════════
#  Form Input Helpers
# ═══════════════════════════════════════════════════════════════
def add_form_input(parent, label):
    lbl = ctk.CTkLabel(parent, text=label, font=F["sm_b"], text_color=C["muted"], anchor="w")
    lbl.pack(anchor='w', padx=16, pady=(12, 4))
    entry = ctk.CTkEntry(parent, fg_color=C["input"], border_color=C["border"],
        text_color=C["text"], font=F["sm"], corner_radius=8, height=38)
    entry.pack(fill='x', padx=16)
    return entry

def add_grid_input(parent, label, row, col):
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.grid(row=row, column=col, sticky='nsew', padx=6, pady=6)
    lbl = ctk.CTkLabel(frame, text=label, font=F["sm_b"], text_color=C["muted"], anchor="w")
    lbl.pack(anchor='w', pady=(0, 4))
    entry = ctk.CTkEntry(frame, fg_color=C["input"], border_color=C["border"],
        text_color=C["text"], font=F["sm"], corner_radius=8, height=38)
    entry.pack(fill='x')
    return entry

def add_section_divider(parent, text):
    f = ctk.CTkFrame(parent, fg_color="transparent")
    f.pack(fill='x', padx=16, pady=(20, 10))
    lbl = ctk.CTkLabel(f, text=text, font=F["h3"], text_color=C["accent"])
    lbl.pack(side='left')
    sep = ctk.CTkFrame(f, fg_color=C["border"], height=1, corner_radius=0)
    sep.pack(side='left', fill='x', expand=True, padx=(12, 0))

# Legacy compat
def enable_canvas_mousewheel(canvas):
    """No longer needed — CTkScrollableFrame handles scrolling natively"""
    pass

# ═══════════════════════════════════════════════════════════════
#  TagChipContainer — Premium Pill-Shaped Badges
# ═══════════════════════════════════════════════════════════════
class TagChipContainer(ctk.CTkFrame):
    def __init__(self, parent, initial_items, label_text, on_change_callback):
        super().__init__(parent, fg_color="transparent")
        self.items = list(initial_items)
        self.on_change = on_change_callback

        lbl = ctk.CTkLabel(self, text=label_text, font=F["sm_b"], text_color=C["muted"], anchor="w")
        lbl.pack(anchor='w', padx=16, pady=(10, 5))

        self.chips_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.chips_frame.pack(fill='x', padx=16, pady=3)

        self.entry = ctk.CTkEntry(self, placeholder_text="Type and press Enter...",
            fg_color=C["input"], border_color=C["border"], text_color=C["text"],
            font=F["sm"], corner_radius=8, height=36)
        self.entry.pack(fill='x', padx=16, pady=(4, 6))

        self.entry.bind("<Return>", self.add_item_event)
        self.entry.bind("<KeyPress-comma>", self.add_item_comma)
        self.redraw_chips()

    def redraw_chips(self):
        for widget in self.chips_frame.winfo_children():
            widget.destroy()
        row, col = 0, 0
        for item in self.items:
            chip = ctk.CTkButton(self.chips_frame,
                text=f" {item}  ✕", fg_color=C["chip"], hover_color=C["red"],
                text_color=C["chip_text"], font=F["xs_b"],
                corner_radius=14, height=28, width=0,
                command=lambda val=item: self.remove_item(val))
            chip.grid(row=row, column=col, padx=4, pady=4, sticky='w')
            col += 1
            if col >= 5:
                col = 0
                row += 1

    def add_item_event(self, event):
        self.add_item()
        return "break"

    def add_item_comma(self, event):
        self.after(10, self.add_item)
        return "break"

    def add_item(self):
        val = self.entry.get().replace(",", "").strip()
        if val and val not in self.items:
            self.items.append(val)
            self.redraw_chips()
            self.on_change(self.items)
        self.entry.delete(0, 'end')

    def remove_item(self, val):
        if val in self.items:
            self.items.remove(val)
            self.redraw_chips()
            self.on_change(self.items)

    def update_items(self, new_items):
        self.items = list(new_items)
        self.redraw_chips()
