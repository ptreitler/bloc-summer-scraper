# Bloc Summer Sessions — Scraper & Stats

Scrapes competition data from [boulder-top.com](https://boulder-top.com) for the **Bloc Summer Sessions 2026** (BSS26) bouldering competition, caches it locally, and provides stats tables, charts, and a range of per-competitor and region-level reports.

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

> **Visitor filter:** completion stats (topped %, difficulty ranking, etc.) only count competitors who actually visited a gym (topped at least one boulder there). Non-visitors are excluded from the denominator so that low engagement doesn't inflate difficulty.

---

## Setup

```bash
pip install -r requirements.txt
```

Requires Python 3.10+.

---

## Commands

### `scrape` — fetch and cache data

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

### `stats` — boulder completion tables

Prints a Rich-formatted table per gym showing topped/total and completion % for each boulder, coloured green/yellow/red by difficulty.

```bash
python main.py stats                          # Graz, all classes
python main.py stats --region Wien
python main.py stats --class Frauen
python main.py stats --region Wien --class Männer
```

Add `--chart` to save PNG bar charts to `data/`:

```bash
python main.py stats --chart
python main.py stats --region Wien --class Frauen --chart
```

Charts sort boulders by completion rate (hardest left). When showing all classes, Männer and Frauen rates are overlaid as lines on top of the combined bars.

---

### `participants` — region participation report

Summarises who signed up for a region: field size, score distribution, gym activation rates, and gym difficulty. Outputs a self-contained HTML report.

```bash
python main.py participants                  # Graz (default)
python main.py participants --region Wien
```

**Report sections:**
1. Overview — competitor count, avg/median score, avg completion % per class
2. Gym activation — enrolled vs. visitors, activation %, avg topped per gym
3. Score distribution — how many competitors fall in each 25% band
4. Gyms visited — how many competitors visited 1, 2, 3… gyms
5. Gym difficulty — avg topped % among visitors, hardest first

Output: `data/participants/<region>.html`

---

### `leaderboard` — rankings & distributions

Shows the full ranked leaderboard plus score distribution, gym visit breakdown, and gym difficulty. Outputs an HTML report.

```bash
python main.py leaderboard                   # Graz, full list
python main.py leaderboard --region Wien
python main.py leaderboard --limit 10        # cap at top 10 per class
```

**Report sections:**
1. Full leaderboard (or top N if `--limit` is set) per class
2. Score distribution (0–25%, 25–50%, 50–75%, 75–100% of max)
3. Gyms visited per class
4. Gym difficulty ranking per class

Output: `data/leaderboard/<region>.html`

---

### `find` — search competitors by name

Case-insensitive substring search across all classes in a region. Console output only.

```bash
python main.py find "müller"
python main.py find --region Wien "anna"
```

---

### `score` — score card for one competitor

Full breakdown for a single competitor: ranking, gym-by-gym performance, the 5 hardest boulders they topped, and a visual boulder grid per gym.

```bash
python main.py score --name "Wurm Lisa"
python main.py score --region Wien --name "Jesus Paulo"
```

**Console sections:**
- Overall: rank (N of M), score, max, %
- Gym breakdown: topped / max, %, rank among that gym's visitors — plus a **Total** row with overall rank
- Top 5 hardest boulders topped (peer completion % coloured red/yellow/green)
- Topped boulder numbers per gym

**HTML report** additionally shows a colour-coded boulder grid per gym (green = topped, grey = missed).

Output: `data/score/<region>_<name>.html`

---

### `recommend` — untapped boulders

Shows which boulders a competitor hasn't topped yet, sorted by peers' completion rate — highest first (most reachable).

```bash
python main.py recommend --name "Wurm Lisa"
python main.py recommend --region Wien --name "Jesus Paulo"
```

| Colour | Peer completion % |
|--------|-------------------|
| Green  | ≥ 60 % |
| Yellow | 30 – 59 % |
| Red    | < 30 % |

Output: terminal table + `data/recommend/<region>_<name>.html`

---

### `compare` — head-to-head comparison

Compares two competitors in the same class and region.

```bash
python main.py compare "Wurm Lisa" "Muster Maria"
python main.py compare --region Wien "Jesus Paulo" "Smith John"
```

**Output sections:**
- Overall: rank, score, max, % side by side (winner bolded)
- Gym breakdown: topped / max and % per gym for each competitor, with a Total row
- Boulders topped by A but not B (with peer topped count and %)
- Boulders topped by B but not A

Both competitors must be in the same class. Use `find` first if unsure of exact names.

Output: terminal tables + `data/compare/<region>_<name_a>_vs_<name_b>.html`

---

## Output files

```
data/
  latest_graz.json                    # most recent Graz scrape (gitignored)
  latest_wien.json                    # most recent Wien scrape (gitignored)
  participants/
    graz.html                         # participants report
  leaderboard/
    graz.html                         # leaderboard report
  score/
    graz_wurm_lisa.html               # score card
  recommend/
    graz_wurm_lisa.html               # recommendation report
  compare/
    graz_wurm_lisa_vs_muster_maria.html
```

JSON files and all HTML output directories are gitignored. The `data/` directory is tracked via `.gitkeep`.

---

## Notes

- The ranking API (`ranking-xmlhttp_loadRanking.php`) requires specific POST parameters including `REid` (region ID) and `KLid` (class ID). These were reverse-engineered from the site's JavaScript.
- Frauen use `KLid=687`, Männer `KLid=686` — these are competition-wide constants; only `REid` changes per region.
- Re-running `scrape` without `--force` is a no-op if a cache already exists.
