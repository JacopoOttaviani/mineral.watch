#!/usr/bin/env python3
"""Build the 'Who produces what' portfolio Sankey for the mineral.watch homepage.

Reads world_mineral_statistics.csv (BGS), computes each top producer's share of
world mine production per tracked mineral, renders a static inline SVG plus a
data table, and injects both between the portfolio-sankey markers in index.html.
Re-run after a BGS data refresh (bump YEAR below)."""
import csv, html
from collections import defaultdict

import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = f'{ROOT}/world_mineral_statistics.csv'
INDEX = f'{ROOT}/index.html'
YEAR = '2024'
MIN_SHARE = 4.0   # producers below this % fold into "All others"
TOP_N = 4

# Editorial-warm palette, CVD-validated in this exact column order (dataviz skill
# validator; adjacent-pair CVD ΔE >= 8 and normal-vision floor pass): the brand
# lime lands on rare earths, the most concentrated chain. Nickel (emerald) and
# antimony (orchid) sit where they clear their neighbours.
MINERALS = [
    ('Manganese',   'manganese ore',     '#c08ad6', '/manganese/'),
    ('Graphite',    'graphite',          '#e6b95e', '/graphite/'),
    ('Cobalt',      'cobalt, mine',      '#84a5f0', '/cobalt/'),
    ('Nickel',      'nickel, mine',      '#34d399', '/nickel/'),
    ('Copper',      'copper, mine',      '#e08256', '/copper/'),
    ('Antimony',    'antimony, mine',    '#f0abfc', '/antimony/'),
    ('Rare earths', 'rare earth oxides', '#c8ff6b', '/rare-earths/'),
    ('Uranium',     'uranium',           '#4cc9f0', '/uranium/'),
    ('Lithium',     'lithium minerals',  '#ff7d9c', '/lithium/'),
]
SHORT = {'Congo, Democratic Republic': 'DR Congo'}

# ---- data ----
by_comm = defaultdict(lambda: defaultdict(float))
with open(CSV) as f:
    for r in csv.DictReader(f):
        if r['year'][:4] == YEAR and r['bgs_statistic_type_trans'] == 'Production':
            try: q = float(r['quantity'])
            except ValueError: continue
            by_comm[r['bgs_commodity_trans']][r['country_trans']] += q

links = []          # (country, mineral, share, color)
table_rows = {}     # mineral -> [(country, share)]
for mname, comm, color, _href in MINERALS:
    d = by_comm[comm]
    tot = sum(d.values())
    head = [(k, 100*v/tot) for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:TOP_N]]
    head = [(k, s) for k, s in head if s >= MIN_SHARE]
    others = 100 - sum(s for _, s in head)
    for k, s in head:
        links.append((SHORT.get(k, k), mname, s, color))
    links.append(('All others', mname, others, color))
    table_rows[mname] = head + [('All others', others)]

country_tot = defaultdict(float)
for c, _, s, _ in links: country_tot[c] += s
countries = [c for c, _ in sorted(country_tot.items(), key=lambda kv: -kv[1]) if c != 'All others'] + ['All others']
minerals = [m[0] for m in MINERALS]
mcolor = {m[0]: m[2] for m in MINERALS}
mhref = {m[0]: m[3] for m in MINERALS}

# ---- svg ----
W, H, TOP, BOT, NW, PADL, PADR, XL, XR = 880, 560, 30, 12, 12, 12, 12, 172, 694
tot_pts = sum(s for _, _, s, _ in links)
sL = (H-TOP-BOT-PADL*(len(countries)-1)) / tot_pts
sR = (H-TOP-BOT-PADR*(len(minerals)-1)) / tot_pts
sc = min(sL, sR)

lgeo, y = {}, TOP
for c in countries:
    h = country_tot[c]*sc; lgeo[c] = [y, h, y]; y += h + PADL
rgeo, y = {}, TOP
msum = defaultdict(float)
for _, m, s, _ in links: msum[m] += s
for m in minerals:
    h = msum[m]*sc; rgeo[m] = [y, h, y]; y += h + PADR

parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Sankey diagram: top producer countries and their share of world mine production for {len(MINERALS)} strategic minerals, {YEAR}" xmlns="http://www.w3.org/2000/svg">']
parts.append(f'<text x="{XL+NW/2}" y="{TOP-14}" text-anchor="middle" class="sk-col">PRODUCER</text>')
parts.append(f'<text x="{XR+NW/2}" y="{TOP-14}" text-anchor="middle" class="sk-col">MINERAL</text>')

def ribbon(y0, y1, t, color, tip):
    xm = (XL+NW+XR)/2
    return (f'<path class="sk-rb" d="M{XL+NW},{y0:.1f} C{xm:.1f},{y0:.1f} {xm:.1f},{y1:.1f} {XR},{y1:.1f} '
            f'L{XR},{y1+t:.1f} C{xm:.1f},{y1+t:.1f} {xm:.1f},{y0+t:.1f} {XL+NW},{y0+t:.1f} Z" '
            f'fill="{color}"><title>{html.escape(tip)}</title></path>')

for c, m, s, color in sorted(links, key=lambda l: (countries.index(l[0]), minerals.index(l[1]))):
    t = s*sc
    y0 = lgeo[c][2]; lgeo[c][2] += t
    y1 = rgeo[m][2]; rgeo[m][2] += t
    who = 'All other producers' if c == 'All others' else c
    parts.append(ribbon(y0, y1, t, color, f'{who} → {m}: {s:.1f}% of world production ({YEAR})'))

for c in countries:
    y, h, _ = lgeo[c]
    parts.append(f'<rect x="{XL}" y="{y:.1f}" width="{NW}" height="{max(h,1.5):.1f}" rx="2" fill="#8b98a5"/>')
    parts.append(f'<text x="{XL-8}" y="{y+h/2:.1f}" dy="4" text-anchor="end" class="sk-lab">{html.escape(c)}</text>')
for m in minerals:
    y, h, _ = rgeo[m]
    parts.append(f'<rect x="{XR}" y="{y:.1f}" width="{NW}" height="{h:.1f}" rx="2" fill="{mcolor[m]}"/>')
    parts.append(f'<a href="{mhref[m]}"><text x="{XR+NW+8}" y="{y+h/2:.1f}" dy="4" text-anchor="start" class="sk-min">{html.escape(m)}</text></a>')
parts.append('</svg>')
svg = '\n    '.join(parts)

# ---- table ----
trows = []
for m in minerals:
    for i, (c, s) in enumerate(table_rows[m]):
        cell = f'<td rowspan="{len(table_rows[m])}"><b>{html.escape(m)}</b></td>' if i == 0 else ''
        trows.append(f'<tr>{cell}<td>{html.escape(SHORT.get(c, c))}</td><td>{s:.1f}%</td></tr>')
table = ('<table><thead><tr><th>Mineral</th><th>Producer</th><th>Share of world mine production, '
         f'{YEAR}</th></tr></thead><tbody>' + ''.join(trows) + '</tbody></table>')

# ---- inject ----
src = open(INDEX).read()
def inject(src, tag, payload):
    a, b = f'<!-- portfolio-sankey:{tag}:start -->', f'<!-- portfolio-sankey:{tag}:end -->'
    i, j = src.index(a) + len(a), src.index(b)
    return src[:i] + '\n    ' + payload + '\n    ' + src[j:]
src = inject(src, 'svg', svg)
src = inject(src, 'table', table)
open(INDEX, 'w').write(src)
print(f'injected: {len(countries)} producers, {len(links)} ribbons, min visible share '
      f'{min(s for _, _, s, _ in links):.1f}%')
