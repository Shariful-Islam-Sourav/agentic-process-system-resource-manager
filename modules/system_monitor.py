"""
modules/system_monitor.py

Phase 1 — System Monitoring Module
────────────────────────────────────
Collects real-time CPU, Memory, Disk, Network and Process data
using the psutil library. Runs in a background daemon thread and
pushes SystemSnapshot objects onto a thread-safe queue for the UI
to consume without blocking.
"""

import psutil
import threading
import queue
import time
from dataclasses import dataclass, field
from typing import List, Optional


# ── Data Classes ───────────────────────────────────────────────────────────────

@dataclass
class ProcessInfo:
    """Lightweight snapshot of a single running process."""
    pid: int
    name: str
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    status: str
    username: str


@dataclass
class SystemSnapshot:
    """Full system resource snapshot captured at a point in time."""
    timestamp: float

    # CPU
    cpu_percent: float
    cpu_per_core: List[float]
    cpu_freq_mhz: float
    cpu_count_logical: int
    cpu_count_physical: int

    # Memory
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    memory_available_gb: float
    swap_percent: float
    swap_used_gb: float
    swap_total_gb: float

    # Disk (primary partition)
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    disk_free_gb: float

    # Network (rates in KB/s)
    net_bytes_sent: float
    net_bytes_recv: float

    # Processes
    processes: List[ProcessInfo]


# ── Monitor ────────────────────────────────────────────────────────────────────

class SystemMonitor:
    """
    Background thread that continuously collects system metrics and
    exposes them via a thread-safe queue (data_queue).

    OS Concepts demonstrated:
      • Process scheduling  — psutil.cpu_percent per core
      • Memory management   — virtual_memory() / swap_memory()
      • Resource allocation — threshold monitoring
    """

    def __init__(self, interval: float = 2.0):
        self.interval = interval
        self.data_queue: queue.Queue = queue.Queue(maxsize=20)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_net_io = None
        self._last_net_time: Optional[float] = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background monitoring thread."""
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="SystemMonitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the monitoring thread to stop."""
        self._running = False

    # ── Internal ───────────────────────────────────────────────────────────────

    def _monitor_loop(self) -> None:
        """Main loop: warm up CPU counters, then collect on interval."""
        # Warm-up: psutil needs one dummy call before cpu_percent is accurate
        psutil.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None, percpu=True)
        for proc in psutil.process_iter(["cpu_percent"]):
            try:
                proc.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        time.sleep(1.0)

        while self._running:
            snapshot = self._collect()
            self._push(snapshot)
            time.sleep(self.interval)

    def _push(self, snapshot: SystemSnapshot) -> None:
        """Drop oldest item if queue is full, then push new snapshot."""
        if self.data_queue.full():
            try:
                self.data_queue.get_nowait()
            except queue.Empty:
                pass
        try:
            self.data_queue.put_nowait(snapshot)
        except queue.Full:
            pass

    def _collect(self) -> SystemSnapshot:
        """Gather all metrics and return a SystemSnapshot."""
        now = time.time()

        # ── CPU ────────────────────────────────────────────────────────────────
        cpu_pct = psutil.cpu_percent(interval=None)
        try:
            cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
        except Exception:
            cpu_per_core = [cpu_pct]
        try:
            freq = psutil.cpu_freq()
            cpu_freq = freq.current if freq else 0.0
        except Exception:
            cpu_freq = 0.0
        cpu_logical = psutil.cpu_count(logical=True) or 1
        cpu_physical = psutil.cpu_count(logical=False) or 1

        # ── Memory ────────────────────────────────────────────────────────────
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # ── Disk (primary) ────────────────────────────────────────────────────
        disk = self._get_primary_disk()

        # ── Network ──────────────────────────────────────────────────────────
        net_sent_rate, net_recv_rate = self._calc_net_rates(now)

        # ── Processes ────────────────────────────────────────────────────────
        processes = self._collect_processes()

        return SystemSnapshot(
            timestamp=now,
            cpu_percent=cpu_pct,
            cpu_per_core=cpu_per_core,
            cpu_freq_mhz=cpu_freq,
            cpu_count_logical=cpu_logical,
            cpu_count_physical=cpu_physical,
            memory_percent=mem.percent,
            memory_used_gb=mem.used / (1024 ** 3),
            memory_total_gb=mem.total / (1024 ** 3),
            memory_available_gb=mem.available / (1024 ** 3),
            swap_percent=swap.percent,
            swap_used_gb=swap.used / (1024 ** 3),
            swap_total_gb=swap.total / (1024 ** 3),
            disk_percent=disk.percent if disk else 0.0,
            disk_used_gb=disk.used / (1024 ** 3) if disk else 0.0,
            disk_total_gb=disk.total / (1024 ** 3) if disk else 0.0,
            disk_free_gb=disk.free / (1024 ** 3) if disk else 0.0,
            net_bytes_sent=net_sent_rate,
            net_bytes_recv=net_recv_rate,
            processes=processes,
        )

    @staticmethod
    def _get_primary_disk():
        """Return disk usage for the most relevant partition."""
        candidates = ["C:\\", "C:/", "/"]
        for path in candidates:
            try:
                return psutil.disk_usage(path)
            except Exception:
                pass
        # Fallback: use the first accessible partition
        try:
            for part in psutil.disk_partitions(all=False):
                try:
                    return psutil.disk_usage(part.mountpoint)
                except Exception:
                    pass
        except Exception:
            pass
        return None

    def _calc_net_rates(self, now: float):
        """Calculate send/receive rates in KB/s since last call."""
        try:
            net_io = psutil.net_io_counters()
        except Exception:
            return 0.0, 0.0

        sent_rate = recv_rate = 0.0
        if self._last_net_io and self._last_net_time:
            dt = now - self._last_net_time
            if dt > 0:
                sent_rate = (net_io.bytes_sent - self._last_net_io.bytes_sent) / dt / 1024
                recv_rate = (net_io.bytes_recv - self._last_net_io.bytes_recv) / dt / 1024
        self._last_net_io = net_io
        self._last_net_time = now
        return max(0.0, sent_rate), max(0.0, recv_rate)

    @staticmethod
    def _collect_processes() -> List[ProcessInfo]:
        """Collect per-process stats, silently skipping inaccessible ones."""
        results: List[ProcessInfo] = []
        attrs = ["pid", "name", "cpu_percent", "memory_info", "memory_percent", "status", "username"]
        for proc in psutil.process_iter(attrs):
            try:
                info = proc.info
                mem_info = info.get("memory_info")
                mem_mb = (mem_info.rss / (1024 * 1024)) if mem_info else 0.0
                results.append(ProcessInfo(
                    pid=info["pid"],
                    name=info.get("name") or "Unknown",
                    cpu_percent=info.get("cpu_percent") or 0.0,
                    memory_mb=mem_mb,
                    memory_percent=info.get("memory_percent") or 0.0,
                    status=info.get("status") or "unknown",
                    username=info.get("username") or "N/A",
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return results
