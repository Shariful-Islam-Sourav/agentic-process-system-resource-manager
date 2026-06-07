"""
ui/widgets/process_table.py

Sortable, colour-coded process table using ttk.Treeview styled to
match the dark theme.  Provides:
  • Column-header click to sort ascending / descending
  • Row colour coding  (red = high CPU, amber = moderate CPU)
  • Right-click context menu (Terminate / Copy name)
  • "Kill Selected" button with confirmation
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from typing import List, Callable, Optional

from modules.system_monitor import ProcessInfo
from ui.theme import COLORS


class ProcessTable(ctk.CTkFrame):
    """
    Process table widget.

    Columns : # | PID | Process Name | CPU % | Memory MB | Status | User
    """

    _COLUMNS = [
        ("#",           40,  "center"),
        ("PID",         68,  "center"),
        ("Process Name",195, "w"),
        ("CPU %",       72,  "center"),
        ("Mem MB",      80,  "center"),
        ("Status",      80,  "center"),
        ("User",        100, "w"),
    ]

    def __init__(self, master, on_kill: Optional[Callable] = None, **kwargs):
        super().__init__(master, fg_color="transparent", corner_radius=0, **kwargs)
        self._on_kill       = on_kill
        self._processes: List[ProcessInfo] = []
        self._sort_col      = "CPU %"
        self._sort_reverse  = True
        self._sel_pid: Optional[int]  = None
        self._sel_name: Optional[str] = None

        self._setup_style()
        self._build()

    # ── Style ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _setup_style() -> None:
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except tk.TclError:
            s.theme_use("default")

        s.configure(
            "Dark.Treeview",
            background="#0F1525",
            foreground="#E8EAF0",
            rowheight=26,
            fieldbackground="#0F1525",
            font=("Consolas", 10),
            borderwidth=0,
        )
        s.configure(
            "Dark.Treeview.Heading",
            background="#141928",
            foreground="#8892A4",
            font=("Segoe UI", 10, "bold"),
            borderwidth=1,
            relief="flat",
        )
        s.map("Dark.Treeview",
              background=[("selected", "#1A2035")],
              foreground=[("selected", "#00D4FF")])
        s.map("Dark.Treeview.Heading",
              background=[("active", "#1A2035")],
              foreground=[("active", "#00D4FF")])

        # Scrollbar
        s.configure(
            "Dark.Vertical.TScrollbar",
            background="#141928",
            troughcolor="#0F1525",
            bordercolor="#141928",
            arrowcolor="#4A5568",
        )

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        col_ids = [c[0] for c in self._COLUMNS]

        # Container keeps treeview + scrollbar together
        container = tk.Frame(self, bg="#0F1525")
        container.pack(fill="both", expand=True)

        vsb = ttk.Scrollbar(container, orient="vertical",
                            style="Dark.Vertical.TScrollbar")
        vsb.pack(side="right", fill="y")

        self._tree = ttk.Treeview(
            container,
            columns=col_ids,
            show="headings",
            style="Dark.Treeview",
            yscrollcommand=vsb.set,
            selectmode="browse",
        )
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.config(command=self._tree.yview)

        # Column headings & widths
        for name, width, anchor in self._COLUMNS:
            self._tree.heading(name, text=name,
                               command=lambda c=name: self._sort_by(c))
            self._tree.column(name, width=width, minwidth=30, anchor=anchor)

        # Row colour tags
        self._tree.tag_configure("crit",  background="#1F0A0B", foreground="#FF4757")
        self._tree.tag_configure("high",  background="#1A1506", foreground="#FFB700")
        self._tree.tag_configure("even",  background="#0F1525", foreground="#E8EAF0")
        self._tree.tag_configure("odd",   background="#111A28", foreground="#E8EAF0")

        # Right-click menu
        self._ctx = tk.Menu(
            self._tree, tearoff=0,
            bg="#141928", fg="#E8EAF0",
            activebackground="#1A2035", activeforeground="#00D4FF",
            relief="flat",
        )
        self._ctx.add_command(label="  🔴  Terminate Process",
                              command=self._kill_selected)
        self._ctx.add_separator()
        self._ctx.add_command(label="  📋  Copy Process Name",
                              command=self._copy_name)

        self._tree.bind("<Button-3>",         self._on_right_click)
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Bottom toolbar
        bar = ctk.CTkFrame(self, fg_color="transparent", height=36)
        bar.pack(fill="x", pady=(4, 0))
        bar.pack_propagate(False)

        ctk.CTkLabel(
            bar,
            text="Click column header to sort  •  Right-click row for options",
            font=("Segoe UI", 9),
            text_color=COLORS["text_muted"],
        ).pack(side="left", padx=10)

        self._kill_btn = ctk.CTkButton(
            bar,
            text="🔴  Kill Selected",
            width=138, height=28,
            font=("Segoe UI", 10, "bold"),
            fg_color="#200A0B",
            hover_color="#FF4757",
            text_color="#FF4757",
            corner_radius=7,
            border_width=1,
            border_color="#FF4757",
            command=self._kill_selected,
            state="disabled",
        )
        self._kill_btn.pack(side="right", padx=10)

    # ── Event Handlers ─────────────────────────────────────────────────────────

    def _on_select(self, _event) -> None:
        sel = self._tree.selection()
        if sel:
            vals = self._tree.item(sel[0])["values"]
            if vals and len(vals) >= 3:
                self._sel_pid  = int(vals[1])
                self._sel_name = str(vals[2])
                short = self._sel_name[:16]
                self._kill_btn.configure(
                    state="normal",
                    text=f"🔴  Kill: {short}",
                )

    def _on_right_click(self, event) -> None:
        row = self._tree.identify_row(event.y)
        if row:
            self._tree.selection_set(row)
            vals = self._tree.item(row)["values"]
            if vals and len(vals) >= 3:
                self._sel_pid  = int(vals[1])
                self._sel_name = str(vals[2])
            try:
                self._ctx.tk_popup(event.x_root, event.y_root)
            finally:
                self._ctx.grab_release()

    def _kill_selected(self) -> None:
        if self._sel_pid and self._on_kill:
            self._on_kill(self._sel_pid, self._sel_name or "Unknown")

    def _copy_name(self) -> None:
        if self._sel_name:
            self.clipboard_clear()
            self.clipboard_append(self._sel_name)

    def _sort_by(self, col: str) -> None:
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col     = col
            self._sort_reverse = True
        if self._processes:
            self.update_processes(self._processes)

    # ── Public API ─────────────────────────────────────────────────────────────

    def update_processes(self, processes: List[ProcessInfo]) -> None:
        """Refresh the table with new process data."""
        self._processes = processes

        _key = {
            "CPU %":        lambda p: p.cpu_percent,
            "Mem MB":       lambda p: p.memory_mb,
            "PID":          lambda p: p.pid,
            "Process Name": lambda p: p.name.lower(),
            "Status":       lambda p: p.status,
            "#":            lambda p: p.cpu_percent,
            "User":         lambda p: (p.username or "").lower(),
        }
        key_fn = _key.get(self._sort_col, lambda p: p.cpu_percent)
        sorted_procs = sorted(processes, key=key_fn, reverse=self._sort_reverse)

        existing = self._tree.get_children()
        MAX_ROWS = 150

        for i, proc in enumerate(sorted_procs[:MAX_ROWS]):
            # Row colour based on CPU usage
            if proc.cpu_percent >= 50:
                tag = "crit"
            elif proc.cpu_percent >= 15:
                tag = "high"
            elif i % 2 == 0:
                tag = "even"
            else:
                tag = "odd"

            vals = (
                i + 1,
                proc.pid,
                proc.name[:28],
                f"{proc.cpu_percent:.1f}",
                f"{proc.memory_mb:.0f}",
                proc.status,
                (proc.username or "N/A")[:14],
            )

            if i < len(existing):
                self._tree.item(existing[i], values=vals, tags=(tag,))
            else:
                self._tree.insert("", "end", values=vals, tags=(tag,))

        # Remove surplus rows
        surplus = len(existing) - len(sorted_procs[:MAX_ROWS])
        if surplus > 0:
            for item in existing[len(sorted_procs[:MAX_ROWS]):]:
                self._tree.delete(item)
