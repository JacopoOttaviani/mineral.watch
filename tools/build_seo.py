#!/usr/bin/env python3
"""Rebuild the site's discovery layer and check it.

    python3 tools/build_seo.py          # rebuild + report
    python3 tools/build_seo.py --check  # report only, exit 1 on problems

What it does
  1. sitemap.xml — every page, lastmod from the last git commit touching it
     (today if the file has uncommitted changes), priority by page type.
  2. dateModified — refreshes the WebPage (and, on dashboards, Dataset)
     nodes in each page's JSON-LD to match the sitemap lastmod.
  3. llms-full.txt — llms.txt followed by each dashboard's description,
     dataset record, sources and FAQ, so AI crawlers get the full picture in
     one plain-text file.
  4. Checks — JSON-LD parses, every page has title/description/canonical/
     og:image/robots, visible FAQ count matches the FAQPage schema, internal
     links resolve, sitemap and llms.txt cover every page.

Run it after adding or editing a page, and after tools/build_data_page.py.
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://mineral.watch'
DASHBOARDS = ['graphite', 'rare-earths', 'copper', 'uranium', 'lithium', 'manganese', 'cobalt', 'antimony', 'nickel', 'oil-gas', 'green']
PRIORITY = {'': ('weekly', '1.0'), 'data': ('weekly', '0.8'), 'explorer': ('monthly', '0.8'), 'supply-chain': ('monthly', '0.8'), 'terms': ('yearly', '0.3')}
LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def sh(*args):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True).stdout.strip()


def pages():
    out = [('', 'index.html')]
    for d in sorted(os.listdir(ROOT)):
        if os.path.isfile(f'{ROOT}/{d}/index.html') and not d.startswith('.'):
            out.append((d, f'{d}/index.html'))
    return out


def lastmod(rel):
    if sh('git', 'status', '--porcelain', '--', rel):
        return dt.date.today().isoformat()
    return sh('git', 'log', '-1', '--format=%cs', '--', rel) or dt.date.today().isoformat()


def read_ld(html):
    m = LD_RE.search(html)
    return (json.loads(m.group(1)), m) if m else (None, None)


def write_ld(html, m, ld):
    # keep whichever serialisation the page already uses (the data catalogue is compact, everything else pretty-printed)
    compact = '\n' not in m.group(1).strip()
    body = json.dumps(ld, separators=(',', ':'), ensure_ascii=False) if compact else json.dumps(ld, indent=2, ensure_ascii=False)
    return html[:m.start()] + '<script type="application/ld+json">\n' + body + '\n</script>' + html[m.end():]


def refresh_dates(slug, rel, date):
    path = f'{ROOT}/{rel}'
    html = open(path).read()
    ld, m = read_ld(html)
    if not ld:
        return False
    changed = False
    for node in ld.get('@graph', [ld]):
        t = node.get('@type')
        if t == 'WebPage' or (t == 'Dataset' and slug in DASHBOARDS):
            if node.get('dateModified') != date:
                node['dateModified'] = date
                changed = True
    if changed:
        open(path, 'w').write(write_ld(html, m, ld))
    return changed


def build_sitemap(entries):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for slug, date in entries:
        freq, pri = PRIORITY.get(slug, ('weekly', '0.9'))
        loc = f'{SITE}/{slug}/' if slug else f'{SITE}/'
        lines += ['  <url>', f'    <loc>{loc}</loc>', f'    <lastmod>{date}</lastmod>', f'    <changefreq>{freq}</changefreq>', f'    <priority>{pri}</priority>', '  </url>']
    lines.append('</urlset>')
    open(f'{ROOT}/sitemap.xml', 'w').write('\n'.join(lines) + '\n')


def text(s):
    s = re.sub(r'<[^>]+>', '', s)
    return re.sub(r'\s+', ' ', s.replace('&amp;', '&').replace('&nbsp;', ' ').replace('&quot;', '"').replace('&#39;', "'")).strip()


def build_llms_full():
    base = open(f'{ROOT}/llms.txt').read().rstrip() + '\n'
    parts = [base, '\n---\n\n# Dashboards in full\n\n'
             'Each section below reproduces a page\'s description, its schema.org Dataset record (coverage, variables, downloads, sources) '
             'and its published questions and answers verbatim. Figures are as of the page\'s last update; cite mineral.watch and the primary source named.\n']
    for slug, rel in pages():
        if slug in ('', 'terms'):
            continue
        html = open(f'{ROOT}/{rel}').read()
        ld, _ = read_ld(html)
        title = text(re.search(r'<title>(.*?)</title>', html).group(1))
        desc = text(re.search(r'<meta name="description" content="(.*?)">', html).group(1))
        nodes = ld.get('@graph', []) if ld else []
        by = {}
        for n in nodes:
            by.setdefault(n.get('@type'), n)
        parts.append(f'\n## {title}\n\nURL: {SITE}/{slug}/\n\n{desc}\n')
        page = by.get('WebPage', {})
        if page.get('dateModified'):
            parts.append(f'\nLast updated: {page["dateModified"]}\n')
        ds = by.get('Dataset') or by.get('DataCatalog')
        if ds:
            parts.append(f'\n### Dataset\n\n{ds.get("name", "")}\n\n{ds.get("description", "")}\n')
            if ds.get('temporalCoverage'):
                parts.append(f'\n- Temporal coverage: {ds["temporalCoverage"]}')
            if ds.get('variableMeasured'):
                parts.append(f'\n- Variables: {", ".join(ds["variableMeasured"])}')
            if ds.get('license'):
                parts.append(f'\n- Licence: {ds["license"]}')
            for d in ds.get('distribution', []):
                parts.append(f'\n- Download: {d.get("contentUrl")} ({d.get("name", "JSON")})')
            if ds.get('citation'):
                parts.append('\n- Sources: ' + '; '.join(ds['citation']))
            elif ds.get('isBasedOn'):
                parts.append('\n- Based on: ' + ', '.join(ds['isBasedOn']))
            parts.append('\n')
        faq = by.get('FAQPage')
        if faq:
            parts.append('\n### Questions and answers\n')
            for q in faq.get('mainEntity', []):
                parts.append(f'\n**{q["name"]}**\n\n{q["acceptedAnswer"]["text"]}\n')
    open(f'{ROOT}/llms-full.txt', 'w').write(''.join(parts))


def check(entries):
    problems, warnings = [], []
    sitemap = open(f'{ROOT}/sitemap.xml').read()
    llms = open(f'{ROOT}/llms.txt').read()
    for slug, rel in pages():
        html = open(f'{ROOT}/{rel}').read()
        url = f'{SITE}/{slug}/' if slug else f'{SITE}/'
        for label, pat in [('title', r'<title>.+?</title>'), ('description', r'<meta name="description" content=".{50,}?">'),
                           ('canonical', rf'<link rel="canonical" href="{re.escape(url)}">'), ('og:image', r'<meta property="og:image" content="https://'),
                           ('robots', r'<meta name="robots" content="index, follow'), ('h1', r'<h1[\s>]'), ('lang', r'<html lang="en">')]:
            if not re.search(pat, html, re.S):
                problems.append(f'{rel}: missing {label}')
        if len(re.findall(r'<h1[\s>]', html)) > 1:
            warnings.append(f'{rel}: more than one <h1>')
        blocks = LD_RE.findall(html)
        if not blocks:
            problems.append(f'{rel}: no JSON-LD')
        for b in blocks:
            try:
                ld = json.loads(b)
            except Exception as e:
                problems.append(f'{rel}: invalid JSON-LD ({e})'); continue
            for n in ld.get('@graph', [ld]):
                if n.get('@type') == 'FAQPage':
                    faq_html = re.search(r'<section id="faq[^"]*".*?</section>', html, re.S)
                    visible = len(re.findall(r'<summary>', faq_html.group(0) if faq_html else html))
                    if visible != len(n.get('mainEntity', [])):
                        warnings.append(f'{rel}: {visible} visible FAQ items vs {len(n["mainEntity"])} in FAQPage schema')
                if n.get('@type') == 'Dataset' and not str(n.get('license', '')).startswith('https://creativecommons.org/'):
                    problems.append(f'{rel}: Dataset licence is {n.get("license")!r}')
        for href in set(re.findall(r'href="(/[^"#?]*)', html)):
            target = f'{ROOT}{href}'
            if not (os.path.exists(target) or os.path.exists(f'{target}/index.html') or os.path.exists(f'{target}index.html')):
                problems.append(f'{rel}: broken internal link {href}')
        if url not in sitemap:
            problems.append(f'{rel}: not in sitemap.xml')
        if slug and url not in llms:
            warnings.append(f'{rel}: not mentioned in llms.txt')
    return problems, warnings


def main():
    check_only = '--check' in sys.argv
    entries = []
    for slug, rel in pages():
        date = lastmod(rel)
        if not check_only and refresh_dates(slug, rel, date):
            date = lastmod(rel)
        entries.append((slug, date))
    if not check_only:
        build_sitemap(entries)
        build_llms_full()
        print(f'sitemap.xml: {len(entries)} URLs; llms-full.txt: {os.path.getsize(f"{ROOT}/llms-full.txt") // 1024} KB')
    problems, warnings = check(entries)
    for w in warnings:
        print('warn ', w)
    for p in problems:
        print('FAIL ', p)
    print(f'{len(entries)} pages checked — {len(problems)} problems, {len(warnings)} warnings')
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
