# Backward-compatibility launcher pointing to the new modular entry point
from ui.app_window import AppWindow

if __name__ == "__main__":
    app = AppWindow()
    app.mainloop()
