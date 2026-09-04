#!/usr/bin/env python3
"""Generate the open data catalogue at data/index.html.

The page lists every dataset the site publishes: the 110 BGS World Mineral
Statistics commodity series under map_data/data/ (one JSON per commodity),
the two reference files (meta.json, countries.json) and the curated datasets
behind each dashboard. It carries a schema.org DataCatalog with one Dataset
per file so Google Dataset Search and AI crawlers can index the data itself,
not just the dashboards.

Re-run whenever map_data/ changes or a dashboard is added, then run
tools/build_seo.py so the sitemap and llms-full.txt pick it up:

    python3 tools/build_data_page.py && python3 tools/build_seo.py
"""
import datetime as dt
import html
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://mineral.watch'
URL = f'{SITE}/data/'
ORG = f'{SITE}/#organization'
WEBSITE = f'{SITE}/#website'
CC = 'https://creativecommons.org/licenses/by-nc-sa/4.0/'
BGS = 'https://www.bgs.ac.uk/mineralsuk/statistics/world-mineral-statistics/'
OUT = f'{ROOT}/data/index.html'
STAT_ORDER = ['Production', 'Imports', 'Exports']

# Dashboards in homepage order; the accent colour is read from each page.
DASHBOARDS = ['graphite', 'lithium', 'cobalt', 'nickel', 'rare-earths', 'copper', 'manganese', 'uranium', 'antimony', 'oil-gas', 'green']


def git_date(rel):
    out = subprocess.run(['git', 'log', '-1', '--format=%cs', '--', rel], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return out or dt.date.today().isoformat()


def cap(s):
    return s[:1].upper() + s[1:]


def esc(s):
    return html.escape(s, quote=True)


def load_ld(path):
    s = open(path).read()
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)
    return json.loads(m.group(1)) if m else {'@graph': []}


def commodity_rows(meta):
    rows = []
    for c in meta['commodities']:
        slug, name = c['slug'], c['name']
        if not slug:
            continue
        p = f'{ROOT}/map_data/data/{slug}.json'
        if not os.path.exists(p):
            continue
        d = json.load(open(p))
        stats = sorted(d.keys(), key=STAT_ORDER.index)
        years = sorted(int(y) for st in d.values() for y in st)
        countries = {iso for st in d.values() for y in st.values() for iso in y}
        units = meta['units'].get(name, {})
        rows.append(dict(slug=slug, name=name, stats=stats, y0=years[0], y1=years[-1], n=len(countries),
                         units=units, size=os.path.getsize(p)))
    return rows


def dashboard_cards():
    cards = []
    for slug in DASHBOARDS:
        path = f'{ROOT}/{slug}/index.html'
        s = open(path).read()
        accent = re.search(r'--accent:(#[0-9a-fA-F]{3,6})', s).group(1)
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', s, re.S).group(1)
        h1 = html.unescape(re.sub(r'<[^>]+>', '', h1)).strip()
        brand = re.search(r'<div class="brand">(.*?)</div>', s).group(1)
        ds = next(n for n in load_ld(path)['@graph'] if n.get('@type') == 'Dataset')
        cards.append(dict(slug=slug, accent=accent, h1=h1, brand=html.unescape(brand), ds=ds))
    return cards


def kb(n):
    return f'{n / 1024:.0f} KB' if n < 1024 * 1024 else f'{n / 1024 / 1024:.1f} MB'


def dataset_node(r):
    unit_txt = '; '.join(f'{s.lower()} in {r["units"][s]}' for s in r['stats'] if s in r['units'])
    stats_txt = ', '.join(s.lower() for s in r['stats'])
    return {
        "@type": "Dataset", "@id": f"{URL}#{r['slug']}",
        "name": f"{cap(r['name'])} — world {stats_txt} by country, {r['y0']}–{r['y1']}",
        "description": (f"Annual {stats_txt} of {r['name']} for {r['n']} countries, {r['y0']}–{r['y1']}, compiled by mineral.watch from the British Geological Survey's "
                        f"World Mineral Statistics. Units: {unit_txt}. One JSON file keyed statistic → year → ISO3 country code → quantity."),
        "url": f"{URL}#{r['slug']}", "sameAs": f"{SITE}/explorer/?commodity={r['slug']}",
        "creator": {"@id": ORG}, "publisher": {"@id": ORG}, "isBasedOn": [BGS], "license": CC, "isAccessibleForFree": True,
        "inLanguage": "en", "temporalCoverage": f"{r['y0']}/{r['y1']}", "spatialCoverage": {"@type": "Place", "name": f"Worldwide ({r['n']} countries)"},
        "variableMeasured": r['stats'], "keywords": [r['name'], *[s.lower() for s in r['stats']], "world mineral statistics", "by country", "BGS", "open data"],
        "includedInDataCatalog": {"@id": f"{URL}#catalog"},
        "distribution": [{"@type": "DataDownload", "contentUrl": f"{SITE}/map_data/data/{r['slug']}.json", "encodingFormat": "application/json", "contentSize": kb(r['size'])}],
        "citation": ["British Geological Survey, World Mineral Statistics (BGS © UKRI)"],
    }


def build():
    meta = json.load(open(f'{ROOT}/map_data/meta.json'))
    rows = commodity_rows(meta)
    cards = dashboard_cards()
    n_countries = len(json.load(open(f'{ROOT}/map_data/countries.json')))
    total_size = sum(r['size'] for r in rows)
    y0, y1 = meta['years']['min'], meta['years']['max']
    updated = git_date('map_data/meta.json')
    today = dt.date.today()

    title = 'Open Data Catalogue — Mineral, Oil &amp; Gas and Green-Transition Datasets | mineral.watch'
    desc = (f'Download the open data behind mineral.watch: {len(rows)} BGS World Mineral Statistics series (production, imports and exports by country, {y0}–{y1}) as JSON, '
            f'plus the curated datasets behind the {len(cards)} mineral, oil &amp; gas and green-transition dashboards. CC BY-NC-SA 4.0.')

    # ---- structured data ----------------------------------------------------
    catalog = {
        "@type": "DataCatalog", "@id": f"{URL}#catalog", "name": "mineral.watch open data catalogue", "url": URL,
        "description": html.unescape(desc), "publisher": {"@id": ORG}, "license": CC, "inLanguage": "en", "dateModified": updated,
        "dataset": [dataset_node(r) for r in rows] + [
            {"@type": "Dataset", "@id": f"{SITE}/{c['slug']}/#dataset", "name": c['ds']['name'], "url": f"{SITE}/{c['slug']}/",
             "description": c['ds']['description'], "license": CC, "creator": {"@id": ORG}} for c in cards
        ] + [
            {"@type": "Dataset", "@id": f"{URL}#meta", "name": "Commodity index — names, slugs, statistics, year range and units",
             "description": f"Index of the {len(rows)} commodity series: BGS commodity name, URL slug, statistics available, {y0}–{y1} year range and the unit of each statistic.",
             "url": f"{URL}#reference", "license": CC, "creator": {"@id": ORG}, "isBasedOn": [BGS],
             "distribution": [{"@type": "DataDownload", "contentUrl": f"{SITE}/map_data/meta.json", "encodingFormat": "application/json"}]},
            {"@type": "Dataset", "@id": f"{URL}#countries", "name": f"Country names and centroids by ISO3 code ({n_countries} entries)",
             "description": "Lookup table mapping ISO 3166-1 alpha-3 codes (plus historical codes used by BGS, such as YUG, CSK, DDR) to a country name and a geographic centroid in WGS84.",
             "url": f"{URL}#reference", "license": CC, "creator": {"@id": ORG},
             "distribution": [{"@type": "DataDownload", "contentUrl": f"{SITE}/map_data/countries.json", "encodingFormat": "application/json"}]},
        ],
    }
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "@id": f"{URL}#webpage", "url": URL, "name": html.unescape(title), "description": html.unescape(desc),
         "isPartOf": {"@id": WEBSITE}, "publisher": {"@id": ORG}, "inLanguage": "en", "dateModified": updated, "license": CC,
         "breadcrumb": {"@id": f"{URL}#breadcrumb"}, "mainEntity": {"@id": f"{URL}#catalog"},
         "primaryImageOfPage": {"@type": "ImageObject", "url": f"{SITE}/brand/og-image.png?v=3", "width": 1200, "height": 630}},
        {"@type": "BreadcrumbList", "@id": f"{URL}#breadcrumb", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "mineral.watch", "item": f"{SITE}/"},
            {"@type": "ListItem", "position": 2, "name": "Open data", "item": URL}]},
        catalog,
    ]}

    # ---- html fragments ----------------------------------------------------
    def card(c):
        ds = c['ds']
        dl = ''.join(f'<a class="chip" href="{esc(d["contentUrl"])}" download>{esc(d["contentUrl"].rsplit("/", 1)[-1])}</a>'
                     for d in ds.get('distribution', []))
        dl_block = f'<div class="chips">{dl}</div>' if dl else '<p class="note">Data embedded in the page and cited inline; no separate file.</p>'
        return (f'<article class="dcard" id="{c["slug"]}-dashboard" style="--accent:{c["accent"]}">'
                f'<h3><a href="/{c["slug"]}/">{esc(c["brand"])}</a> <span class="q">{esc(c["h1"])}</span></h3>'
                f'<p>{esc(ds["description"])}</p>'
                f'<p class="meta">Coverage {esc(ds.get("temporalCoverage", ""))} · {esc(", ".join(ds.get("variableMeasured", [])[:6]))}'
                f'{" …" if len(ds.get("variableMeasured", [])) > 6 else ""}</p>'
                f'{dl_block}</article>')

    def row(r):
        stats = ''.join(f'<span class="st st-{s[0].lower()}" title="{s}">{s[0]}</span>' for s in r['stats'])
        units = '<br>'.join(f'{esc(s.lower())}: {esc(r["units"][s])}' for s in r['stats'] if s in r['units'])
        return (f'<tr id="{r["slug"]}" data-name="{esc(r["name"].lower())}">'
                f'<td class="c"><a href="/explorer/?commodity={r["slug"]}">{esc(cap(r["name"]))}</a></td>'
                f'<td class="s">{stats}</td><td class="y">{r["y0"]}–{r["y1"]}</td><td class="n">{r["n"]}</td>'
                f'<td class="u">{units}</td>'
                f'<td class="d"><a class="chip" href="/map_data/data/{r["slug"]}.json" download>JSON</a> <span class="sz">{kb(r["size"])}</span></td></tr>')

    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
<meta name="author" content="mineral.watch">
<meta name="copyright" content="© 2026 mineral.watch">
<link rel="license" href="{CC}">
<meta name="theme-color" content="#0d1117">
<link rel="canonical" href="{URL}">
<link rel="icon" type="image/svg+xml" href="/brand/favicon.svg">
<link rel="alternate icon" href="/brand/favicon.png">
<link rel="apple-touch-icon" href="/brand/apple-touch-icon.png">
<link rel="alternate" type="application/json" href="/map_data/meta.json" title="Commodity index (JSON)">
<!-- Open Graph / Facebook / WhatsApp -->
<meta property="og:type" content="website">
<meta property="og:url" content="{URL}">
<meta property="og:site_name" content="mineral.watch">
<meta property="og:locale" content="en_US">
<meta property="og:title" content="Open data catalogue — mineral.watch">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{SITE}/brand/og-image.png?v=3">
<meta property="og:image:secure_url" content="{SITE}/brand/og-image.png?v=3">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="mineral.watch — open data and intelligence on minerals, oil &amp; gas and the green transition">
<!-- Twitter / X -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Open data catalogue — mineral.watch">
<meta name="twitter:description" content="{len(rows)} commodity series ({y0}–{y1}) as JSON plus the data behind every dashboard. CC BY-NC-SA 4.0.">
<meta name="twitter:image" content="{SITE}/brand/og-image.png?v=3">
<meta name="twitter:image:alt" content="mineral.watch — open data and intelligence on minerals, oil &amp; gas and the green transition">
<!-- Structured data -->
<script type="application/ld+json">
{json.dumps(ld, separators=(",", ":"), ensure_ascii=False)}
</script>
<style>
:root{{
  --bg:#0d1117;--bg2:#151b23;--card:#1a222c;--ink:#e6edf3;--muted:#8b98a5;
  --accent:#c8ff6b;--teal:#4cc9f0;--line:#2b3644;
  --radius:14px;--pad:16px;
  font-size:16px;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.6;-webkit-font-smoothing:antialiased}}
a{{color:var(--teal)}}
h1,h2,h3{{line-height:1.15;font-weight:700;letter-spacing:-.015em}}
.serif{{font-family:Georgia,"Times New Roman",serif}}
code,.mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}

nav{{position:sticky;top:0;z-index:100;background:rgba(13,17,23,.92);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}}
.nav-inner{{display:flex;align-items:center;gap:6px;padding:12px var(--pad);max-width:1080px;margin:0 auto;overflow-x:auto;scrollbar-width:none}}
.nav-inner::-webkit-scrollbar{{display:none}}
.brand{{font-weight:800;font-size:1rem;white-space:nowrap;margin-right:auto;color:var(--ink);text-decoration:none;display:flex;align-items:center}}
.brand span{{color:var(--accent)}}
.brand svg{{flex:none;margin-right:8px}}
nav a.link{{color:var(--muted);text-decoration:none;font-size:.82rem;padding:6px 12px;border-radius:99px;white-space:nowrap}}
nav a.link:hover{{color:var(--ink);background:var(--card)}}

.wrap{{max-width:1080px;margin:0 auto;padding:48px var(--pad) 64px}}
.kicker{{color:var(--accent);text-transform:uppercase;letter-spacing:.15em;font-size:.72rem;font-weight:700;margin-bottom:10px}}
h1{{font-size:2.1rem;margin-bottom:14px}}
.lede{{color:var(--muted);font-size:1.02rem;margin-bottom:10px;max-width:760px}}
.updated{{color:var(--muted);font-size:.78rem;border-top:1px solid var(--line);padding-top:14px;margin-top:22px}}
h2{{font-size:1.28rem;margin:38px 0 12px;padding-top:22px;border-top:1px solid var(--line)}}
h2:first-of-type{{border-top:none;padding-top:0}}
h3{{font-size:1rem;margin:22px 0 6px;color:var(--accent)}}
p{{margin-bottom:12px}}
ul{{margin:0 0 12px 20px}}
li{{margin-bottom:6px}}
strong{{color:var(--ink)}}

.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:26px 0 8px}}
.stat{{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:14px 16px}}
.stat b{{display:block;font-size:1.45rem;letter-spacing:-.02em;color:var(--accent);font-variant-numeric:tabular-nums}}
.stat span{{font-size:.78rem;color:var(--muted)}}

.dgrid{{display:grid;gap:12px;margin:18px 0}}
.dcard{{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:var(--radius);padding:18px 20px}}
.dcard h3{{margin-top:0;color:var(--ink);font-size:1.02rem}}
.dcard h3 a{{color:var(--accent);text-decoration:none}}
.dcard h3 a:hover{{text-decoration:underline}}
.dcard h3 .q{{font-weight:400;color:var(--muted);font-family:Georgia,"Times New Roman",serif;font-style:italic}}
.dcard p{{font-size:.9rem;color:var(--muted);margin-bottom:8px}}
.dcard .meta{{font-size:.78rem}}
.dcard .note{{font-size:.78rem;margin:0}}
.chips{{display:flex;flex-wrap:wrap;gap:6px}}
.chip{{display:inline-block;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.72rem;background:var(--bg2);border:1px solid var(--line);border-radius:99px;padding:3px 10px;color:var(--ink);text-decoration:none;white-space:nowrap}}
.chip:hover{{border-color:var(--accent);color:var(--accent)}}

.filter{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:14px 0}}
.filter input{{flex:1;min-width:220px;background:var(--bg2);border:1px solid var(--line);border-radius:10px;padding:10px 14px;color:var(--ink);font:inherit;font-size:.92rem}}
.filter input:focus{{outline:2px solid var(--teal);outline-offset:1px}}
.filter .count{{font-size:.8rem;color:var(--muted);font-variant-numeric:tabular-nums}}
.tablewrap{{overflow-x:auto;border:1px solid var(--line);border-radius:var(--radius);background:var(--card)}}
table{{width:100%;border-collapse:collapse;font-size:.86rem;min-width:720px}}
th,td{{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-weight:700;background:var(--bg2);position:sticky;top:0}}
tr:last-child td{{border-bottom:none}}
td.c a{{color:var(--ink);text-decoration:none;font-weight:600}}
td.c a:hover{{color:var(--accent)}}
td.y,td.n{{font-variant-numeric:tabular-nums;white-space:nowrap}}
td.u{{color:var(--muted);font-size:.78rem;line-height:1.45}}
td.d{{white-space:nowrap}}
.sz{{font-size:.72rem;color:var(--muted);margin-left:4px}}
.st{{display:inline-block;width:20px;height:20px;line-height:20px;text-align:center;border-radius:6px;font-size:.7rem;font-weight:700;margin-right:3px;background:var(--bg2);border:1px solid var(--line);color:var(--muted)}}
.st-p{{color:var(--accent);border-color:rgba(200,255,107,.4)}}
.st-i{{color:var(--teal);border-color:rgba(76,201,240,.4)}}
.st-e{{color:#fbbf24;border-color:rgba(251,191,36,.4)}}
tr[hidden]{{display:none}}

pre{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.8rem;background:var(--bg2);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0;color:var(--ink);overflow-x:auto;line-height:1.5}}
.callout{{background:var(--bg2);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:var(--radius);padding:16px 20px;margin:18px 0}}
.callout p{{font-size:.9rem;margin-bottom:0}}
.callout p + p{{margin-top:8px}}
.attrib{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.82rem;background:var(--bg2);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0;color:var(--ink);overflow-x:auto;line-height:1.5}}
.legend{{font-size:.78rem;color:var(--muted);margin:8px 0 0}}

footer{{border-top:1px solid var(--line);padding:28px var(--pad);text-align:center;color:var(--muted);font-size:.76rem}}
footer a{{color:inherit;text-decoration:none}}
footer a:hover{{color:var(--accent)}}
.legal{{display:block;margin-top:8px;opacity:.85}}

@media(min-width:720px){{
  :root{{--pad:24px}}
  .dgrid{{grid-template-columns:1fr 1fr}}
  h1{{font-size:2.6rem}}
}}
@media(min-width:1000px){{.dgrid{{grid-template-columns:1fr 1fr 1fr}}}}
</style>
</head>
<body>

<nav>
  <div class="nav-inner">
    <a class="brand" href="/"><svg width="22" height="22" viewBox="0 0 64 64" fill="none" aria-hidden="true"><g stroke="var(--ink)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12 H44"/><path d="M20 12 L6 26"/><path d="M44 12 L58 26"/><path d="M6 26 H58"/><path d="M6 26 L32 56"/><path d="M58 26 L32 56"/><path d="M20 12 L32 26"/><path d="M44 12 L32 26"/><path d="M32 26 V56"/></g><g fill="var(--bg)" stroke="var(--ink)" stroke-width="2.5"><circle cx="20" cy="12" r="4"/><circle cx="44" cy="12" r="4"/><circle cx="6" cy="26" r="4"/><circle cx="58" cy="26" r="4"/><circle cx="32" cy="56" r="4"/></g><circle cx="32" cy="26" r="5.5" fill="var(--accent)"/></svg>mineral<span>.watch</span></a>
    <a class="link" href="/#minerals">Minerals</a>
    <a class="link" href="/oil-gas/">Oil &amp; gas</a>
    <a class="link" href="/green/">Green transition</a>
    <a class="link" href="/explorer/">Explorer</a>
    <a class="link" href="/terms/">Licensing</a>
  </div>
</nav>

<main class="wrap">

  <div class="kicker">Open data</div>
  <h1 class="serif">The open data behind mineral.watch</h1>
  <p class="lede">Every number on this site traces back to a public source, and the compiled files are yours to reuse. This catalogue lists all of them: {len(rows)} commodity series mirrored from the British Geological Survey's World Mineral Statistics as plain JSON, the reference files that go with them, and the curated datasets behind each dashboard on minerals, oil &amp; gas and the green transition.</p>
  <p class="lede">Licence: <a href="{CC}" rel="license">CC BY-NC-SA 4.0</a> for the compilation — cite <strong>mineral.watch</strong> and the original publisher. Underlying statistics remain the property of their publishers (BGS © UKRI, USGS, IEA, EIA, OPEC and others).</p>

  <div class="stats" aria-label="Catalogue at a glance">
    <div class="stat"><b>{len(rows)}</b><span>commodity series as JSON</span></div>
    <div class="stat"><b>{n_countries}</b><span>countries and territories</span></div>
    <div class="stat"><b>{y0}–{y1}</b><span>years covered</span></div>
    <div class="stat"><b>{len(cards)}</b><span>curated dashboard datasets</span></div>
    <div class="stat"><b>{kb(total_size)}</b><span>total download, uncompressed</span></div>
  </div>

  <h2 id="dashboards">Dashboard datasets</h2>
  <p class="lede">Each dashboard compiles production, reserves, trade, price and policy data from the primary sources it cites — USGS, BGS, UN Comtrade, the IEA, the EIA, OPEC, industry bodies and company disclosures. The BGS series that feed its maps are downloadable below; the rest is embedded in the page, cited and dated inline, and described in the page's schema.org <code>Dataset</code> record.</p>
  <div class="dgrid">
    {''.join(card(c) for c in cards)}
  </div>

  <h2 id="bgs">World mineral statistics, {y0}–{y1}, as JSON</h2>
  <p class="lede">One file per commodity, mirrored from the <a href="{BGS}">BGS World Mineral Statistics</a> database via the BGS OGC API Features service and reshaped for the <a href="/explorer/">Mineral Explorer</a> and the <a href="/supply-chain/">mined-vs-refined map</a>. Figures for a given country, commodity and year are summed across BGS sub-commodity breakdowns. Click a commodity to open it on the map.</p>
  <div class="filter">
    <input type="search" id="q" placeholder="Filter commodities — e.g. copper, lithium, crude, rare earth" aria-label="Filter commodities" autocomplete="off">
    <span class="count" id="count">{len(rows)} of {len(rows)}</span>
  </div>
  <div class="tablewrap">
  <table id="tbl">
    <thead><tr><th>Commodity</th><th>Statistics</th><th>Years</th><th>Countries</th><th>Units</th><th>Download</th></tr></thead>
    <tbody>
    {''.join(row(r) for r in rows)}
    </tbody>
  </table>
  </div>
  <p class="legend"><span class="st st-p">P</span> production · <span class="st st-i">I</span> imports · <span class="st st-e">E</span> exports. Country counts are the number of distinct ISO3 codes reporting at least one year. Sizes are uncompressed.</p>

  <h2 id="reference">Reference files</h2>
  <ul>
    <li><a class="chip" href="/map_data/meta.json" download>meta.json</a> — the commodity index: BGS name, URL slug, statistics available, year range and the unit of each statistic.</li>
    <li><a class="chip" href="/map_data/countries.json" download>countries.json</a> — {n_countries} ISO 3166-1 alpha-3 codes (plus the historical codes BGS uses, such as YUG, CSK and DDR) mapped to a country name and a WGS84 centroid.</li>
  </ul>

  <h2 id="format">File format</h2>
  <p>Commodity files live at <code>https://mineral.watch/map_data/data/&lt;slug&gt;.json</code> and are keyed statistic → year → ISO3 code → quantity, in the unit given in <code>meta.json</code>:</p>
<pre>{{
  "Production": {{
    "2024": {{ "CHL": 5300000, "COD": 3200000, "PER": 2700000, … }},
    "2023": {{ … }}
  }},
  "Imports":  {{ "2024": {{ "CHN": …, "JPN": … }}, … }},
  "Exports":  {{ "2024": {{ "CHL": …, "PER": … }}, … }}
}}</pre>
  <p>Files are static, CORS-readable and served over HTTPS, so you can <code>fetch()</code> them directly from a browser or pull them with <code>curl</code>. Quantities are numbers, never strings; a country absent from a year has no reported figure for it. Mine-stage series for cobalt, copper and nickel are metal content; refined and smelter series are gross tonnes — compare shares between stages, not absolute volumes.</p>
<pre>curl -s https://mineral.watch/map_data/data/copper-mine.json | python3 -c "import json,sys; d=json.load(sys.stdin)['Production']['2024']; print(sorted(d.items(), key=lambda kv:-kv[1])[:5])"</pre>

  <h2 id="machine">Machine-readable access</h2>
  <ul>
    <li><strong>Structured data.</strong> Every page carries schema.org JSON-LD — <code>Dataset</code>, <code>DataCatalog</code>, <code>WebPage</code>, <code>BreadcrumbList</code> and <code>FAQPage</code> — with source citations, coverage, licence and download links.</li>
    <li><strong>For AI assistants and crawlers.</strong> <a href="/llms.txt">/llms.txt</a> summarises the site and its key facts; <a href="/llms-full.txt">/llms-full.txt</a> adds each dashboard's questions and answers. Both follow the llms.txt convention.</li>
    <li><strong>Site index.</strong> <a href="/sitemap.xml">/sitemap.xml</a> lists every page with its last-modified date; <a href="/robots.txt">/robots.txt</a> welcomes search and AI crawlers alike.</li>
    <li><strong>Source code.</strong> The site, its dashboards and the tooling that builds this catalogue are on <a href="https://github.com/JacopoOttaviani/mineral.watch">GitHub</a> under AGPL-3.0.</li>
  </ul>

  <h2 id="cite">Licence and citation</h2>
  <p>The compilation — selection, cleaning, cross-checking, geocoding and arrangement — is licensed <a href="{CC}" rel="license">CC BY-NC-SA 4.0</a>; the sui generis database right is asserted. Use this credit line, hyperlinked where the medium allows, and credit the original publisher alongside it:</p>
  <div class="attrib">Source: mineral.watch (https://mineral.watch), compiled from BGS World Mineral Statistics — CC BY-NC-SA 4.0</div>
  <p>Full terms, including what needs a licence, are on the <a href="/terms/">terms &amp; licensing</a> page and in the <a href="/LICENSE.txt">licensing notice</a>. If you want the raw figures with no strings attached, go to the <a href="{BGS}">original BGS publication</a> — that is the honest route and we will happily point you to the right table.</p>

  <h2 id="contact">Corrections, bulk access and custom datasets</h2>
  <div class="callout">
    <p><strong>Spotted an error?</strong> Corrections are always welcome and always free: <a href="mailto:hello@mineral.watch">hello@mineral.watch</a>.</p>
    <p><strong>Need more?</strong> Commercial licences, bulk exports, UN Comtrade trade-flow extracts, geocoded facility lists and bespoke, source-cited datasets on any mineral, fuel or clean-energy supply chain are available on commission — same address.</p>
  </div>

  <p class="updated">Data files last updated {updated}. Catalogue generated {today.isoformat()}. © 2026 mineral.watch.</p>

</main>

<footer>
  <a href="/">mineral.watch</a> · open data &amp; intelligence on minerals, oil &amp; gas and the green transition · sources: USGS, BGS, UN Comtrade, IEA, EIA
  <span class="legal">© 2026 mineral.watch · Content &amp; data <a href="{CC}" rel="license">CC BY-NC-SA 4.0</a> · Code <a href="https://www.gnu.org/licenses/agpl-3.0.html" rel="license">AGPL-3.0</a> · <a href="/data/">Open data</a> · <a href="/terms/">Terms &amp; licensing</a></span>
</footer>

<script>
(function(){{
  const q = document.getElementById('q'), rows = [...document.querySelectorAll('#tbl tbody tr')], count = document.getElementById('count');
  function apply(){{
    const t = q.value.trim().toLowerCase();
    let n = 0;
    rows.forEach(r => {{ const hit = !t || r.dataset.name.includes(t) || r.id.includes(t); r.hidden = !hit; if (hit) n++; }});
    count.textContent = n + ' of ' + rows.length;
  }}
  q.addEventListener('input', apply);
  if (location.hash) {{ const el = document.getElementById(location.hash.slice(1)); if (el && el.tagName === 'TR') el.style.background = 'rgba(200,255,107,.08)'; }}
}})();
</script>
</body>
</html>
'''
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w').write(page)
    print(f'wrote {os.path.relpath(OUT, ROOT)} ({os.path.getsize(OUT) // 1024} KB, {len(rows)} series, {len(cards)} dashboards)')


if __name__ == '__main__':
    build()
