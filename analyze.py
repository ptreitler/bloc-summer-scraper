"""
Analysis and visualization of Bloc Summer scraper data.

Difficulty is inferred from completion rate — boulder numbers have no inherent
ordering by difficulty, as problems are set randomly on the wall.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table

DATA_DIR = Path("data")
console = Console()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(path: Path | None = None, region: str = "Graz") -> dict:
    if path is None:
        region_slug = region.lower().replace(" ", "_")
        path = DATA_DIR / f"latest_{region_slug}.json"
        # backward compat: fall back to legacy latest.json for Graz
        if not path.exists() and region == "Graz":
            path = DATA_DIR / "latest.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No data file found at {path}. Run `scrape --region {region}` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Stats computation
# ---------------------------------------------------------------------------

def boulder_completion_stats(data: dict) -> pd.DataFrame:
    """
    Build a DataFrame of per-boulder completion stats.

    Columns: gym, boulder, class, topped_count, total_competitors, topped_pct
    Includes rows for class="All" (aggregate across Männer + Frauen).
    """
    rows = []
    for cls in data["classes"]:
        cls_name = cls["name"]
        for comp in cls["competitors"]:
            for gym, boulders in comp["boulders"].items():
                for idx, topped in enumerate(boulders):
                    rows.append({
                        "gym": gym,
                        "boulder": idx + 1,
                        "class": cls_name,
                        "competitor_id": comp["id"],
                        "topped": int(topped),
                    })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Exclude competitors who never topped any boulder at a given gym
    # (i.e. they never visited — all zeros). They shouldn't inflate the denominator.
    gym_totals = df.groupby(["competitor_id", "gym"])["topped"].transform("sum")
    df = df[gym_totals > 0]

    per_class = (
        df.groupby(["gym", "boulder", "class"])
        .agg(topped_count=("topped", "sum"), total=("topped", "count"))
        .reset_index()
    )
    per_class["topped_pct"] = (
        per_class["topped_count"] / per_class["total"] * 100
    ).round(1)

    all_agg = (
        df.groupby(["gym", "boulder"])
        .agg(topped_count=("topped", "sum"), total=("topped", "count"))
        .reset_index()
    )
    all_agg["class"] = "All"
    all_agg["topped_pct"] = (
        all_agg["topped_count"] / all_agg["total"] * 100
    ).round(1)

    return pd.concat([per_class, all_agg], ignore_index=True)


# ---------------------------------------------------------------------------
# Participant summary
# ---------------------------------------------------------------------------

def participant_summary(data: dict) -> dict:
    """
    Return a structured summary of participants for the region.

    Returns a dict with:
      region       – region name
      scraped_at   – ISO timestamp string
      overall      – DataFrame: class | count | avg_score | median_score
                                | avg_total | avg_pct
      gym_stats    – DataFrame: gym | class | enrolled | visitors
                                | activation_pct | avg_topped | avg_topped_pct
                     (only participants who enrolled in that gym are included)
    """
    class_names = [c["name"] for c in data["classes"]]
    gyms_per_class: dict[str, list[str]] = {}
    for cls in data["classes"]:
        gyms_per_class[cls["name"]] = list(cls["competitors"][0]["boulders"].keys()) if cls["competitors"] else []

    all_gyms: list[str] = []
    for gyms in gyms_per_class.values():
        for g in gyms:
            if g not in all_gyms:
                all_gyms.append(g)

    boulders_per_gym: dict[str, int] = {}
    for cls in data["classes"]:
        for comp in cls["competitors"]:
            for gym, boulders in comp["boulders"].items():
                boulders_per_gym[gym] = len(boulders)

    # ----- overall stats per class + "All" -----
    overall_rows = []
    for cls in data["classes"]:
        comps = cls["competitors"]
        if not comps:
            continue
        scores = [c["score"] for c in comps]
        max_boulders = comps[0]["total"]  # enrollment max (e.g. 120 or 160)
        overall_rows.append({
            "class": cls["name"],
            "count": len(comps),
            "avg_score": round(sum(scores) / len(scores), 1),
            "median_score": float(pd.Series(scores).median()),
            "avg_total": round(sum(scores) / len(scores), 1),
            "avg_pct": round(sum(scores) / len(scores) / max_boulders * 100, 1),
        })
    # "All" aggregate
    all_comps = [c for cls in data["classes"] for c in cls["competitors"]]
    if all_comps:
        scores = [c["score"] for c in all_comps]
        max_boulders = all_comps[0]["total"]
        overall_rows.append({
            "class": "All",
            "count": len(all_comps),
            "avg_score": round(sum(scores) / len(scores), 1),
            "median_score": float(pd.Series(scores).median()),
            "avg_total": round(sum(scores) / len(scores), 1),
            "avg_pct": round(sum(scores) / len(scores) / max_boulders * 100, 1),
        })
    overall_df = pd.DataFrame(overall_rows)

    # ----- per-gym activation + topped stats -----
    gym_rows = []
    for gym in all_gyms:
        n_boulders = boulders_per_gym.get(gym, 0)
        for cls in data["classes"]:
            comps = cls["competitors"]
            if not comps:
                continue
            enrolled = len(comps)
            topped_counts = [sum(c["boulders"].get(gym, [])) for c in comps]
            visitors = sum(1 for t in topped_counts if t > 0)
            visited_topped = [t for t in topped_counts if t > 0]
            gym_rows.append({
                "gym": gym,
                "class": cls["name"],
                "enrolled": enrolled,
                "visitors": visitors,
                "activation_pct": round(visitors / enrolled * 100, 1) if enrolled else 0,
                "avg_topped": round(sum(visited_topped) / len(visited_topped), 1) if visited_topped else 0.0,
                "avg_topped_pct": round(sum(visited_topped) / len(visited_topped) / n_boulders * 100, 1) if visited_topped and n_boulders else 0.0,
            })
        # "All" row for this gym
        all_enrolled = len(all_comps)
        topped_counts = [sum(c["boulders"].get(gym, [])) for c in all_comps]
        visitors = sum(1 for t in topped_counts if t > 0)
        visited_topped = [t for t in topped_counts if t > 0]
        gym_rows.append({
            "gym": gym,
            "class": "All",
            "enrolled": all_enrolled,
            "visitors": visitors,
            "activation_pct": round(visitors / all_enrolled * 100, 1) if all_enrolled else 0,
            "avg_topped": round(sum(visited_topped) / len(visited_topped), 1) if visited_topped else 0.0,
            "avg_topped_pct": round(sum(visited_topped) / len(visited_topped) / n_boulders * 100, 1) if visited_topped and n_boulders else 0.0,
        })

    gym_df = pd.DataFrame(gym_rows)

    return {
        "region": data.get("region", ""),
        "scraped_at": data.get("scraped_at", ""),
        "overall": overall_df,
        "gym_stats": gym_df,
    }


# ---------------------------------------------------------------------------
# Leaderboard summary
# ---------------------------------------------------------------------------

def leaderboard_summary(data: dict, top_n: int | None = None) -> dict:
    """
    Return four DataFrames for the leaderboard command:

    top_df        – all (or top_n) competitors per class (not "All"), ranked by score
    brackets_df   – score distribution in four fixed bands (% of max possible)
    visits_df     – how many competitors visited exactly N gyms, per class
    diff_df       – gym difficulty ranking (avg topped % among visitors),
                    sorted hardest-first, per class
    """
    all_gyms: list[str] = []
    boulders_per_gym: dict[str, int] = {}
    for cls in data["classes"]:
        for comp in cls["competitors"]:
            for gym, boulders in comp["boulders"].items():
                boulders_per_gym[gym] = len(boulders)
                if gym not in all_gyms:
                    all_gyms.append(gym)

    max_boulders = sum(boulders_per_gym.values())

    named_classes = {cls["name"]: cls["competitors"] for cls in data["classes"]}
    all_comps = [c for cls in data["classes"] for c in cls["competitors"]]
    all_classes = dict(**named_classes, All=all_comps)

    # 1. Top-N leaderboard (per named class only — All is not meaningful here)
    top_rows = []
    for cls_name, comps in named_classes.items():
        sorted_comps = sorted(comps, key=lambda c: (-c["score"], c["name"]))
        for pos, comp in enumerate(sorted_comps[:top_n], start=1):
            top_rows.append({
                "class": cls_name,
                "position": pos,
                "name": comp["name"],
                "score": comp["score"],
                "score_pct": round(comp["score"] / max_boulders * 100, 1),
            })
    top_df = pd.DataFrame(top_rows)

    # 2. Score brackets — fixed bands as % of max possible score
    band_edges = [(0, 25, "0–25 %"), (25, 50, "25–50 %"), (50, 75, "50–75 %"), (75, 101, "75–100 %")]
    bracket_rows = []
    for cls_name, comps in all_classes.items():
        if not comps:
            continue
        n = len(comps)
        for lo, hi, label in band_edges:
            count = sum(
                1 for c in comps
                if lo <= c["score"] / max_boulders * 100 < hi
            )
            bracket_rows.append({
                "class": cls_name,
                "bracket": label,
                "count": count,
                "field_pct": round(count / n * 100, 1),
            })
    brackets_df = pd.DataFrame(bracket_rows)

    # 3. Gym visit distribution — how many gyms did each competitor visit?
    visit_rows = []
    for cls_name, comps in all_classes.items():
        if not comps:
            continue
        n = len(comps)
        visit_counts = [
            sum(1 for boulders in c["boulders"].values() if sum(boulders) > 0)
            for c in comps
        ]
        for n_gyms in range(len(all_gyms) + 1):
            count = sum(1 for v in visit_counts if v == n_gyms)
            if count > 0:
                visit_rows.append({
                    "class": cls_name,
                    "gyms_visited": n_gyms,
                    "count": count,
                    "field_pct": round(count / n * 100, 1),
                })
    visits_df = pd.DataFrame(visit_rows)

    # 4. Gym difficulty ranking — avg topped % among visitors, hardest first
    diff_rows = []
    for gym in all_gyms:
        n_boulders = boulders_per_gym[gym]
        for cls_name, comps in all_classes.items():
            if not comps:
                continue
            topped_counts = [sum(c["boulders"].get(gym, [])) for c in comps]
            visited = [t for t in topped_counts if t > 0]
            if visited:
                diff_rows.append({
                    "class": cls_name,
                    "gym": gym,
                    "visitors": len(visited),
                    "avg_topped": round(sum(visited) / len(visited), 1),
                    "avg_topped_pct": round(sum(visited) / len(visited) / n_boulders * 100, 1),
                })
    diff_df = (
        pd.DataFrame(diff_rows)
        .sort_values(["class", "avg_topped_pct"])
        .reset_index(drop=True)
    )

    return {
        "region": data.get("region", ""),
        "scraped_at": data.get("scraped_at", ""),
        "max_boulders": max_boulders,
        "top_n": top_n,
        "top_df": top_df,
        "brackets_df": brackets_df,
        "visits_df": visits_df,
        "diff_df": diff_df,
    }


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def competitor_recommendations(data: dict, name: str) -> pd.DataFrame:
    """
    Return boulders the named competitor hasn't topped yet, sorted by
    community completion rate (descending) — highest = most "reachable".
    Only peers in the same class are used as the comparison baseline.
    """
    name_lower = name.lower()
    comp_data = None
    comp_class_name = None

    for cls in data["classes"]:
        for comp in cls["competitors"]:
            if comp["name"].lower() == name_lower:
                comp_data = comp
                comp_class_name = cls["name"]
                break
        if comp_data:
            break

    if comp_data is None:
        raise ValueError(
            f"Competitor '{name}' not found. "
            "Check spelling or run `python main.py stats` to list names."
        )

    # Build completion stats for the same class (excluding non-visitors)
    peers = next(c for c in data["classes"] if c["name"] == comp_class_name)
    rows = []
    for comp in peers["competitors"]:
        for gym, boulders in comp["boulders"].items():
            for idx, topped in enumerate(boulders):
                rows.append({"competitor_id": comp["id"], "gym": gym, "boulder": idx + 1, "topped": int(topped)})

    peer_df = pd.DataFrame(rows)
    gym_totals = peer_df.groupby(["competitor_id", "gym"])["topped"].transform("sum")
    peer_df = peer_df[gym_totals > 0]
    peer_stats = (
        peer_df.groupby(["gym", "boulder"])
        .agg(topped_count=("topped", "sum"), total=("topped", "count"))
        .reset_index()
    )
    peer_stats["topped_pct"] = (
        peer_stats["topped_count"] / peer_stats["total"] * 100
    ).round(1)

    # Collect untapped boulders for this competitor
    untapped = [
        {"gym": gym, "boulder": idx + 1}
        for gym, boulders in comp_data["boulders"].items()
        for idx, topped in enumerate(boulders)
        if not topped
    ]

    if not untapped:
        return pd.DataFrame()

    untapped_df = pd.DataFrame(untapped)
    result = untapped_df.merge(peer_stats, on=["gym", "boulder"])
    return result.sort_values("topped_pct", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Score summary
# ---------------------------------------------------------------------------

def competitor_score_summary(data: dict, name: str) -> dict:
    """
    Return a score card for the named competitor.

    Keys:
      name, class_name, rank, total_competitors,
      score, comp_total, score_pct,
      gym_stats   – DataFrame: gym | topped | n_boulders | pct | gym_rank | gym_visitors
      hardest_topped – DataFrame (top 5): gym | boulder | topped_count | total_peers | topped_pct
      topped_per_gym – dict {gym: [boulder_numbers 1-based]}
    """
    name_lower = name.lower()
    comp_data = None
    comp_class = None
    for cls in data["classes"]:
        for comp in cls["competitors"]:
            if comp["name"].lower() == name_lower:
                comp_data = comp
                comp_class = cls
                break
        if comp_data:
            break

    if comp_data is None:
        raise ValueError(
            f"Competitor '{name}' not found. "
            "Check spelling or use `find` to search."
        )

    cls_name = comp_class["name"]
    all_comps = comp_class["competitors"]
    total_competitors = len(all_comps)
    all_gyms = list(comp_data["boulders"].keys())

    score = comp_data["score"]
    comp_total = comp_data["total"]
    score_pct = round(score / comp_total * 100, 1) if comp_total else 0.0

    # --- per-gym stats + gym rank ---
    gym_stat_rows = []
    topped_per_gym: dict[str, list[int]] = {}
    for gym in all_gyms:
        boulders = comp_data["boulders"].get(gym, [])
        n_boulders = len(boulders)
        topped = sum(boulders)
        pct = round(topped / n_boulders * 100, 1) if n_boulders else 0.0
        topped_per_gym[gym] = [i + 1 for i, t in enumerate(boulders) if t]

        # rank among visitors to this gym (topped > 0 there)
        gym_scores = [(sum(c["boulders"].get(gym, [])), c["id"]) for c in all_comps]
        visitors = sorted([(t, cid) for t, cid in gym_scores if t > 0], key=lambda x: -x[0])
        gym_visitors = len(visitors)
        if topped > 0:
            gym_rank = next(
                (i + 1 for i, (t, cid) in enumerate(visitors) if cid == comp_data["id"]),
                None,
            )
        else:
            gym_rank = None  # did not visit

        gym_stat_rows.append({
            "gym": gym,
            "topped": topped,
            "n_boulders": n_boulders,
            "pct": pct,
            "gym_rank": gym_rank,
            "gym_visitors": gym_visitors,
        })
    gym_stats_df = pd.DataFrame(gym_stat_rows)

    # --- peer stats for hardest-topped computation (visitor-filtered) ---
    peer_rows = []
    for comp in all_comps:
        for gym, boulders in comp["boulders"].items():
            for idx, t in enumerate(boulders):
                peer_rows.append({
                    "competitor_id": comp["id"],
                    "gym": gym,
                    "boulder": idx + 1,
                    "topped": int(t),
                })
    peer_df = pd.DataFrame(peer_rows)
    gym_totals = peer_df.groupby(["competitor_id", "gym"])["topped"].transform("sum")
    peer_df = peer_df[gym_totals > 0]
    peer_stats = (
        peer_df.groupby(["gym", "boulder"])
        .agg(topped_count=("topped", "sum"), total_peers=("topped", "count"))
        .reset_index()
    )
    peer_stats["topped_pct"] = (
        peer_stats["topped_count"] / peer_stats["total_peers"] * 100
    ).round(1)

    # top-5 hardest boulders this competitor topped
    my_topped = [
        {"gym": gym, "boulder": idx + 1}
        for gym, boulders in comp_data["boulders"].items()
        for idx, t in enumerate(boulders)
        if t
    ]
    if my_topped:
        my_df = pd.DataFrame(my_topped).merge(peer_stats, on=["gym", "boulder"])
        hardest_df = my_df.sort_values("topped_pct").head(5).reset_index(drop=True)
    else:
        hardest_df = pd.DataFrame(
            columns=["gym", "boulder", "topped_count", "total_peers", "topped_pct"]
        )

    return {
        "name": comp_data["name"],
        "class_name": cls_name,
        "rank": comp_data["rank"],
        "total_competitors": total_competitors,
        "score": score,
        "comp_total": comp_total,
        "score_pct": score_pct,
        "gym_stats": gym_stats_df,
        "hardest_topped": hardest_df,
        "topped_per_gym": topped_per_gym,
    }


# ---------------------------------------------------------------------------
# Rich table output
# ---------------------------------------------------------------------------

def _pct_color(pct: float) -> str:
    if pct >= 60:
        return "green"
    if pct >= 30:
        return "yellow"
    return "red"


def _fmt_cell(topped: int, total: int, pct: float) -> str:
    color = _pct_color(pct)
    return f"[{color}]{topped}/{total} ({pct:.1f}%)[/{color}]"


def print_stats_table(data: dict, class_filter: str = "all") -> None:
    stats = boulder_completion_stats(data)
    if stats.empty:
        console.print("[red]No data available.[/red]")
        return

    gyms = sorted(stats["gym"].unique())

    if class_filter == "all":
        # Wide table: boulder | Männer | Frauen | All
        for gym in gyms:
            table = Table(title=f"[bold]{gym}[/bold]", show_header=True, header_style="bold")
            table.add_column("Boulder", justify="right")
            table.add_column("Männer", justify="right")
            table.add_column("Frauen", justify="right")
            table.add_column("All", justify="right")

            # Pivot to get all classes per boulder, sorted by boulder number
            gym_stats = stats[stats["gym"] == gym].set_index(["boulder", "class"])
            boulders = sorted(stats[stats["gym"] == gym]["boulder"].unique())

            for b in boulders:
                cells = []
                for cls in ["Männer", "Frauen", "All"]:
                    try:
                        row = gym_stats.loc[(b, cls)]
                        cells.append(
                            _fmt_cell(row["topped_count"], row["total"], row["topped_pct"])
                        )
                    except KeyError:
                        cells.append("[dim]—[/dim]")
                table.add_row(str(b), *cells)

            console.print(table)
    else:
        # Single-class table
        for gym in gyms:
            gym_stats = stats[
                (stats["gym"] == gym) & (stats["class"] == class_filter)
            ].sort_values("boulder")

            table = Table(
                title=f"[bold]{gym} — {class_filter}[/bold]",
                show_header=True,
                header_style="bold",
            )
            table.add_column("Boulder", justify="right")
            table.add_column("Topped", justify="right")
            table.add_column("Total", justify="right")
            table.add_column("Completion %", justify="right")

            for _, row in gym_stats.iterrows():
                color = _pct_color(row["topped_pct"])
                table.add_row(
                    str(int(row["boulder"])),
                    str(int(row["topped_count"])),
                    str(int(row["total"])),
                    f"[{color}]{row['topped_pct']:.1f}%[/{color}]",
                )
            console.print(table)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def plot_distribution(
    data: dict,
    class_filter: str = "all",
    out_dir: Path = DATA_DIR,
) -> list[Path]:
    """
    Save one PNG chart per gym.

    Boulders are sorted by their overall completion rate (lowest = hardest on the
    left) since boulder numbers carry no inherent difficulty ordering.
    Each bar represents one boulder; bars are coloured by a red-yellow-green
    gradient. When class_filter='all', Männer and Frauen completion rates are
    overlaid as line plots on top of the All bars.
    """
    stats = boulder_completion_stats(data)
    if stats.empty:
        console.print("[red]No data to plot.[/red]")
        return []

    out_dir.mkdir(exist_ok=True)
    gyms = sorted(stats["gym"].unique())
    saved: list[Path] = []

    for gym in gyms:
        fig, ax = plt.subplots(figsize=(14, 5))

        # Sort boulders by "All" completion rate (ascending = hardest first)
        all_stats = (
            stats[(stats["gym"] == gym) & (stats["class"] == "All")]
            .sort_values("topped_pct")
            .reset_index(drop=True)
        )

        if all_stats.empty:
            plt.close(fig)
            continue

        x = np.arange(len(all_stats))
        labels = all_stats["boulder"].astype(str).tolist()
        pcts = all_stats["topped_pct"].values

        # Colour bars by completion rate
        bar_colors = plt.cm.RdYlGn(pcts / 100)  # type: ignore[attr-defined]

        if class_filter == "all":
            ax.bar(x, pcts, color=bar_colors, alpha=0.65, width=0.8, label="All")

            # Overlay Männer and Frauen as lines
            boulder_order = all_stats["boulder"].tolist()
            for cls_name, color, marker in [
                ("Männer", "steelblue", "o"),
                ("Frauen", "coral", "s"),
            ]:
                cls_stats = (
                    stats[(stats["gym"] == gym) & (stats["class"] == cls_name)]
                    .set_index("boulder")
                )
                y = [
                    cls_stats.loc[b, "topped_pct"] if b in cls_stats.index else float("nan")
                    for b in boulder_order
                ]
                ax.plot(
                    x, y,
                    color=color, marker=marker, markersize=4,
                    linewidth=1.5, label=cls_name, zorder=5,
                )
            title_suffix = "All classes"
            xlabel = "Boulder number (sorted by overall completion rate, hardest → easiest)"
        else:
            # Sort by the selected class's own completion rate
            cls_df = (
                stats[(stats["gym"] == gym) & (stats["class"] == class_filter)]
                .sort_values("topped_pct")
                .reset_index(drop=True)
            )
            x = np.arange(len(cls_df))
            labels = cls_df["boulder"].astype(str).tolist()
            y = cls_df["topped_pct"].values
            cls_colors = plt.cm.RdYlGn(  # type: ignore[attr-defined]
                np.array(y, dtype=float) / 100
            )
            ax.bar(x, y, color=cls_colors, alpha=0.85, width=0.8)
            title_suffix = class_filter
            xlabel = f"Boulder number (sorted by {class_filter} completion rate, hardest → easiest)"

        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=7, rotation=90)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Completion %")
        ax.set_title(f"{gym} — Difficulty Distribution ({title_suffix})")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter())
        ax.set_ylim(0, 105)
        if class_filter == "all":
            ax.legend()
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()

        gym_slug = gym.lower().replace(" ", "_")
        cls_slug = "all" if class_filter == "all" else class_filter.lower()
        filename = out_dir / f"chart_{gym_slug}_{cls_slug}.png"
        fig.savefig(filename, dpi=150)
        plt.close(fig)
        saved.append(filename)
        console.print(f"  Chart saved: [cyan]{filename}[/cyan]")

    return saved
