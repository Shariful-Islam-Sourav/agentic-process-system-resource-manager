# ⚡ Smart Process & Resource Management Agent

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![CustomTkinter](https://img.shields.io/badge/CustomTkinter-5.2-1E90FF?style=for-the-badge)
![psutil](https://img.shields.io/badge/psutil-7.2-orange?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**A real-time system resource monitoring and process management agent — available as both a desktop app and a browser-based web dashboard.**

[Features](#-features) • [Desktop App](#-desktop-app) • [Web App](#-web-app) • [Installation](#-installation) • [Usage](#-usage) • [Architecture](#-architecture) • [Project Structure](#-project-structure)

</div>

---

## 📌 Overview

Modern computer users often experience slow performance due to excessive CPU, memory, or disk usage — without knowing which processes are responsible.

The **Smart Process & Resource Management Agent** continuously monitors your system's resources, analyzes usage patterns, identifies bottlenecks, and provides intelligent recommendations. It also lets you **terminate problematic processes** directly from the dashboard.

It comes in **two modes**:
| Mode | Description |
|---|---|
| 🖥️ **Desktop App** | Native dark-themed GUI built with CustomTkinter |
| 🌐 **Web App** | Browser dashboard powered by FastAPI + WebSocket |

---

## ✨ Features

- 📊 **Live Resource Gauges** — Animated circular arc gauges for CPU, Memory, and Disk
- 📈 **60-Second History Chart** — Rolling line chart for CPU, Memory, and Disk trends
- 🏥 **System Health Score** — 0–100 score with EXCELLENT / GOOD / FAIR / POOR classification
- 🌐 **Network & Memory Stats** — Upload/Download speed, RAM usage, Swap, and Process count
- ⚙️ **Process Monitor** — Sortable table of all running processes with colour-coded severity
- 🤖 **Agent Recommendations** — Rule-based engine that detects issues and suggests actions
- 🔴 **Kill Process** — Terminate any process with a confirmation dialog (desktop & web)
- 📄 **Report Generation** — Save timestamped `.txt` and `.json` reports to disk
- 🔄 **Auto Refresh** — Configurable 2-second polling with toggle control

---

## 🖥️ Desktop App

Built with **CustomTkinter** for a native dark-themed desktop experience.

### Features
- Animated arc gauges (60 fps, eased animation)
- Scrollable main area — see all sections even on small screens
- Right-click context menu on process rows
- Sortable process table with column headers
- Kill confirmation dialog before terminating any process

### Launch
```bash
py main.py
```

---

## 🌐 Web App

A full-featured browser dashboard powered by **FastAPI** and **WebSocket** for real-time data push.

### Features
- SVG arc gauges animated via `requestAnimationFrame`
- Real-time **Chart.js** history chart
- WebSocket auto-reconnect with exponential backoff
- Toast notifications for kill/report actions
- Works in any modern browser (Chrome, Firefox, Edge)

### Launch
```bash
py webapp/server.py
```
Then open **http://localhost:8000** in your browser.

> The server automatically opens your browser on startup.

---

## ⚙️ Installation

### Prerequisites
- Python **3.10+**
- Windows / macOS / Linux

### 1. Clone the repository
```bash
git clone https://github.com/Shariful-Islam-Sourav/agentic-process-system-resource-manager.git
cd agentic-process-system-resource-manager
```

### 2. Install dependencies

**For the Desktop App:**
```bash
py -m pip install customtkinter psutil
```

**For the Web App:**
```bash
py -m pip install fastapi "uvicorn[standard]" psutil
```

**Or install everything at once:**
```bash
py -m pip install -r requirements.txt
```

---

## 🚀 Usage

### Desktop App
```bash
py main.py
```

### Web App
```bash
py webapp/server.py
# Open http://localhost:8000
```

### Generating a Report
Click the **📄 Generate Report** button in the footer. Reports are saved to the `reports/` folder in two formats:
```
reports/
├── report_20260608_120000.txt     ← Human-readable
└── report_20260608_120000.json    ← Structured data
```

### Killing a Process
1. Find the process in the **Process Monitor** table or **Agent Recommendations** panel
2. Click the **🔴 Kill** button
3. Confirm in the dialog — the process is terminated via `psutil.terminate()`

> ⚠️ Some system processes require Administrator / root privileges to terminate.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    User Interface                         │
│  ┌──────────────────────┐   ┌──────────────────────────┐ │
│  │  Desktop App         │   │  Web App (Browser)        │ │
│  │  (CustomTkinter)     │   │  HTML + CSS + JS          │ │
│  └──────────┬───────────┘   └────────────┬─────────────┘ │
└─────────────┼──────────────────────────── ┼──────────────┘
              │  direct call                 │  WebSocket / REST
┌─────────────▼──────────────────────────── ▼──────────────┐
│                    Backend (Python)                        │
│                                                           │
│  ┌──────────────┐  ┌───────────────┐  ┌───────────────┐  │
│  │ System       │  │ Process       │  │ Decision      │  │
│  │ Monitor      │  │ Analyzer      │  │ Engine        │  │
│  │ (psutil)     │  │ (ranking)     │  │ (rules)       │  │
│  └──────┬───────┘  └───────┬───────┘  └──────┬────────┘  │
│         └──────────────────┼──────────────────┘           │
│                            ▼                               │
│                   ┌────────────────┐                      │
│                   │ Report         │                      │
│                   │ Generator      │                      │
│                   │ (.txt + .json) │                      │
│                   └────────────────┘                      │
└───────────────────────────────────────────────────────────┘
              │
              ▼
     Local Machine  (psutil reads YOUR system data)
```

### Data Flow
1. `SystemMonitor` runs in a **background daemon thread**, collecting snapshots every 2 seconds and pushing them to a `queue.Queue`
2. `ProcessAnalyzer` ranks processes by CPU and memory usage
3. `DecisionEngine` applies threshold-based rules to generate recommendations and compute a health score
4. `ReportGenerator` maintains a session history and writes timestamped reports on demand
5. The **UI layer** (desktop or web) polls the queue and updates all widgets without blocking

---

## 📁 Project Structure

```
agentic-process-system-resource-manager/
│
├── main.py                          # Desktop app entry point
├── requirements.txt                 # Python dependencies
│
├── modules/                         # Core backend logic
│   ├── __init__.py
│   ├── system_monitor.py            # Phase 1: Data collection (psutil)
│   ├── process_analyzer.py          # Phase 2: Process ranking
│   ├── decision_engine.py           # Phase 3: Rules + health score
│   └── report_generator.py          # Phase 5: .txt / .json reports
│
├── ui/                              # Desktop UI (CustomTkinter)
│   ├── __init__.py
│   ├── theme.py                     # Color palette & design constants
│   ├── dashboard.py                 # Main dashboard frame
│   └── widgets/
│       ├── __init__.py
│       ├── gauge_widget.py          # Animated circular arc gauge
│       ├── history_chart.py         # 60-second rolling line chart
│       ├── process_table.py         # Sortable process table
│       └── recommendation_panel.py  # Severity-coded recommendation cards
│
├── webapp/                          # Web app (FastAPI)
│   ├── server.py                    # FastAPI + WebSocket backend
│   └── static/
│       ├── index.html               # Single-page dashboard
│       ├── css/
│       │   └── style.css            # Dark glassmorphism theme
│       └── js/
│           └── app.js               # Gauges, chart, table, WS client
│
└── reports/                         # Generated reports (auto-created)
    ├── report_*.txt
    └── report_*.json
```

---

## 🔧 Module Details

### `system_monitor.py`
Collects a `SystemSnapshot` dataclass every 2 seconds using `psutil`:
- CPU percent + frequency
- Memory used / total / swap
- Disk used / free
- Network bytes sent / received (KB/s)
- All running process info (`ProcessInfo` list)

### `process_analyzer.py`
Ranks processes by CPU and memory usage, returns top-N lists and aggregate statistics.

### `decision_engine.py`
Rule-based agent that evaluates thresholds:

| Condition | Severity | Example |
|---|---|---|
| CPU > 85% | CRITICAL | "CPU is critically overloaded" |
| CPU > 60% | WARNING | "High CPU usage detected" |
| Memory > 90% | CRITICAL | "Memory critically low" |
| Disk > 90% | WARNING | "Disk space running low" |
| Swap > 50% | WARNING | "Heavy swap usage" |
| Single process > 40% CPU | WARNING | "process.exe consuming high CPU" |

**Health Score formula:**
```
score = 100 - (cpu% × 0.30) - (mem% × 0.30) - (disk% × 0.20) - (swap% × 0.15)
```

### `report_generator.py`
Writes two files per report:
- **`.txt`** — Human-readable with sections for system stats, top processes, recommendations, and session averages
- **`.json`** — Full structured data for programmatic use

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| System data | `psutil` |
| Desktop UI | `customtkinter`, `tkinter` |
| Web backend | `FastAPI`, `Uvicorn` |
| Real-time push | WebSocket |
| Web charts | `Chart.js` (CDN) |
| Web gauges | SVG + JavaScript animation |
| Web styling | Vanilla CSS (glassmorphism dark theme) |
| Fonts | Google Fonts — Inter, JetBrains Mono |

---

## 📊 Health Score Reference

| Score | Status | Description |
|---|---|---|
| 80 – 100 | 🟢 **EXCELLENT** | System running smoothly |
| 60 – 79  | 🟡 **GOOD** | Minor resource usage, no action needed |
| 40 – 59  | 🟠 **FAIR** | Elevated usage, monitor closely |
| 0 – 39   | 🔴 **POOR** | Action needed — check recommendations |

---

## 🔒 Permissions & Security

- The agent is **read-only by default** — it only monitors and recommends
- Process termination requires **explicit user action** (button click + confirmation)
- Some system/protected processes may require running as **Administrator** (Windows) or **root** (Linux/macOS) to terminate
- All data stays **local** — nothing is sent to any external server

---

## 📋 Requirements

```
customtkinter>=5.2.0
psutil>=7.0.0
fastapi>=0.100.0
uvicorn[standard]>=0.20.0
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "Add my feature"`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License**.

---

## 👨‍💻 Author

Built as part of **Operating Systems — Semester 4** coursework.

> Demonstrates real-world OS concepts: process scheduling visibility, resource monitoring, inter-process communication patterns, and system calls via `psutil`.

---

<div align="center">
  <sub>⚡ Smart Process & Resource Management Agent — Built with Python</sub>
</div>
