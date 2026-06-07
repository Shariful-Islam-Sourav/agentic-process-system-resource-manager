"""
ui/widgets/recommendation_panel.py

Scrollable panel of colour-coded recommendation cards.
Each card includes a severity border, title, message, action text,
and an optional "Kill Process" button when a PID is associated.
"""

import customtkinter as ctk
from typing import List, Callable, Optional

from modules.decision_engine import Recommendation
from ui.theme import COLORS, SEVERITY_COLORS, SEVERITY_BG


class RecommendationPanel(ctk.CTkScrollableFrame):
    """
    Displays a scrollable list of Recommendation cards.
    Cards are rebuilt on each update call.
    """

    def __init__(
        self,
        master,
        on_kill: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._on_kill = on_kill

    # ── Public API ─────────────────────────────────────────────────────────────

    def update_recommendations(self, recommendations: List[Recommendation]) -> None:
        """Rebuild all recommendation cards."""
        for widget in self.winfo_children():
            widget.destroy()

        for rec in recommendations:
            self._make_card(rec).pack(fill="x", pady=3)

        if not recommendations:
            ctk.CTkLabel(
                self,
                text="No active recommendations.",
                font=("Segoe UI", 11),
                text_color=COLORS["text_muted"],
            ).pack(pady=20)

    # ── Card Builder ───────────────────────────────────────────────────────────

    def _make_card(self, rec: Recommendation) -> ctk.CTkFrame:
        sev_color = SEVERITY_COLORS.get(rec.severity, COLORS["accent_cyan"])
        bg_color  = SEVERITY_BG.get(rec.severity, "#0D1E2E")

        card = ctk.CTkFrame(self, fg_color=bg_color, corner_radius=10)

        # Left accent bar
        accent = ctk.CTkFrame(card, fg_color=sev_color, width=4, corner_radius=2)
        accent.pack(side="left", fill="y", padx=(6, 10), pady=8)
        accent.pack_propagate(False)

        # Content area
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, pady=8)

        # ── Header row ────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(body, fg_color="transparent")
        hdr.pack(fill="x")

        ctk.CTkLabel(
            hdr,
            text=rec.title,
            font=("Segoe UI", 11, "bold"),
            text_color=sev_color,
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        # Severity badge
        ctk.CTkLabel(
            hdr,
            text=f" {rec.severity} ",
            font=("Segoe UI", 8, "bold"),
            text_color=sev_color,
            fg_color="#0A0E1A",
            corner_radius=4,
        ).pack(side="right", padx=(4, 10))

        # ── Category tag ──────────────────────────────────────────────────────
        ctk.CTkLabel(
            body,
            text=f"Category: {rec.category}",
            font=("Segoe UI", 8),
            text_color=COLORS["text_muted"],
            anchor="w",
        ).pack(fill="x", pady=(0, 1))

        # ── Message ───────────────────────────────────────────────────────────
        ctk.CTkLabel(
            body,
            text=rec.message,
            font=("Segoe UI", 10),
            text_color=COLORS["text_secondary"],
            anchor="w",
            wraplength=290,
            justify="left",
        ).pack(fill="x")

        # ── Action ────────────────────────────────────────────────────────────
        ctk.CTkLabel(
            body,
            text=f"→  {rec.action}",
            font=("Segoe UI", 9),
            text_color=COLORS["text_muted"],
            anchor="w",
            wraplength=290,
            justify="left",
        ).pack(fill="x", pady=(2, 0))

        # ── Kill button (if severity warrants and PID is known) ───────────────
        if rec.pid and self._on_kill and rec.severity in ("WARNING", "CRITICAL"):
            pid  = rec.pid
            name = rec.proc_name or "Process"

            ctk.CTkButton(
                body,
                text=f"🔴  Kill  PID {pid}",
                width=120, height=24,
                font=("Segoe UI", 9, "bold"),
                fg_color="#200A0B",
                hover_color="#FF4757",
                text_color="#FF4757",
                corner_radius=6,
                border_width=1,
                border_color="#FF4757",
                command=lambda p=pid, n=name: self._on_kill(p, n),
            ).pack(anchor="w", pady=(5, 0))

        return card
