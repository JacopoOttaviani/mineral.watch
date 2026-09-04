#!/usr/bin/env python3
"""Photo-background Instagram sets, one per mineral, under social/instagram/minerals/.

Each mineral gets a 4-slide set (usable as one carousel or as four standalone
posts): a cover with the dashboard's headline question, two big-number stat
cards and a "why it matters" card with the dashboard URL. The background is the
mineral's own header photo from brand/headers/ rendered as a duotone — the photo
is desaturated, multiplied by the mineral's dashboard accent colour and lifted
onto the site's #0d1117 ground, i.e. the same treatment the dashboard heroes use,
pushed further so type stays legible. Every slide carries "visit mineral.watch".

Shares the palette, frame chrome and renderer with gen_instagram_posts.py.

Outputs (social/instagram/minerals/):
  <slug>/slide-01.jpg … slide-04.jpg   (JPEG q90 — photo backgrounds)
  captions.md · posts.json · _contact-sheet.png

Re-run:                 python3 tools/gen_instagram_mineral_sets.py
Render a subset:        python3 tools/gen_instagram_mineral_sets.py cobalt nickel
"""
import datetime as dt
import json
import os
import sys
import tempfile

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_instagram_posts as base  # noqa: E402  (palette, chrome, renderer)

ROOT = base.ROOT
OUT = f'{ROOT}/social/instagram/minerals'
PHOTOS = f'{ROOT}/brand/headers'
BG, INK, MUTED, SOFT, LINE = base.BG, base.INK, base.MUTED, base.SOFT, base.LINE

EXTRA_CSS = f'''
.photo{{position:absolute;inset:0;overflow:hidden;background:{BG}}}
.photo img{{display:block;width:100%;height:100%;object-fit:cover;filter:grayscale(1) contrast(1.1) brightness(1.04)}}
.duo{{position:absolute;inset:0;background:var(--accent);mix-blend-mode:multiply}}
.lift{{position:absolute;inset:0;background:{BG};mix-blend-mode:screen}}
.dark{{position:absolute;inset:0;background:{BG}}}
.scrim{{position:absolute;inset:0;background:
  linear-gradient(180deg,rgba(13,17,23,.82) 0%,rgba(13,17,23,.38) 22%,rgba(13,17,23,.18) 45%,rgba(13,17,23,.62) 66%,rgba(13,17,23,.94) 84%,{BG} 100%)}}
.body.bottom{{justify-content:flex-end}}
.hook{{font-size:34px;line-height:1.38;color:{SOFT};margin-top:26px;max-width:860px;text-shadow:0 2px 18px rgba(13,17,23,.6)}}
h1.photo-h{{text-shadow:0 2px 24px rgba(13,17,23,.65)}}
.hero.photo-n{{text-shadow:0 4px 30px rgba(13,17,23,.55)}}
.urlpill{{display:inline-flex;align-items:center;gap:16px;background:rgba(13,17,23,.72);border:1.5px solid var(--accent);color:{INK};
  font-weight:800;font-size:31px;padding:20px 34px;border-radius:99px;margin-top:34px;align-self:flex-start;letter-spacing:-.01em;
  backdrop-filter:blur(6px)}}
.urlpill b{{color:var(--accent)}}
.urlpill i{{display:block;width:12px;height:12px;border-radius:50%;background:var(--accent)}}
.symtag{{position:absolute;right:84px;top:182px;font-family:Georgia,"Times New Roman",serif;font-weight:700;font-size:150px;line-height:1;
  color:var(--accent);opacity:.9;text-shadow:0 4px 30px rgba(13,17,23,.6)}}
.credit{{position:absolute;left:84px;bottom:158px;font-family:"SF Mono",ui-monospace,Menlo,monospace;font-size:15px;color:#78868f;letter-spacing:.02em}}
'''

# object-position for the portrait crop of each landscape header photo
FOCUS = {'cobalt': '62% 50%', 'graphite': '50% 60%', 'nickel': '50% 55%'}

# Header-photo credits as recorded on the dashboards (sources "Notes"). None = no
# credit recorded on the site — confirm the licence before publishing that set.
CREDITS = {
    'cobalt': 'Photo: artisanal cobalt miners, DRC — IIED via Wikimedia Commons, CC BY 2.5',
    'nickel': 'Photo: nickel-ore mining, North Kolaka, Sulawesi — Marwan Mohamad via Wikimedia Commons, CC BY-SA 4.0',
}

# Per-mineral copy. hook = cover lede; a/b = (number, label, source); why = closing card.
SETS = {
    'graphite': dict(
        hook="The biggest material in an EV battery isn't lithium.",
        a=('82%', 'of the world’s natural graphite was mined in China in 2025.', 'USGS MCS 2026'),
        b=('~50 kg', 'of graphite in every electric car: the largest material by weight in a lithium-ion battery.', 'USGS · IEA'),
        why='China refines ~90% of battery-grade graphite and ~95% of the spherical graphite used in anodes. The US imports 100% of '
            'the natural graphite it uses. Reserves are ample at ~310 Mt; the chokepoint is processing, not geology.',
        tags='#graphite #batteries #evbattery #anode #criticalminerals #supplychain #china #energytransition #mining #mineralwatch'),
    'lithium': dict(
        hook='A price that went from $11,700 to $63,700 to $9,000 in four years.',
        a=('88%', 'of the world’s lithium goes into batteries.', 'USGS MCS 2026'),
        b=('$63,700', '/t: the 2022 average price of battery-grade lithium carbonate. By 2025 it averaged $9,000.', 'USGS / Benchmark'),
        why='China converts ~70% of battery-grade lithium chemicals and makes more than 98% of LFP cells. A single mine, CATL’s '
            'Jianxiawo, swung the 2025–26 market when its permit lapsed in August 2025 and was renewed in June 2026.',
        tags='#lithium #batteries #evbattery #criticalminerals #commodities #energytransition #mining #supplychain #mineralwatch'),
    'cobalt': dict(
        hook='Nearly all cobalt is a by-product. Most of it comes from one country.',
        a=('73%', 'of the world’s cobalt was mined in the DR Congo in 2025.', 'USGS MCS 2026'),
        b=('~79%', 'of the world’s refined cobalt came from China in 2025.', 'Cobalt Institute'),
        why='Since October 2025 the DRC caps exports at 96,600 t a year, about half of 2024 volumes. Some 150,000–250,000 artisanal '
            'miners dig cobalt by hand. Cobalt-free LFP batteries already power more than half of new EVs.',
        tags='#cobalt #drc #criticalminerals #batteries #evbattery #supplychain #mining #indonesia #energytransition #mineralwatch'),
    'nickel': dict(
        hook='Stainless steel, batteries, and a market that broke in 2022.',
        a=('66%', 'of the world’s nickel was mined in Indonesia in 2025.', 'USGS MCS 2026'),
        b=('$100,000', '/t: where nickel traded on 8 March 2022, before the LME cancelled the market.', 'LME'),
        why='Indonesia and China refined ~76% of the world’s nickel in 2025. Class-1 metal is only about a quarter of supply. Western '
            'mines are closing: BHP’s Nickel West is suspended and Koniambo’s furnaces have been cold since August 2024.',
        tags='#nickel #lme #indonesia #stainlesssteel #batteries #criticalminerals #commodities #supplychain #mining #mineralwatch'),
    'rare-earths': dict(
        hook='17 elements, and one supplier for the magnets in every motor and missile.',
        a=('94%', 'of sintered NdFeB magnets are made in China.', 'IEA'),
        b=('7 of 17', 'rare earth elements have been under Chinese export controls since April 2025.', 'MOFCOM · USGS'),
        why='China handles ~91% of rare earth refining and separation. US import reliance is 67% overall and 100% for heavy rare '
            'earths. Global reserves exceed 75 Mt; the constraint is separation capacity, not geology.',
        tags='#rareearths #neodymium #magnets #exportcontrols #criticalminerals #china #supplychain #defence #energytransition #mineralwatch'),
    'copper': dict(
        hook='The metal of electrification is running short of smelter feed.',
        a=('$0/t', 'the 2026 benchmark treatment charge for copper concentrate, the lowest on record.', 'benchmark settlement · USGS'),
        b=('~30%', 'of copper demand in 2035 is not covered by existing or announced mines.', 'IEA'),
        why='China refines ~48% of the world’s copper and holds ~50% of smelting capacity. LME copper hit a record $14,527.50/t in '
            'January 2026 as Cobre Panama, Grasberg and El Teniente disruptions tightened the mine side.',
        tags='#copper #commodities #smelting #criticalminerals #chile #china #supplychain #energytransition #mining #mineralwatch'),
    'manganese': dict(
        hook='Ninety percent goes into steel, and nothing else does the job.',
        a=('95%', 'of battery-grade manganese sulphate is refined in China.', 'IEA'),
        b=('4%', 'of the world’s manganese ore is mined in China. South Africa mines ~38%.', 'USGS MCS 2026'),
        why='USGS lists no satisfactory substitute for manganese in steelmaking. Gabon bans raw ore exports from 2029. Battery '
            'demand for manganese is projected to grow more than eightfold this decade.',
        tags='#manganese #steel #batteries #southafrica #gabon #criticalminerals #china #supplychain #mining #mineralwatch'),
    'uranium': dict(
        hook='The nuclear revival runs through Russian centrifuges.',
        a=('43%', 'of the world’s uranium enrichment capacity is Russian (Rosatom).', 'WNA 2025'),
        b=('1 Jan 2028', 'when US waivers on the ban on Russian enriched uranium expire.', 'US law · EIA'),
        why='Kazakhstan mined ~41% of the world’s uranium in 2025. 79 reactors are under construction, 37 of them in China. Spot '
            'uranium is near $90/lb, with the long-term price at a record $95.50/lb.',
        tags='#uranium #nuclear #nuclearenergy #enrichment #kazakhstan #russia #criticalminerals #energysecurity #supplychain #mineralwatch'),
    'antimony': dict(
        hook='A small market with one of the thinnest reserve cushions of any strategic mineral.',
        a=('>85%', 'of the world’s antimony is mined in China, Russia and Tajikistan.', 'USGS MCS 2026'),
        b=('$60,000', '/t: the spring-2025 price peak after China began licensing exports, up from ~$12,000–14,000.', 'price-agency assessments'),
        why='Reserves of ~2 Mt are under two decades of supply at current mining rates. Antimony goes into flame retardants, lead-acid '
            'batteries, solar glass, ammunition primers and night-vision detectors.',
        tags='#antimony #criticalminerals #exportcontrols #china #defence #supplychain #mining #commodities #mineralwatch'),
}


def photo_frame(body, slug, *, counter=None, pill=None, src='', dim=0.0, bottom=False, sym=False, credit=None):
    mm = base.MINERALS[slug]
    img = f'file://{PHOTOS}/{slug}.jpg'
    pos = FOCUS.get(slug, '50% 50%')
    dark = f'<div class="dark" style="opacity:{dim}"></div>' if dim else ''
    symtag = f'<div class="symtag">{mm["sym"]}</div>' if sym else ''
    cred = f'<div class="credit">{base.esc(credit)}</div>' if credit else ''
    return (f'<!doctype html><meta charset="utf-8"><style>{base.CSS}{EXTRA_CSS}</style>'
            f'<div class="frame" style="--accent:{mm["accent"]}">'
            f'<div class="photo"><img src="{img}" style="object-position:{pos}"></div>'
            f'<div class="duo"></div><div class="lift"></div>{dark}<div class="scrim"></div>{symtag}'
            f'{base.top(pill, counter)}<div class="body{" bottom" if bottom else ""}">{body}</div>{cred}'
            f'{base.foot(slug, src)}</div>')


def build(slug):
    mm, s = base.MINERALS[slug], SETS[slug]
    name, n = mm['name'], 4
    q = mm['q'][0].upper() + mm['q'][1:]
    credit = CREDITS.get(slug)
    slides = []
    # 1 · cover
    body = (base.kicker(f'{name} · mineral.watch/{slug}') +
            f'<h1 class="photo-h">{base.esc(q)}</h1>'
            f'<p class="hook">{base.esc(s["hook"])}</p><div class="rule"></div>')
    slides.append(dict(html=photo_frame(body, slug, counter=base.counter(1, n), src='swipe ›', dim=.12, bottom=True, sym=True, credit=credit),
                       alt=f'{name}: {q} Duotone photo of a {name.lower()} mining site.',
                       caption=f'{name}: {q.lower()} {s["hook"]}\n\nFull dashboard: mineral.watch/{slug} (link in bio).'))
    # 2 · stat A
    for k, (num, label, src) in (('a', s['a']), ('b', s['b'])):
        i = 2 if k == 'a' else 3
        hero_cls = 'hero photo-n' + ('' if len(num) <= 4 else ' m' if len(num) <= 7 else ' s')
        body = (base.kicker(f'{name} · {"the mine side" if k == "a" else "the chokepoint"}') +
                f'<div class="spacer"></div><div class="{hero_cls}">{num}</div>'
                f'<div class="herolabel">{base.esc(label)}</div>')
        slides.append(dict(html=photo_frame(body, slug, counter=base.counter(i, n), src=src, dim=.34, bottom=True),
                           alt=f'{name}: {num} {label}',
                           caption=f'{num} {label}\n\nSource: {src}. More at mineral.watch/{slug} (link in bio).'))
    # 4 · why it matters + URL
    body = (base.kicker(f'{name} · why it matters') +
            f'<h1 class="md photo-h">Small market. Outsized leverage.</h1>'
            f'<p class="hook" style="font-size:31px">{base.esc(s["why"])}</p>'
            f'<div class="urlpill"><i></i><span>mineral.watch/<b>{slug}</b></span></div>')
    slides.append(dict(html=photo_frame(body, slug, counter=base.counter(n, n), src='map · charts · timeline · sources', dim=.4, bottom=True),
                       alt=f'{name}, why it matters: {s["why"][:120]}',
                       caption=f'{name}: why it matters. {s["why"]}\n\nMap, charts and timeline: mineral.watch/{slug} (link in bio).'))

    a, b = s['a'], s['b']
    carousel = (f'{name}: {q.lower()}\n\n{s["hook"]}\n\n'
                f'{a[0]} {a[1]} ({a[2]})\n{b[0]} {b[1]} ({b[2]})\n\n'
                f'{s["why"]}\n\n'
                f'Interactive map of mines, smelters and refineries, production and price charts, and the full timeline: '
                f'mineral.watch/{slug} (link in bio).')
    if credit:
        carousel += f'\n\n{credit}'
    return dict(slug=slug, title=f'{name}: {q.lower()}', slides=slides, caption=carousel, first_comment=s['tags'],
                photo_credit=credit or 'NOT RECORDED on the site — confirm the header photo licence before publishing this set',
                link=f'https://mineral.watch/{slug}')


def contact_sheet(sets, path):
    tw, th, g = 216, 270, 10
    rows, cols = len(sets), 4
    sheet = Image.new('RGB', (g + cols * (tw + g) + 200, g + rows * (th + g)), BG)
    d = ImageDraw.Draw(sheet)
    for r, st in enumerate(sets):
        y = g + r * (th + g)
        d.text((g, y + 6), st['title'], fill=MUTED)
        for c in range(cols):
            p = f'{OUT}/{st["slug"]}/slide-{c + 1:02d}.jpg'
            if not os.path.exists(p):
                continue
            im = Image.open(p).resize((tw, th), Image.LANCZOS)
            sheet.paste(im, (200 + g + c * (tw + g), y))
    sheet.save(path, optimize=True)


def main():
    only = [a for a in sys.argv[1:] if a in SETS]
    os.makedirs(OUT, exist_ok=True)
    sets = [build(slug) for slug in SETS]
    with tempfile.TemporaryDirectory() as tmp:
        for st in sets:
            os.makedirs(f'{OUT}/{st["slug"]}', exist_ok=True)
            for j, sl in enumerate(st['slides'], start=1):
                rel = f'{st["slug"]}/slide-{j:02d}.jpg'   # JPEG: photo backgrounds, ~5x smaller than PNG
                sl['file'] = rel
                if not only or st['slug'] in only:
                    base.render(sl.pop('html'), f'{tmp}/slide.png', tmp)
                    Image.open(f'{tmp}/slide.png').convert('RGB').save(f'{OUT}/{rel}', quality=90, optimize=True, subsampling=0)
                    print(f'  rendered {rel}')
                else:
                    sl.pop('html', None)

    manifest = dict(account='https://instagram.com/mineralwatch', format='1080x1350 PNG (4:5), duotone photo backgrounds',
                    generated=dt.date.today().isoformat(),
                    note='Each set works as one 4-slide carousel (use `caption`) or as four standalone posts (use each slide’s `caption`).',
                    sets=[dict(slug=s['slug'], title=s['title'], link=s['link'], photo_credit=s['photo_credit'], caption=s['caption'],
                               first_comment=s['first_comment'],
                               media=[dict(file=sl['file'], alt=sl['alt'], caption=sl['caption']) for sl in s['slides']]) for s in sets])
    with open(f'{OUT}/posts.json', 'w') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    with open(f'{OUT}/captions.md', 'w') as f:
        f.write('# mineral.watch · per-mineral photo sets (duotone)\n\n')
        f.write('Nine sets of four 1080×1350 slides. Post each set as one carousel with the caption below, or use the slides one at a '
                'time with the standalone captions. Hashtags go in the first comment. Background photos are the dashboard header '
                'photos from brand/headers/ with a duotone treatment in the mineral’s accent colour.\n\n')
        f.write('## Photo credits\n\n')
        for s in sets:
            f.write(f'- **{base.MINERALS[s["slug"]]["name"]}**: {s["photo_credit"]}\n')
        f.write('\n')
        for s in sets:
            f.write(f'## {s["title"]}\n\n- **Link:** {s["link"]}\n- **Files:** ' + ', '.join(f'`{sl["file"]}`' for sl in s['slides']) + '\n\n')
            f.write('**Carousel caption**\n\n```\n' + s['caption'] + '\n```\n\n')
            f.write('**First comment**\n\n```\n' + s['first_comment'] + '\n```\n\n')
            f.write('**Standalone captions and alt text**\n\n')
            for j, sl in enumerate(s['slides'], start=1):
                f.write(f'{j}. `{sl["file"]}`\n   - caption: {sl["caption"].replace(chr(10), " ")}\n   - alt: {sl["alt"]}\n')
            f.write('\n')

    contact_sheet(sets, f'{OUT}/_contact-sheet.png')
    print(f'wrote {len(sets)} sets / {4 * len(sets)} images + posts.json, captions.md to {OUT}')


if __name__ == '__main__':
    main()
