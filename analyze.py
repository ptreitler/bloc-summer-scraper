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

    # Build completion stats for the same class
    peers = next(c for c in data["classes"] if c["name"] == comp_class_name)
    rows = []
    for comp in peers["competitors"]:
        for gym, boulders in comp["boulders"].items():
            for idx, topped in enumerate(boulders):
                rows.append({"gym": gym, "boulder": idx + 1, "topped": int(topped)})

    peer_df = pd.DataFrame(rows)
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
