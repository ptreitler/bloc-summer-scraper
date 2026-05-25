"""web/routes/index.py — Login, logout, and landing page"""
from __future__ import annotations

from flask import Blueprint, Response, redirect, request, session, url_for

from web.auth import check_credentials, require_login
from web.nav import inject_nav

bp = Blueprint("index", __name__)

DEFAULT_REGION = "Graz"


@bp.route("/")
@require_login
def index():
    region = request.args.get("region", DEFAULT_REGION)
    from analyze import leaderboard_summary, load_data, participant_summary
    from web.rendering import render_participants

    try:
        data = load_data(region=region)
    except FileNotFoundError:
        return Response(
            f"<h1>No data for {region}</h1><p>Data not yet scraped.</p>",
            status=503,
            content_type="text/html",
        )
    summary = participant_summary(data)
    lb = leaderboard_summary(data)
    html = render_participants(summary, lb, region)
    return inject_nav(html, active_region=region)


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    next_url = request.args.get("next", "/")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        ok, is_admin = check_credentials(username, password)
        if ok:
            session.clear()
            session["username"] = username
            session["is_admin"] = is_admin
            # Safely redirect — only allow relative paths to prevent open redirect
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for("index.index"))
        error = "Invalid username or password."
    return Response(_render_login(error, next_url), content_type="text/html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index.login"))


def _render_login(error=None, next_url: str = "/") -> str:
    err_html = f"<p style='color:#c00;margin-bottom:.5rem'>{error}</p>" if error else ""
    # Escape next_url so it is safe to embed in HTML attribute
    safe_next = next_url.replace("&", "&amp;").replace('"', "%22").replace("'", "%27") if next_url else "/"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Login — BSS26</title>
<style>
  *{{box-sizing:border-box}}
  body{{font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#1a2a3a}}
  .card{{background:#fff;padding:2rem 2.5rem;border-radius:8px;box-shadow:0 4px 24px rgba(0,0,0,.3);min-width:300px;width:100%;max-width:360px}}
  h1{{font-size:1.2rem;margin:0 0 1.5rem;color:#1a2a3a}}
  label{{display:block;font-size:.85rem;color:#555;margin-bottom:.25rem}}
  input{{width:100%;padding:.5rem .75rem;border:1px solid #ccc;border-radius:4px;font-size:1rem;margin-bottom:1rem}}
  input:focus{{outline:2px solid #1a5c8a;border-color:#1a5c8a}}
  button{{width:100%;padding:.6rem;background:#1a2a3a;color:#fff;border:none;border-radius:4px;font-size:1rem;cursor:pointer;transition:background .15s}}
  button:hover{{background:#2d4a6a}}
</style>
</head>
<body>
<div class="card">
  <h1>&#129495; BSS26 Dashboard</h1>
  {err_html}
  <form method="post">
    <input type="hidden" name="next" value="{safe_next}">
    <label for="un">Username</label>
    <input id="un" type="text" name="username" autofocus autocomplete="username">
    <label for="pw">Password</label>
    <input id="pw" type="password" name="password" autocomplete="current-password">
    <button type="submit">Sign in</button>
  </form>
</div>
</body>
</html>"""
