"""
Bloc Summer Scraper CLI

Commands:
  scrape [--force]                  Fetch and cache competition data
  stats [--class Männer|Frauen]     Show completion tables; --chart saves PNGs
  recommend --name "Name"           Rank untapped boulders for a competitor
"""

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()

TAGS_FILE = Path("data") / "tags.json"


def _load_tags() -> dict:
    if TAGS_FILE.exists():
        return json.loads(TAGS_FILE.read_text(encoding="utf-8"))
    return {}


def _save_tags(tags: dict) -> None:
    TAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TAGS_FILE.write_text(json.dumps(tags, indent=2, ensure_ascii=False), encoding="utf-8")


def _get_tags(tags: dict, region: str, gym: str, boulder: int) -> list[str]:
    return tags.get(region, {}).get(gym, {}).get(str(boulder), [])


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

    tags = _load_tags()
    class_filter = args.cls if args.cls else "all"
    print_stats_table(data, class_filter, tags=tags, region=args.region)

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

    tags = _load_tags()
    has_tags = bool(tags.get(args.region))
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
    if has_tags:
        table.add_column("Tags", style="dim")

    for i, row in df.iterrows():
        pct = row["topped_pct"]
        color = "green" if pct >= 60 else "yellow" if pct >= 30 else "red"
        cells = [
            str(int(i) + 1),
            row["gym"],
            str(int(row["boulder"])),
            str(int(row["topped_count"])),
            str(int(row["total"])),
            f"[{color}]{pct:.1f}%[/{color}]",
        ]
        if has_tags:
            cells.append(", ".join(_get_tags(tags, args.region, row["gym"], int(row["boulder"]))))
        table.add_row(*cells)

    console.print(table)

    from web.rendering import render_recommend
    name_slug = args.name.lower().replace(" ", "_")
    region_slug = args.region.lower().replace(" ", "_")
    out_dir = Path("data") / "recommend"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{region_slug}_{name_slug}.html"
    out_path.write_text(render_recommend(df, args.region, args.name, tags), encoding="utf-8")
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

    from web.rendering import render_participants
    region_slug = args.region.lower().replace(" ", "_")
    out_dir = Path("data") / "participants"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{region_slug}.html"
    out_path.write_text(render_participants(summary, lb, args.region), encoding="utf-8")
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
    tags = _load_tags()
    has_tags = bool(tags.get(region))

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
        if has_tags:
            hard_t.add_column("Tags", style="dim")
        for _, row in sc["hardest_topped"].iterrows():
            pct = row["topped_pct"]
            color = "green" if pct >= 60 else "yellow" if pct >= 30 else "red"
            cells = [
                row["gym"],
                str(int(row["boulder"])),
                str(int(row["topped_count"])),
                str(int(row["total_peers"])),
                f"[{color}]{pct:.1f}%[/{color}]",
            ]
            if has_tags:
                cells.append(", ".join(_get_tags(tags, region, row["gym"], int(row["boulder"]))))
            hard_t.add_row(*cells)
        console.print(hard_t)

    # ── 4. Boulders topped per gym ──────────────────────────────────────────
    for gym, boulders in sc["topped_per_gym"].items():
        if boulders:
            parts = []
            for b in boulders:
                t_list = _get_tags(tags, region, gym, b)
                parts.append(f"{b} [dim][{', '.join(t_list)}][/dim]" if t_list else str(b))
            console.print(f"[bold]{gym}[/bold]: {', '.join(parts)}")
        else:
            console.print(f"[bold]{gym}[/bold]: [dim]none[/dim]")

    from web.rendering import render_score
    name_slug = name.lower().replace(" ", "_")
    region_slug = region.lower().replace(" ", "_")
    out_dir = Path("data") / "score"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{region_slug}_{name_slug}.html"
    out_path.write_text(render_score(sc, region, tags), encoding="utf-8")
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
    tags = _load_tags()
    has_tags = bool(tags.get(region))
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
        if has_tags:
            t.add_column("Tags", style="dim")
        for _, row in df.iterrows():
            pct = row["topped_pct"]
            color = pct_color(pct)
            cells = [
                row["gym"],
                str(int(row["boulder"])),
                str(int(row["topped_count"])),
                str(int(row["total_peers"])),
                f"[{color}]{pct:.1f}%[/{color}]",
            ]
            if has_tags:
                cells.append(", ".join(_get_tags(tags, region, row["gym"], int(row["boulder"]))))
            t.add_row(*cells)
        console.print(t)

    _print_exclusive(cmp["only_a"], na, nb)
    _print_exclusive(cmp["only_b"], nb, na)

    from web.rendering import render_compare
    slug_a = na.lower().replace(" ", "_")
    slug_b = nb.lower().replace(" ", "_")
    region_slug = region.lower().replace(" ", "_")
    out_dir = Path("data") / "compare"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{region_slug}_{slug_a}_vs_{slug_b}.html"
    out_path.write_text(render_compare(cmp, region, tags), encoding="utf-8")
    console.print(f"  Saved: [cyan]{out_path}[/cyan]")


def cmd_tag(args: argparse.Namespace) -> None:
    tags = _load_tags()
    region = args.region

    if args.gym is None:
        # List all tagged boulders in the region
        region_tags = tags.get(region, {})
        if not region_tags:
            console.print(f"[dim]No tags set for {region}.[/dim]")
            return
        t = Table(title=f"Tags — {region}", show_header=True, header_style="bold")
        t.add_column("Gym")
        t.add_column("Boulder", justify="right")
        t.add_column("Tags")
        for gym in sorted(region_tags):
            for b_str, tag_list in sorted(region_tags[gym].items(), key=lambda x: int(x[0])):
                if tag_list:
                    t.add_row(gym, b_str, ", ".join(tag_list))
        console.print(t)
        return

    if args.boulder is None:
        console.print("[red]--boulder is required when --gym is specified.[/red]")
        sys.exit(1)

    gym = args.gym
    boulder = str(args.boulder)

    if args.clear:
        found = False
        if region in tags and gym in tags[region] and boulder in tags[region][gym]:
            del tags[region][gym][boulder]
            if not tags[region][gym]:
                del tags[region][gym]
            if not tags[region]:
                del tags[region]
            _save_tags(tags)
            found = True
        console.print(
            f"[dim]Cleared tags for {gym} #{boulder}.[/dim]" if found
            else f"[dim]{gym} #{boulder} had no tags.[/dim]"
        )
        return

    if not args.tags:
        current = _get_tags(tags, region, gym, args.boulder)
        if current:
            console.print(f"[bold]{gym} #{boulder}:[/bold] {', '.join(current)}")
        else:
            console.print(f"[dim]{gym} #{boulder}: no tags set[/dim]")
        return

    # Set tags (replaces existing)
    tags.setdefault(region, {}).setdefault(gym, {})[boulder] = list(args.tags)
    _save_tags(tags)
    console.print(f"[green]Tagged {gym} #{boulder}:[/green] {', '.join(args.tags)}")


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

    from web.rendering import render_leaderboard
    region_slug = args.region.lower().replace(" ", "_")
    out_dir = Path("data") / "leaderboard"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{region_slug}.html"
    out_path.write_text(render_leaderboard(lb, args.region, top_n), encoding="utf-8")
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

    # -- tag --
    p_tag = sub.add_parser("tag", help="Set/view tags on boulders (hold colour, style, etc.)")
    p_tag.add_argument(
        "--region", choices=region_choices, default="Graz",
        help="Region (default: Graz)",
    )
    p_tag.add_argument("--gym", default=None, metavar="GYM",
        help="Gym name (required when tagging/viewing a specific boulder)")
    p_tag.add_argument("--boulder", type=int, default=None, metavar="N",
        help="Boulder number")
    p_tag.add_argument("--clear", action="store_true",
        help="Remove all tags from this boulder")
    p_tag.add_argument("tags", nargs="*", metavar="TAG",
        help="Tags to set, replacing existing ones (omit to view current tags)")
    p_tag.set_defaults(func=cmd_tag)

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
