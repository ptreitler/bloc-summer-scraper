# Bloc Summer Sessions — Scraper & Stats

Scrapes competition data from [boulder-top.com](https://boulder-top.com) for the **Bloc Summer Sessions 2026** (BSS26) bouldering competition, caches it locally, and provides stats tables, charts, and per-competitor recommendations.

The site loads ranking data via AJAX, so a plain HTML fetch is not enough — this tool handles that transparently.

---

## Competition structure

| Parameter | Value |
|-----------|-------|
| Competition | Bloc Summer Sessions 2026 |
| Phase | Qualification (29 Apr – 31 May 2026) |
| Classes | Männer, Frauen |
| Regions | Graz, Kärnten, Linz, Murtal, Salzburg, Traunviertel, Wien |
| Boulders | 40 per gym |

**Graz gyms:** BLOC house, Boulderclub, Newton (120 boulders total)  
**Wien gyms:** BigWall, Boulder Monkeys, Boulderbar Wienerberg, Kletteranlage Klosterneuburg (160 boulders total)

Boulder numbers carry **no inherent difficulty ordering** — problems are set randomly on the wall. Difficulty is inferred from community completion rates.

---

## Setup

```bash
pip install -r requirements.txt
```

Requires Python 3.10+.

---

## Usage

### Scrape data

Fetches the ranking and each competitor's detail page. Rate-limited to 0.5 s between requests. Takes ~5 min per region.

```bash
python main.py scrape                    # Graz (default)
python main.py scrape --region Wien
python main.py scrape --region Salzburg
python main.py scrape --force            # re-fetch even if cache exists
```

Data is saved to `data/latest_<region>.json` and a timestamped copy alongside it.

Available regions: `Graz`, `Kärnten`, `Linz`, `Murtal`, `Salzburg`, `Traunviertel`, `Wien`

---

### Stats tables

Prints a Rich-formatted table per gym showing topped/total and completion % for each boulder, coloured green/yellow/red by difficulty.

```bash
python main.py stats                          # Graz, all classes
python main.py stats --region Wien            # Wien, all classes
python main.py stats --class Frauen           # Graz, Frauen only
python main.py stats --region Wien --class Männer
```

Add `--chart` to save PNG bar charts to `data/`:

```bash
python main.py stats --chart
python main.py stats --region Wien --class Frauen --chart
```

Charts sort boulders by completion rate (hardest left). When showing all classes, Männer and Frauen rates are overlaid as lines on top of the combined bars. When a single class is selected, boulders are sorted by that class's own rates.

---

### Recommend untapped boulders

Shows which boulders a competitor hasn't topped yet, sorted by their peers' completion rate — highest first (most reachable). Also writes a self-contained HTML file you can share.

```bash
python main.py recommend --name "Wurm Lisa"
python main.py recommend --region Wien --name "Jesus Paulo"
```

Output: terminal table + `data/recommend_<region>_<name>.html`

The HTML uses green/yellow/red colour coding:

| Colour | Peer completion % |
|--------|-------------------|
| 🟢 Green | ≥ 60% |
| 🟡 Yellow | 30 – 59% |
| 🔴 Red | < 30% |

---

## Data files

```
data/
  latest_graz.json              # most recent Graz scrape
  latest_wien.json              # most recent Wien scrape
  bss26_graz_20260524_104534.json   # timestamped archive
  chart_bloc_house_all.png      # gym chart, all classes
  chart_bloc_house_frauen.png   # gym chart, Frauen only
  recommend_graz_wurm_lisa.html # shareable recommendation
```

JSON and PNG files are gitignored. The `data/` directory is tracked via `.gitkeep`.

---

## Notes

- The ranking API (`ranking-xmlhttp_loadRanking.php`) requires specific POST parameters including `REid` (region ID) and `KLid` (class ID). These were reverse-engineered from the site's JavaScript.
- Frauen use `KLid=687`, Männer `KLid=686` — these are **competition-wide** and the same across all regions; only `REid` changes per region.
- Re-running `scrape` without `--force` is a no-op if a cache already exists.
