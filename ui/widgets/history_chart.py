"""
ui/widgets/history_chart.py

Rolling line chart built with tkinter.Canvas.
Displays the last 60 data points for CPU, Memory, and Disk.
No external charting libraries required.
"""

import customtkinter as ctk
import tkinter as tk
from collections import deque
from ui.theme import COLORS


class HistoryChart(ctk.CTkFrame):
    """
    60-second rolling resource history chart.

    Three lines are drawn:
      • CPU    — cyan   (#00D4FF)
      • Memory — purple (#7B61FF)
      • Disk   — green  (#00FF88)

    Grid lines, Y-axis labels, and a legend are included.
    """

    MAX_POINTS = 60

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color=COLORS["bg_card"], corner_radius=12)

        self._cpu_hist  = deque([0.0] * self.MAX_POINTS, maxlen=self.MAX_POINTS)
        self._mem_hist  = deque([0.0] * self.MAX_POINTS, maxlen=self.MAX_POINTS)
        self._disk_hist = deque([0.0] * self.MAX_POINTS, maxlen=self.MAX_POINTS)

        self._cw = 600
        self._ch = 120

        self._setup_widgets()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _setup_widgets(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=15, pady=(10, 2))

        ctk.CTkLabel(
            hdr, text="📈  Resource History  (last 60 s)",
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        # Legend
        legend = ctk.CTkFrame(hdr, fg_color="transparent")
        legend.pack(side="right")
        for label, color in [
            ("CPU",    "#00D4FF"),
            ("Memory", "#7B61FF"),
            ("Disk",   "#00FF88"),
        ]:
            dot = tk.Canvas(
                legend, width=10, height=10,
                bg=COLORS["bg_card"], highlightthickness=0,
            )
            dot.create_oval(1, 1, 9, 9, fill=color, outline="")
            dot.pack(side="left", padx=(8, 2))
            ctk.CTkLabel(
                legend, text=label,
                font=("Segoe UI", 9),
                text_color=COLORS["text_secondary"],
            ).pack(side="left", padx=(0, 4))

        self._canvas = tk.Canvas(
            self, bg=COLORS["bg_card"], highlightthickness=0,
            height=130,
        )
        self._canvas.pack(fill="both", expand=True, padx=15, pady=(0, 12))
        self._canvas.bind("<Configure>", self._on_canvas_resize)

    # ── Public API ─────────────────────────────────────────────────────────────

    def update_data(self, cpu: float, memory: float, disk: float) -> None:
        self._cpu_hist.append(cpu)
        self._mem_hist.append(memory)
        self._disk_hist.append(disk)
        self._paint()

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _on_canvas_resize(self, event) -> None:
        self._cw = event.width
        self._ch = event.height
        self._paint()

    def _paint(self) -> None:
        c = self._canvas
        c.delete("all")

        w, h = self._cw, self._ch
        pl, pr, pt, pb = 44, 12, 8, 22        # padding left/right/top/bottom
        chart_w = w - pl - pr
        chart_h = h - pt - pb

        if chart_w < 20 or chart_h < 20:
            return

        # ── Grid & Y-axis labels ──────────────────────────────────────────────
        for pct in (0, 25, 50, 75, 100):
            y = pt + chart_h - (pct / 100) * chart_h
            c.create_line(pl, y, pl + chart_w, y,
                          fill="#1E2A3A", width=1, dash=(4, 6))
            c.create_text(pl - 5, y, text=f"{pct}%",
                          font=("Consolas", 7), fill="#4A5568", anchor="e")

        # ── Chart border ──────────────────────────────────────────────────────
        c.create_rectangle(pl, pt, pl + chart_w, pt + chart_h,
                           outline="#1E2A3A", fill="")

        # ── Dataset lines ─────────────────────────────────────────────────────
        datasets = [
            (self._cpu_hist,  "#00D4FF", 2),
            (self._mem_hist,  "#7B61FF", 2),
            (self._disk_hist, "#00FF88", 1),
        ]

        n = self.MAX_POINTS
        for hist, color, lw in datasets:
            data = list(hist)
            if len(data) < 2:
                continue

            pts = []
            for i, val in enumerate(data):
                x = pl + (i / (n - 1)) * chart_w
                y = pt + chart_h - (val / 100) * chart_h
                pts.append((x, y))

            # Subtle area fill
            fill_poly = [(pl, pt + chart_h)] + pts + [(pl + chart_w, pt + chart_h)]
            flat = [coord for p in fill_poly for coord in p]
            if len(flat) >= 6:
                c.create_polygon(flat, fill=color, stipple="gray12", outline="")

            # Lines
            for i in range(len(pts) - 1):
                c.create_line(
                    pts[i][0], pts[i][1],
                    pts[i + 1][0], pts[i + 1][1],
                    fill=color, width=lw, smooth=True,
                )

            # Latest value dot
            if pts:
                lx, ly = pts[-1]
                c.create_oval(lx - 3, ly - 3, lx + 3, ly + 3,
                              fill=color, outline=COLORS["bg_card"], width=2)

        # ── X-axis labels ─────────────────────────────────────────────────────
        c.create_text(pl + 2, h - 4,
                      text="60 s ago", font=("Segoe UI", 7),
                      fill="#4A5568", anchor="w")
        c.create_text(pl + chart_w, h - 4,
                      text="now", font=("Segoe UI", 7),
                      fill="#4A5568", anchor="e")
