import tkinter as tk
from tkinter import ttk

# Reusable UI widgets and layout handlers
def make_btn_interactive(btn, bg_normal, bg_hover, fg_normal, fg_hover):
    btn.config(bg=bg_normal, fg=fg_normal, activebackground=bg_hover, activeforeground=fg_hover, relief='flat', bd=0, cursor='hand2')
    btn.bind("<Enter>", lambda e: btn.config(bg=bg_hover, fg=fg_hover))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg_normal, fg=fg_normal))

def enable_canvas_mousewheel(canvas):
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
    def bind_tree(widget):
        widget.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        widget.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        for child in widget.winfo_children():
            bind_tree(child)
            
    bind_tree(canvas)

def add_form_input(parent, label):
    lbl = ttk.Label(parent, text=label, style='Card.TLabel')
    lbl.config(font=('Segoe UI', 9, 'bold'), foreground='#94a3b8')
    lbl.pack(anchor='w', pady=(12, 4))
    
    entry = tk.Entry(parent, bg="#080c14", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#1f2937", font=('Segoe UI', 10))
    entry.pack(fill='x', ipady=8)
    
    entry.bind("<FocusIn>", lambda e: entry.config(highlightbackground="#2563eb", highlightcolor="#2563eb"))
    entry.bind("<FocusOut>", lambda e: entry.config(highlightbackground="#1f2937", highlightcolor="#1f2937"))
    return entry

def add_grid_input(parent, label, row, col):
    frame = ttk.Frame(parent)
    frame.grid(row=row, column=col, sticky='nsew', padx=10, pady=8)
    
    lbl = ttk.Label(frame, text=label, style='Card.TLabel')
    lbl.config(font=('Segoe UI', 9, 'bold'), foreground='#94a3b8')
    lbl.pack(anchor='w', pady=(0, 4))
    
    entry = tk.Entry(frame, bg="#080c14", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#1f2937", font=('Segoe UI', 10))
    entry.pack(fill='x', ipady=8)
    
    entry.bind("<FocusIn>", lambda e: entry.config(highlightbackground="#2563eb", highlightcolor="#2563eb"))
    entry.bind("<FocusOut>", lambda e: entry.config(highlightbackground="#1f2937", highlightcolor="#1f2937"))
    return entry

class TagChipContainer(ttk.Frame):
    def __init__(self, parent, initial_items, label_text, on_change_callback):
        super().__init__(parent, style='Card.TFrame')
        self.items = list(initial_items)
        self.on_change = on_change_callback
        
        lbl = ttk.Label(self, text=label_text, style='Card.TLabel')
        lbl.config(font=('Segoe UI', 9, 'bold'), foreground='#94a3b8')
        lbl.pack(anchor='w', pady=(10, 4))
        
        self.chips_frame = ttk.Frame(self, style='Card.TFrame')
        self.chips_frame.pack(fill='x', pady=2)
        
        self.entry = tk.Entry(self, bg="#080c14", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#1f2937", font=('Segoe UI', 10))
        self.entry.pack(fill='x', ipady=7, pady=(4, 8))
        
        self.entry.bind("<Return>", self.add_item_event)
        self.entry.bind("<KeyPress-comma>", self.add_item_comma)
        
        self.entry.bind("<FocusIn>", lambda e: self.entry.config(highlightbackground="#2563eb", highlightcolor="#2563eb"))
        self.entry.bind("<FocusOut>", lambda e: self.entry.config(highlightbackground="#1f2937", highlightcolor="#1f2937"))
        
        self.redraw_chips()
        
    def redraw_chips(self):
        for widget in self.chips_frame.winfo_children():
            widget.destroy()
            
        row, col = 0, 0
        max_cols = 4
        
        for item in self.items:
            chip = tk.Frame(self.chips_frame, bg="#2563eb", padx=8, pady=4)
            chip.grid(row=row, column=col, padx=4, pady=4, sticky='w')
            
            lbl_val = tk.Label(chip, text=item, bg="#2563eb", fg="white", font=('Segoe UI', 9, 'bold'))
            lbl_val.pack(side='left')
            
            btn_del = tk.Button(chip, text="×", bg="#2563eb", fg="white", activebackground="#ef4444", activeforeground="white", font=('Segoe UI', 9, 'bold'), bd=0, relief='flat', cursor='hand2', command=lambda val=item: self.remove_item(val))
            btn_del.pack(side='left', padx=(6, 0))
            
            col += 1
            if col >= max_cols:
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
