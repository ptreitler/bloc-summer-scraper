"""
Scraper for Bloc Summer Sessions competition data.

The site uses AJAX endpoints:
  POST https://boulder-top.com/ranking-xmlhttp_loadRanking.php  → ranking HTML in JSON
  GET  /comp/bss26/page/boulder-eintragen/t=…&k=…&r=…&v=…&c=…&h=  → static detail page
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

DOMAIN = "https://boulder-top.com"
RANKING_API = f"{DOMAIN}/ranking-xmlhttp_loadRanking.php"
DETAIL_BASE = f"{DOMAIN}/comp/bss26/page/boulder-eintragen"

COMP_SHORT = "bss26"
COMP_C = 190          # CID
COMP_V = 198          # VID
RANKING_TYP = 1       # RankingTyp (classic)
GRUPP_TYP = 2         # GruppierungTyp
START_DATE = "2026-04-29 07:00:00"
END_DATE = "2026-05-31 23:59:00"

REGIONS: dict[str, dict] = {
    "Graz":         {"id": 251, "name": "Graz"},
    "Kärnten":      {"id": 245, "name": "Kärnten"},
    "Linz":         {"id": 249, "name": "Linz"},
    "Murtal":       {"id": 247, "name": "Murtal"},
    "Salzburg":     {"id": 248, "name": "Salzburg"},
    "Traunviertel": {"id": 252, "name": "Traunviertel"},
    "Wien":         {"id": 246, "name": "Wien"},
}

CLASSES = [
    {"id": 686, "name": "Männer", "bez": "Männer"},
    {"id": 687, "name": "Frauen", "bez": "Frauen"},
]

DATA_DIR = Path("data")
RATE_LIMIT = 0.5  # seconds between requests

console = Console()


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "bloc-summer-scraper/1.0 (educational, non-commercial)"
    return s


def _detail_url(participant_id: int, class_k: int, region_id: int) -> str:
    return (
        f"{DETAIL_BASE}/"
        f"t={participant_id}&k={class_k}&r={region_id}&v={COMP_V}&c={COMP_C}&h="
    )


def fetch_ranking_html(session: requests.Session, cls: dict, region: dict) -> str:
    """POST to the AJAX ranking endpoint and return the HTML body string."""
    resp = session.post(
        RANKING_API,
        data={
            "comp": COMP_SHORT,
            "CID": COMP_C,
            "VID": COMP_V,
            "REid": region["id"],
            "KLid": cls["id"],
            "RankingTyp": RANKING_TYP,
            "REBez": region["name"],
            "KLBez": cls["bez"],
            "GTyp": GRUPP_TYP,
            "StartDate": START_DATE,
            "EndDate": END_DATE,
            "Backend": "0",
            "HAID": "",
            "AusgabeTyp": "1",
            "KWID": "0",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["Return_DIV_Body"]


def parse_ranking(html: str) -> list[dict]:
    """
    Extract competitor list from the AJAX-returned ranking HTML.

    Each competitor entry is an <a> with href like:
      javascript:toggle('f1-2248', 190, 198, 686, 2248, 0, 1)
    Parameters: c, v, k (class_k for detail URLs), participant_id
    """
    soup = BeautifulSoup(html, "lxml")
    # toggle('fRANK-ID', CID, VID, class_k, participant_id, BoulderEintragen, RTYP)
    pattern = re.compile(
        r"toggle\('f(\d+)-\d+',\s*\d+,\s*\d+,\s*(\d+),\s*(\d+),\s*0,\s*1\)"
    )
    competitors = []
    seen: set[int] = set()

    for a in soup.find_all("a", href=re.compile(r"javascript:toggle")):
        href = a.get("href", "")
        m = pattern.search(href)
        if not m:
            continue
        rank = int(m.group(1))
        class_k = int(m.group(2))
        participant_id = int(m.group(3))

        if participant_id in seen:
            continue
        seen.add(participant_id)

        # Text like "1. Tritthart Clemens  119 / 120▼99%"
        # Use separator=' ' to preserve spaces between text nodes
        text = re.sub(r"\s+", " ", a.get_text(separator=" ")).strip()
        text = re.sub(r"^\d+\.\s*", "", text)  # strip leading rank
        sm = re.search(r"^(.+?)\s+(\d+)\s*/\s*(\d+)", text)
        if sm:
            name = sm.group(1).strip()
            score = int(sm.group(2))
            total = int(sm.group(3))
        else:
            name = text.strip()
            score = total = 0

        competitors.append({
            "id": participant_id,
            "class_k": class_k,
            "name": name,
            "rank": rank,
            "score": score,
            "total": total,
        })

    return competitors


def parse_detail(html: str) -> dict[str, list[bool]]:
    """
    Extract per-gym boulder completions from a competitor's detail page.

    Structure in div.row:
      col-md-12 containing h5 "GymName: X / 40 - Y%"  → gym header
      col-md-12 with 40 button.btn-success / button.btn-dark  → boulders

    Buttons appear in document order (boulder 1 first, boulder 40 last).
    True = topped (btn-success), False = not topped (btn-dark).
    """
    soup = BeautifulSoup(html, "lxml")
    result: dict[str, list[bool]] = {}

    # Find the first h5 that looks like a gym header; its row ancestor is our container
    gym_pattern = re.compile(r"^(.+?):\s*\d+\s*/\s*\d+")
    first_h5 = soup.find("h5", string=gym_pattern)
    if not first_h5:
        return result

    # Walk up to the shared div.row (2 levels: h5 → div → col-md-12 → div.row)
    row_div = first_h5.parent.parent.parent

    current_gym: str | None = None
    for child in row_div.children:
        if not hasattr(child, "name") or not child.name:
            continue

        h5 = child.find("h5")
        if h5:
            m = gym_pattern.match(h5.get_text(strip=True))
            if m:
                current_gym = m.group(1).strip()
                continue

        if current_gym is not None:
            btns = child.find_all("button", class_=re.compile(r"btn-(success|dark)"))
            if btns:
                boulders = [
                    "btn-success" in (b.get("class") or [])
                    for b in btns
                ]
                result[current_gym] = boulders
                current_gym = None  # reset; next h5 sets the next gym

    return result


def scrape_all(region_name: str = "Graz", force: bool = False) -> Path:
    """
    Scrape ranking + competitor detail pages for all classes in the given region.
    Saves JSON to data/bss26_<region>_<timestamp>.json and data/latest_<region>.json.
    Returns the path to the region-specific latest file.
    """
    if region_name not in REGIONS:
        raise ValueError(f"Unknown region '{region_name}'. Choose from: {', '.join(REGIONS)}")
    region = REGIONS[region_name]
    region_slug = region_name.lower().replace(" ", "_")
    DATA_DIR.mkdir(exist_ok=True)
    latest = DATA_DIR / f"latest_{region_slug}.json"

    if latest.exists() and not force:
        console.print(
            f"[yellow]Using cached data ({latest}). Pass --force to re-scrape.[/yellow]"
        )
        return latest

    session = _session()
    data: dict = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "competition": {"c": COMP_C, "v": COMP_V},
        "region": {"id": region["id"], "name": region_name},
        "classes": [],
    }

    for cls in CLASSES:
        console.print(f"\n[bold]Fetching {cls['name']} ranking ({region_name})...[/bold]")
        ranking_html = fetch_ranking_html(session, cls, region)
        competitors = parse_ranking(ranking_html)
        console.print(f"  Found [cyan]{len(competitors)}[/cyan] competitors")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Scraping {cls['name']} details", total=len(competitors)
            )
            for comp in competitors:
                time.sleep(RATE_LIMIT)
                detail_resp = session.get(
                    _detail_url(comp["id"], comp["class_k"], region["id"]), timeout=15
                )
                detail_resp.raise_for_status()
                comp["boulders"] = parse_detail(detail_resp.text)
                if not comp["boulders"]:
                    console.print(
                        f"  [red]Warning:[/red] no boulder data for {comp['name']} "
                        f"(id={comp['id']})"
                    )
                del comp["class_k"]
                progress.advance(task)

        data["classes"].append({
            "id": cls["id"],
            "name": cls["name"],
            "competitors": competitors,
        })

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = DATA_DIR / f"bss26_{region_slug}_{timestamp}.json"
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    out.write_text(payload, encoding="utf-8")
    latest.write_text(payload, encoding="utf-8")

    console.print(f"\n[green]Data saved to {out}[/green]")
    return latest
