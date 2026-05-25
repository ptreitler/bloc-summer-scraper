"""web/nav.py — Navigation bar injection"""
from __future__ import annotations

from flask import session

from scraper import REGIONS

REGION_NAMES: list[str] = list(REGIONS.keys())


def _nav_bar(active_region: str | None = None) -> str:
    username = session.get("username", "")
    is_admin = session.get("is_admin", False)

    region_links = " ".join(
        f"<a href='/?region={r}' style='color:{'#fff' if r == active_region else '#9ba8b4'};"
        f"text-decoration:none;padding:0.1rem 0.3rem;border-radius:3px;"
        f"{'background:#2d4a6a' if r == active_region else ''}' "
        f">{r}</a>"
        for r in REGION_NAMES
    )

    admin_link = (
        "<a href='/admin' style='color:#f0a500;text-decoration:none;"
        "padding:0.1rem 0.3rem;border-radius:3px'>Admin</a>"
        if is_admin
        else ""
    )

    return (
        f"<nav style='background:#1a2a3a;color:#ccc;padding:0.5rem 1.2rem;"
        f"display:flex;flex-wrap:wrap;gap:0.5rem 1rem;font-family:system-ui,sans-serif;"
        f"font-size:0.85rem;align-items:center;border-bottom:2px solid #2d4a6a;"
        f"box-sizing:border-box;width:100%;max-width:100%'>"
        f"<a href='/' style='color:#fff;font-weight:700;text-decoration:none;"
        f"font-size:1rem;margin-right:0.3rem'>&#129495; BSS26</a>"
        f"<span style='color:#3d5a7a'>|</span>"
        f"{region_links}"
        f"<span style='flex:1'></span>"
        f"{admin_link}"
        f"<span style='color:#8899aa'>{username}</span>"
        f"<a href='/logout' style='color:#8899aa;text-decoration:none;"
        f"border:1px solid #3d5a7a;padding:0.1rem 0.5rem;border-radius:3px'>Logout</a>"
        f"</nav>"
    )


def inject_nav(html: str, active_region: str | None = None) -> str:
    """Insert the navigation bar immediately after the opening <body> tag."""
    nav = _nav_bar(active_region)
    return html.replace("<body>", f"<body>\n{nav}\n", 1)
