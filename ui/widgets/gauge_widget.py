"""
ui/widgets/gauge_widget.py

Animated circular arc gauge built with tkinter.Canvas.
Displays a percentage value with a colour-coded fill arc that
smoothly animates toward the target value at ~60 fps.
"""

import customtkinter as ctk
import tkinter as tk
from ui.theme import COLORS


class GaugeWidget(ctk.CTkFrame):
    """
    Speedometer-style circular gauge.

    Arc sweeps 270° clockwise from the bottom-left to the bottom-right.
    Colour transitions:
      0–59 %  → green   (#00FF88)
      60–79 % → amber   (#FFB700)
      80–100% → red     (#FF4757)
    """

    # Arc geometry (tkinter Canvas angles: 0=east, counterclockwise positive)
    _ARC_START   = 225    # bottom-left in standard Tkinter coords
    _ARC_TOTAL   = 270    # total sweep (clockwise, so we use negative extent)

    def __init__(
        self,
        master,
        label: str = "CPU",
        unit: str = "%",
        color: str = COLORS["accent_cyan"],
        size: int = 160,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self._label_text = label
        self._unit       = unit
        self._accent     = color     # default accent (unused for arc, kept for glows)
        self._size       = size
        self._current    = 0.0
        self._target     = 0.0
        self._animating  = False

        self.configure(fg_color=COLORS["bg_card"], corner_radius=16)

        # Canvas for the arc graphic
        self._canvas = tk.Canvas(
            self, width=size, height=size,
            bg=COLORS["bg_card"], highlightthickness=0,
        )
        self._canvas.pack(pady=(12, 2))

        # Subtitle label (e.g. "4.2 / 8.0 GB")
        self._sub_label = ctk.CTkLabel(
            self, text="",
            font=("Segoe UI", 9),
            text_color=COLORS["text_secondary"],
        )
        self._sub_label.pack(pady=(0, 12))

        self._render(0.0)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_value(self, value: float, sub_text: str = "") -> None:
        """Set target percentage and optional sub-label text."""
        self._target = max(0.0, min(100.0, float(value)))
        if sub_text:
            self._sub_label.configure(text=sub_text)
        if not self._animating:
            self._tick()

    # ── Animation ─────────────────────────────────────────────────────────────

    def _tick(self) -> None:
        diff = self._target - self._current
        if abs(diff) < 0.3:
            self._current = self._target
            self._render(self._current)
            self._animating = False
            return
        self._animating = True
        self._current += diff * 0.22      # easing coefficient
        self._render(self._current)
        self.after(16, self._tick)        # ~60 fps

    # ── Drawing ───────────────────────────────────────────────────────────────

    @staticmethod
    def _value_color(v: float) -> str:
        if v < 60:
            return "#00FF88"
        if v < 80:
            return "#FFB700"
        return "#FF4757"

    def _render(self, value: float) -> None:
        c = self._canvas
        c.delete("all")

        s = self._size
        cx, cy = s // 2, s // 2
        r      = s // 2 - 20
        x0, y0, x1, y1 = cx - r, cy - r, cx + r, cy + r

        color = self._value_color(value)

        # ── Background track (two rings for depth) ────────────────────────────
        c.create_arc(
            x0 - 2, y0 - 2, x1 + 2, y1 + 2,
            start=self._ARC_START, extent=-self._ARC_TOTAL,
            style=tk.ARC, outline="#151E30", width=14,
        )
        c.create_arc(
            x0, y0, x1, y1,
            start=self._ARC_START, extent=-self._ARC_TOTAL,
            style=tk.ARC, outline="#1E2A3A", width=10,
        )

        # ── Filled arc ────────────────────────────────────────────────────────
        if value > 0.3:
            extent = -self._ARC_TOTAL * (value / 100.0)
            # Outer glow
            c.create_arc(
                x0 - 1, y0 - 1, x1 + 1, y1 + 1,
                start=self._ARC_START, extent=extent,
                style=tk.ARC, outline=color, width=14,
            )
            # Core line
            c.create_arc(
                x0, y0, x1, y1,
                start=self._ARC_START, extent=extent,
                style=tk.ARC, outline=color, width=9,
            )

        # ── Value text (large number, centred) ────────────────────────────────
        # Positioned slightly above centre so unit text fits below without overlap
        c.create_text(
            cx, cy - 10,
            text=f"{value:.1f}",
            font=("Segoe UI", 19, "bold"),
            fill="#E8EAF0",
        )

        # ── Unit label (%, below the number) ─────────────────────────────────
        c.create_text(
            cx, cy + 16,
            text=self._unit,
            font=("Segoe UI", 10),
            fill=color if value > 0.3 else "#8892A4",
        )

        # ── Metric name at the very bottom of the canvas ──────────────────────
        c.create_text(
            cx, s - 6,
            text=self._label_text,
            font=("Segoe UI", 9, "bold"),
            fill="#8892A4",
        )

