"""
webapp/server.py
────────────────────────────────────────────────────────────────────────────────
Smart Process & Resource Management Agent — FastAPI Web Server

Run from the project root:
    py webapp/server.py

Then open http://localhost:8000 in your browser.
"""

import asyncio
import json
import os
import platform
import queue
import socket
import sys
from pathlib import Path
from typing import List, Optional

import psutil
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# ── Path setup ─────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent.parent   # project root
STATIC_DIR = Path(__file__).resolve().parent / "static"
sys.path.insert(0, str(ROOT))

from modules.system_monitor   import SystemMonitor, SystemSnapshot
from modules.process_analyzer import ProcessAnalyzer
from modules.decision_engine  import DecisionEngine
from modules.report_generator import ReportGenerator

# ── Backend singletons ─────────────────────────────────────────────────────────
monitor  = SystemMonitor(interval=2.0)
analyzer = ProcessAnalyzer(top_n=60)
engine   = DecisionEngine()
reporter = ReportGenerator(report_dir=str(ROOT / "reports"))

# ── Shared state ───────────────────────────────────────────────────────────────
_latest_json:     Optional[str]            = None
_last_snapshot:   Optional[SystemSnapshot] = None
_last_analysis:   Optional[dict]           = None
_last_recs:       Optional[list]           = None


# ── WebSocket Connection Manager ──────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self._clients: List[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.append(ws)
        if _latest_json:                    # give new clients instant data
            try:
                await ws.send_text(_latest_json)
            except Exception:
                pass

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._clients:
            self._clients.remove(ws)

    async def broadcast(self, text: str) -> None:
        dead = []
        for ws in self._clients:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


# ── FastAPI ───────────────────────────────────────────────────────────────────
app = FastAPI(title="Resource Monitor API", docs_url=None, redoc_url=None)


@app.on_event("startup")
async def _startup() -> None:
    monitor.start()
    asyncio.create_task(_monitor_loop())


async def _monitor_loop() -> None:
    """Poll the SystemMonitor queue and broadcast live data to all WS clients."""
    global _latest_json, _last_snapshot, _last_analysis, _last_recs
    while True:
        try:
            snapshot: SystemSnapshot = monitor.data_queue.get_nowait()
            analysis = analyzer.analyze(snapshot)
            recs     = engine.analyze(snapshot)
            health   = engine.compute_health_score(snapshot)
            reporter.add_snapshot(snapshot)

            _last_snapshot = snapshot
            _last_analysis = analysis
            _last_recs     = recs

            payload = {
                "type": "snapshot",
                # ── Gauges ──────────────────────────────────────────────────
                "cpu_percent":    round(snapshot.cpu_percent, 1),
                "cpu_freq_mhz":   round(getattr(snapshot, "cpu_freq_mhz", 0), 0),
                "memory_percent": round(snapshot.memory_percent, 1),
                "memory_used_gb": round(snapshot.memory_used_gb, 2),
                "memory_total_gb": round(snapshot.memory_total_gb, 2),
                "disk_percent":   round(snapshot.disk_percent, 1),
                "disk_free_gb":   round(snapshot.disk_free_gb, 2),
                # ── Cards ───────────────────────────────────────────────────
                "swap_percent":   round(snapshot.swap_percent, 1),
                "net_bytes_sent": round(snapshot.net_bytes_sent, 1),
                "net_bytes_recv": round(snapshot.net_bytes_recv, 1),
                "health_score":   health,
                "total_processes": analysis["total_count"],
                # ── Process list ────────────────────────────────────────────
                "processes": [
                    {
                        "pid":         p.pid,
                        "name":        p.name,
                        "cpu":         round(p.cpu_percent, 1),
                        "mem":         round(p.memory_mb, 1),
                        "status":      p.status,
                        "user":        (p.username or "N/A")[:18],
                    }
                    for p in analysis["all_by_cpu"][:80]
                ],
                # ── Recommendations ─────────────────────────────────────────
                "recommendations": [
                    {
                        "severity":  r.severity,
                        "category":  r.category,
                        "title":     r.title,
                        "message":   r.message,
                        "action":    r.action,
                        "pid":       r.pid,
                        "proc_name": r.proc_name,
                    }
                    for r in recs
                ],
            }
            _latest_json = json.dumps(payload)
            await manager.broadcast(_latest_json)

        except queue.Empty:
            pass
        except Exception:
            pass

        await asyncio.sleep(0.5)


# ── WebSocket endpoint ────────────────────────────────────────────────────────
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()   # ping-pong keepalive
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ── REST: system info ─────────────────────────────────────────────────────────
@app.get("/api/sysinfo")
async def sysinfo() -> dict:
    return {
        "hostname":  socket.gethostname(),
        "os":        f"{platform.system()} {platform.release()}",
        "cores_p":   psutil.cpu_count(logical=False),
        "cores_l":   psutil.cpu_count(logical=True),
        "total_ram": round(psutil.virtual_memory().total / (1024 ** 3), 1),
    }


# ── REST: kill process ────────────────────────────────────────────────────────
@app.post("/api/kill/{pid}")
async def kill_process(pid: int) -> dict:
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.terminate()
        return {"success": True, "message": f"'{name}' (PID {pid}) terminated."}
    except psutil.NoSuchProcess:
        return JSONResponse(status_code=404,
                            content={"success": False,
                                     "message": "Process not found — it may have already exited."})
    except psutil.AccessDenied:
        return JSONResponse(status_code=403,
                            content={"success": False,
                                     "message": "Access denied. Run the server as Administrator."})
    except Exception as exc:
        return JSONResponse(status_code=500,
                            content={"success": False, "message": str(exc)})


# ── REST: generate report ─────────────────────────────────────────────────────
@app.post("/api/report")
async def generate_report() -> dict:
    if _last_snapshot is None or _last_analysis is None or _last_recs is None:
        return JSONResponse(status_code=503,
                            content={"success": False,
                                     "message": "No data yet. Wait a moment and try again."})
    try:
        path = reporter.generate_report(_last_snapshot, _last_recs, _last_analysis)
        return {"success": True, "path": str(path)}
    except Exception as exc:
        return JSONResponse(status_code=500,
                            content={"success": False, "message": str(exc)})


# ── Static files (must be LAST) ───────────────────────────────────────────────
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import webbrowser, threading
    def _open():
        import time; time.sleep(1.5)
        webbrowser.open("http://localhost:8000")
    threading.Thread(target=_open, daemon=True).start()

    print("\n  ⚡  Smart Resource Monitor")
    print("  ─────────────────────────────────────")
    print("  Local:   http://localhost:8000")
    print("  Network: http://0.0.0.0:8000")
    print("  Press Ctrl+C to stop\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
