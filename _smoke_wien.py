import requests
from scraper import _session, RANKING_API, parse_ranking, parse_detail

s = _session()

# Fetch Wien Männer ranking
r = s.post(RANKING_API, data={
    "comp": "bss26", "CID": 190, "VID": 198, "REid": 246, "KLid": 686,
    "RankingTyp": 1, "REBez": "Wien", "KLBez": "Männer", "GTyp": 2,
    "StartDate": "2026-04-29 07:00:00", "EndDate": "2026-05-31 23:59:00",
    "Backend": "0", "HAID": "", "AusgabeTyp": "1", "KWID": "0",
}, timeout=15)
body = r.json()["Return_DIV_Body"]
competitors = parse_ranking(body)
print(f"Wien Männer: {len(competitors)} competitors")
if competitors:
    c = competitors[0]
    print(f"  First: {c['name']}  {c['score']}/{c['total']}  id={c['id']}")
    detail_url = f"https://boulder-top.com/comp/bss26/page/boulder-eintragen/t={c['id']}&k={c['class_k']}&r=246&v=198&c=190&h="
    detail = s.get(detail_url, timeout=15)
    boulders = parse_detail(detail.text)
    for gym, b in boulders.items():
        print(f"  {gym}: {len(b)} boulders, {sum(b)} topped")

# Frauen
r2 = s.post(RANKING_API, data={
    "comp": "bss26", "CID": 190, "VID": 198, "REid": 246, "KLid": 687,
    "RankingTyp": 1, "REBez": "Wien", "KLBez": "Frauen", "GTyp": 2,
    "StartDate": "2026-04-29 07:00:00", "EndDate": "2026-05-31 23:59:00",
    "Backend": "0", "HAID": "", "AusgabeTyp": "1", "KWID": "0",
}, timeout=15)
body2 = r2.json()["Return_DIV_Body"]
competitors2 = parse_ranking(body2)
print(f"Wien Frauen: {len(competitors2)} competitors")
if competitors2:
    c2 = competitors2[0]
    print(f"  First: {c2['name']}  {c2['score']}/{c2['total']}  id={c2['id']}")
