"""
telegram_bot.py
───────────────────────────────────────────────────────────────────────────────
Smart Process & Resource Management Agent — Telegram Bot

SETUP (one-time):
  1. Open Telegram → search @BotFather → send /newbot → copy your Bot Token
  2. Start a chat with your new bot, then visit:
       https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
     Send any message to the bot first, then refresh the URL to find your chat_id.
  3. Copy telegram_config.example.json → telegram_config.json and fill in values.
  4. Run: py telegram_bot.py

BOT COMMANDS:
  /status    — Live CPU, Memory, Disk snapshot
  /health    — Health score + recommendations
  /processes — Top 10 processes by CPU
  /kill <pid>— Terminate a process (with confirmation)
  /report    — Generate and receive report file
  /alerts    — Toggle automatic push alerts on/off
  /help      — Show all commands
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import psutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from modules.system_monitor   import SystemMonitor, SystemSnapshot
from modules.process_analyzer import ProcessAnalyzer
from modules.decision_engine  import DecisionEngine
from modules.report_generator import ReportGenerator

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_FILE = ROOT / "telegram_config.json"

def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        print(
            f"\n❌  Config file not found: {CONFIG_FILE}\n"
            f"    Copy telegram_config.example.json → telegram_config.json\n"
            f"    and fill in your bot_token and chat_id.\n"
        )
        sys.exit(1)
    with open(CONFIG_FILE, encoding="utf-8") as fh:
        return json.load(fh)

_cfg = _load_config()

BOT_TOKEN  = _cfg["bot_token"]
CHAT_ID    = str(_cfg["chat_id"])

THRESHOLDS = {
    "cpu":    _cfg.get("alert_cpu_threshold",    85),
    "mem":    _cfg.get("alert_mem_threshold",    85),
    "disk":   _cfg.get("alert_disk_threshold",   90),
    "health": _cfg.get("alert_health_threshold", 40),
}
ALERT_INTERVAL = _cfg.get("alert_interval_seconds", 30)
ALERT_COOLDOWN = _cfg.get("alert_cooldown_seconds", 300)   # 5 min between repeat alerts

if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or CHAT_ID == "YOUR_CHAT_ID_HERE":
    print("\n❌  Please fill in bot_token and chat_id in telegram_config.json\n")
    sys.exit(1)

# ── Backend singletons ────────────────────────────────────────────────────────
monitor  = SystemMonitor(interval=2.0)
analyzer = ProcessAnalyzer(top_n=20)
engine   = DecisionEngine()
reporter = ReportGenerator(report_dir=str(ROOT / "reports"))

# ── Shared state ──────────────────────────────────────────────────────────────
_latest_snapshot: Optional[SystemSnapshot] = None
_alerts_enabled:  bool                     = True
_last_alert_at:   dict                     = {"cpu": 0.0, "mem": 0.0,
                                               "disk": 0.0, "health": 0.0}

# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _refresh_snapshot() -> Optional[SystemSnapshot]:
    """Drain the monitor queue and return the newest snapshot."""
    global _latest_snapshot
    try:
        while not monitor.data_queue.empty():
            _latest_snapshot = monitor.data_queue.get_nowait()
    except Exception:
        pass
    return _latest_snapshot


def _fmt_net(kbps: float) -> str:
    return f"{kbps / 1024:.1f} MB/s" if kbps >= 1024 else f"{kbps:.1f} KB/s"


def _health_emoji(score: int) -> str:
    return "🟢" if score >= 80 else "🟡" if score >= 60 else "🟠" if score >= 40 else "🔴"


def _health_label(score: int) -> str:
    return ("EXCELLENT" if score >= 80 else "GOOD" if score >= 60
            else "FAIR" if score >= 40 else "POOR")


def _authorized(update: Update) -> bool:
    return str(update.effective_chat.id) == CHAT_ID


async def _deny(update: Update) -> None:
    await update.message.reply_text("⛔ Unauthorized.")


# ═════════════════════════════════════════════════════════════════════════════
# COMMANDS
# ═════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return await _deny(update)
    await update.message.reply_text(
        "⚡ *Smart Resource Monitor Bot*\n\n"
        "I'm watching your system in real-time from this machine.\n\n"
        "📋 *Commands:*\n"
        "`/status`    — Live CPU / Memory / Disk\n"
        "`/health`    — Health score + recommendations\n"
        "`/processes` — Top 10 processes by CPU\n"
        "`/kill <pid>`— Terminate a process\n"
        "`/report`    — Generate & receive report file\n"
        "`/alerts`    — Toggle automatic alerts\n"
        "`/help`      — Show this message",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


# ── /status ───────────────────────────────────────────────────────────────────
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return await _deny(update)

    snap = _refresh_snapshot()
    if snap is None:
        return await update.message.reply_text(
            "⏳ Waiting for first snapshot. Try again in 3 seconds."
        )

    health = engine.compute_health_score(snap)

    await update.message.reply_text(
        f"📊 *System Status*\n\n"
        f"🔵 CPU      `{snap.cpu_percent:>5.1f}%`  —  {snap.cpu_freq_mhz:.0f} MHz\n"
        f"🟣 Memory   `{snap.memory_percent:>5.1f}%`  —  "
        f"{snap.memory_used_gb:.1f} / {snap.memory_total_gb:.1f} GB\n"
        f"🟢 Disk     `{snap.disk_percent:>5.1f}%`  —  {snap.disk_free_gb:.1f} GB free\n"
        f"🔄 Swap     `{snap.swap_percent:>5.1f}%`\n\n"
        f"🌐 Upload   `{_fmt_net(snap.net_bytes_sent)}`\n"
        f"🌐 Download `{_fmt_net(snap.net_bytes_recv)}`\n\n"
        f"{_health_emoji(health)} Health: *{health}/100 — {_health_label(health)}*",
        parse_mode="Markdown",
    )


# ── /health ───────────────────────────────────────────────────────────────────
async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return await _deny(update)

    snap = _refresh_snapshot()
    if snap is None:
        return await update.message.reply_text("⏳ No data yet.")

    health = engine.compute_health_score(snap)
    recs   = engine.analyze(snap)
    crits  = sum(1 for r in recs if r.severity == "CRITICAL")
    warns  = sum(1 for r in recs if r.severity == "WARNING")

    bar   = "█" * (health // 10) + "░" * (10 - health // 10)
    lines = [
        f"{_health_emoji(health)} *Health Score: {health}/100 — {_health_label(health)}*",
        f"`[{bar}]`",
    ]

    if recs:
        lines.append(f"\n🔴 {crits} critical   🟡 {warns} warning\n")
        for r in recs[:6]:
            icon = "🔴" if r.severity == "CRITICAL" else "🟡" if r.severity == "WARNING" else "🔵"
            lines.append(f"{icon} *{r.title}*")
            lines.append(f"   _{r.action}_")
    else:
        lines.append("\n✅ No active recommendations — system looks healthy!")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /processes ────────────────────────────────────────────────────────────────
async def cmd_processes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return await _deny(update)

    snap = _refresh_snapshot()
    if snap is None:
        return await update.message.reply_text("⏳ No data yet.")

    analysis = analyzer.analyze(snap)
    procs    = analysis["all_by_cpu"][:10]
    total    = analysis["total_count"]

    lines = [f"⚙️ *Top 10 Processes by CPU*  _{total} total_\n"]
    lines.append("`  #    PID  Name                CPU%    Mem`")
    lines.append("`────────────────────────────────────────────`")

    for i, p in enumerate(procs, 1):
        flag = "🔴" if p.cpu_percent >= 50 else "🟡" if p.cpu_percent >= 15 else "  "
        name = (p.name[:17] + "…") if len(p.name) > 18 else p.name.ljust(18)
        lines.append(
            f"`{flag}{i:>2}  {p.pid:>5}  {name}  {p.cpu_percent:>4.1f}%  {p.memory_mb:>5.0f}MB`"
        )

    lines.append("\n_Tip: /kill \\<pid\\> to terminate a process_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /kill ─────────────────────────────────────────────────────────────────────
async def cmd_kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return await _deny(update)

    if not context.args:
        return await update.message.reply_text(
            "Usage: `/kill <pid>`\nExample: `/kill 4532`",
            parse_mode="Markdown",
        )

    try:
        pid = int(context.args[0])
    except ValueError:
        return await update.message.reply_text("❌ PID must be a number.")

    try:
        proc = psutil.Process(pid)
        name = proc.name()
        cpu  = proc.cpu_percent(interval=0.1)
        mem  = proc.memory_info().rss / (1024 ** 2)
    except psutil.NoSuchProcess:
        return await update.message.reply_text(f"❌ No process found with PID `{pid}`.", parse_mode="Markdown")
    except Exception as e:
        return await update.message.reply_text(f"❌ Error: {e}")

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔴  Kill It",  callback_data=f"kill_{pid}"),
        InlineKeyboardButton("❌  Cancel",   callback_data="kill_cancel"),
    ]])

    await update.message.reply_text(
        f"⚠️ *Confirm Termination*\n\n"
        f"Process : `{name}`\n"
        f"PID     : `{pid}`\n"
        f"CPU     : `{cpu:.1f}%`\n"
        f"Memory  : `{mem:.0f} MB`\n\n"
        f"This will force-close the process.\n"
        f"Unsaved data may be lost.",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def callback_kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "kill_cancel":
        await query.edit_message_text("❌ Kill cancelled.")
        return

    pid = int(data.split("_")[1])

    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.terminate()
        await query.edit_message_text(
            f"✅ *Process Terminated*\n`{name}` (PID {pid}) has been terminated.",
            parse_mode="Markdown",
        )
    except psutil.NoSuchProcess:
        await query.edit_message_text(
            f"⚠️ PID {pid} no longer exists — it may have exited on its own."
        )
    except psutil.AccessDenied:
        await query.edit_message_text(
            "🔒 *Access Denied*\n"
            "Run the bot as Administrator to terminate system-level processes.",
            parse_mode="Markdown",
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Unexpected error: {e}")


# ── /report ───────────────────────────────────────────────────────────────────
async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return await _deny(update)

    snap = _refresh_snapshot()
    if snap is None:
        return await update.message.reply_text("⏳ No data yet. Wait a few seconds.")

    msg = await update.message.reply_text("⏳ Generating report…")

    try:
        analysis = analyzer.analyze(snap)
        recs     = engine.analyze(snap)
        reporter.add_snapshot(snap)
        path = reporter.generate_report(snap, recs, analysis)

        with open(path, "rb") as fh:
            await context.bot.send_document(
                chat_id=CHAT_ID,
                document=fh,
                filename=Path(path).name,
                caption=(
                    f"📄 *Report generated*\n"
                    f"`{Path(path).name}`\n\n"
                    f"Health: {engine.compute_health_score(snap)}/100"
                ),
                parse_mode="Markdown",
            )
        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ Report failed: {e}")


# ── /alerts ───────────────────────────────────────────────────────────────────
async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return await _deny(update)

    global _alerts_enabled
    _alerts_enabled = not _alerts_enabled

    status = "✅ *ON*" if _alerts_enabled else "🔕 *OFF*"
    await update.message.reply_text(
        f"Automatic alerts: {status}\n\n"
        f"*Alert thresholds:*\n"
        f"• CPU ≥ `{THRESHOLDS['cpu']}%`\n"
        f"• Memory ≥ `{THRESHOLDS['mem']}%`\n"
        f"• Disk ≥ `{THRESHOLDS['disk']}%`\n"
        f"• Health ≤ `{THRESHOLDS['health']}`\n"
        f"• Cooldown: `{ALERT_COOLDOWN}s` between repeat alerts",
        parse_mode="Markdown",
    )


# ═════════════════════════════════════════════════════════════════════════════
# PROACTIVE ALERT JOB  (runs every ALERT_INTERVAL seconds)
# ═════════════════════════════════════════════════════════════════════════════

async def _alert_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _alerts_enabled:
        return

    snap = _refresh_snapshot()
    if snap is None:
        return

    now    = time.time()
    health = engine.compute_health_score(snap)

    checks = [
        ("cpu",
         snap.cpu_percent, THRESHOLDS["cpu"],
         "🔴 *CPU Alert*",
         f"CPU is at `{snap.cpu_percent:.1f}%`\nUse /processes to find the culprit."),

        ("mem",
         snap.memory_percent, THRESHOLDS["mem"],
         "🟣 *Memory Alert*",
         f"Memory usage: `{snap.memory_percent:.1f}%` "
         f"({snap.memory_used_gb:.1f} / {snap.memory_total_gb:.1f} GB)"),

        ("disk",
         snap.disk_percent, THRESHOLDS["disk"],
         "💾 *Disk Space Alert*",
         f"Disk at `{snap.disk_percent:.1f}%` — only `{snap.disk_free_gb:.1f} GB` remaining"),
    ]

    for key, value, threshold, title, detail in checks:
        if value >= threshold and (now - _last_alert_at[key]) >= ALERT_COOLDOWN:
            _last_alert_at[key] = now
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=f"{title}\n{detail}",
                parse_mode="Markdown",
            )

    if health <= THRESHOLDS["health"] and (now - _last_alert_at["health"]) >= ALERT_COOLDOWN:
        _last_alert_at["health"] = now
        recs = engine.analyze(snap)
        rec_lines = "\n".join(
            f"• {r.title}" for r in recs[:3] if r.severity == "CRITICAL"
        )
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"🔴 *Low Health Score: {health}/100*\n\n"
                f"{rec_lines}\n\n"
                f"Use /health for full recommendations."
            ),
            parse_mode="Markdown",
        )


# ═════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

def main() -> None:
    monitor.start()

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("status",    cmd_status))
    app.add_handler(CommandHandler("health",    cmd_health))
    app.add_handler(CommandHandler("processes", cmd_processes))
    app.add_handler(CommandHandler("kill",      cmd_kill))
    app.add_handler(CommandHandler("report",    cmd_report))
    app.add_handler(CommandHandler("alerts",    cmd_alerts))

    # Inline keyboard callback (kill confirmation)
    app.add_handler(CallbackQueryHandler(callback_kill, pattern=r"^kill_"))

    # Proactive alert job
    app.job_queue.run_repeating(
        _alert_job, interval=ALERT_INTERVAL, first=15
    )

    print("\n  ⚡  Smart Resource Monitor — Telegram Bot")
    print("  ──────────────────────────────────────────────")
    print(f"  Chat ID  : {CHAT_ID}")
    print(f"  Alerts   : every {ALERT_INTERVAL}s  |  cooldown {ALERT_COOLDOWN}s")
    print(f"  CPU alert: ≥ {THRESHOLDS['cpu']}%")
    print(f"  Mem alert: ≥ {THRESHOLDS['mem']}%")
    print(f"  Disk alert: ≥ {THRESHOLDS['disk']}%")
    print(f"  Health alert: ≤ {THRESHOLDS['health']}")
    print("  Send /start in Telegram to begin.")
    print("  Press Ctrl+C to stop.\n")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
