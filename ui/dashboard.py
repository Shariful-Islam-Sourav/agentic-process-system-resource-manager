"""
ui/dashboard.py

Phase 4 — Main Dashboard
────────────────────────────────────
Assembles all widgets into a full-window CustomTkinter dashboard.
Polls the SystemMonitor queue every 500 ms and pushes updates to
all child widgets without blocking the UI thread.
"""

import os
import platform
import socket
from datetime import datetime
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk
import psutil

from modules.system_monitor import SystemMonitor, SystemSnapshot
from modules.process_analyzer import ProcessAnalyzer
from modules.decision_engine import DecisionEngine, Recommendation
from modules.report_generator import ReportGenerator
from ui.theme import COLORS
from ui.widgets.gauge_widget import GaugeWidget
from ui.widgets.history_chart import HistoryChart
from ui.widgets.process_table import ProcessTable
from ui.widgets.recommendation_panel import RecommendationPanel


# ── Dashboard ─────────────────────────────────────────────────────────────────

class Dashboard(ctk.CTkFrame):
    """
    Root dashboard frame.
    Layout (top → bottom):
      Header → [Gauges | Health + Net] → History Chart
           → [Process Table | Recommendations] → Footer
    """

    POLL_MS = 500   # UI polling interval (ms)

    def __init__(self, master):
        super().__init__(master,
                         fg_color=COLORS["bg_primary"],
                         corner_radius=0)

        # ── Backend ───────────────────────────────────────────────────────────
        self._monitor  = SystemMonitor(interval=2.0)
        self._analyzer = ProcessAnalyzer(top_n=20)
        self._engine   = DecisionEngine()
        self._reporter = ReportGenerator(report_dir="reports")

        # State
        self._last_snapshot: Optional[SystemSnapshot] = None
        self._last_analysis: Optional[dict]           = None
        self._last_recs: Optional[list]               = None
        self._auto_refresh = True

        # ── UI ────────────────────────────────────────────────────────────────
        self._build_ui()

        # Start monitoring and first poll
        self._monitor.start()
        self._poll()

    # ══════════════════════════════════════════════════════════════════════════
    # BUILD
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        self._build_header()
        self._build_footer()   # must pack BEFORE body so expand=True doesn't eat it
        self._build_body()

    # ── Header ─────────────────────────────────────────────────────────────────

    def _build_header(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"],
                           corner_radius=0, height=68)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Left: icon + titles
        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", padx=18, pady=8)

        ctk.CTkLabel(left, text="⚡", font=("Segoe UI", 30)).pack(side="left", padx=(0, 12))

        txt = ctk.CTkFrame(left, fg_color="transparent")
        txt.pack(side="left")

        ctk.CTkLabel(
            txt,
            text="Smart Process & Resource Management Agent",
            font=("Segoe UI", 15, "bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w")

        try:
            hostname  = socket.gethostname()
            os_name   = f"{platform.system()} {platform.release()}"
            cores_l   = psutil.cpu_count(logical=True)
            cores_p   = psutil.cpu_count(logical=False)
            total_ram = psutil.virtual_memory().total / (1024 ** 3)
            sub_info  = (
                f"{hostname}  •  {os_name}  •  "
                f"{cores_p}C / {cores_l}T  •  {total_ram:.1f} GB RAM"
            )
        except Exception:
            sub_info = platform.system()

        ctk.CTkLabel(
            txt,
            text=sub_info,
            font=("Segoe UI", 9),
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w")

        # Right: status + clock
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right", padx=18)

        self._status_dot = ctk.CTkLabel(
            right, text="●", font=("Segoe UI", 13),
            text_color=COLORS["accent_green"],
        )
        self._status_dot.pack(side="left")

        self._status_lbl = ctk.CTkLabel(
            right, text="  LIVE MONITORING",
            font=("Segoe UI", 10, "bold"),
            text_color=COLORS["accent_green"],
        )
        self._status_lbl.pack(side="left", padx=(0, 20))

        self._clock_lbl = ctk.CTkLabel(
            right, text="",
            font=("Consolas", 14),
            text_color=COLORS["text_secondary"],
        )
        self._clock_lbl.pack(side="left")
        self._tick_clock()

    def _tick_clock(self) -> None:
        self._clock_lbl.configure(text=datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._tick_clock)

    # ── Body ──────────────────────────────────────────────────────────────────

    def _build_body(self) -> None:
        # Scrollable body so the user can reach the process table
        # even on smaller screens
        body = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["bg_primary"],
            corner_radius=0,
            scrollbar_button_color=COLORS["bg_card"],
            scrollbar_button_hover_color=COLORS["accent_cyan"],
        )
        body.pack(fill="both", expand=True)
        self._body = body

        self._build_top_row(body)
        self._build_chart_row(body)
        self._build_bottom_row(body)

    # ── Top row: Gauges + Health + Network ───────────────────────────────────

    def _build_top_row(self, parent) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(10, 5))

        # Three gauges
        gauge_wrap = ctk.CTkFrame(row, fg_color="transparent")
        gauge_wrap.pack(side="left")

        self._cpu_gauge = GaugeWidget(
            gauge_wrap, label="CPU", unit="%",
            color=COLORS["accent_cyan"], size=158,
        )
        self._cpu_gauge.pack(side="left", padx=5)

        self._mem_gauge = GaugeWidget(
            gauge_wrap, label="MEMORY", unit="%",
            color=COLORS["accent_purple"], size=158,
        )
        self._mem_gauge.pack(side="left", padx=5)

        self._disk_gauge = GaugeWidget(
            gauge_wrap, label="DISK", unit="%",
            color=COLORS["accent_green"], size=158,
        )
        self._disk_gauge.pack(side="left", padx=5)

        # Right-side info cards
        info_wrap = ctk.CTkFrame(row, fg_color="transparent")
        info_wrap.pack(side="right", fill="both", expand=True, padx=(10, 0))

        self._health_card = self._make_health_card(info_wrap)
        self._health_card.pack(side="left", fill="both", expand=True, padx=5)

        self._net_card = self._make_net_card(info_wrap)
        self._net_card.pack(side="left", fill="both", expand=True, padx=5)

    def _make_health_card(self, parent) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=14)

        ctk.CTkLabel(
            card, text="🏥  System Health",
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"],
        ).pack(pady=(16, 4))

        self._health_score_lbl = ctk.CTkLabel(
            card, text="—",
            font=("Segoe UI", 46, "bold"),
            text_color=COLORS["accent_green"],
        )
        self._health_score_lbl.pack()

        ctk.CTkLabel(
            card, text="/ 100",
            font=("Segoe UI", 12),
            text_color=COLORS["text_secondary"],
        ).pack()

        self._health_status_lbl = ctk.CTkLabel(
            card, text="INITIALISING",
            font=("Segoe UI", 11, "bold"),
            text_color=COLORS["text_muted"],
        )
        self._health_status_lbl.pack(pady=(6, 10))

        self._health_bar = ctk.CTkProgressBar(
            card, height=8, corner_radius=4,
            progress_color=COLORS["accent_green"],
        )
        self._health_bar.pack(fill="x", padx=18, pady=(0, 16))
        self._health_bar.set(0)

        return card

    def _make_net_card(self, parent) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=14)

        ctk.CTkLabel(
            card, text="🌐  Network & Memory",
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"],
        ).pack(pady=(16, 8))

        def _stat_row(label, color, attr_name):
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=2)
            ctk.CTkLabel(row, text=label,
                         font=("Segoe UI", 10),
                         text_color=color).pack(side="left")
            lbl = ctk.CTkLabel(row, text="—",
                                font=("Consolas", 11, "bold"),
                                text_color=COLORS["text_primary"])
            lbl.pack(side="right")
            setattr(self, attr_name, lbl)

        _stat_row("▲  Upload",   COLORS["accent_orange"], "_net_up_lbl")
        _stat_row("▼  Download", COLORS["accent_cyan"],   "_net_dn_lbl")

        ctk.CTkFrame(card, height=1, fg_color=COLORS["border"]).pack(
            fill="x", padx=16, pady=8)

        ctk.CTkLabel(
            card, text="💾  Memory Details",
            font=("Segoe UI", 10, "bold"),
            text_color=COLORS["text_secondary"],
        ).pack(pady=(0, 4))

        _stat_row("RAM",       COLORS["text_secondary"], "_mem_detail_lbl")
        _stat_row("Swap",      COLORS["text_secondary"], "_swap_lbl")
        _stat_row("Processes", COLORS["text_secondary"], "_proc_cnt_lbl")

        ctk.CTkFrame(card, height=10, fg_color="transparent").pack()
        return card

    # ── Chart row ─────────────────────────────────────────────────────────────

    def _build_chart_row(self, parent) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=5)

        self._chart = HistoryChart(row)
        self._chart.pack(fill="x")

    # ── Bottom row: Process table + Recommendations ───────────────────────────

    def _build_bottom_row(self, parent) -> None:
        # Fixed height needed inside CTkScrollableFrame (expand=True collapses there)
        row = ctk.CTkFrame(parent, fg_color="transparent", height=480)
        row.pack(fill="x", padx=14, pady=(5, 10))
        row.pack_propagate(False)

        # ── Process table panel ───────────────────────────────────────────────
        proc_panel = ctk.CTkFrame(row, fg_color=COLORS["bg_card"], corner_radius=14)
        proc_panel.pack(side="left", fill="both", expand=True, padx=(0, 5))

        ph = ctk.CTkFrame(proc_panel, fg_color="transparent")
        ph.pack(fill="x", padx=14, pady=(12, 0))

        ctk.CTkLabel(
            ph, text="⚙️  Process Monitor",
            font=("Segoe UI", 13, "bold"),
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        self._proc_count_badge = ctk.CTkLabel(
            ph, text="",
            font=("Segoe UI", 10),
            text_color=COLORS["text_secondary"],
        )
        self._proc_count_badge.pack(side="right")

        self._proc_table = ProcessTable(proc_panel, on_kill=self._on_kill)
        self._proc_table.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Recommendations panel ─────────────────────────────────────────────
        rec_panel = ctk.CTkFrame(row, fg_color=COLORS["bg_card"],
                                 corner_radius=14, width=368)
        rec_panel.pack(side="right", fill="both", padx=(5, 0))
        rec_panel.pack_propagate(False)

        rh = ctk.CTkFrame(rec_panel, fg_color="transparent")
        rh.pack(fill="x", padx=14, pady=(12, 0))

        ctk.CTkLabel(
            rh, text="🤖  Agent Recommendations",
            font=("Segoe UI", 13, "bold"),
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        self._rec_badge = ctk.CTkLabel(
            rh, text="",
            font=("Segoe UI", 10),
            text_color=COLORS["text_secondary"],
        )
        self._rec_badge.pack(side="right")

        self._rec_panel = RecommendationPanel(rec_panel, on_kill=self._on_kill)
        self._rec_panel.pack(fill="both", expand=True, padx=8, pady=8)


    # ── Footer ─────────────────────────────────────────────────────────────────

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"],
                              corner_radius=0, height=46)
        footer.pack(fill="x", side="bottom")   # side=bottom keeps it always visible
        footer.pack_propagate(False)

        # Left: last update
        left = ctk.CTkFrame(footer, fg_color="transparent")
        left.pack(side="left", padx=18, pady=8)

        self._last_update_lbl = ctk.CTkLabel(
            left, text="Waiting for data…",
            font=("Segoe UI", 10),
            text_color=COLORS["text_muted"],
        )
        self._last_update_lbl.pack(side="left")

        # Right: controls
        right = ctk.CTkFrame(footer, fg_color="transparent")
        right.pack(side="right", padx=18, pady=6)

        ctk.CTkButton(
            right, text="📄  Generate Report",
            width=155, height=32,
            font=("Segoe UI", 11),
            fg_color=COLORS["accent_purple"],
            hover_color="#6A50EF",
            corner_radius=8,
            command=self._generate_report,
        ).pack(side="right", padx=6)

        self._auto_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            right, text="Auto Refresh",
            variable=self._auto_var,
            font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"],
            fg_color=COLORS["accent_cyan"],
            hover_color=COLORS["accent_purple"],
            command=self._toggle_auto,
        ).pack(side="right", padx=14)

        ctk.CTkButton(
            right, text="🔄  Refresh Now",
            width=130, height=32,
            font=("Segoe UI", 11),
            fg_color="#1A2035",
            hover_color="#242D45",
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
            command=lambda: None,   # monitor pushes data automatically
        ).pack(side="right", padx=6)

    # ══════════════════════════════════════════════════════════════════════════
    # POLL & UPDATE
    # ══════════════════════════════════════════════════════════════════════════

    def _poll(self) -> None:
        """Drain the monitor queue and refresh UI on every new snapshot."""
        if self._auto_refresh:
            latest = None
            try:
                while True:
                    latest = self._monitor.data_queue.get_nowait()
            except Exception:
                pass
            if latest:
                self._refresh(latest)

        self.after(self.POLL_MS, self._poll)

    def _refresh(self, snapshot: SystemSnapshot) -> None:
        self._last_snapshot = snapshot
        analysis            = self._analyzer.analyze(snapshot)
        recs                = self._engine.analyze(snapshot)
        health              = self._engine.compute_health_score(snapshot)

        self._last_analysis = analysis
        self._last_recs     = recs

        # Reporter history
        self._reporter.add_snapshot(snapshot)

        # Gauges
        self._cpu_gauge.set_value(
            snapshot.cpu_percent,
            f"{snapshot.cpu_freq_mhz:.0f} MHz",
        )
        self._mem_gauge.set_value(
            snapshot.memory_percent,
            f"{snapshot.memory_used_gb:.1f} / {snapshot.memory_total_gb:.1f} GB",
        )
        self._disk_gauge.set_value(
            snapshot.disk_percent,
            f"{snapshot.disk_free_gb:.1f} GB free",
        )

        # Health card
        self._update_health(health)

        # Network & memory card
        self._net_up_lbl.configure(text=self._fmt_net(snapshot.net_bytes_sent))
        self._net_dn_lbl.configure(text=self._fmt_net(snapshot.net_bytes_recv))
        self._mem_detail_lbl.configure(
            text=f"{snapshot.memory_used_gb:.1f} / {snapshot.memory_total_gb:.1f} GB"
        )
        self._swap_lbl.configure(text=f"{snapshot.swap_percent:.1f}%")
        self._proc_cnt_lbl.configure(text=str(analysis["total_count"]))

        # History chart
        self._chart.update_data(
            snapshot.cpu_percent,
            snapshot.memory_percent,
            snapshot.disk_percent,
        )

        # Process table
        self._proc_table.update_processes(analysis["all_by_cpu"])
        self._proc_count_badge.configure(
            text=f"{analysis['total_count']} processes"
        )

        # Recommendations
        self._rec_panel.update_recommendations(recs)
        crits = sum(1 for r in recs if r.severity == "CRITICAL")
        warns = sum(1 for r in recs if r.severity == "WARNING")
        parts = []
        if crits:
            parts.append(f"{crits} critical")
        if warns:
            parts.append(f"{warns} warning")
        self._rec_badge.configure(text="  ".join(parts))

        # Footer timestamp
        self._last_update_lbl.configure(
            text=f"Last update: {datetime.now().strftime('%H:%M:%S')}"
        )

    def _update_health(self, score: int) -> None:
        if score >= 80:
            color, label = COLORS["accent_green"],  "EXCELLENT"
        elif score >= 60:
            color, label = COLORS["accent_amber"],  "GOOD"
        elif score >= 40:
            color, label = COLORS["accent_orange"], "FAIR"
        else:
            color, label = COLORS["accent_red"],    "POOR — ACTION NEEDED"

        self._health_score_lbl.configure(text=str(score), text_color=color)
        self._health_status_lbl.configure(text=label, text_color=color)
        self._health_bar.configure(progress_color=color)
        self._health_bar.set(score / 100)

    @staticmethod
    def _fmt_net(kbps: float) -> str:
        if kbps >= 1024:
            return f"{kbps / 1024:.1f} MB/s"
        return f"{kbps:.1f} KB/s"

    # ══════════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def _toggle_auto(self) -> None:
        self._auto_refresh = self._auto_var.get()

    def _on_kill(self, pid: int, name: str) -> None:
        """Show a confirmation dialog then terminate the selected process."""
        dlg = _KillDialog(self, pid=pid, name=name)
        self.wait_window(dlg)
        if not dlg.confirmed:
            return
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            messagebox.showinfo(
                "Process Terminated",
                f"'{name}' (PID {pid}) has been terminated.",
            )
        except psutil.NoSuchProcess:
            messagebox.showwarning(
                "Not Found",
                f"Process '{name}' (PID {pid}) no longer exists.",
            )
        except psutil.AccessDenied:
            messagebox.showerror(
                "Access Denied",
                f"Cannot terminate '{name}'.\nTry running the application as Administrator.",
            )
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to terminate process:\n{exc}")

    def _generate_report(self) -> None:
        if not (self._last_snapshot and self._last_analysis and self._last_recs):
            messagebox.showwarning(
                "No Data",
                "Waiting for system data.\nPlease wait a moment and try again.",
            )
            return
        try:
            path = self._reporter.generate_report(
                self._last_snapshot,
                self._last_recs,
                self._last_analysis,
            )
            messagebox.showinfo(
                "Report Saved",
                f"Report saved successfully:\n\n{path}",
            )
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to generate report:\n{exc}")

    # ── Cleanup ────────────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        """Stop background threads before window closes."""
        self._monitor.stop()


# ══════════════════════════════════════════════════════════════════════════════
# Kill Confirmation Dialog
# ══════════════════════════════════════════════════════════════════════════════

class _KillDialog(ctk.CTkToplevel):
    """Modal confirmation dialog for process termination."""

    def __init__(self, parent, pid: int, name: str):
        super().__init__(parent)
        self.confirmed = False
        self.title("Confirm Termination")
        self.geometry("420x230")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg_card"])
        self.grab_set()
        self.lift()
        self.focus_force()

        ctk.CTkLabel(self, text="⚠️", font=("Segoe UI", 36)).pack(pady=(18, 4))

        ctk.CTkLabel(
            self,
            text="Terminate Process?",
            font=("Segoe UI", 16, "bold"),
            text_color=COLORS["text_primary"],
        ).pack()

        ctk.CTkLabel(
            self,
            text=f"{name}\nPID: {pid}\n\nThis will force-close the process.",
            font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"],
            justify="center",
        ).pack(pady=8)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=8)

        ctk.CTkButton(
            btn_row, text="Cancel",
            width=120, height=36,
            fg_color="#1A2035", hover_color="#242D45",
            font=("Segoe UI", 12),
            corner_radius=8,
            command=self.destroy,
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_row, text="Kill Process",
            width=120, height=36,
            fg_color=COLORS["accent_red"],
            hover_color="#D93040",
            font=("Segoe UI", 12, "bold"),
            corner_radius=8,
            command=self._confirm,
        ).pack(side="left", padx=10)

    def _confirm(self) -> None:
        self.confirmed = True
        self.destroy()
