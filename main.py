"""
main.py — Entry point

Smart Process & Resource Management Agent
──────────────────────────────────────────
Initialises the CustomTkinter application, applies the dark theme,
creates the Dashboard, and starts the main event loop.
"""

import sys
import os

# Ensure project root is on the module search path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk
from ui.dashboard import Dashboard


def main() -> None:
    # ── Appearance ────────────────────────────────────────────────────────────
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    # ── Root Window ───────────────────────────────────────────────────────────
    app = ctk.CTk()
    app.title("Smart Process & Resource Management Agent")
    app.geometry("1300x840")
    app.minsize(1100, 740)
    app.configure(fg_color="#0A0E1A")

    # ── Dashboard ─────────────────────────────────────────────────────────────
    dashboard = Dashboard(app)
    dashboard.pack(fill="both", expand=True)

    # ── Graceful close ────────────────────────────────────────────────────────
    def _on_close() -> None:
        dashboard.cleanup()
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", _on_close)

    # ── Event loop ────────────────────────────────────────────────────────────
    app.mainloop()


if __name__ == "__main__":
    main()
