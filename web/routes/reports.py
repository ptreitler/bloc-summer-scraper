"""web/routes/reports.py — All data report endpoints"""
from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, Response, request

from web.nav import inject_nav

bp = Blueprint("reports", __name__)

TAGS_FILE = Path("data") / "tags.json"


def _load_tags() -> dict:
    return json.loads(TAGS_FILE.read_text(encoding="utf-8")) if TAGS_FILE.exists() else {}


def _load(region: str):
    from analyze import load_data
    return load_data(region=region)


def _no_data(region: str, status: int = 503) -> Response:
    return Response(
        f"<html><body><h1>No data for {region}</h1>"
        f"<p>Data not yet scraped. Try again later.</p></body></html>",
        status=status,
        content_type="text/html",
    )


@bp.route("/leaderboard")
def leaderboard():
    region = request.args.get("region", "Graz")
    limit = request.args.get("limit", type=int)
    from analyze import leaderboard_summary
    from web.rendering import render_leaderboard

    try:
        data = _load(region)
    except FileNotFoundError:
        return _no_data(region)
    lb = leaderboard_summary(data, top_n=limit)
    return inject_nav(render_leaderboard(lb, region, limit), active_region=region)


@bp.route("/score")
def score():
    region = request.args.get("region", "Graz")
    name = request.args.get("name", "")
    if not name:
        return Response("<h1>Missing name parameter</h1>", status=400, content_type="text/html")
    from analyze import competitor_score_summary
    from web.rendering import render_score

    try:
        data = _load(region)
    except FileNotFoundError:
        return _no_data(region)
    try:
        sc = competitor_score_summary(data, name)
    except ValueError as e:
        return Response(
            f"<html><body><h1>Not found</h1><p>{e}</p></body></html>",
            status=404,
            content_type="text/html",
        )
    return inject_nav(render_score(sc, region, _load_tags()), active_region=region)


@bp.route("/recommend")
def recommend():
    region = request.args.get("region", "Graz")
    name = request.args.get("name", "")
    if not name:
        return Response("<h1>Missing name parameter</h1>", status=400, content_type="text/html")
    from analyze import competitor_recommendations
    from web.rendering import render_recommend

    try:
        data = _load(region)
    except FileNotFoundError:
        return _no_data(region)
    try:
        df = competitor_recommendations(data, name)
    except ValueError as e:
        return Response(
            f"<html><body><h1>Not found</h1><p>{e}</p></body></html>",
            status=404,
            content_type="text/html",
        )
    return inject_nav(render_recommend(df, region, name, _load_tags()), active_region=region)


@bp.route("/compare")
def compare():
    region = request.args.get("region", "Graz")
    name_a = request.args.get("a", "")
    name_b = request.args.get("b", "")
    if not name_a or not name_b:
        return Response("<h1>Missing a or b parameter</h1>", status=400, content_type="text/html")
    from analyze import competitor_compare_summary
    from web.rendering import render_compare

    try:
        data = _load(region)
    except FileNotFoundError:
        return _no_data(region)
    try:
        cmp = competitor_compare_summary(data, name_a, name_b)
    except ValueError as e:
        return Response(
            f"<html><body><h1>Not found</h1><p>{e}</p></body></html>",
            status=404,
            content_type="text/html",
        )
    return inject_nav(render_compare(cmp, region, _load_tags()), active_region=region)


@bp.route("/stats")
def stats():
    region = request.args.get("region", "Graz")
    class_filter = request.args.get("class", "all")
    from analyze import boulder_completion_stats, load_data
    from web.rendering import render_stats

    try:
        data = _load(region)
    except FileNotFoundError:
        return _no_data(region)
    df = boulder_completion_stats(data)
    return inject_nav(render_stats(df, region, class_filter, _load_tags()), active_region=region)


@bp.route("/find")
def find():
    region = request.args.get("region", "Graz")
    query = request.args.get("q", "")
    if not query:
        return Response("<h1>Missing q parameter</h1>", status=400, content_type="text/html")
    from web.rendering import render_find

    try:
        data = _load(region)
    except FileNotFoundError:
        return _no_data(region)
    hits = []
    for cls in data.get("classes", []):
        for c in cls.get("competitors", []):
            if query.lower() in c["name"].lower():
                hits.append((cls["name"], c["rank"], c["name"], c["score"], c["total"]))
    return inject_nav(render_find(hits, region, query), active_region=region)
