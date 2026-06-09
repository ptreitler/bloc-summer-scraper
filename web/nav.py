"""web/nav.py — Navigation bar injection"""
from __future__ import annotations

from flask import request, session

from scraper import REGIONS

REGION_NAMES: list[str] = list(REGIONS.keys())

# Pages directly linkable from the nav (no extra required params)
_NAV_PAGES = [
    ("Participants", "/"),
    ("Leaderboard", "/leaderboard"),
    ("Stats", "/stats"),
]

_NAV_STYLE = (
    "background:#1a2a3a;color:#ccc;padding:0.5rem 1.2rem;"
    "display:flex;flex-wrap:wrap;gap:0.5rem 1rem;font-family:system-ui,sans-serif;"
    "font-size:0.85rem;align-items:center;border-bottom:2px solid #2d4a6a;"
    "box-sizing:border-box;width:100%;max-width:100%"
)


def _a(href: str, label: str, *, active: bool = False, accent: bool = False, btn: bool = False) -> str:
    color = "#fff" if active else ("#f0a500" if accent else "#9ba8b4")
    bg = "background:#2d4a6a;" if active else ""
    border = "border:1px solid #3d5a7a;" if btn else ""
    padding = "0.1rem 0.5rem" if btn else "0.1rem 0.3rem"
    return (
        f"<a href='{href}' style='color:{color};text-decoration:none;"
        f"padding:{padding};border-radius:3px;{bg}{border}'>{label}</a>"
    )


def _nav_bar(active_region: str | None = None) -> str:
    is_admin = session.get("is_admin", False)
    logged_in = "username" in session
    region = active_region or "Graz"
    current_path = request.path

    # Page-type links — preserve current region
    page_links = " ".join(
        _a(f"{path}?region={region}", label, active=(current_path == path))
        for label, path in _NAV_PAGES
    )

    # Region links — preserve current page
    region_links = " ".join(
        _a(f"{current_path}?region={r}", r, active=(r == active_region))
        for r in REGION_NAMES
    )

    admin_link = _a("/admin", "Admin", accent=True) if is_admin else ""
    auth_link = (
        _a("/logout", "Logout", btn=True)
        if logged_in
        else _a("/login", "Admin Login", btn=True)
    )

    sep = "<span style='color:#3d5a7a'>|</span>"
    return (
        f"<nav style='{_NAV_STYLE}'>"
        f"<a href='/' style='color:#fff;font-weight:700;text-decoration:none;"
        f"font-size:1rem;margin-right:0.3rem'>&#129495; BSS26</a>"
        f"{sep}"
        f"{page_links}"
        f"{sep}"
        f"{region_links}"
        f"<span style='flex:1'></span>"
        f"{admin_link}"
        f"{auth_link}"
        f"</nav>"
    )


def inject_nav(html: str, active_region: str | None = None) -> str:
    """Insert the navigation bar immediately after the opening <body> tag."""
    nav = _nav_bar(active_region)
    return html.replace("<body>", f"<body>\n{nav}\n", 1)
