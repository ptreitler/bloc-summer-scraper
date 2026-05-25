"""
Bloc Summer Scraper CLI

Commands:
  scrape [--force]                  Fetch and cache competition data
  stats [--class Männer|Frauen]     Show completion tables; --chart saves PNGs
  recommend --name "Name"           Rank untapped boulders for a competitor
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()


def cmd_scrape(args: argparse.Namespace) -> None:
    from scraper import scrape_all
    scrape_all(region_name=args.region, force=args.force)


def cmd_stats(args: argparse.Namespace) -> None:
    from analyze import load_data, print_stats_table, plot_distribution

    try:
        data = load_data(region=args.region)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    class_filter = args.cls if args.cls else "all"
    print_stats_table(data, class_filter)

    if args.chart:
        console.print("\n[bold]Saving charts...[/bold]")
        plot_distribution(data, class_filter)


def cmd_recommend(args: argparse.Namespace) -> None:
    from analyze import load_data, competitor_recommendations

    try:
        data = load_data(region=args.region)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    try:
        df = competitor_recommendations(data, args.name)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")

        # Print available names to help the user
        names = sorted(
            comp["name"]
            for cls in data["classes"]
            for comp in cls["competitors"]
        )
        console.print("\n[bold]Available competitors:[/bold]")
        for n in names:
            console.print(f"  {n}")
        sys.exit(1)

    if df.empty:
        console.print(f"[green]{args.name} has topped every single boulder — impressive![/green]")
        return

    table = Table(
        title=f"Untapped boulders for [bold]{args.name}[/bold] "
              "(sorted by peers' completion rate — most reachable first)",
        show_header=True,
        header_style="bold",
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Gym")
    table.add_column("Boulder", justify="right")
    table.add_column("Topped by peers", justify="right")
    table.add_column("Total peers", justify="right")
    table.add_column("Peer completion %", justify="right")

    for i, row in df.iterrows():
        pct = row["topped_pct"]
        color = "green" if pct >= 60 else "yellow" if pct >= 30 else "red"
        table.add_row(
            str(int(i) + 1),
            row["gym"],
            str(int(row["boulder"])),
            str(int(row["topped_count"])),
            str(int(row["total"])),
            f"[{color}]{pct:.1f}%[/{color}]",
        )

    console.print(table)

    # Save colour-coded HTML table
    name_slug = args.name.lower().replace(" ", "_")
    region_slug = args.region.lower().replace(" ", "_")
    out_dir = Path("data") / "recommend"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{region_slug}_{name_slug}.html"

    rows_html = []
    for i, row in df.iterrows():
        pct = row["topped_pct"]
        if pct >= 60:
            color = "#2d7a2d"
            bg = "#eafaea"
        elif pct >= 30:
            color = "#8a6000"
            bg = "#fffbe6"
        else:
            color = "#a00000"
            bg = "#fff0f0"
        rows_html.append(
            f"<tr>"
            f"<td>{int(i) + 1}</td>"
            f"<td>{row['gym']}</td>"
            f"<td>{int(row['boulder'])}</td>"
            f"<td>{int(row['topped_count'])}</td>"
            f"<td>{int(row['total'])}</td>"
            f"<td style='color:{color};background:{bg};font-weight:bold'>{pct:.1f}%</td>"
            f"</tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Recommendations — {args.name}</title>
<style>
  body {{ font-family: system-ui, sans-serif; padding: 1.5rem; color: #111; }}
  h1 {{ font-size: 1.1rem; margin-bottom: 0.25rem; }}
  p.subtitle {{ color: #555; font-size: 0.9rem; margin-top: 0; }}
  table {{ border-collapse: collapse; width: 100%; max-width: 820px; }}
  th, td {{ padding: 0.45rem 0.75rem; text-align: left; border: 1px solid #ddd; }}
  th {{ background: #f0f0f0; font-weight: 600; }}
  tr:nth-child(even) td {{ background: #fafafa; }}
  td:nth-child(1), td:nth-child(3), td:nth-child(4), td:nth-child(5) {{ text-align: right; }}
  td:nth-child(6) {{ text-align: right; border-radius: 3px; }}
</style>
</head>
<body>
<h1>Untapped boulders for <strong>{args.name}</strong></h1>
<p class="subtitle">Region: {args.region} &nbsp;|&nbsp; Sorted by peers' completion rate — most reachable first</p>
<table>
<thead>
<tr>
  <th>#</th><th>Gym</th><th>Boulder</th>
  <th>Topped by peers</th><th>Total peers</th><th>Peer completion %</th>
</tr>
</thead>
<tbody>
{"".join(rows_html)}
</tbody>
</table>
</body>
</html>"""

    out_path.write_text(html, encoding="utf-8")
    console.print(f"  Saved: [cyan]{out_path}[/cyan]")


def cmd_participants(args: argparse.Namespace) -> None:
    from analyze import load_data, participant_summary, leaderboard_summary

    try:
        data = load_data(region=args.region)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    summary = participant_summary(data)
    overall = summary["overall"]
    gym_df = summary["gym_stats"]

    lb = leaderboard_summary(data)
    brackets_df = lb["brackets_df"]
    visits_df   = lb["visits_df"]
    diff_df     = lb["diff_df"]
    max_boulders = lb["max_boulders"]

    # ---- terminal: overall table ----
    t_overall = Table(
        title=f"[bold]{args.region}[/bold] — Participant overview",
        show_header=True, header_style="bold",
    )
    t_overall.add_column("Class")
    t_overall.add_column("Count", justify="right")
    t_overall.add_column("Avg score", justify="right")
    t_overall.add_column("Median score", justify="right")
    t_overall.add_column("Avg topped", justify="right")
    t_overall.add_column("Avg completion %", justify="right")

    for _, row in overall.iterrows():
        style = "bold" if row["class"] == "All" else ""
        t_overall.add_row(
            row["class"],
            str(int(row["count"])),
            f"{row['avg_score']:.1f}",
            f"{row['median_score']:.1f}",
            f"{row['avg_total']:.1f}",
            f"{row['avg_pct']:.1f}%",
            style=style,
        )
    console.print(t_overall)

    # ---- terminal: per-gym activation table ----
    gyms = gym_df["gym"].unique()
    for gym in gyms:
        g = gym_df[gym_df["gym"] == gym]
        t_gym = Table(
            title=f"[bold]{gym}[/bold] — Activation & topped",
            show_header=True, header_style="bold",
        )
        t_gym.add_column("Class")
        t_gym.add_column("Enrolled", justify="right")
        t_gym.add_column("Visited", justify="right")
        t_gym.add_column("Activation %", justify="right")
        t_gym.add_column("Avg topped", justify="right")
        t_gym.add_column("Avg topped %", justify="right")

        for _, row in g.iterrows():
            act = row["activation_pct"]
            color = "green" if act >= 70 else "yellow" if act >= 40 else "red"
            style = "bold" if row["class"] == "All" else ""
            t_gym.add_row(
                row["class"],
                str(int(row["enrolled"])),
                str(int(row["visitors"])),
                f"[{color}]{act:.1f}%[/{color}]",
                f"{row['avg_topped']:.1f}",
                f"{row['avg_topped_pct']:.1f}%",
                style=style,
            )
        console.print(t_gym)

    # ---- HTML output ----
    region_slug = args.region.lower().replace(" ", "_")
    out_dir = Path("data") / "participants"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{region_slug}.html"

    def pct_style(pct: float) -> str:
        if pct >= 70:
            return "color:#2d7a2d;background:#eafaea;font-weight:bold"
        if pct >= 40:
            return "color:#8a6000;background:#fffbe6;font-weight:bold"
        return "color:#a00000;background:#fff0f0;font-weight:bold"

    def bracket_style(band: str) -> str:
        return {
            "0–25 %":   "color:#a00000;background:#fff0f0",
            "25–50 %":  "color:#8a6000;background:#fffbe6",
            "50–75 %":  "color:#1a5c8a;background:#e8f4fb",
            "75–100 %": "color:#2d7a2d;background:#eafaea",
        }.get(band, "")

    def difficulty_style(pct: float) -> str:
        if pct >= 60:
            return "color:#2d7a2d;background:#eafaea;font-weight:bold"
        if pct >= 40:
            return "color:#8a6000;background:#fffbe6;font-weight:bold"
        return "color:#a00000;background:#fff0f0;font-weight:bold"

    # overall table rows
    overall_rows_html = []
    for _, row in overall.iterrows():
        bold = " font-weight:bold; background:#f5f5f5;" if row["class"] == "All" else ""
        overall_rows_html.append(
            f"<tr style='{bold}'>"
            f"<td>{row['class']}</td>"
            f"<td>{int(row['count'])}</td>"
            f"<td>{row['avg_score']:.1f}</td>"
            f"<td>{row['median_score']:.1f}</td>"
            f"<td>{row['avg_total']:.1f}</td>"
            f"<td>{row['avg_pct']:.1f}%</td>"
            f"</tr>"
        )

    # per-gym activation sections
    gym_sections_html = []
    for gym in gyms:
        g = gym_df[gym_df["gym"] == gym]
        gym_rows_html = []
        for _, row in g.iterrows():
            act = row["activation_pct"]
            bold_style = " font-weight:bold; background:#f5f5f5;" if row["class"] == "All" else ""
            gym_rows_html.append(
                f"<tr style='{bold_style}'>"
                f"<td>{row['class']}</td>"
                f"<td>{int(row['enrolled'])}</td>"
                f"<td>{int(row['visitors'])}</td>"
                f"<td style='{pct_style(act)}'>{act:.1f}%</td>"
                f"<td>{row['avg_topped']:.1f}</td>"
                f"<td>{row['avg_topped_pct']:.1f}%</td>"
                f"</tr>"
            )
        gym_sections_html.append(f"""
<h3>{gym}</h3>
<table>
<thead><tr>
  <th>Class</th><th>Enrolled</th><th>Visited</th>
  <th>Activation %</th><th>Avg topped</th><th>Avg topped %</th>
</tr></thead>
<tbody>{"".join(gym_rows_html)}</tbody>
</table>""")

    # score distribution sections
    bracket_sections_html = []
    for cls_name in brackets_df["class"].unique():
        rows = brackets_df[brackets_df["class"] == cls_name]
        tbody = "".join(
            f"<tr>"
            f"<td style='{bracket_style(r['bracket'])}'>{r['bracket']}</td>"
            f"<td>{int(r['count'])}</td>"
            f"<td>{r['field_pct']:.1f}%</td>"
            f"</tr>"
            for _, r in rows.iterrows()
        )
        bracket_sections_html.append(f"""
<h3>{cls_name} <span class="meta">(max {max_boulders} boulders)</span></h3>
<table>
<thead><tr><th>Band</th><th>Competitors</th><th>% of field</th></tr></thead>
<tbody>{tbody}</tbody>
</table>""")

    # gym visit distribution sections
    visit_sections_html = []
    for cls_name in visits_df["class"].unique():
        rows = visits_df[visits_df["class"] == cls_name]
        tbody = "".join(
            f"<tr><td>{int(r['gyms_visited'])}</td><td>{int(r['count'])}</td><td>{r['field_pct']:.1f}%</td></tr>"
            for _, r in rows.iterrows()
        )
        visit_sections_html.append(f"""
<h3>{cls_name}</h3>
<table>
<thead><tr><th>Gyms visited</th><th>Competitors</th><th>% of field</th></tr></thead>
<tbody>{tbody}</tbody>
</table>""")

    # gym difficulty sections
    diff_sections_html = []
    for cls_name in diff_df["class"].unique():
        rows = diff_df[diff_df["class"] == cls_name]
        tbody = "".join(
            f"<tr>"
            f"<td style='text-align:left'>{r['gym']}</td>"
            f"<td>{int(r['visitors'])}</td>"
            f"<td>{r['avg_topped']:.1f}</td>"
            f"<td style='{difficulty_style(r['avg_topped_pct'])}'>{r['avg_topped_pct']:.1f}%</td>"
            f"</tr>"
            for _, r in rows.iterrows()
        )
        diff_sections_html.append(f"""
<h3>{cls_name}</h3>
<table>
<thead><tr>
  <th style="text-align:left">Gym</th><th>Visitors</th><th>Avg topped</th><th>Avg topped %</th>
</tr></thead>
<tbody>{tbody}</tbody>
</table>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Participants — {args.region}</title>
<style>
  body {{ font-family: system-ui, sans-serif; padding: 1.5rem; color: #111; max-width: 860px; }}
  h1 {{ font-size: 1.3rem; margin-bottom: 0.1rem; }}
  h2 {{ font-size: 1.05rem; margin: 2rem 0 0.3rem; color: #333; border-bottom: 2px solid #ddd; padding-bottom: 0.2rem; }}
  h3 {{ font-size: 0.95rem; margin: 1rem 0 0.3rem; color: #444; }}
  p.meta, span.meta {{ color: #777; font-size: 0.85rem; margin-top: 0; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 0.8rem; }}
  th, td {{ padding: 0.4rem 0.7rem; text-align: right; border: 1px solid #ddd; }}
  th {{ background: #f0f0f0; font-weight: 600; }}
  th:first-child, td:first-child {{ text-align: left; }}
  tr:nth-child(even) td {{ background: #fafafa; }}
</style>
</head>
<body>
<h1>Participants — <strong>{args.region}</strong></h1>
<p class="meta">Scraped: {summary['scraped_at']}</p>

<h2>Overview</h2>
<table>
<thead><tr>
  <th>Class</th><th>Count</th><th>Avg score</th><th>Median score</th>
  <th>Avg topped</th><th>Avg completion %</th>
</tr></thead>
<tbody>{"".join(overall_rows_html)}</tbody>
</table>

<h2>Gym activation</h2>
{"".join(gym_sections_html)}

<h2>Score distribution</h2>
{"".join(bracket_sections_html)}

<h2>Gyms visited per competitor</h2>
{"".join(visit_sections_html)}

<h2>Gym difficulty <span class="meta">(hardest first)</span></h2>
{"".join(diff_sections_html)}
</body>
</html>"""

    out_path.write_text(html, encoding="utf-8")
    console.print(f"\n  Saved: [cyan]{out_path}[/cyan]")


def cmd_score(args: argparse.Namespace) -> None:
    from analyze import load_data, competitor_score_summary

    try:
        data = load_data(region=args.region)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    try:
        sc = competitor_score_summary(data, args.name)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    name = sc["name"]
    cls_name = sc["class_name"]
    region = args.region

    # ── 1. Overall summary ──────────────────────────────────────────────────
    summary = Table(title=f"Score card — [bold]{name}[/bold] ({cls_name}, {region})",
                    show_header=True, header_style="bold")
    summary.add_column("Rank", justify="right")
    summary.add_column("Field", justify="right")
    summary.add_column("Score", justify="right")
    summary.add_column("Max", justify="right")
    summary.add_column("%", justify="right")
    summary.add_row(
        str(sc["rank"]),
        str(sc["total_competitors"]),
        str(sc["score"]),
        str(sc["comp_total"]),
        f"{sc['score_pct']:.1f}%",
    )
    console.print(summary)

    # ── 2. Per-gym stats ────────────────────────────────────────────────────
    gym_t = Table(title="Gym breakdown", show_header=True, header_style="bold")
    gym_t.add_column("Gym", style="bold")
    gym_t.add_column("Topped", justify="right")
    gym_t.add_column("Max", justify="right")
    gym_t.add_column("%", justify="right")
    gym_t.add_column("Rank", justify="right")
    for _, row in sc["gym_stats"].iterrows():
        rank_str = f"{int(row['gym_rank'])}/{int(row['gym_visitors'])}" if row["gym_rank"] is not None else "—"
        gym_t.add_row(
            row["gym"],
            str(int(row["topped"])),
            str(int(row["n_boulders"])),
            f"{row['pct']:.1f}%",
            rank_str,
        )
    total_topped = int(sc["gym_stats"]["topped"].sum())
    total_max = int(sc["gym_stats"]["n_boulders"].sum())
    total_pct = total_topped / total_max * 100 if total_max else 0.0
    gym_t.add_section()
    gym_t.add_row(
        "[bold]Total[/bold]",
        f"[bold]{total_topped}[/bold]",
        f"[bold]{total_max}[/bold]",
        f"[bold]{total_pct:.1f}%[/bold]",
        f"[bold]{sc['rank']}/{sc['total_competitors']}[/bold]",
    )
    console.print(gym_t)

    # ── 3. Top-5 hardest topped ─────────────────────────────────────────────
    if not sc["hardest_topped"].empty:
        hard_t = Table(title="Top 5 hardest boulders topped", show_header=True, header_style="bold")
        hard_t.add_column("Gym")
        hard_t.add_column("Boulder", justify="right")
        hard_t.add_column("Topped by", justify="right")
        hard_t.add_column("Peers", justify="right")
        hard_t.add_column("%", justify="right")
        for _, row in sc["hardest_topped"].iterrows():
            pct = row["topped_pct"]
            color = "green" if pct >= 60 else "yellow" if pct >= 30 else "red"
            hard_t.add_row(
                row["gym"],
                str(int(row["boulder"])),
                str(int(row["topped_count"])),
                str(int(row["total_peers"])),
                f"[{color}]{pct:.1f}%[/{color}]",
            )
        console.print(hard_t)

    # ── 4. Boulders topped per gym ──────────────────────────────────────────
    for gym, boulders in sc["topped_per_gym"].items():
        if boulders:
            console.print(f"[bold]{gym}[/bold]: {', '.join(str(b) for b in boulders)}")
        else:
            console.print(f"[bold]{gym}[/bold]: [dim]none[/dim]")

    # ── HTML output ─────────────────────────────────────────────────────────
    name_slug = name.lower().replace(" ", "_")
    region_slug = region.lower().replace(" ", "_")
    out_dir = Path("data") / "score"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{region_slug}_{name_slug}.html"

    # gym breakdown rows
    total_topped = int(sc["gym_stats"]["topped"].sum())
    total_max = int(sc["gym_stats"]["n_boulders"].sum())
    total_pct = total_topped / total_max * 100 if total_max else 0.0
    gym_rows_html = []
    for _, row in sc["gym_stats"].iterrows():
        rank_str = f"{int(row['gym_rank'])}&thinsp;/&thinsp;{int(row['gym_visitors'])}" if row["gym_rank"] is not None else "—"
        gym_rows_html.append(
            f"<tr><td>{row['gym']}</td>"
            f"<td>{int(row['topped'])}&thinsp;/&thinsp;{int(row['n_boulders'])}</td>"
            f"<td>{row['pct']:.1f}%</td>"
            f"<td>{rank_str}</td></tr>"
        )
    gym_rows_html.append(
        f"<tr style='font-weight:bold;border-top:2px solid #bbb'>"
        f"<td>Total</td>"
        f"<td>{total_topped}&thinsp;/&thinsp;{total_max}</td>"
        f"<td>{total_pct:.1f}%</td>"
        f"<td>{sc['rank']}&thinsp;/&thinsp;{sc['total_competitors']}</td></tr>"
    )

    # hardest topped rows
    hard_rows_html = []
    for _, row in sc["hardest_topped"].iterrows():
        pct = row["topped_pct"]
        color = "#2d7a2d" if pct >= 60 else "#8a6000" if pct >= 30 else "#a00000"
        bg = "#eafaea" if pct >= 60 else "#fffbe6" if pct >= 30 else "#fff0f0"
        hard_rows_html.append(
            f"<tr><td>{row['gym']}</td>"
            f"<td>{int(row['boulder'])}</td>"
            f"<td>{int(row['topped_count'])}&thinsp;/&thinsp;{int(row['total_peers'])}</td>"
            f"<td style='color:{color};background:{bg};font-weight:bold'>{pct:.1f}%</td></tr>"
        )

    # boulder grids per gym
    grid_sections_html = []
    for _, gym_row in sc["gym_stats"].iterrows():
        gym = gym_row["gym"]
        topped_set = set(sc["topped_per_gym"].get(gym, []))
        n = int(gym_row["n_boulders"])
        cells = []
        for b in range(1, n + 1):
            if b in topped_set:
                cells.append(f"<span class='b-topped'>{b}</span>")
            else:
                cells.append(f"<span class='b-miss'>{b}</span>")
        topped_count = int(gym_row["topped"])
        pct = gym_row["pct"]
        grid_sections_html.append(
            f"<h3>{gym} <small>({topped_count}&thinsp;/&thinsp;{n}, {pct:.1f}%)</small></h3>"
            f"<div class='boulder-grid'>{''.join(cells)}</div>"
        )

    hardest_section = ""
    if hard_rows_html:
        hardest_section = f"""
<h2>Top 5 hardest boulders topped</h2>
<table>
<thead><tr><th>Gym</th><th>Boulder</th><th>Topped&thinsp;/&thinsp;Peers</th><th>Peer %</th></tr></thead>
<tbody>{"".join(hard_rows_html)}</tbody>
</table>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Score — {name}</title>
<style>
  body {{ font-family: system-ui, sans-serif; padding: 1.5rem; color: #111; max-width: 860px; }}
  h1 {{ font-size: 1.25rem; margin-bottom: 0.1rem; }}
  p.sub {{ color: #555; font-size: 0.9rem; margin-top: 0; margin-bottom: 1.5rem; }}
  h2 {{ font-size: 1rem; margin: 1.5rem 0 0.4rem; border-bottom: 1px solid #ddd; padding-bottom: 0.2rem; }}
  h3 {{ font-size: 0.95rem; margin: 1rem 0 0.3rem; color: #333; }}
  h3 small {{ font-weight: normal; color: #666; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 1rem; }}
  th, td {{ padding: 0.4rem 0.7rem; border: 1px solid #ddd; }}
  th {{ background: #f0f0f0; font-weight: 600; text-align: left; }}
  td {{ text-align: right; }}
  td:first-child {{ text-align: left; }}
  tr:nth-child(even) td {{ background: #fafafa; }}
  .boulder-grid {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 0.5rem; }}
  .b-topped, .b-miss {{
    display: inline-block; width: 2rem; text-align: center;
    padding: 0.2rem 0; border-radius: 4px; font-size: 0.8rem; font-weight: 600;
  }}
  .b-topped {{ background: #c6efce; color: #276221; }}
  .b-miss   {{ background: #f0f0f0; color: #999; }}
</style>
</head>
<body>
<h1>Score card — <strong>{name}</strong></h1>
<p class="sub">{cls_name} &nbsp;|&nbsp; {region} &nbsp;|&nbsp; Rank {sc['rank']} of {sc['total_competitors']} &nbsp;|&nbsp; {sc['score']}&thinsp;/&thinsp;{sc['comp_total']} boulders ({sc['score_pct']:.1f}%)</p>

<h2>Gym breakdown</h2>
<table>
<thead><tr><th>Gym</th><th>Topped&thinsp;/&thinsp;Max</th><th>%</th><th>Rank</th></tr></thead>
<tbody>{"".join(gym_rows_html)}</tbody>
</table>
{hardest_section}
<h2>Boulders topped per gym</h2>
{"".join(grid_sections_html)}
</body>
</html>"""

    out_path.write_text(html, encoding="utf-8")
    console.print(f"  Saved: [cyan]{out_path}[/cyan]")


def cmd_compare(args: argparse.Namespace) -> None:
    from analyze import load_data, competitor_compare_summary

    try:
        data = load_data(region=args.region)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    try:
        cmp = competitor_compare_summary(data, args.name_a, args.name_b)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    na, nb = cmp["name_a"], cmp["name_b"]
    region = args.region
    total = cmp["comp_total"]
    n_competitors = cmp["total_competitors"]

    def pct_color(pct: float) -> str:
        return "green" if pct >= 60 else "yellow" if pct >= 30 else "red"

    # ── 1. Overall comparison ────────────────────────────────────────────────
    ov = Table(
        title=f"[bold]{na}[/bold] vs [bold]{nb}[/bold] — {cmp['class_name']}, {region}",
        show_header=True, header_style="bold",
    )
    ov.add_column("", style="dim")
    ov.add_column(na, justify="right")
    ov.add_column(nb, justify="right")
    sa, sb = cmp["score_a"], cmp["score_b"]
    pct_a = sa / total * 100 if total else 0.0
    pct_b = sb / total * 100 if total else 0.0
    ov.add_row("Rank", f"{cmp['rank_a']} / {n_competitors}", f"{cmp['rank_b']} / {n_competitors}")
    ov.add_row("Score", str(sa), str(sb))
    ov.add_row("Max", str(total), str(total))
    ov.add_row("%", f"{pct_a:.1f}%", f"{pct_b:.1f}%")
    console.print(ov)

    # ── 2. Per-gym comparison ────────────────────────────────────────────────
    gym_t = Table(title="Gym breakdown", show_header=True, header_style="bold")
    gym_t.add_column("Gym", style="bold")
    gym_t.add_column(f"{na} topped", justify="right")
    gym_t.add_column(f"{na} %", justify="right")
    gym_t.add_column(f"{nb} topped", justify="right")
    gym_t.add_column(f"{nb} %", justify="right")
    for _, row in cmp["gym_cmp"].iterrows():
        n = int(row["n_boulders"])
        gym_t.add_row(
            row["gym"],
            f"{int(row['topped_a'])} / {n}",
            f"{row['pct_a']:.1f}%",
            f"{int(row['topped_b'])} / {n}",
            f"{row['pct_b']:.1f}%",
        )
    total_a = int(cmp["gym_cmp"]["topped_a"].sum())
    total_b = int(cmp["gym_cmp"]["topped_b"].sum())
    total_n = int(cmp["gym_cmp"]["n_boulders"].sum())
    tpct_a = total_a / total_n * 100 if total_n else 0.0
    tpct_b = total_b / total_n * 100 if total_n else 0.0
    gym_t.add_section()
    gym_t.add_row(
        "[bold]Total[/bold]",
        f"[bold]{total_a} / {total_n}[/bold]",
        f"[bold]{tpct_a:.1f}%[/bold]",
        f"[bold]{total_b} / {total_n}[/bold]",
        f"[bold]{tpct_b:.1f}%[/bold]",
    )
    console.print(gym_t)

    # ── 3 & 4. Exclusive boulders ────────────────────────────────────────────
    def _print_exclusive(df, owner: str, other: str) -> None:
        if df.empty:
            console.print(f"[dim]{owner} has no boulders that {other} hasn't also topped.[/dim]")
            return
        t = Table(
            title=f"Topped by [bold]{owner}[/bold], not by [bold]{other}[/bold]",
            show_header=True, header_style="bold",
        )
        t.add_column("Gym")
        t.add_column("Boulder", justify="right")
        t.add_column("Topped by peers", justify="right")
        t.add_column("Total peers", justify="right")
        t.add_column("Peer %", justify="right")
        for _, row in df.iterrows():
            pct = row["topped_pct"]
            color = pct_color(pct)
            t.add_row(
                row["gym"],
                str(int(row["boulder"])),
                str(int(row["topped_count"])),
                str(int(row["total_peers"])),
                f"[{color}]{pct:.1f}%[/{color}]",
            )
        console.print(t)

    _print_exclusive(cmp["only_a"], na, nb)
    _print_exclusive(cmp["only_b"], nb, na)

    # ── HTML output ──────────────────────────────────────────────────────────
    slug_a = na.lower().replace(" ", "_")
    slug_b = nb.lower().replace(" ", "_")
    region_slug = region.lower().replace(" ", "_")
    out_dir = Path("data") / "compare"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{region_slug}_{slug_a}_vs_{slug_b}.html"

    def _pct_style(pct: float) -> str:
        if pct >= 60:
            return "color:#2d7a2d;background:#eafaea"
        if pct >= 30:
            return "color:#8a6000;background:#fffbe6"
        return "color:#a00000;background:#fff0f0"

    # overall rows
    winner_score = "a" if sa > sb else ("b" if sb > sa else "")
    hl_a = " style='font-weight:bold'" if winner_score == "a" else ""
    hl_b = " style='font-weight:bold'" if winner_score == "b" else ""
    overall_html = f"""
<table>
<thead><tr><th></th><th>{na}</th><th>{nb}</th></tr></thead>
<tbody>
<tr><td>Rank</td><td{hl_a}>{cmp['rank_a']} / {n_competitors}</td><td{hl_b}>{cmp['rank_b']} / {n_competitors}</td></tr>
<tr><td>Score</td><td{hl_a}>{sa} / {total}</td><td{hl_b}>{sb} / {total}</td></tr>
<tr><td>%</td><td{hl_a}>{pct_a:.1f}%</td><td{hl_b}>{pct_b:.1f}%</td></tr>
</tbody>
</table>"""

    # gym rows
    gym_html_rows = []
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

    def _exclusive_html(df, owner: str, other: str) -> str:
        if df.empty:
            return f"<p class='none'>{owner} has no boulders that {other} hasn't also topped.</p>"
        rows = []
        for _, row in df.iterrows():
            pct = row["topped_pct"]
            style = _pct_style(pct)
            rows.append(
                f"<tr><td>{row['gym']}</td>"
                f"<td>{int(row['boulder'])}</td>"
                f"<td>{int(row['topped_count'])}&thinsp;/&thinsp;{int(row['total_peers'])}</td>"
                f"<td style='{style};font-weight:bold'>{pct:.1f}%</td></tr>"
            )
        return (
            f"<table>"
            f"<thead><tr><th>Gym</th><th>Boulder</th><th>Peers topped</th><th>Peer %</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            f"</table>"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Compare — {na} vs {nb}</title>
<style>
  body {{ font-family: system-ui, sans-serif; padding: 1.5rem; color: #111; max-width: 900px; }}
  h1 {{ font-size: 1.2rem; margin-bottom: 0.1rem; }}
  p.sub {{ color: #555; font-size: 0.9rem; margin-top: 0; margin-bottom: 1.5rem; }}
  h2 {{ font-size: 1rem; margin: 1.5rem 0 0.4rem; border-bottom: 1px solid #ddd; padding-bottom: 0.2rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 0.5rem; }}
  th, td {{ padding: 0.4rem 0.7rem; border: 1px solid #ddd; }}
  th {{ background: #f0f0f0; font-weight: 600; text-align: left; }}
  td {{ text-align: right; }}
  td:first-child {{ text-align: left; }}
  tr:nth-child(even) td {{ background: #fafafa; }}
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
{_exclusive_html(cmp['only_a'], na, nb)}

<h2>Topped by {nb}, not by {na}</h2>
{_exclusive_html(cmp['only_b'], nb, na)}
</body>
</html>"""

    out_path.write_text(html, encoding="utf-8")
    console.print(f"  Saved: [cyan]{out_path}[/cyan]")


def cmd_find(args: argparse.Namespace) -> None:
    from analyze import load_data

    data = load_data(region=args.region)
    query = args.query.lower()

    hits: list[tuple[str, int, str, int, int]] = []  # class, rank, name, score, total
    for cls in data["classes"]:
        cls_name = cls["name"]
        for c in cls["competitors"]:
            if query in c["name"].lower():
                hits.append((cls_name, c["rank"], c["name"], c["score"], c["total"]))

    if not hits:
        console.print(f"[yellow]No competitors found matching '{args.query}'[/yellow]")
        return

    t = Table(title=f"Search: '{args.query}' — {args.region}", show_lines=False)
    t.add_column("Class", style="dim")
    t.add_column("Rank", justify="right")
    t.add_column("Name", style="bold")
    t.add_column("Score", justify="right")
    t.add_column("Max", justify="right")
    t.add_column("%", justify="right")
    for cls_name, rank, name, score, total in sorted(hits, key=lambda x: (x[0], x[1])):
        pct = score / total * 100 if total else 0.0
        t.add_row(cls_name, str(rank), name, str(score), str(total), f"{pct:.1f}%")
    console.print(t)


def cmd_leaderboard(args: argparse.Namespace) -> None:
    from analyze import load_data, leaderboard_summary

    try:
        data = load_data(region=args.region)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    top_n = args.limit
    lb = leaderboard_summary(data, top_n=top_n)
    top_df = lb["top_df"]
    brackets_df = lb["brackets_df"]
    visits_df = lb["visits_df"]
    diff_df = lb["diff_df"]
    max_boulders = lb["max_boulders"]

    # ---- terminal output ----
    for cls_name in top_df["class"].unique():
        rows = top_df[top_df["class"] == cls_name]
        t = Table(
            title=f"{'Top ' + str(top_n) + ' — ' if top_n else ''}{cls_name} — [bold]{args.region}[/bold]",
            show_header=True, header_style="bold",
        )
        t.add_column("#", justify="right", style="dim")
        t.add_column("Name")
        t.add_column("Score", justify="right")
        t.add_column("% of max", justify="right")
        for _, row in rows.iterrows():
            pos = int(row["position"])
            medal = {1: "[yellow]1[/yellow]", 2: "[white]2[/white]", 3: "[yellow3]3[/yellow3]"}.get(pos, str(pos))
            t.add_row(medal, row["name"], str(int(row["score"])), f"{row['score_pct']:.1f}%")
        console.print(t)

    for cls_name in brackets_df["class"].unique():
        rows = brackets_df[brackets_df["class"] == cls_name]
        t = Table(
            title=f"Score distribution — [bold]{cls_name}[/bold]  (max {max_boulders} boulders)",
            show_header=True, header_style="bold",
        )
        t.add_column("Band (% of max)")
        t.add_column("Competitors", justify="right")
        t.add_column("% of field", justify="right")
        colors = ["red", "yellow", "cyan", "green"]
        for (_, row), color in zip(rows.iterrows(), colors):
            t.add_row(
                f"[{color}]{row['bracket']}[/{color}]",
                str(int(row["count"])),
                f"{row['field_pct']:.1f}%",
            )
        console.print(t)

    for cls_name in visits_df["class"].unique():
        rows = visits_df[visits_df["class"] == cls_name]
        t = Table(
            title=f"Gyms visited — [bold]{cls_name}[/bold]",
            show_header=True, header_style="bold",
        )
        t.add_column("Gyms visited", justify="right")
        t.add_column("Competitors", justify="right")
        t.add_column("% of field", justify="right")
        for _, row in rows.iterrows():
            t.add_row(str(int(row["gyms_visited"])), str(int(row["count"])), f"{row['field_pct']:.1f}%")
        console.print(t)

    for cls_name in diff_df["class"].unique():
        rows = diff_df[diff_df["class"] == cls_name]
        t = Table(
            title=f"Gym difficulty — [bold]{cls_name}[/bold]  (hardest first)",
            show_header=True, header_style="bold",
        )
        t.add_column("Gym")
        t.add_column("Visitors", justify="right")
        t.add_column("Avg topped", justify="right")
        t.add_column("Avg topped %", justify="right")
        n_gyms = len(rows)
        for i, (_, row) in enumerate(rows.iterrows()):
            pct = row["avg_topped_pct"]
            color = "green" if i >= n_gyms - 1 else "yellow" if i >= n_gyms // 2 else "red"
            t.add_row(
                row["gym"],
                str(int(row["visitors"])),
                f"{row['avg_topped']:.1f}",
                f"[{color}]{pct:.1f}%[/{color}]",
            )
        console.print(t)

    # ---- HTML output ----
    region_slug = args.region.lower().replace(" ", "_")
    out_dir = Path("data") / "leaderboard"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{region_slug}.html"

    def bracket_style(band: str) -> str:
        styles = {
            "0–25 %":   "color:#a00000;background:#fff0f0",
            "25–50 %":  "color:#8a6000;background:#fffbe6",
            "50–75 %":  "color:#1a5c8a;background:#e8f4fb",
            "75–100 %": "color:#2d7a2d;background:#eafaea",
        }
        return styles.get(band, "")

    def pct_color_style(pct: float) -> str:
        if pct >= 60:
            return "color:#2d7a2d;background:#eafaea;font-weight:bold"
        if pct >= 40:
            return "color:#8a6000;background:#fffbe6;font-weight:bold"
        return "color:#a00000;background:#fff0f0;font-weight:bold"

    sections: list[str] = []

    # Section 1 — top-N per class
    for cls_name in top_df["class"].unique():
        rows = top_df[top_df["class"] == cls_name]
        tbody = "".join(
            f"<tr>"
            f"<td>{int(r['position'])}</td>"
            f"<td style='text-align:left'>{r['name']}</td>"
            f"<td>{int(r['score'])}</td>"
            f"<td>{r['score_pct']:.1f}%</td>"
            f"</tr>"
            for _, r in rows.iterrows()
        )
        heading = f"Top {top_n} — {cls_name}" if top_n else f"Leaderboard — {cls_name}"
        sections.append(f"""
<h2>{heading}</h2>
<table>
<thead><tr><th>#</th><th style="text-align:left">Name</th><th>Score</th><th>% of max</th></tr></thead>
<tbody>{tbody}</tbody>
</table>""")

    # Section 2 — score brackets
    sections.append("<h2>Score distribution</h2>")
    for cls_name in brackets_df["class"].unique():
        rows = brackets_df[brackets_df["class"] == cls_name]
        tbody = "".join(
            f"<tr>"
            f"<td style='{bracket_style(r['bracket'])}'>{r['bracket']}</td>"
            f"<td>{int(r['count'])}</td>"
            f"<td>{r['field_pct']:.1f}%</td>"
            f"</tr>"
            for _, r in rows.iterrows()
        )
        sections.append(f"""
<h3>{cls_name} <span class="meta">(max {max_boulders} boulders)</span></h3>
<table>
<thead><tr><th>Band</th><th>Competitors</th><th>% of field</th></tr></thead>
<tbody>{tbody}</tbody>
</table>""")

    # Section 3 — gym visit distribution
    sections.append("<h2>Gyms visited per competitor</h2>")
    for cls_name in visits_df["class"].unique():
        rows = visits_df[visits_df["class"] == cls_name]
        tbody = "".join(
            f"<tr><td>{int(r['gyms_visited'])}</td><td>{int(r['count'])}</td><td>{r['field_pct']:.1f}%</td></tr>"
            for _, r in rows.iterrows()
        )
        sections.append(f"""
<h3>{cls_name}</h3>
<table>
<thead><tr><th>Gyms visited</th><th>Competitors</th><th>% of field</th></tr></thead>
<tbody>{tbody}</tbody>
</table>""")

    # Section 4 — gym difficulty
    sections.append("<h2>Gym difficulty ranking <span class=\"meta\">(hardest first)</span></h2>")
    for cls_name in diff_df["class"].unique():
        rows = diff_df[diff_df["class"] == cls_name]
        n_gyms = len(rows)
        tbody_parts = []
        for i, (_, r) in enumerate(rows.iterrows()):
            style = pct_color_style(r["avg_topped_pct"])
            tbody_parts.append(
                f"<tr>"
                f"<td style='text-align:left'>{r['gym']}</td>"
                f"<td>{int(r['visitors'])}</td>"
                f"<td>{r['avg_topped']:.1f}</td>"
                f"<td style='{style}'>{r['avg_topped_pct']:.1f}%</td>"
                f"</tr>"
            )
        sections.append(f"""
<h3>{cls_name}</h3>
<table>
<thead><tr>
  <th style="text-align:left">Gym</th><th>Visitors</th><th>Avg topped</th><th>Avg topped %</th>
</tr></thead>
<tbody>{"".join(tbody_parts)}</tbody>
</table>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Leaderboard — {args.region}</title>
<style>
  body {{ font-family: system-ui, sans-serif; padding: 1.5rem; color: #111; max-width: 860px; }}
  h1 {{ font-size: 1.3rem; margin-bottom: 0.1rem; }}
  h2 {{ font-size: 1.1rem; margin: 2rem 0 0.3rem; border-bottom: 2px solid #ddd; padding-bottom: 0.2rem; }}
  h3 {{ font-size: 0.95rem; margin: 1rem 0 0.3rem; color: #444; }}
  p.meta, span.meta {{ color: #777; font-size: 0.85rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 0.8rem; }}
  th, td {{ padding: 0.4rem 0.7rem; border: 1px solid #ddd; text-align: right; }}
  th {{ background: #f0f0f0; font-weight: 600; }}
  tr:nth-child(even) td {{ background: #fafafa; }}
</style>
</head>
<body>
<h1>Leaderboard — <strong>{args.region}</strong></h1>
<p class="meta">Scraped: {lb['scraped_at']}</p>
{"".join(sections)}
</body>
</html>"""

    out_path.write_text(html, encoding="utf-8")
    console.print(f"\n  Saved: [cyan]{out_path}[/cyan]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bloc Summer Sessions — scraper and stats tool"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # shared --region argument
    from scraper import REGIONS
    region_choices = list(REGIONS.keys())

    # -- scrape --
    p_scrape = sub.add_parser("scrape", help="Fetch and cache competition data")
    p_scrape.add_argument(
        "--region", choices=region_choices, default="Graz",
        help="Region to scrape (default: Graz)",
    )
    p_scrape.add_argument(
        "--force", action="store_true",
        help="Re-fetch even if a cached file already exists",
    )
    p_scrape.set_defaults(func=cmd_scrape)

    # -- stats --
    p_stats = sub.add_parser("stats", help="Show boulder completion statistics")
    p_stats.add_argument(
        "--region", choices=region_choices, default="Graz",
        help="Region to show stats for (default: Graz)",
    )
    p_stats.add_argument(
        "--class", dest="cls", choices=["Männer", "Frauen"], default=None,
        help="Filter by class (default: show all classes)",
    )
    p_stats.add_argument(
        "--chart", action="store_true",
        help="Save difficulty-distribution charts as PNG files in data/",
    )
    p_stats.set_defaults(func=cmd_stats)

    # -- recommend --
    p_rec = sub.add_parser(
        "recommend",
        help="Show untapped boulders for a competitor, ranked by reachability",
    )
    p_rec.add_argument(
        "--region", choices=region_choices, default="Graz",
        help="Region the competitor is registered in (default: Graz)",
    )
    p_rec.add_argument("--name", required=True, help='Competitor name, e.g. "Wurm Lisa"')
    p_rec.set_defaults(func=cmd_recommend)

    # -- participants --
    p_part = sub.add_parser(
        "participants",
        help="Show participant counts, gym activation rates and average scores",
    )
    p_part.add_argument(
        "--region", choices=region_choices, default="Graz",
        help="Region to show participants for (default: Graz)",
    )
    p_part.set_defaults(func=cmd_participants)

    # -- leaderboard --
    p_lb = sub.add_parser(
        "leaderboard",
        help="Top-N rankings, score distribution, gym visit breakdown, difficulty ranking",
    )
    p_lb.add_argument(
        "--region", choices=region_choices, default="Graz",
        help="Region (default: Graz)",
    )
    p_lb.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Limit leaderboard to top N competitors per class (default: show all)",
    )
    p_lb.set_defaults(func=cmd_leaderboard)

    # -- score --
    p_score = sub.add_parser("score", help="Score card for a single competitor")
    p_score.add_argument(
        "--region", choices=region_choices, default="Graz",
        help="Region (default: Graz)",
    )
    p_score.add_argument("--name", required=True, help="Exact competitor name")
    p_score.set_defaults(func=cmd_score)

    # -- compare --
    p_cmp = sub.add_parser("compare", help="Head-to-head comparison of two competitors")
    p_cmp.add_argument("--region", choices=region_choices, default="Graz",
        help="Region (default: Graz)",
    )
    p_cmp.add_argument("name_a", help="First competitor name")
    p_cmp.add_argument("name_b", help="Second competitor name")
    p_cmp.set_defaults(func=cmd_compare)

    # -- find --
    p_find = sub.add_parser("find", help="Search competitors by name substring")
    p_find.add_argument(
        "--region", choices=region_choices, default="Graz",
        help="Region (default: Graz)",
    )
    p_find.add_argument("query", help="Substring to search for in competitor names")
    p_find.set_defaults(func=cmd_find)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
