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
    out_path = Path("data") / f"recommend_{region_slug}_{name_slug}.html"

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
    from analyze import load_data, participant_summary

    try:
        data = load_data(region=args.region)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    summary = participant_summary(data)
    overall = summary["overall"]
    gym_df = summary["gym_stats"]

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
    out_path = Path("data") / f"participants_{region_slug}.html"

    def pct_style(pct: float) -> str:
        if pct >= 70:
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

    # per-gym sections
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
<h2>{gym}</h2>
<table>
<thead><tr>
  <th>Class</th><th>Enrolled</th><th>Visited</th>
  <th>Activation %</th><th>Avg topped</th><th>Avg topped %</th>
</tr></thead>
<tbody>{"".join(gym_rows_html)}</tbody>
</table>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Participants — {args.region}</title>
<style>
  body {{ font-family: system-ui, sans-serif; padding: 1.5rem; color: #111; }}
  h1 {{ font-size: 1.3rem; margin-bottom: 0.1rem; }}
  h2 {{ font-size: 1.05rem; margin: 1.5rem 0 0.4rem; color: #333; }}
  p.meta {{ color: #777; font-size: 0.85rem; margin-top: 0; }}
  table {{ border-collapse: collapse; width: 100%; max-width: 780px; margin-bottom: 1rem; }}
  th, td {{ padding: 0.4rem 0.7rem; text-align: left; border: 1px solid #ddd; }}
  th {{ background: #f0f0f0; font-weight: 600; }}
  tr:nth-child(even) td {{ background: #fafafa; }}
  td:nth-child(n+2) {{ text-align: right; }}
</style>
</head>
<body>
<h1>Participants — <strong>{args.region}</strong></h1>
<p class="meta">Scraped: {summary['scraped_at']}</p>

<h2>Overall</h2>
<table>
<thead><tr>
  <th>Class</th><th>Count</th><th>Avg score</th><th>Median score</th>
  <th>Avg topped</th><th>Avg completion %</th>
</tr></thead>
<tbody>{"".join(overall_rows_html)}</tbody>
</table>

{"".join(gym_sections_html)}
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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
