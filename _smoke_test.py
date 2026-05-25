import requests
from scraper import fetch_ranking_html, parse_ranking, parse_detail, _detail_url, _session, CLASSES, REGIONS

s = _session()
graz = REGIONS["Graz"]

# Test ranking parse for both classes
for cls in CLASSES:
    html = fetch_ranking_html(s, cls, graz)
    competitors = parse_ranking(html)
    print(f"{cls['name']}: {len(competitors)} competitors")
    for c in competitors[:3]:
        print(f"  {c['rank']}. {c['name']}  {c['score']}/{c['total']}  (id={c['id']})")

# Test detail parse for Treitler Peter (Männer, class_k=686, id=2723)
# Expected: BLOC house 30/40, Boulderclub 23/40, Newton 29/40
detail_html = s.get(_detail_url(2723, 686, graz["id"]), timeout=15).text
boulders = parse_detail(detail_html)
expected = {"BLOC house": 30, "Boulderclub": 23, "Newton": 29}
print("\nDetail for Treitler Peter:")
for gym, b in boulders.items():
    ok = "✓" if sum(b) == expected.get(gym, -1) else "✗"
    print(f"  {ok} {gym}: {sum(b)}/{len(b)} (expected {expected.get(gym, '?')})")