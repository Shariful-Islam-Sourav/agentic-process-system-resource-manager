"""
modules/report_generator.py

Phase 5 — Report Generation Module
────────────────────────────────────
Saves timestamped system analysis reports in both plain-text and
JSON formats to a local 'reports/' folder.
Tracks session history for statistical summaries.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any

from modules.system_monitor import SystemSnapshot
from modules.decision_engine import Recommendation


class ReportGenerator:
    """
    Generates and saves system analysis reports.

    Output formats:
      • <timestamp>.txt  — human-readable plain-text report
      • <timestamp>.json — structured JSON for programmatic use
    """

    MAX_HISTORY = 300   # ~10 minutes at 2 s polling

    def __init__(self, report_dir: str = "reports"):
        self.report_dir = report_dir
        os.makedirs(report_dir, exist_ok=True)
        self._session_history: List[Dict[str, float]] = []

    # ── Public ─────────────────────────────────────────────────────────────────

    def add_snapshot(self, snapshot: SystemSnapshot) -> None:
        """Record a lightweight history entry for session statistics."""
        self._session_history.append({
            "timestamp": snapshot.timestamp,
            "cpu":       snapshot.cpu_percent,
            "memory":    snapshot.memory_percent,
            "disk":      snapshot.disk_percent,
        })
        if len(self._session_history) > self.MAX_HISTORY:
            self._session_history.pop(0)

    def generate_report(
        self,
        snapshot: SystemSnapshot,
        recommendations: List[Recommendation],
        analysis: Dict[str, Any],
    ) -> str:
        """
        Write .txt and .json reports.
        Returns the absolute path of the text report.
        """
        ts = datetime.now()
        base = ts.strftime("report_%Y%m%d_%H%M%S")
        txt_path  = os.path.join(self.report_dir, f"{base}.txt")
        json_path = os.path.join(self.report_dir, f"{base}.json")

        self._write_text(txt_path,  snapshot, recommendations, analysis, ts)
        self._write_json(json_path, snapshot, recommendations, analysis, ts)

        return os.path.abspath(txt_path)

    # ── Text Report ────────────────────────────────────────────────────────────

    def _write_text(self, path, snapshot, recommendations, analysis, ts):
        div  = "=" * 72
        sep  = "-" * 45
        lines = []

        lines += [
            div,
            "  SMART PROCESS & RESOURCE MANAGEMENT AGENT — SYSTEM REPORT",
            f"  Generated : {ts.strftime('%Y-%m-%d  %H:%M:%S')}",
            div, "",
        ]

        # Section 1: Resource Snapshot
        lines += [
            "SECTION 1 — RESOURCE USAGE SNAPSHOT",
            sep,
            f"  CPU Usage          : {snapshot.cpu_percent:>6.1f}%",
            f"  CPU Frequency      : {snapshot.cpu_freq_mhz:>6.0f} MHz",
            f"  CPU Cores          : {snapshot.cpu_count_logical} logical / {snapshot.cpu_count_physical} physical",
            f"  RAM Usage          : {snapshot.memory_percent:>6.1f}%"
            f"  ({snapshot.memory_used_gb:.1f} / {snapshot.memory_total_gb:.1f} GB)",
            f"  RAM Available      : {snapshot.memory_available_gb:.1f} GB",
            f"  Swap Usage         : {snapshot.swap_percent:>6.1f}%"
            f"  ({snapshot.swap_used_gb:.1f} / {snapshot.swap_total_gb:.1f} GB)",
            f"  Disk Usage (C:)    : {snapshot.disk_percent:>6.1f}%"
            f"  ({snapshot.disk_used_gb:.1f} / {snapshot.disk_total_gb:.1f} GB)",
            f"  Disk Free          : {snapshot.disk_free_gb:.1f} GB",
            f"  Net Upload         : {snapshot.net_bytes_sent:.1f} KB/s",
            f"  Net Download       : {snapshot.net_bytes_recv:.1f} KB/s",
            f"  Active Processes   : {analysis['total_count']}",
            "",
        ]

        # Section 2: Top CPU Processes
        lines += ["SECTION 2 — TOP CPU-CONSUMING PROCESSES", sep]
        lines.append(f"  {'#':<4} {'PID':<8} {'Process Name':<28} {'CPU %':<8} {'MEM MB':<10} {'Status'}")
        lines.append(f"  {'-'*3} {'-'*7} {'-'*27} {'-'*7} {'-'*9} {'-'*10}")
        for i, p in enumerate(analysis["top_cpu"][:10], 1):
            lines.append(
                f"  {i:<4} {p.pid:<8} {p.name[:27]:<28} {p.cpu_percent:<8.1f} {p.memory_mb:<10.1f} {p.status}"
            )
        lines.append("")

        # Section 3: Top Memory Processes
        lines += ["SECTION 3 — TOP MEMORY-CONSUMING PROCESSES", sep]
        lines.append(f"  {'#':<4} {'PID':<8} {'Process Name':<28} {'MEM MB':<10} {'MEM %':<8} {'Status'}")
        lines.append(f"  {'-'*3} {'-'*7} {'-'*27} {'-'*9} {'-'*7} {'-'*10}")
        for i, p in enumerate(analysis["top_mem"][:10], 1):
            lines.append(
                f"  {i:<4} {p.pid:<8} {p.name[:27]:<28} {p.memory_mb:<10.1f} {p.memory_percent:<8.2f} {p.status}"
            )
        lines.append("")

        # Section 4: Recommendations
        lines += ["SECTION 4 — AGENT RECOMMENDATIONS", sep]
        for r in recommendations:
            lines += [
                f"  [{r.severity}] {r.title}",
                f"  Category : {r.category}",
                f"  Observation : {r.message}",
                f"  Recommended Action : {r.action}",
                "",
            ]

        # Section 5: Session Statistics
        if self._session_history:
            cpus  = [h["cpu"]    for h in self._session_history]
            mems  = [h["memory"] for h in self._session_history]
            disks = [h["disk"]   for h in self._session_history]
            dur_s = len(self._session_history) * 2

            lines += [
                "SECTION 5 — SESSION STATISTICS",
                sep,
                f"  Session Duration   : ~{dur_s} seconds ({dur_s // 60}m {dur_s % 60}s)",
                f"  CPU  — Avg: {sum(cpus)/len(cpus):>5.1f}%  Peak: {max(cpus):>5.1f}%  Min: {min(cpus):>5.1f}%",
                f"  RAM  — Avg: {sum(mems)/len(mems):>5.1f}%  Peak: {max(mems):>5.1f}%  Min: {min(mems):>5.1f}%",
                f"  Disk — Avg: {sum(disks)/len(disks):>5.1f}%  Peak: {max(disks):>5.1f}%  Min: {min(disks):>5.1f}%",
                "",
            ]

        lines += [div, "  END OF REPORT", div]

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # ── JSON Report ────────────────────────────────────────────────────────────

    def _write_json(self, path, snapshot, recommendations, analysis, ts):
        data = {
            "generated_at": ts.isoformat(),
            "system_snapshot": {
                "cpu_percent":       round(snapshot.cpu_percent, 1),
                "cpu_freq_mhz":      round(snapshot.cpu_freq_mhz, 0),
                "cpu_cores_logical": snapshot.cpu_count_logical,
                "cpu_cores_physical":snapshot.cpu_count_physical,
                "memory_percent":    round(snapshot.memory_percent, 1),
                "memory_used_gb":    round(snapshot.memory_used_gb, 2),
                "memory_total_gb":   round(snapshot.memory_total_gb, 2),
                "memory_avail_gb":   round(snapshot.memory_available_gb, 2),
                "swap_percent":      round(snapshot.swap_percent, 1),
                "disk_percent":      round(snapshot.disk_percent, 1),
                "disk_free_gb":      round(snapshot.disk_free_gb, 2),
                "disk_total_gb":     round(snapshot.disk_total_gb, 2),
                "net_upload_kbps":   round(snapshot.net_bytes_sent, 2),
                "net_download_kbps": round(snapshot.net_bytes_recv, 2),
                "process_count":     analysis["total_count"],
            },
            "top_cpu_processes": [
                {
                    "rank": i + 1,
                    "pid": p.pid,
                    "name": p.name,
                    "cpu_percent": round(p.cpu_percent, 1),
                    "memory_mb":   round(p.memory_mb, 1),
                    "status":      p.status,
                }
                for i, p in enumerate(analysis["top_cpu"][:10])
            ],
            "top_memory_processes": [
                {
                    "rank": i + 1,
                    "pid": p.pid,
                    "name": p.name,
                    "memory_mb":      round(p.memory_mb, 1),
                    "memory_percent": round(p.memory_percent, 2),
                    "status":         p.status,
                }
                for i, p in enumerate(analysis["top_mem"][:10])
            ],
            "recommendations": [
                {
                    "severity": r.severity,
                    "category": r.category,
                    "title":    r.title,
                    "message":  r.message,
                    "action":   r.action,
                    "pid":      r.pid,
                }
                for r in recommendations
            ],
            "session_summary": self._build_session_summary(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _build_session_summary(self) -> Dict:
        if not self._session_history:
            return {}
        cpus  = [h["cpu"]    for h in self._session_history]
        mems  = [h["memory"] for h in self._session_history]
        disks = [h["disk"]   for h in self._session_history]
        return {
            "data_points":    len(self._session_history),
            "cpu_avg":        round(sum(cpus)  / len(cpus),  1),
            "cpu_peak":       round(max(cpus),  1),
            "memory_avg":     round(sum(mems)  / len(mems),  1),
            "memory_peak":    round(max(mems),  1),
            "disk_avg":       round(sum(disks) / len(disks), 1),
        }
