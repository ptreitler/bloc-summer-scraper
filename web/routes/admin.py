"""web/routes/admin.py — Admin panel (tag management, scrape trigger, data freshness)"""
from __future__ import annotations

import json
import os
from pathlib import Path

from flask import Blueprint, Response, abort, jsonify, request

from web.auth import require_admin

bp = Blueprint("admin", __name__)

TAGS_FILE = Path("data") / "tags.json"


def _load_tags() -> dict:
    return json.loads(TAGS_FILE.read_text(encoding="utf-8")) if TAGS_FILE.exists() else {}


def _save_tags(tags: dict) -> None:
    TAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TAGS_FILE.write_text(json.dumps(tags, indent=2, ensure_ascii=False), encoding="utf-8")


def _commit_tags_to_github(tags: dict) -> None:
    """Push tags.json to GitHub via the Contents API so the scrape job picks it up."""
    import base64
    import requests as req

    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPO", "")
    if not token or not repo:
        return

    url = f"https://api.github.com/repos/{repo}/contents/data/tags.json"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Fetch the current file SHA (needed for updates)
    r = req.get(url, headers=headers, timeout=10)
    sha = r.json().get("sha", "") if r.ok else ""

    content = base64.b64encode(
        json.dumps(tags, indent=2, ensure_ascii=False).encode("utf-8")
    ).decode()
    body: dict = {"message": "chore: update tags via admin panel", "content": content}
    if sha:
        body["sha"] = sha

    req.put(url, headers=headers, json=body, timeout=10)


def _commit_region_to_github(region: str) -> None:
    """Commit one latest_<region>.json file to GitHub via the Contents API."""
    import base64
    from datetime import datetime, timezone

    import requests as req

    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPO", "")
    if not token or not repo:
        return

    slug = region.lower().replace(" ", "_")
    p = Path("data") / f"latest_{slug}.json"
    if not p.exists():
        return

    url = f"https://api.github.com/repos/{repo}/contents/data/latest_{slug}.json"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    r = req.get(url, headers=headers, timeout=10)
    sha = r.json().get("sha", "") if r.ok else ""

    content = base64.b64encode(p.read_bytes()).decode()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    body: dict = {"message": f"chore: scrape {region} [{ts}]", "content": content}
    if sha:
        body["sha"] = sha

    req.put(url, headers=headers, json=body, timeout=30)


@bp.route("/admin/ping")
def ping():
    """No-auth health check — verifies the blueprint is registered and routing works."""
    return jsonify({"ok": True, "routes": [str(r) for r in bp.deferred_functions]})


@bp.route("/admin/scrape-region", methods=["POST"])
def scrape_region_api():
    """Run the scraper for one region synchronously, then commit the result to GitHub.

    Called by the GitHub Actions workflow via curl.  Auth is a shared Bearer token
    stored in the SCRAPE_SECRET env var (not a user session).
    """
    secret = os.environ.get("SCRAPE_SECRET", "")
    auth_header = request.headers.get("Authorization", "")
    if not secret or auth_header != f"Bearer {secret}":
        abort(401)

    data = request.get_json(silent=True) or {}
    region = data.get("region") or request.args.get("region", "")
    if not region:
        return jsonify({"ok": False, "error": "missing region"}), 400

    import subprocess
    import sys

    app_root = str(Path(__file__).parent.parent.parent)
    result = subprocess.run(
        [sys.executable, "main.py", "scrape", "--region", region, "--force"],
        cwd=app_root,
        capture_output=True,
        text=True,
        timeout=600,
    )

    if result.returncode != 0:
        return jsonify({"ok": False, "region": region, "error": result.stderr[-1000:]}), 500

    _commit_region_to_github(region)
    return jsonify({"ok": True, "region": region})


@bp.route("/admin")
@require_admin
def admin():
    from scraper import REGIONS
    regions = list(REGIONS.keys())
    tags = _load_tags()

    # Build data-freshness table
    info_rows = []
    for r in regions:
        slug = r.lower().replace(" ", "_")
        p = Path("data") / f"latest_{slug}.json"
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                info_rows.append(f"<tr><td>{r}</td><td>{d.get('scraped_at', '?')}</td></tr>")
            except Exception:
                info_rows.append(f"<tr><td>{r}</td><td>error reading</td></tr>")
        else:
            info_rows.append(f"<tr><td>{r}</td><td><em>no data</em></td></tr>")

    info_table = (
        "<table>\n<thead><tr><th>Region</th><th>Last scraped</th></tr></thead>\n<tbody>"
        + "".join(info_rows)
        + "</tbody>\n</table>"
    )

    return Response(_render_admin(info_table, regions, tags), content_type="text/html")


@bp.route("/admin/trigger-scrape", methods=["POST"])
@require_admin
def trigger_scrape():
    import requests as req

    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPO", "")
    if not token or not repo:
        return Response(
            "<html><body><p>GITHUB_TOKEN or GITHUB_REPO not configured.</p>"
            "<a href='/admin'>Back</a></body></html>",
            status=503,
            content_type="text/html",
        )
    url = f"https://api.github.com/repos/{repo}/actions/workflows/scrape.yml/dispatches"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    r = req.post(url, headers=headers, json={"ref": "main"}, timeout=10)
    if r.status_code == 204:
        return Response(
            "<html><body><p>Scrape triggered successfully. Check GitHub Actions for progress.</p>"
            "<a href='/admin'>Back</a></body></html>",
            content_type="text/html",
        )
    return Response(
        f"<html><body><p>Error: {r.status_code}</p><a href='/admin'>Back</a></body></html>",
        status=500,
        content_type="text/html",
    )


@bp.route("/admin/tag", methods=["POST"])
@require_admin
def set_tag():
    region = request.form.get("region", "")
    gym = request.form.get("gym", "")
    boulder = request.form.get("boulder", "")
    tag_str = request.form.get("tags", "")
    action = request.form.get("action", "set")

    if not region or not gym or not boulder:
        return Response("<p>Missing fields.</p>", status=400, content_type="text/html")

    tags = _load_tags()
    if action == "clear":
        if (
            region in tags
            and gym in tags[region]
            and boulder in tags[region][gym]
        ):
            del tags[region][gym][boulder]
            if not tags[region][gym]:
                del tags[region][gym]
            if not tags[region]:
                del tags[region]
    else:
        tag_list = [t.strip() for t in tag_str.split(",") if t.strip()]
        tags.setdefault(region, {}).setdefault(gym, {})[boulder] = tag_list

    _save_tags(tags)
    _commit_tags_to_github(tags)
    return Response(
        "<html><body><p>Tags updated.</p><a href='/admin'>Back</a></body></html>",
        content_type="text/html",
    )


def _render_admin(info_table: str, regions: list[str], tags: dict) -> str:
    region_opts = "".join(f"<option>{r}</option>" for r in regions)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Admin — BSS26</title>
<style>
  *{{box-sizing:border-box}}
  body{{font-family:system-ui,sans-serif;padding:1.5rem;max-width:900px;color:#111}}
  h1{{font-size:1.3rem;margin-bottom:0}}
  h2{{font-size:1.05rem;border-bottom:2px solid #ddd;padding-bottom:.2rem;margin-top:2rem}}
  table{{border-collapse:collapse;width:100%}}
  th,td{{padding:.4rem .7rem;border:1px solid #ddd;text-align:left}}
  th{{background:#f0f0f0}}
  button{{padding:.4rem 1rem;cursor:pointer;border:1px solid #aaa;border-radius:4px;background:#fff}}
  button:hover{{background:#e8e8e8}}
  input,select{{padding:.35rem .6rem;border:1px solid #ccc;border-radius:4px;font-size:.9rem}}
  .row{{display:flex;flex-wrap:wrap;gap:.5rem;align-items:flex-end;margin-top:.5rem}}
  label span{{display:block;font-size:.8rem;color:#555;margin-bottom:.2rem}}
</style>
</head>
<body>
<h1>Admin Panel</h1>
<a href="/" style="font-size:.85rem;color:#1a5c8a">← Back to dashboard</a>

<h2>Data freshness</h2>
{info_table}

<h2>Trigger scrape</h2>
<form method="post" action="/admin/trigger-scrape">
  <button type="submit">&#128260; Trigger scrape now</button>
</form>

<h2>Tag a boulder</h2>
<form method="post" action="/admin/tag">
  <div class="row">
    <label><span>Region</span><select name="region">{region_opts}</select></label>
    <label><span>Gym</span><input name="gym" placeholder="e.g. BlocHouse Graz" style="width:16rem"></label>
    <label><span>Boulder #</span><input name="boulder" type="number" min="1" style="width:5rem"></label>
    <label><span>Tags (comma-separated)</span><input name="tags" placeholder="crimpy, red" style="width:14rem"></label>
    <button type="submit" name="action" value="set">Set</button>
    <button type="submit" name="action" value="clear">Clear</button>
  </div>
</form>
</body>
</html>"""
