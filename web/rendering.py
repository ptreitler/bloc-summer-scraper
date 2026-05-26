"""
HTML rendering functions shared by the CLI and the web layer.

Each render_* function accepts pre-computed data (DataFrames / dicts from
analyze.py) and returns a self-contained HTML string (complete page with
<html>, <head>, <body>).

The web layer calls inject_nav() afterwards to insert a navigation bar.
The CLI simply writes the returned string to a file.
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def get_tags(tags: dict, region: str, gym: str, boulder: int) -> list[str]:
    return tags.get(region, {}).get(gym, {}).get(str(boulder), [])


def _pct_style(pct: float, bold: bool = True) -> str:
    if pct >= 60:
        color, bg = "#2d7a2d", "#eafaea"
    elif pct >= 30:
        color, bg = "#8a6000", "#fffbe6"
    else:
        color, bg = "#a00000", "#fff0f0"
    fw = ";font-weight:bold" if bold else ""
    return f"color:{color};background:{bg}{fw}"


def _bracket_style(band: str) -> str:
    return {
        "0–25 %":   "color:#a00000;background:#fff0f0",
        "25–50 %":  "color:#8a6000;background:#fffbe6",
        "50–75 %":  "color:#1a5c8a;background:#e8f4fb",
        "75–100 %": "color:#2d7a2d;background:#eafaea",
    }.get(band, "")


_BASE_CSS = """
  body { font-family: system-ui, sans-serif; padding: 1.5rem; color: #111; max-width: 900px; margin: 0; }
  h1 { font-size: 1.25rem; margin-bottom: 0.1rem; }
  h2 { font-size: 1.05rem; margin: 2rem 0 0.3rem; color: #333;
       border-bottom: 2px solid #ddd; padding-bottom: 0.2rem; }
  h3 { font-size: 0.95rem; margin: 1rem 0 0.3rem; color: #444; }
  p.meta, span.meta { color: #777; font-size: 0.85rem; margin-top: 0; }
  p.sub { color: #555; font-size: 0.9rem; margin-top: 0; margin-bottom: 1.5rem; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 0.8rem; }
  th, td { padding: 0.4rem 0.7rem; border: 1px solid #ddd; text-align: right; }
  th { background: #f0f0f0; font-weight: 600; }
  th:first-child, td:first-child { text-align: left; }
  tr:nth-child(even) td { background: #fafafa; }
"""


# ---------------------------------------------------------------------------
# Nav bar (web layer only – CLI output ignores this)
# ---------------------------------------------------------------------------

def inject_nav(html: str, nav_html: str) -> str:
    """Inject a navigation bar immediately after <body>."""
    return html.replace("<body>", f"<body>\n{nav_html}\n", 1)


# ---------------------------------------------------------------------------
# render_recommend
# ---------------------------------------------------------------------------

def render_recommend(df: pd.DataFrame, region: str, name: str, tags: dict) -> str:
    has_tags = bool(tags.get(region))
    tag_th = "<th>Tags</th>" if has_tags else ""

    rows_html = []
    for i, row in df.iterrows():
        pct = row["topped_pct"]
        tag_list = get_tags(tags, region, row["gym"], int(row["boulder"]))
        tag_cell = f"<td style='color:#555'>{', '.join(tag_list)}</td>" if has_tags else ""
        rows_html.append(
            f"<tr>"
            f"<td>{int(i) + 1}</td>"
            f"<td>{row['gym']}</td>"
            f"<td>{int(row['boulder'])}</td>"
            f"<td>{int(row['topped_count'])}</td>"
            f"<td>{int(row['total'])}</td>"
            f"<td style='{_pct_style(pct)}'>{pct:.1f}%</td>"
            f"{tag_cell}"
            f"</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Recommendations — {name}</title>
<style>
{_BASE_CSS}
  td:nth-child(1), td:nth-child(3), td:nth-child(4), td:nth-child(5) {{ text-align: right; }}
  td:nth-child(6) {{ text-align: right; border-radius: 3px; }}
</style>
</head>
<body>
<h1>Untapped boulders for <strong>{name}</strong></h1>
<p class="sub">Region: {region} &nbsp;|&nbsp; Sorted by peers' completion rate — most reachable first</p>
<table>
<thead>
<tr>
  <th>#</th><th>Gym</th><th>Boulder</th>
  <th>Topped by peers</th><th>Total peers</th><th>Peer completion %</th>{tag_th}
</tr>
</thead>
<tbody>
{"".join(rows_html)}
</tbody>
</table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# render_participants
# ---------------------------------------------------------------------------

def render_participants(summary: dict, lb: dict, region: str) -> str:
    overall = summary["overall"]
    gym_df = summary["gym_stats"]
    brackets_df = lb["brackets_df"]
    visits_df = lb["visits_df"]
    diff_df = lb["diff_df"]
    max_boulders = lb["max_boulders"]
    gyms = gym_df["gym"].unique()

    # overall rows
    overall_rows = []
    for _, row in overall.iterrows():
        bold = " font-weight:bold; background:#f5f5f5;" if row["class"] == "All" else ""
        overall_rows.append(
            f"<tr style='{bold}'>"
            f"<td>{row['class']}</td><td>{int(row['count'])}</td>"
            f"<td>{row['avg_score']:.1f}</td><td>{row['median_score']:.1f}</td>"
            f"<td>{row['avg_total']:.1f}</td><td>{row['avg_pct']:.1f}%</td>"
            f"</tr>"
        )

    # per-gym sections
    gym_sections = []
    for gym in gyms:
        g = gym_df[gym_df["gym"] == gym]
        gym_rows = []
        for _, row in g.iterrows():
            act = row["activation_pct"]
            bold_style = " font-weight:bold; background:#f5f5f5;" if row["class"] == "All" else ""
            gym_rows.append(
                f"<tr style='{bold_style}'>"
                f"<td>{row['class']}</td><td>{int(row['enrolled'])}</td>"
                f"<td>{int(row['visitors'])}</td>"
                f"<td style='{_pct_style(act)}'>{act:.1f}%</td>"
                f"<td>{row['avg_topped']:.1f}</td><td>{row['avg_topped_pct']:.1f}%</td>"
                f"</tr>"
            )
        gym_sections.append(f"""
<h3>{gym}</h3>
<table>
<thead><tr>
  <th>Class</th><th>Enrolled</th><th>Visited</th>
  <th>Activation %</th><th>Avg topped</th><th>Avg topped %</th>
</tr></thead>
<tbody>{"".join(gym_rows)}</tbody>
</table>""")

    # score brackets
    bracket_sections = []
    for cls_name in brackets_df["class"].unique():
        rows = brackets_df[brackets_df["class"] == cls_name]
        tbody = "".join(
            f"<tr><td style='{_bracket_style(r['bracket'])}'>{r['bracket']}</td>"
            f"<td>{int(r['count'])}</td><td>{r['field_pct']:.1f}%</td></tr>"
            for _, r in rows.iterrows()
        )
        bracket_sections.append(f"""
<h3>{cls_name} <span class="meta">(max {max_boulders} boulders)</span></h3>
<table>
<thead><tr><th>Band</th><th>Competitors</th><th>% of field</th></tr></thead>
<tbody>{tbody}</tbody>
</table>""")

    # visits
    visit_sections = []
    for cls_name in visits_df["class"].unique():
        rows = visits_df[visits_df["class"] == cls_name]
        tbody = "".join(
            f"<tr><td>{int(r['gyms_visited'])}</td><td>{int(r['count'])}</td>"
            f"<td>{r['field_pct']:.1f}%</td></tr>"
            for _, r in rows.iterrows()
        )
        visit_sections.append(f"""
<h3>{cls_name}</h3>
<table>
<thead><tr><th>Gyms visited</th><th>Competitors</th><th>% of field</th></tr></thead>
<tbody>{tbody}</tbody>
</table>""")

    # difficulty
    diff_sections = []
    for cls_name in diff_df["class"].unique():
        rows = diff_df[diff_df["class"] == cls_name]
        tbody = "".join(
            f"<tr><td>{r['gym']}</td><td>{int(r['visitors'])}</td>"
            f"<td>{r['avg_topped']:.1f}</td>"
            f"<td style='{_pct_style(r['avg_topped_pct'])}'>{r['avg_topped_pct']:.1f}%</td>"
            f"</tr>"
            for _, r in rows.iterrows()
        )
        diff_sections.append(f"""
<h3>{cls_name}</h3>
<table>
<thead><tr>
  <th>Gym</th><th>Visitors</th><th>Avg topped</th><th>Avg topped %</th>
</tr></thead>
<tbody>{tbody}</tbody>
</table>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Participants — {region}</title>
<style>
{_BASE_CSS}
</style>
</head>
<body>
<h1>Participants — <strong>{region}</strong></h1>
<p class="meta">Scraped: {summary['scraped_at']}</p>

<h2>Overview</h2>
<table>
<thead><tr>
  <th>Class</th><th>Count</th><th>Avg score</th><th>Median score</th>
  <th>Avg topped</th><th>Avg completion %</th>
</tr></thead>
<tbody>{"".join(overall_rows)}</tbody>
</table>

<h2>Gym activation</h2>
{"".join(gym_sections)}

<h2>Score distribution</h2>
{"".join(bracket_sections)}

<h2>Gyms visited per competitor</h2>
{"".join(visit_sections)}

<h2>Gym difficulty <span class="meta">(hardest first)</span></h2>
{"".join(diff_sections)}
</body>
</html>"""


# ---------------------------------------------------------------------------
# render_score
# ---------------------------------------------------------------------------

def render_score(sc: dict, region: str, tags: dict) -> str:
    name = sc["name"]
    cls_name = sc["class_name"]
    has_tags = bool(tags.get(region))

    # gym breakdown rows
    total_topped = int(sc["gym_stats"]["topped"].sum())
    total_max = int(sc["gym_stats"]["n_boulders"].sum())
    total_pct = total_topped / total_max * 100 if total_max else 0.0

    gym_rows = []
    for _, row in sc["gym_stats"].iterrows():
        rank_str = (
            f"{int(row['gym_rank'])}&thinsp;/&thinsp;{int(row['gym_visitors'])}"
            if row["gym_rank"] is not None else "—"
        )
        gym_rows.append(
            f"<tr><td>{row['gym']}</td>"
            f"<td>{int(row['topped'])}&thinsp;/&thinsp;{int(row['n_boulders'])}</td>"
            f"<td>{row['pct']:.1f}%</td><td>{rank_str}</td></tr>"
        )
    gym_rows.append(
        f"<tr style='font-weight:bold;border-top:2px solid #bbb'>"
        f"<td>Total</td>"
        f"<td>{total_topped}&thinsp;/&thinsp;{total_max}</td>"
        f"<td>{total_pct:.1f}%</td>"
        f"<td>{sc['rank']}&thinsp;/&thinsp;{sc['total_competitors']}</td></tr>"
    )

    # hardest topped rows
    hard_rows = []
    for _, row in sc["hardest_topped"].iterrows():
        pct = row["topped_pct"]
        tag_list = get_tags(tags, region, row["gym"], int(row["boulder"]))
        tag_cell = f"<td style='color:#555'>{', '.join(tag_list)}</td>" if has_tags else ""
        hard_rows.append(
            f"<tr><td>{row['gym']}</td><td>{int(row['boulder'])}</td>"
            f"<td>{int(row['topped_count'])}&thinsp;/&thinsp;{int(row['total_peers'])}</td>"
            f"<td style='{_pct_style(pct)}'>{pct:.1f}%</td>{tag_cell}</tr>"
        )

    # boulder grids
    grid_sections = []
    for _, gym_row in sc["gym_stats"].iterrows():
        gym = gym_row["gym"]
        topped_set = set(sc["topped_per_gym"].get(gym, []))
        n = int(gym_row["n_boulders"])
        cells = []
        for b in range(1, n + 1):
            tag_list = get_tags(tags, region, gym, b)
            tag_title = f' title="{", ".join(tag_list)}"' if tag_list else ""
            tag_cls = " has-tags" if tag_list else ""
            cls_span = "b-topped" if b in topped_set else "b-miss"
            cells.append(f"<span class='{cls_span}{tag_cls}'{tag_title}>{b}</span>")
        topped_count = int(gym_row["topped"])
        pct = gym_row["pct"]
        grid_sections.append(
            f"<h3>{gym} <small>({topped_count}&thinsp;/&thinsp;{n}, {pct:.1f}%)</small></h3>"
            f"<div class='boulder-grid'>{''.join(cells)}</div>"
        )

    hardest_section = ""
    if hard_rows:
        tag_th = "<th>Tags</th>" if has_tags else ""
        hardest_section = f"""
<h2>Top 5 hardest boulders topped</h2>
<table>
<thead><tr><th>Gym</th><th>Boulder</th><th>Topped&thinsp;/&thinsp;Peers</th>
<th>Peer %</th>{tag_th}</tr></thead>
<tbody>{"".join(hard_rows)}</tbody>
</table>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Score — {name}</title>
<style>
{_BASE_CSS}
  h3 small {{ font-weight: normal; color: #666; }}
  .boulder-grid {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 0.5rem; }}
  .b-topped, .b-miss {{
    display: inline-block; width: 2rem; text-align: center;
    padding: 0.2rem 0; border-radius: 4px; font-size: 0.8rem; font-weight: 600;
  }}
  .b-topped {{ background: #c6efce; color: #276221; }}
  .b-miss   {{ background: #f0f0f0; color: #999; }}
  .has-tags::after {{ content: '\00B7'; font-size: 0.55rem; vertical-align: super;
                      color: #e06c00; margin-left: 1px; }}
</style>
</head>
<body>
<h1>Score card — <strong>{name}</strong></h1>
<p class="sub">{cls_name} &nbsp;|&nbsp; {region} &nbsp;|&nbsp;
Rank {sc['rank']} of {sc['total_competitors']} &nbsp;|&nbsp;
{sc['score']}&thinsp;/&thinsp;{sc['comp_total']} boulders ({sc['score_pct']:.1f}%)</p>

<h2>Gym breakdown</h2>
<table>
<thead><tr><th>Gym</th><th>Topped&thinsp;/&thinsp;Max</th><th>%</th><th>Rank</th></tr></thead>
<tbody>{"".join(gym_rows)}</tbody>
</table>
{hardest_section}
<h2>Boulders topped per gym</h2>
{"".join(grid_sections)}
</body>
</html>"""


# ---------------------------------------------------------------------------
# render_compare
# ---------------------------------------------------------------------------

def render_compare(cmp: dict, region: str, tags: dict) -> str:
    na, nb = cmp["name_a"], cmp["name_b"]
    has_tags = bool(tags.get(region))
    total = cmp["comp_total"]
    n_competitors = cmp["total_competitors"]
    sa, sb = cmp["score_a"], cmp["score_b"]
    pct_a = sa / total * 100 if total else 0.0
    pct_b = sb / total * 100 if total else 0.0

    winner = "a" if sa > sb else ("b" if sb > sa else "")
    hl_a = " style='font-weight:bold'" if winner == "a" else ""
    hl_b = " style='font-weight:bold'" if winner == "b" else ""

    overall_html = f"""
<table>
<thead><tr><th></th><th>{na}</th><th>{nb}</th></tr></thead>
<tbody>
<tr><td>Rank</td>
    <td{hl_a}>{cmp['rank_a']} / {n_competitors}</td>
    <td{hl_b}>{cmp['rank_b']} / {n_competitors}</td></tr>
<tr><td>Score</td>
    <td{hl_a}>{sa} / {total}</td>
    <td{hl_b}>{sb} / {total}</td></tr>
<tr><td>%</td>
    <td{hl_a}>{pct_a:.1f}%</td>
    <td{hl_b}>{pct_b:.1f}%</td></tr>
</tbody>
</table>"""

    gym_html_rows = []
    total_a = int(cmp["gym_cmp"]["topped_a"].sum())
    total_b = int(cmp["gym_cmp"]["topped_b"].sum())
    total_n = int(cmp["gym_cmp"]["n_boulders"].sum())
    tpct_a = total_a / total_n * 100 if total_n else 0.0
    tpct_b = total_b / total_n * 100 if total_n else 0.0

    for _, row in cmp["gym_cmp"].iterrows():
        n = int(row["n_boulders"])
        win = "a" if row["topped_a"] > row["topped_b"] else ("b" if row["topped_b"] > row["topped_a"] else "")
        hla = " style='font-weight:bold'" if win == "a" else ""
        hlb = " style='font-weight:bold'" if win == "b" else ""
        gym_html_rows.append(
            f"<tr><td>{row['gym']}</td>"
            f"<td{hla}>{int(row['topped_a'])}&thinsp;/&thinsp;{n} ({row['pct_a']:.1f}%)</td>"
            f"<td{hlb}>{int(row['topped_b'])}&thinsp;/&thinsp;{n} ({row['pct_b']:.1f}%)</td></tr>"
        )
    win_total = "a" if total_a > total_b else ("b" if total_b > total_a else "")
    hla = " style='font-weight:bold'" if win_total == "a" else ""
    hlb = " style='font-weight:bold'" if win_total == "b" else ""
    gym_html_rows.append(
        f"<tr style='border-top:2px solid #bbb'>"
        f"<td><strong>Total</strong></td>"
        f"<td{hla}><strong>{total_a}&thinsp;/&thinsp;{total_n} ({tpct_a:.1f}%)</strong></td>"
        f"<td{hlb}><strong>{total_b}&thinsp;/&thinsp;{total_n} ({tpct_b:.1f}%)</strong></td></tr>"
    )

    def _excl_html(df: pd.DataFrame, owner: str, other: str) -> str:
        if df.empty:
            return f"<p class='none'>{owner} has no boulders that {other} hasn't also topped.</p>"
        tag_th = "<th>Tags</th>" if has_tags else ""
        rows = []
        for _, row in df.iterrows():
            pct = row["topped_pct"]
            tag_list = get_tags(tags, region, row["gym"], int(row["boulder"]))
            tag_cell = f"<td style='color:#555'>{', '.join(tag_list)}</td>" if has_tags else ""
            rows.append(
                f"<tr><td>{row['gym']}</td><td>{int(row['boulder'])}</td>"
                f"<td>{int(row['topped_count'])}&thinsp;/&thinsp;{int(row['total_peers'])}</td>"
                f"<td style='{_pct_style(pct)}'>{pct:.1f}%</td>{tag_cell}</tr>"
            )
        return (
            f"<table><thead><tr><th>Gym</th><th>Boulder</th>"
            f"<th>Peers topped</th><th>Peer %</th>{tag_th}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Compare — {na} vs {nb}</title>
<style>
{_BASE_CSS}
  p.none {{ color: #888; font-style: italic; font-size: 0.9rem; }}
</style>
</head>
<body>
<h1>Compare — <strong>{na}</strong> vs <strong>{nb}</strong></h1>
<p class="sub">{cmp['class_name']} &nbsp;|&nbsp; {region}</p>

<h2>Overall</h2>
{overall_html}

<h2>Gym breakdown</h2>
<table>
<thead><tr><th>Gym</th><th>{na}</th><th>{nb}</th></tr></thead>
<tbody>{"".join(gym_html_rows)}</tbody>
</table>

<h2>Topped by {na}, not by {nb}</h2>
{_excl_html(cmp['only_a'], na, nb)}

<h2>Topped by {nb}, not by {na}</h2>
{_excl_html(cmp['only_b'], nb, na)}
</body>
</html>"""


# ---------------------------------------------------------------------------
# render_leaderboard
# ---------------------------------------------------------------------------

def render_leaderboard(lb: dict, region: str, limit: int | None = None) -> str:
    top_df = lb["top_df"]
    brackets_df = lb["brackets_df"]
    visits_df = lb["visits_df"]
    diff_df = lb["diff_df"]
    max_boulders = lb["max_boulders"]

    sections: list[str] = []

    # top-N per class
    for cls_name in top_df["class"].unique():
        rows = top_df[top_df["class"] == cls_name]
        tbody = "".join(
            f"<tr><td>{int(r['position'])}</td>"
            f"<td style='text-align:left'>{r['name']}</td>"
            f"<td>{int(r['score'])}</td><td>{r['score_pct']:.1f}%</td></tr>"
            for _, r in rows.iterrows()
        )
        heading = f"Top {limit} — {cls_name}" if limit else f"Leaderboard — {cls_name}"
        sections.append(f"""
<h2>{heading}</h2>
<table>
<thead><tr><th>#</th><th style="text-align:left">Name</th>
<th>Score</th><th>% of max</th></tr></thead>
<tbody>{tbody}</tbody>
</table>""")

    # score brackets
    sections.append("<h2>Score distribution</h2>")
    for cls_name in brackets_df["class"].unique():
        rows = brackets_df[brackets_df["class"] == cls_name]
        tbody = "".join(
            f"<tr><td style='{_bracket_style(r['bracket'])}'>{r['bracket']}</td>"
            f"<td>{int(r['count'])}</td><td>{r['field_pct']:.1f}%</td></tr>"
            for _, r in rows.iterrows()
        )
        sections.append(f"""
<h3>{cls_name} <span class="meta">(max {max_boulders} boulders)</span></h3>
<table>
<thead><tr><th>Band</th><th>Competitors</th><th>% of field</th></tr></thead>
<tbody>{tbody}</tbody>
</table>""")

    # gym visits
    sections.append("<h2>Gyms visited per competitor</h2>")
    for cls_name in visits_df["class"].unique():
        rows = visits_df[visits_df["class"] == cls_name]
        tbody = "".join(
            f"<tr><td>{int(r['gyms_visited'])}</td><td>{int(r['count'])}</td>"
            f"<td>{r['field_pct']:.1f}%</td></tr>"
            for _, r in rows.iterrows()
        )
        sections.append(f"""
<h3>{cls_name}</h3>
<table>
<thead><tr><th>Gyms visited</th><th>Competitors</th><th>% of field</th></tr></thead>
<tbody>{tbody}</tbody>
</table>""")

    # gym difficulty
    sections.append('<h2>Gym difficulty ranking <span class="meta">(hardest first)</span></h2>')
    for cls_name in diff_df["class"].unique():
        rows = diff_df[diff_df["class"] == cls_name]
        tbody = "".join(
            f"<tr><td>{r['gym']}</td><td>{int(r['visitors'])}</td>"
            f"<td>{r['avg_topped']:.1f}</td>"
            f"<td style='{_pct_style(r['avg_topped_pct'])}'>{r['avg_topped_pct']:.1f}%</td>"
            f"</tr>"
            for _, r in rows.iterrows()
        )
        sections.append(f"""
<h3>{cls_name}</h3>
<table>
<thead><tr>
  <th>Gym</th><th>Visitors</th><th>Avg topped</th><th>Avg topped %</th>
</tr></thead>
<tbody>{tbody}</tbody>
</table>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Leaderboard — {region}</title>
<style>
{_BASE_CSS}
</style>
</head>
<body>
<h1>Leaderboard — <strong>{region}</strong></h1>
<p class="meta">Scraped: {lb['scraped_at']}</p>
{"".join(sections)}
</body>
</html>"""


# ---------------------------------------------------------------------------
# render_stats  (web-only; console uses print_stats_table from analyze.py)
# ---------------------------------------------------------------------------

def render_stats(df: pd.DataFrame, region: str, class_filter: str, tags: dict) -> str:
    has_tags = bool(tags.get(region))
    sections: list[str] = []

    class_label = class_filter if class_filter != "all" else "All classes"
    cls_values = df["class"].unique()
    show_classes = [class_filter] if class_filter != "all" else [c for c in cls_values if c != "All"]

    for gym in df["gym"].unique():
        gym_df = df[df["gym"] == gym]
        rows = []
        boulders = sorted(gym_df["boulder"].unique())
        tag_th = "<th>Tags</th>" if has_tags else ""
        for b in boulders:
            b_rows = gym_df[gym_df["boulder"] == b]
            cells = [f"<td style='text-align:right'>{int(b)}</td>"]
            for cls in show_classes:
                r = b_rows[b_rows["class"] == cls]
                if r.empty:
                    cells.append("<td>—</td><td>—</td>")
                else:
                    r = r.iloc[0]
                    pct = r["topped_pct"]
                    cells.append(
                        f"<td style='text-align:right'>{int(r['topped_count'])}&thinsp;/"
                        f"&thinsp;{int(r['total'])}</td>"
                        f"<td style='{_pct_style(pct)};text-align:right'>{pct:.1f}%</td>"
                    )
            if has_tags:
                tag_list = get_tags(tags, region, gym, int(b))
                cells.append(f"<td style='color:#555'>{', '.join(tag_list)}</td>")
            rows.append(f"<tr>{''.join(cells)}</tr>")

        class_headers = "".join(f"<th>{c} topped</th><th>{c} %</th>" for c in show_classes)
        sections.append(f"""
<h2>{gym}</h2>
<table>
<thead><tr>
  <th>Boulder</th>{class_headers}{tag_th}
</tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Stats — {region}</title>
<style>
{_BASE_CSS}
</style>
</head>
<body>
<h1>Boulder stats — <strong>{region}</strong></h1>
<p class="sub">Class: {class_label}</p>
{"".join(sections)}
</body>
</html>"""


# ---------------------------------------------------------------------------
# render_find  (web-only; console uses Rich table in main.py)
# ---------------------------------------------------------------------------

def render_find(
    hits: list[tuple[str, int, str, int, int]],
    region: str,
    query: str,
) -> str:
    if not hits:
        body = f"<p>No competitors found matching <strong>{query}</strong>.</p>"
    else:
        rows = []
        for cls_name, rank, name, score, total in sorted(hits, key=lambda x: (x[0], x[1])):
            pct = score / total * 100 if total else 0.0
            rows.append(
                f"<tr><td style='color:#888'>{cls_name}</td>"
                f"<td style='text-align:right'>{rank}</td>"
                f"<td style='font-weight:600'>{name}</td>"
                f"<td style='text-align:right'>{score}</td>"
                f"<td style='text-align:right'>{total}</td>"
                f"<td style='text-align:right'>{pct:.1f}%</td></tr>"
            )
        body = f"""
<table>
<thead><tr>
  <th>Class</th><th>Rank</th><th>Name</th>
  <th>Score</th><th>Max</th><th>%</th>
</tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Search — {query}</title>
<style>
{_BASE_CSS}
</style>
</head>
<body>
<h1>Search results for <strong>{query}</strong></h1>
<p class="sub">Region: {region} &nbsp;|&nbsp; {len(hits)} result(s)</p>
{body}
</body>
</html>"""
