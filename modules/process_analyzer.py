"""
modules/process_analyzer.py

Phase 2 — Process Analysis Module
────────────────────────────────────
Receives a SystemSnapshot and produces ranked lists of processes
sorted by CPU and Memory consumption.
"""

from typing import List, Dict, Any
from modules.system_monitor import SystemSnapshot, ProcessInfo


class ProcessAnalyzer:
    """
    Analyses process data to identify top resource consumers.

    OS Concepts demonstrated:
      • Process Management  — listing and sorting active processes
      • CPU Scheduling      — identifying which processes hold CPU time
      • Memory Management   — ranking processes by RSS memory footprint
    """

    def __init__(self, top_n: int = 20):
        self.top_n = top_n

    def analyze(self, snapshot: SystemSnapshot) -> Dict[str, Any]:
        """
        Return a dict with:
          top_cpu      — processes sorted by CPU% descending (top N)
          top_mem      — processes sorted by Memory MB descending (top N)
          all_by_cpu   — ALL processes sorted by CPU% descending
          total_count  — total number of running processes
        """
        procs: List[ProcessInfo] = snapshot.processes

        top_cpu = sorted(procs, key=lambda p: p.cpu_percent, reverse=True)[: self.top_n]
        top_mem = sorted(procs, key=lambda p: p.memory_mb, reverse=True)[: self.top_n]
        all_by_cpu = sorted(procs, key=lambda p: p.cpu_percent, reverse=True)

        return {
            "top_cpu": top_cpu,
            "top_mem": top_mem,
            "all_by_cpu": all_by_cpu,
            "total_count": len(procs),
        }
