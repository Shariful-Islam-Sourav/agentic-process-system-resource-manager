"""
ui/theme.py
Color palette, severity mappings, and font constants for the dashboard.
"""

# ── Core Color Palette ─────────────────────────────────────────────────────────
COLORS = {
    "bg_primary":    "#0A0E1A",   # darkest canvas background
    "bg_secondary":  "#0F1525",   # header / footer strips
    "bg_card":       "#141928",   # card / panel background
    "bg_card_hover": "#1A2035",   # card on hover
    "accent_cyan":   "#00D4FF",   # CPU accent
    "accent_purple": "#7B61FF",   # Memory accent
    "accent_green":  "#00FF88",   # Disk / healthy accent
    "accent_amber":  "#FFB700",   # Warning accent
    "accent_red":    "#FF4757",   # Critical / kill accent
    "accent_orange": "#FF6B35",   # Upload / fair accent
    "text_primary":  "#E8EAF0",   # Main readable text
    "text_secondary":"#8892A4",   # Subtitles / labels
    "text_muted":    "#4A5568",   # Disabled / hints
    "border":        "#1E2A3A",   # Dividers
}

# ── Severity Colour Mapping ────────────────────────────────────────────────────
SEVERITY_COLORS = {
    "INFO":     "#00D4FF",
    "WARNING":  "#FFB700",
    "CRITICAL": "#FF4757",
}

SEVERITY_BG = {
    "INFO":     "#0D1E2E",
    "WARNING":  "#1E1808",
    "CRITICAL": "#20090A",
}

# ── Font Definitions ───────────────────────────────────────────────────────────
FONTS = {
    "title":       ("Segoe UI", 16, "bold"),
    "heading":     ("Segoe UI", 13, "bold"),
    "subheading":  ("Segoe UI", 12, "bold"),
    "body":        ("Segoe UI", 11),
    "body_small":  ("Segoe UI", 10),
    "body_tiny":   ("Segoe UI", 9),
    "mono":        ("Consolas", 10),
    "mono_large":  ("Consolas", 13, "bold"),
    "gauge_value": ("Segoe UI", 20, "bold"),
    "clock":       ("Consolas", 13),
    "health_big":  ("Segoe UI", 48, "bold"),
}
