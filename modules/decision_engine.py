"""
modules/decision_engine.py

Phase 3 — Agent Decision Engine
────────────────────────────────────
Rule-based analysis of SystemSnapshot data.
Detects performance issues and generates prioritised, actionable
Recommendation objects for the dashboard and reports.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from modules.system_monitor import SystemSnapshot
from modules.process_analyzer import ProcessAnalyzer


# ── Recommendation Data Class ──────────────────────────────────────────────────

@dataclass
class Recommendation:
    """A single agent recommendation with severity and optional target PID."""
    severity: str          # "INFO" | "WARNING" | "CRITICAL"
    category: str          # "CPU" | "MEMORY" | "DISK" | "PROCESS" | "NETWORK"
    title: str
    message: str
    action: str
    pid: Optional[int] = None   # If the recommendation targets a specific process
    proc_name: Optional[str] = None


# ── Decision Engine ────────────────────────────────────────────────────────────

class DecisionEngine:
    """
    Evaluates real-time system data against configurable thresholds
    and emits a list of Recommendation objects.

    OS Concepts demonstrated:
      • Resource Allocation — detecting contention
      • System Monitoring   — threshold-based anomaly detection
      • Process Management  — per-process CPU/memory policies
    """

    DEFAULT_THRESHOLDS = {
        # System-wide
        "cpu_warning":          70.0,
        "cpu_critical":         90.0,
        "memory_warning":       75.0,
        "memory_critical":      90.0,
        "disk_warning":         80.0,
        "disk_critical":        95.0,
        "swap_warning":         50.0,
        # Per-process
        "proc_cpu_warning":     40.0,
        "proc_cpu_critical":    70.0,
        "proc_mem_mb_warning":  500.0,
    }

    def __init__(self):
        self.thresholds = dict(self.DEFAULT_THRESHOLDS)
        self._analyzer = ProcessAnalyzer(top_n=5)

    # ── Public ─────────────────────────────────────────────────────────────────

    def analyze(self, snapshot: SystemSnapshot) -> List[Recommendation]:
        """Return a list of Recommendations ordered by severity."""
        recs: List[Recommendation] = []
        analysis = self._analyzer.analyze(snapshot)

        recs.extend(self._check_cpu(snapshot, analysis))
        recs.extend(self._check_memory(snapshot, analysis))
        recs.extend(self._check_disk(snapshot))
        recs.extend(self._check_processes(analysis))

        # Sort: CRITICAL → WARNING → INFO
        order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
        recs.sort(key=lambda r: order.get(r.severity, 3))
        return recs

    def compute_health_score(self, snapshot: SystemSnapshot) -> int:
        """
        Compute an integer health score 0–100.
        Deducted proportionally from CPU, Memory, Disk and Swap usage.
        """
        score = 100.0
        score -= min(30.0, snapshot.cpu_percent * 0.30)
        score -= min(30.0, snapshot.memory_percent * 0.30)
        score -= min(20.0, snapshot.disk_percent * 0.20)
        score -= min(15.0, snapshot.swap_percent * 0.15)
        return max(0, int(score))

    # ── Private Checks ─────────────────────────────────────────────────────────

    def _check_cpu(self, snap: SystemSnapshot, analysis: dict) -> List[Recommendation]:
        recs = []
        top = analysis["top_cpu"][0] if analysis["top_cpu"] else None

        if snap.cpu_percent >= self.thresholds["cpu_critical"]:
            action = (
                f"Terminate or restart '{top.name}' (PID {top.pid}) which is using "
                f"{top.cpu_percent:.1f}% CPU."
                if top else "Close unnecessary applications immediately."
            )
            recs.append(Recommendation(
                severity="CRITICAL", category="CPU",
                title="🔴 Critical CPU Overload",
                message=f"CPU is at {snap.cpu_percent:.1f}% — system is severely overloaded.",
                action=action,
                pid=top.pid if top else None,
                proc_name=top.name if top else None,
            ))
        elif snap.cpu_percent >= self.thresholds["cpu_warning"]:
            action = (
                f"'{top.name}' (PID {top.pid}) is consuming {top.cpu_percent:.1f}% CPU. "
                f"Consider closing it."
                if top else "Monitor CPU-intensive tasks."
            )
            recs.append(Recommendation(
                severity="WARNING", category="CPU",
                title="⚠️ High CPU Usage",
                message=f"CPU usage is elevated at {snap.cpu_percent:.1f}%.",
                action=action,
                pid=top.pid if top else None,
                proc_name=top.name if top else None,
            ))
        else:
            recs.append(Recommendation(
                severity="INFO", category="CPU",
                title="✅ CPU Healthy",
                message=f"CPU usage is normal at {snap.cpu_percent:.1f}%.",
                action="No action required.",
            ))
        return recs

    def _check_memory(self, snap: SystemSnapshot, analysis: dict) -> List[Recommendation]:
        recs = []
        top = analysis["top_mem"][0] if analysis["top_mem"] else None

        if snap.memory_percent >= self.thresholds["memory_critical"]:
            action = (
                f"Close '{top.name}' (PID {top.pid}, {top.memory_mb:.0f} MB) immediately."
                if top else "Free memory by closing heavy applications."
            )
            recs.append(Recommendation(
                severity="CRITICAL", category="MEMORY",
                title="🔴 Critical Memory Usage",
                message=(
                    f"RAM is {snap.memory_percent:.1f}% full "
                    f"({snap.memory_used_gb:.1f}/{snap.memory_total_gb:.1f} GB). "
                    f"Only {snap.memory_available_gb:.1f} GB available."
                ),
                action=action,
                pid=top.pid if top else None,
                proc_name=top.name if top else None,
            ))
        elif snap.memory_percent >= self.thresholds["memory_warning"]:
            action = (
                f"'{top.name}' (PID {top.pid}) is using {top.memory_mb:.0f} MB. "
                f"Restart if not essential."
                if top else "Close memory-heavy applications."
            )
            recs.append(Recommendation(
                severity="WARNING", category="MEMORY",
                title="⚠️ High Memory Usage",
                message=f"RAM usage is {snap.memory_percent:.1f}% ({snap.memory_available_gb:.1f} GB free).",
                action=action,
                pid=top.pid if top else None,
                proc_name=top.name if top else None,
            ))
        else:
            recs.append(Recommendation(
                severity="INFO", category="MEMORY",
                title="✅ Memory Healthy",
                message=f"RAM usage is {snap.memory_percent:.1f}% ({snap.memory_available_gb:.1f} GB free).",
                action="No action required.",
            ))

        # Swap check
        if snap.swap_percent >= self.thresholds["swap_warning"]:
            recs.append(Recommendation(
                severity="WARNING", category="MEMORY",
                title="⚠️ High Swap Usage",
                message=(
                    f"Swap is {snap.swap_percent:.1f}% utilised "
                    f"({snap.swap_used_gb:.1f}/{snap.swap_total_gb:.1f} GB). "
                    "System is paging to disk — performance is degraded."
                ),
                action="Close unused applications or upgrade RAM.",
            ))
        return recs

    def _check_disk(self, snap: SystemSnapshot) -> List[Recommendation]:
        recs = []
        if snap.disk_percent >= self.thresholds["disk_critical"]:
            recs.append(Recommendation(
                severity="CRITICAL", category="DISK",
                title="🔴 Disk Almost Full",
                message=(
                    f"Disk is {snap.disk_percent:.1f}% full — "
                    f"only {snap.disk_free_gb:.1f} GB remaining."
                ),
                action=(
                    "Delete temp files (run %TEMP% & C:\\Windows\\Temp), "
                    "uninstall unused programs, or move data to external storage."
                ),
            ))
        elif snap.disk_percent >= self.thresholds["disk_warning"]:
            recs.append(Recommendation(
                severity="WARNING", category="DISK",
                title="⚠️ Low Disk Space",
                message=(
                    f"Disk is {snap.disk_percent:.1f}% full "
                    f"({snap.disk_free_gb:.1f} GB free of {snap.disk_total_gb:.1f} GB)."
                ),
                action="Run Disk Cleanup or move large files to free up space.",
            ))
        else:
            recs.append(Recommendation(
                severity="INFO", category="DISK",
                title="✅ Disk Space OK",
                message=(
                    f"Disk usage is {snap.disk_percent:.1f}% "
                    f"({snap.disk_free_gb:.1f} GB free)."
                ),
                action="No action required.",
            ))
        return recs

    def _check_processes(self, analysis: dict) -> List[Recommendation]:
        """Flag individual processes that are hogging CPU or Memory."""
        recs = []

        # Top CPU hogs
        for proc in analysis["top_cpu"][:3]:
            if proc.cpu_percent >= self.thresholds["proc_cpu_critical"]:
                recs.append(Recommendation(
                    severity="CRITICAL", category="PROCESS",
                    title=f"🔴 CPU Hog: {proc.name}",
                    message=(
                        f"'{proc.name}' (PID {proc.pid}) is consuming "
                        f"{proc.cpu_percent:.1f}% CPU continuously."
                    ),
                    action=f"Terminate or restart '{proc.name}' to free CPU resources.",
                    pid=proc.pid,
                    proc_name=proc.name,
                ))
            elif proc.cpu_percent >= self.thresholds["proc_cpu_warning"]:
                recs.append(Recommendation(
                    severity="WARNING", category="PROCESS",
                    title=f"⚠️ High CPU Process: {proc.name}",
                    message=(
                        f"'{proc.name}' (PID {proc.pid}) is using "
                        f"{proc.cpu_percent:.1f}% CPU."
                    ),
                    action=f"Monitor '{proc.name}'. Close it if not essential.",
                    pid=proc.pid,
                    proc_name=proc.name,
                ))

        # Top Memory hogs
        for proc in analysis["top_mem"][:2]:
            if proc.memory_mb >= self.thresholds["proc_mem_mb_warning"]:
                recs.append(Recommendation(
                    severity="WARNING", category="PROCESS",
                    title=f"⚠️ Memory Heavy: {proc.name}",
                    message=(
                        f"'{proc.name}' (PID {proc.pid}) is holding "
                        f"{proc.memory_mb:.0f} MB of RAM."
                    ),
                    action=f"Restart '{proc.name}' if it may be leaking memory.",
                    pid=proc.pid,
                    proc_name=proc.name,
                ))

        return recs
