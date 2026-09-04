#!/usr/bin/env python3
"""Build the mineral.watch Instagram launch set: 15 posts under social/instagram/.

Every slide is a 1080x1350 (4:5) PNG rendered by headless Chrome at 2x from
inline HTML/SVG that reuses the site's palette (bg #0d1117, ink #e6edf3, lime
#c8ff6b, the per-mineral dashboard accents) and the network-diamond mark, then
downsampled so the type stays crisp. Every slide carries "visit mineral.watch".
Figures are the ones published in llms.txt (USGS MCS 2026, IEA, BGS, WNA,
Cobalt Institute, INSG, EIA); the caption of each post names its sources.

Outputs (social/instagram/):
  NN-slug/post.png            single-image posts
  NN-slug/slide-01.png ...    carousels
  captions.md                 captions, first-comment hashtags, alt text
  posts.json                  machine-readable manifest (for schedulers/automation)
  schedule.csv                one row per post: date, media files, caption, first comment
  _contact-sheet.png          all 15 covers at a glance

Re-run after a copy or palette change:   python3 tools/gen_instagram_posts.py
Render a subset (by post number):        python3 tools/gen_instagram_posts.py 04 07
"""
import csv
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = f'{ROOT}/social/instagram'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
W, H = 1080, 1350

# ---------------------------------------------------------------- palette (index.html :root)
BG, BG2, CARD, INK, MUTED, LINE = '#0d1117', '#151b23', '#1a222c', '#e6edf3', '#8b98a5', '#2b3644'
LIME, TEAL = '#c8ff6b', '#4cc9f0'
SOFT = '#a9b6c4'          # secondary ink used on the OG card
GRAY_MARK = '#66768a'     # de-emphasis mark colour (context series), >= 3:1 on BG

# per-mineral dashboard accents, in homepage card order
MINERALS = {
    'graphite':    dict(sym='C',   name='Graphite',    accent='#fbbf24', q='who controls the anode?'),
    'lithium':     dict(sym='Li',  name='Lithium',     accent='#fb7185', q="who holds the world's charge?"),
    'cobalt':      dict(sym='Co',  name='Cobalt',      accent='#5b8aff', q='whose hands power the battery age?'),
    'nickel':      dict(sym='Ni',  name='Nickel',      accent='#a3e635', q='who cornered the metal of the stainless age?'),
    'rare-earths': dict(sym='REE', name='Rare earths', accent='#a78bfa', q='who controls the magnets?'),
    'copper':      dict(sym='Cu',  name='Copper',      accent='#e8926a', q='who keeps the world wired?'),
    'manganese':   dict(sym='Mn',  name='Manganese',   accent='#e879f9', q="who hardens the world's steel?"),
    'uranium':     dict(sym='U',   name='Uranium',     accent='#22d3ee', q='who fuels the nuclear revival?'),
    'antimony':    dict(sym='Sb',  name='Antimony',    accent='#34d399', q="who's playing with fire?"),
}

# Sankey plume ribbons: (colour, top producer's share of 2024 world mine production)
# — identical to brand/og-image.png so the launch post matches the site's social card.
PLUME = [('#c8ff6b', 74.9), ('#84a5f0', 74.6), ('#e6b95e', 73.9), ('#ff7d9c', 62.2),
         ('#34d399', 61.0), ('#f0abfc', 42.8), ('#4cc9f0', 37.3), ('#c08ad6', 36.9), ('#e08256', 24.0)]

MARK = '''<svg viewBox="-2 4 68 58" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
<g stroke="#e6edf3" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" fill="none">
<path d="M20 12 H44"/><path d="M20 12 L6 26"/><path d="M44 12 L58 26"/><path d="M6 26 H58"/>
<path d="M6 26 L32 56"/><path d="M58 26 L32 56"/><path d="M20 12 L32 26"/><path d="M44 12 L32 26"/><path d="M32 26 V56"/>
</g><g fill="#0d1117" stroke="#e6edf3" stroke-width="3">
<circle cx="20" cy="12" r="4.4"/><circle cx="44" cy="12" r="4.4"/><circle cx="6" cy="26" r="4.4"/>
<circle cx="58" cy="26" r="4.4"/><circle cx="32" cy="56" r="4.4"/>
</g><circle cx="32" cy="26" r="6" style="fill:var(--accent)"/></svg>'''

MONO = '"SF Mono",ui-monospace,Menlo,monospace'
SANS = '-apple-system,BlinkMacSystemFont,"SF Pro Display","Helvetica Neue",Arial,sans-serif'

CSS = f'''
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;background:{BG}}}
body{{color:{INK};font-family:{SANS};-webkit-font-smoothing:antialiased;font-kerning:normal;font-feature-settings:"kern" 1,"liga" 1}}
.frame{{position:relative;width:{W}px;height:{H}px;overflow:hidden;--accent:{LIME};
  background:radial-gradient(120% 80% at 50% 0%,{BG2} 0%,{BG} 55%,#090d12 100%)}}
.glow{{position:absolute;inset:0;background:radial-gradient(55% 34% at 84% 18%,color-mix(in srgb,var(--accent) 17%,transparent),transparent 72%)}}
.art{{position:absolute;inset:0;opacity:.85;filter:blur(.4px)}}
.art svg{{display:block;width:{W}px;height:{H}px}}
.scrim{{position:absolute;inset:0;background:
  linear-gradient(90deg,{BG} 0%,{BG} 5%,rgba(13,17,23,.9) 13%,rgba(13,17,23,.3) 30%,rgba(13,17,23,0) 46%),
  linear-gradient(180deg,rgba(13,17,23,0) 0%,rgba(13,17,23,0) 74%,rgba(13,17,23,.92) 87%,{BG} 91%)}}
.top{{position:absolute;left:84px;right:84px;top:74px;display:flex;align-items:center;justify-content:space-between}}
.lock{{display:flex;align-items:center;gap:14px;font-size:30px;font-weight:800;letter-spacing:-.02em}}
.lock b{{color:var(--accent)}}
.lock svg{{width:44px;height:44px}}
.pill{{font-family:{MONO};font-size:19px;color:{MUTED};border:1.5px solid {LINE};border-radius:99px;padding:9px 18px;letter-spacing:.06em;white-space:nowrap}}
.pill.acc{{color:var(--accent);border-color:color-mix(in srgb,var(--accent) 45%,transparent)}}
.body{{position:absolute;left:84px;right:84px;top:196px;bottom:186px;display:flex;flex-direction:column}}
.kicker{{display:flex;align-items:center;gap:14px;color:var(--accent);text-transform:uppercase;letter-spacing:.2em;font-size:21px;font-weight:700;margin-bottom:26px}}
.kicker i{{display:block;width:34px;height:2px;background:var(--accent);flex:none}}
h1{{font-size:76px;line-height:1.03;font-weight:800;letter-spacing:-.035em;color:{INK}}}
h1.xl{{font-size:104px;line-height:1;white-space:nowrap}}
h1.md{{font-size:64px}}
h1 b{{color:var(--accent);font-weight:800}}
.rule{{margin-top:30px;width:84px;height:4px;background:var(--accent);border-radius:2px;flex:none}}
p.lede{{font-size:32px;line-height:1.4;color:{SOFT};margin-top:28px;letter-spacing:-.005em}}
p.lede b{{color:{INK};font-weight:700}}
p.sub{{font-size:26px;line-height:1.45;color:{MUTED};margin-top:24px}}
.hero{{font-size:226px;line-height:.92;font-weight:800;letter-spacing:-.05em;color:var(--accent);white-space:nowrap}}
.hero.m{{font-size:176px}}
.hero.s{{font-size:150px}}
.hero small{{font-size:.36em;letter-spacing:-.02em;color:{SOFT};font-weight:700;margin-left:.06em}}
.herolabel{{font-size:35px;line-height:1.36;color:{INK};margin-top:22px;letter-spacing:-.01em}}
.herolabel span{{color:{MUTED}}}
.kpis{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:auto}}
.kpis.two{{grid-template-columns:1fr 1fr}}
.kpi{{background:rgba(26,34,44,.8);border:1px solid {LINE};border-radius:18px;padding:26px 26px 24px}}
.kpi .v{{font-size:56px;font-weight:800;letter-spacing:-.03em;line-height:1;white-space:nowrap}}
.kpi .l{{font-size:21px;line-height:1.35;color:{MUTED};margin-top:12px}}
.foot{{position:absolute;left:84px;right:84px;bottom:74px;border-top:1px solid {LINE};padding-top:26px;display:flex;align-items:center;justify-content:space-between;gap:30px}}
.visit{{font-size:30px;font-weight:800;letter-spacing:-.02em;color:{INK};white-space:nowrap}}
.visit b{{color:var(--accent)}}
.visit .path{{color:{MUTED};font-weight:600}}
.src{{font-family:{MONO};font-size:17px;color:#78868f;letter-spacing:.02em;text-align:right;line-height:1.45;max-width:560px}}
.sym{{font-family:Georgia,"Times New Roman",serif;font-weight:700;color:var(--accent)}}
.biglock{{display:flex;align-items:center;gap:22px;margin-top:6px}}
.biglock svg{{width:98px;height:98px;flex:none}}
.symrow{{display:flex;align-items:center;gap:34px;margin-bottom:34px}}
.symbig{{font-size:136px;line-height:1;width:230px;height:190px;display:flex;align-items:center;justify-content:center;
  background:rgba(26,34,44,.8);border:1px solid {LINE};border-radius:26px;flex:none}}
.mname{{font-size:50px;font-weight:800;letter-spacing:-.03em;line-height:1.05}}
.mq{{font-size:27px;color:{MUTED};margin-top:10px;line-height:1.3}}
.chips{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:auto}}
.chip{{display:flex;align-items:center;gap:18px;background:rgba(26,34,44,.8);border:1px solid {LINE};border-radius:18px;padding:20px 22px}}
.chip .sym{{font-size:46px;width:96px;text-align:center;flex:none}}
.chip .n{{font-size:24px;font-weight:700;line-height:1.15}}
.list{{margin-top:auto;display:flex;flex-direction:column;gap:12px}}
.row{{display:flex;align-items:center;gap:20px;background:rgba(26,34,44,.8);border:1px solid {LINE};border-radius:16px;padding:13px 22px}}
.row .sym{{font-size:34px;width:74px;text-align:center;flex:none}}
.row .n{{font-size:27px;font-weight:700;flex:1}}
.row .u{{font-family:{MONO};font-size:19px;color:{MUTED}}}
.legend{{display:flex;gap:34px;margin:26px 0 22px;font-size:23px;color:{SOFT};align-items:center}}
.legend i{{display:inline-block;width:16px;height:16px;border-radius:50%;margin-right:12px;vertical-align:-1px}}
.legend b{{color:{INK};font-weight:700}}
.wm{{position:absolute;right:-30px;top:290px;font-family:Georgia,"Times New Roman",serif;font-weight:700;font-size:680px;line-height:1;
  color:var(--accent);opacity:.065;letter-spacing:-.04em;pointer-events:none}}
.plume-inline{{margin-top:auto;height:330px;opacity:.9;filter:blur(.4px)}}
.plume-inline svg{{display:block;width:912px;height:330px}}
.chart{{margin-top:auto}}
.note{{font-size:21px;color:{MUTED};line-height:1.4;margin-top:22px}}
.grid17{{display:grid;grid-template-columns:repeat(6,1fr);gap:14px;margin-top:auto}}
.el{{height:132px;border-radius:16px;background:rgba(26,34,44,.8);border:1px solid {LINE};padding:14px 16px;position:relative}}
.el .s{{font-family:Georgia,"Times New Roman",serif;font-weight:700;font-size:50px;line-height:1;margin-top:14px}}
.el .z{{position:absolute;top:12px;right:14px;font-family:{MONO};font-size:15px;color:{MUTED}}}
.el .nm{{font-size:15px;color:{MUTED};margin-top:8px;letter-spacing:.02em}}
.el.on{{background:var(--accent);border-color:var(--accent)}}
.el.on .s,.el.on .z,.el.on .nm{{color:{BG}}}
.twoup{{display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:auto}}
.twoup .hero{{font-size:190px}}
.twoup .herolabel{{font-size:28px;margin-top:14px}}
.twoup .box{{border-left:4px solid var(--accent);padding-left:28px}}
.twoup .box.g{{border-left-color:{GRAY_MARK}}}
.twoup .box.g .hero{{color:{INK}}}
.steps{{display:flex;flex-direction:column;gap:16px;margin-top:auto}}
.step{{display:flex;gap:22px;align-items:flex-start;background:rgba(26,34,44,.8);border:1px solid {LINE};border-radius:16px;padding:20px 24px}}
.step i{{display:block;width:12px;height:12px;border-radius:50%;background:var(--accent);margin-top:14px;flex:none}}
.step .t{{font-size:26px;font-weight:700;line-height:1.3}}
.step .d{{font-size:22px;color:{MUTED};line-height:1.35;margin-top:4px}}
.btn{{display:inline-block;background:var(--accent);color:{BG};font-weight:800;font-size:30px;padding:24px 42px;border-radius:99px;letter-spacing:-.01em;margin-top:auto;align-self:flex-start}}
.spacer{{flex:1}}
'''


# ---------------------------------------------------------------- small helpers
def esc(s):
    return s.replace('&', '&amp;')


def bar_path(x, y, w, h, r, fill, opacity=1.0):
    """Horizontal bar: square at the baseline (left), 4-6px rounded data end (right)."""
    r = min(r, w / 2, h / 2)
    return (f'<path d="M{x:.1f},{y:.1f} H{x + w - r:.1f} A{r},{r} 0 0 1 {x + w:.1f},{y + r:.1f} '
            f'V{y + h - r:.1f} A{r},{r} 0 0 1 {x + w - r:.1f},{y + h:.1f} H{x:.1f} Z" fill="{fill}" opacity="{opacity}"/>')


def col_path(x, y, w, h, r, fill, opacity=1.0):
    """Vertical column: square at the baseline (bottom), rounded cap (top)."""
    r = min(r, w / 2, h / 2)
    return (f'<path d="M{x:.1f},{y + h:.1f} V{y + r:.1f} A{r},{r} 0 0 1 {x + r:.1f},{y:.1f} '
            f'H{x + w - r:.1f} A{r},{r} 0 0 1 {x + w:.1f},{y + r:.1f} V{y + h:.1f} Z" fill="{fill}" opacity="{opacity}"/>')


def svg_open(w, h):
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" font-family=\'{SANS}\'>'


def plume(x0, x1, origin, spread, gap_o=1.6, gap_s=8.0):
    total = sum(v for _, v in PLUME)
    so = ((origin[1] - origin[0]) - gap_o * (len(PLUME) - 1)) / total
    sd = ((spread[1] - spread[0]) - gap_s * (len(PLUME) - 1)) / total
    c1, c2 = x0 + (x1 - x0) * .44, x0 + (x1 - x0) * .58
    yo, yd, out = origin[0], spread[0], []
    for colour, share in PLUME:
        ho, hd = share * so, share * sd
        out.append(f'<path d="M{x0},{yo:.1f} C{c1:.0f},{yo:.1f} {c2:.0f},{yd:.1f} {x1},{yd:.1f} '
                   f'L{x1},{yd + hd:.1f} C{c2:.0f},{yd + hd:.1f} {c1:.0f},{yo + ho:.1f} {x0},{yo + ho:.1f} Z" fill="{colour}"/>')
        yo += ho + gap_o
        yd += hd + gap_s
    return ''.join(out)


# ---------------------------------------------------------------- chart builders (inline SVG)
def hbars(rows, accent, width=912, label_w=310, bar_h=34, gap=26, vmax=100):
    """One series -> one hue. rows: (label, value, display). Values labelled at the tip."""
    n = len(rows)
    h = n * (bar_h + gap) - gap
    x0, pw = label_w, width - label_w - 104
    out = [svg_open(width, h + 44)]
    for t in (0, 25, 50, 75, 100):
        x = x0 + pw * t / vmax
        out.append(f'<line x1="{x:.1f}" y1="-6" x2="{x:.1f}" y2="{h + 6}" stroke="{LINE}" stroke-width="1"/>')
        out.append(f'<text x="{x:.1f}" y="{h + 36}" fill="{MUTED}" font-size="17" text-anchor="middle" font-family=\'{MONO}\'>{t}%</text>')
    for i, (label, val, disp) in enumerate(rows):
        y = i * (bar_h + gap)
        w = pw * val / vmax
        out.append(f'<text x="0" y="{y + bar_h * .74:.1f}" fill="{INK}" font-size="28" font-weight="600">{esc(label)}</text>')
        out.append(bar_path(x0, y, w, bar_h, 6, accent))
        out.append(f'<text x="{x0 + w + 16:.1f}" y="{y + bar_h * .74:.1f}" fill="{INK}" font-size="28" font-weight="700">{disp}</text>')
    out.append('</svg>')
    return ''.join(out)


def dumbbell(rows, accent, gray, width=912, label_w=250, row_h=112, vmax=100):
    """Before -> after per item (1 hue + gray). rows: (label, a, b, a_disp, b_disp); a=gray, b=accent."""
    n = len(rows)
    h = n * row_h
    x0, pw = label_w, width - label_w - 40
    out = [svg_open(width, h + 40)]
    for t in (0, 25, 50, 75, 100):
        x = x0 + pw * t / vmax
        out.append(f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{h}" stroke="{LINE}" stroke-width="1"/>')
        out.append(f'<text x="{x:.1f}" y="{h + 32}" fill="{MUTED}" font-size="17" text-anchor="middle" font-family=\'{MONO}\'>{t}%</text>')
    for i, (label, a, b, ad, bd) in enumerate(rows):
        cy = i * row_h + row_h / 2
        xa, xb = x0 + pw * a / vmax, x0 + pw * b / vmax
        out.append(f'<text x="0" y="{cy + 10:.1f}" fill="{INK}" font-size="28" font-weight="600">{esc(label)}</text>')
        out.append(f'<line x1="{xa:.1f}" y1="{cy:.1f}" x2="{xb:.1f}" y2="{cy:.1f}" stroke="{gray}" stroke-width="3" stroke-linecap="round"/>')
        # 2px surface ring on each marker
        out.append(f'<circle cx="{xa:.1f}" cy="{cy:.1f}" r="15" fill="{BG}"/><circle cx="{xa:.1f}" cy="{cy:.1f}" r="13" fill="{gray}"/>')
        out.append(f'<circle cx="{xb:.1f}" cy="{cy:.1f}" r="15" fill="{BG}"/><circle cx="{xb:.1f}" cy="{cy:.1f}" r="13" fill="{accent}"/>')
        out.append(f'<text x="{xa:.1f}" y="{cy + 46:.1f}" fill="{MUTED}" font-size="22" font-weight="600" text-anchor="middle">{ad}</text>')
        out.append(f'<text x="{xb:.1f}" y="{cy - 28:.1f}" fill="{INK}" font-size="24" font-weight="700" text-anchor="middle">{bd}</text>')
    out.append('</svg>')
    return ''.join(out)


def sharebar(segs, width=912, h=42, gap=3):
    """Part-to-whole as one stacked horizontal bar with 2-3px surface gaps. segs: (label, value, colour, display)."""
    total = sum(v for _, v, _, _ in segs)
    out = [svg_open(width, h)]
    x = 0.0
    for i, (label, val, colour, disp) in enumerate(segs):
        w = (width - gap * (len(segs) - 1)) * val / total
        r = 8
        if i == 0:
            d = f'M{x + r},0 H{x + w} V{h} H{x + r} A{r},{r} 0 0 1 {x},{h - r} V{r} A{r},{r} 0 0 1 {x + r},0 Z'
        elif i == len(segs) - 1:
            d = f'M{x},0 H{x + w - r} A{r},{r} 0 0 1 {x + w},{r} V{h - r} A{r},{r} 0 0 1 {x + w - r},{h} H{x} Z'
        else:
            d = f'M{x},0 H{x + w} V{h} H{x} Z'
        out.append(f'<path d="{d}" fill="{colour}"/>')
        x += w + gap
    out.append('</svg>')
    # legend as its own row (segments can be too narrow to carry their own label)
    legend = ''.join(f'<span><i style="background:{colour}"></i><b>{disp}</b> {esc(label)}</span>' for label, _, colour, disp in segs)
    return ''.join(out) + f'<div class="legend" style="margin:18px 0 0">{legend}</div>'


def columns(pts, accent, width=912, height=560, ymax=70000, ticks=(0, 20000, 40000, 60000)):
    """Annual columns, one hue; extremes direct-labelled; a floating range for the current spot."""
    left, bottom, top = 92, 54, 40
    pw, ph = width - left - 10, height - bottom - top
    n = len(pts)
    slot = pw / n
    cw = 58
    out = [svg_open(width, height)]

    def ypx(v):
        return top + ph - ph * v / ymax

    for t in ticks:
        y = ypx(t)
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width}" y2="{y:.1f}" stroke="{LINE}" stroke-width="1"/>')
        lab = '$0' if t == 0 else f'${t // 1000}k'
        out.append(f'<text x="{left - 14}" y="{y + 6:.1f}" fill="{MUTED}" font-size="17" text-anchor="end" font-family=\'{MONO}\'>{lab}</text>')
    for i, p in enumerate(pts):
        cx = left + slot * i + slot / 2
        x = cx - cw / 2
        if 'range' in p:
            lo, hi = p['range']
            out.append(f'<line x1="{cx:.1f}" y1="{ypx(0):.1f}" x2="{cx:.1f}" y2="{ypx(lo):.1f}" stroke="{GRAY_MARK}" stroke-width="2"/>')
            y0, y1 = ypx(hi), ypx(lo)
            out.append(f'<rect x="{x:.1f}" y="{y0:.1f}" width="{cw}" height="{y1 - y0:.1f}" rx="6" fill="{accent}" opacity=".78"/>')
            ly = y0 - 16
        else:
            v = p['value']
            out.append(col_path(x, ypx(v), cw, ypx(0) - ypx(v), 6, accent))
            ly = ypx(v) - 16
        if p.get('disp'):
            out.append(f'<text x="{cx:.1f}" y="{ly:.1f}" fill="{INK}" font-size="24" font-weight="700" text-anchor="middle">{p["disp"]}</text>')
        if p.get('note'):
            out.append(f'<text x="{cx:.1f}" y="{ly - 30:.1f}" fill="{MUTED}" font-size="18" text-anchor="middle">{esc(p["note"])}</text>')
        out.append(f'<text x="{cx:.1f}" y="{height - 14}" fill="{SOFT}" font-size="22" font-weight="600" text-anchor="middle" font-family=\'{MONO}\'>{p["label"]}</text>')
    out.append('</svg>')
    return ''.join(out)


def meter(pct, accent, width=912, h=34, label_left='', label_right=''):
    """A single ratio against a limit: fill in the accent, track a lighter step of the same hue."""
    out = [svg_open(width, h + 52)]
    out.append(f'<rect x="0" y="0" width="{width}" height="{h}" rx="8" fill="{accent}" opacity=".16"/>')
    out.append(bar_path(0, 0, width * pct / 100, h, 8, accent))
    out.append(f'<rect x="0" y="0" width="8" height="{h}" fill="{accent}"/>')
    out.append(f'<text x="0" y="{h + 38}" fill="{MUTED}" font-size="22" font-weight="600">{esc(label_left)}</text>')
    out.append(f'<text x="{width}" y="{h + 38}" fill="{MUTED}" font-size="22" font-weight="600" text-anchor="end">{esc(label_right)}</text>')
    out.append('</svg>')
    return ''.join(out)


# ---------------------------------------------------------------- frame
def top(pill=None, counter=None):
    right = ''
    if counter:
        right = f'<div class="pill">{counter}</div>'
    elif pill:
        right = f'<div class="pill acc">{esc(pill)}</div>'
    return f'<div class="top"><div class="lock">{MARK}<span>mineral<b>.watch</b></span></div>{right}</div>'


def foot(visit_path='', src=''):
    vp = f'<span class="path">/{visit_path}</span>' if visit_path else ''
    return f'<div class="foot"><div class="visit">visit <b>mineral.watch</b>{vp}</div><div class="src">{esc(src)}</div></div>'


def frame(body, accent, *, counter=None, pill=None, visit_path='', src='', extra='', glow=True, wm=None):
    g = '<div class="glow"></div>' if glow else ''
    if wm:  # faint giant element symbol as a watermark behind sparse hero slides
        extra += f'<div class="wm" style="font-size:{680 if len(wm) <= 2 else 430}px">{wm}</div>'
    return (f'<!doctype html><meta charset="utf-8"><style>{CSS}</style>'
            f'<div class="frame" style="--accent:{accent}">{g}{extra}{top(pill, counter)}'
            f'<div class="body">{body}</div>{foot(visit_path, src)}</div>')


def kicker(text):
    return f'<div class="kicker"><i></i>{esc(text)}</div>'


def kpi(v, label):
    return f'<div class="kpi"><div class="v">{v}</div><div class="l">{esc(label)}</div></div>'


def counter(i, n):
    return f'{i:02d} / {n:02d}'


# ---------------------------------------------------------------- posts
POSTS = []


def post(slug, title, ptype, slides, caption, tags, visit):
    POSTS.append(dict(slug=slug, title=title, type=ptype, slides=slides, caption=caption.strip(),
                      first_comment=' '.join(tags), visit=visit))


def m(slug):
    return MINERALS[slug]


# ---- 01 launch ---------------------------------------------------------------
def p01():
    art = (f'<div class="art"><svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">'
           f'{plume(30, 1110, (852, 924), (556, 1156))}</svg></div><div class="scrim"></div>')
    body = (kicker('Open data · strategic minerals & rare earths') +
            f'<div class="biglock">{MARK}<h1 class="xl">mineral<b>.watch</b></h1></div>'
            '<p class="lede" style="max-width:800px;font-size:36px">Who mines it, who refines it, and where the chokepoints are.</p>'
            '<div class="rule"></div>'
            '<p class="sub" style="max-width:640px">Nine minerals. Nine interactive dashboards. One supply-chain map. '
            'Independent, source-cited, free to read.</p>')
    html = frame(body, LIME, pill='Now on Instagram', src='USGS · BGS · UN Comtrade · IEA', extra=art, glow=False)
    post('launch', 'mineral.watch is now on Instagram', 'single',
         [(html, 'mineral.watch wordmark and tagline over a fan of nine coloured ribbons, one per tracked mineral.')],
         '''
mineral.watch is now on Instagram.

Who mines it, who refines it, and where the chokepoints are. We cross-reference open data from USGS, BGS, UN Comtrade and the IEA on the minerals powering batteries, magnets, chips and defence: graphite, lithium, cobalt, nickel, rare earths, copper, manganese, uranium and antimony.

Nine interactive dashboards, one supply-chain map, every figure cited and dated. Independent of any government, mining company or trade body.

Follow for one chart at a time. Visit mineral.watch (link in bio).
''',
         ['#criticalminerals', '#strategicminerals', '#rareearths', '#supplychain', '#opendata', '#dataviz',
          '#energytransition', '#mining', '#geopolitics', '#batteries', '#mineralwatch'],
         'mineral.watch')


# ---- 02 nine minerals carousel ------------------------------------------------
NINE = [
    ('graphite',    '82%',  "of the world's graphite was mined in China in 2025.",
     'China also refines ~90% of battery-grade graphite and ~95% of spherical graphite (IEA). US import reliance: 100%.',
     'USGS MCS 2026 · IEA'),
    ('lithium',     '88%',  'of lithium goes into batteries.',
     'China converts ~70% of battery-grade lithium chemicals and makes >98% of LFP cells. Mine output rose 31% in 2025 to ~290,000 t.',
     'USGS MCS 2026 · IEA'),
    ('cobalt',      '73%',  "of the world's cobalt was mined in the DR Congo in 2025.",
     'China refined ~79% of it. Since October 2025 the DRC caps exports at 96,600 t a year, roughly half of 2024 volumes.',
     'USGS MCS 2026 · Cobalt Institute · ARECOMS'),
    ('nickel',      '66%',  "of the world's nickel was mined in Indonesia in 2025.",
     'Indonesia and China refined ~76% of the total. Australia’s mine output fell 54% in a single year.',
     'USGS MCS 2026 · IEA'),
    ('rare-earths', '94%',  'of sintered NdFeB magnets are made in China.',
     'China also handles ~91% of refining and separation. Seven of the 17 rare earths have been under Chinese export controls since April 2025.',
     'USGS MCS 2026 · IEA'),
    ('copper',      '$0/t', 'is the 2026 benchmark treatment charge for copper concentrate.',
     'The lowest on record, down from $21.25/t in 2025. China produces ~48% of refined copper and holds ~50% of smelting capacity.',
     'USGS MCS 2026 · IEA · LME'),
    ('manganese',   '95%',  'of battery-grade manganese sulphate is refined in China.',
     'China mines only ~4% of the ore. Around 90% of manganese goes into steel, and USGS lists no satisfactory substitute.',
     'USGS MCS 2026 · IEA'),
    ('uranium',     '43%',  "of the world's enrichment capacity is Russian.",
     'US utilities still bought 26% of their enrichment from Russia in 2025. Waivers on the US ban run out on 1 January 2028.',
     'WNA 2025 · EIA'),
    ('antimony',    '>85%', 'of antimony is mined in China, Russia and Tajikistan.',
     'Reserves of ~2 Mt are under two decades of supply at current rates. Prices roughly doubled after China began licensing exports in 2024.',
     'USGS MCS 2026'),
]


def p02():
    n = len(NINE) + 2
    slides = []
    chips = ''.join(f'<div class="chip"><span class="sym" style="--accent:{m(s)["accent"]}">{m(s)["sym"]}</span>'
                    f'<span class="n">{m(s)["name"]}</span></div>' for s, *_ in NINE)
    cover = (kicker('The minerals we track') +
             '<h1>Nine minerals.<br>Nine chokepoints.</h1>'
             '<p class="lede">Batteries, magnets, chips, steel and defence all run on a handful of small markets. '
             'One number for each, then the full dashboard.</p>'
             f'<div class="chips">{chips}</div>')
    slides.append((frame(cover, LIME, counter=counter(1, n), src='swipe ›'),
                   'Cover: Nine minerals, nine chokepoints, with a grid of nine element symbols.'))
    for i, (slug, stat, label, sub, src) in enumerate(NINE, start=2):
        mm = m(slug)
        hero_cls = 'hero s' if len(stat) > 3 else 'hero'
        body = (kicker(f'{mm["name"]} · {i - 1} of 9') +
                f'<div class="symrow"><div class="symbig sym" style="font-size:{136 if len(mm["sym"]) <= 2 else 90}px">{mm["sym"]}</div>'
                f'<div><div class="mname">{mm["name"]}</div><div class="mq">{esc(mm["q"])}</div></div></div>'
                f'<div class="spacer"></div>'
                f'<div class="{hero_cls}">{stat}</div>'
                f'<div class="herolabel">{esc(label)}</div>'
                f'<p class="sub">{esc(sub)}</p>')
        slides.append((frame(body, mm['accent'], counter=counter(i, n), visit_path=slug, src=src, wm=mm['sym']),
                       f'{mm["name"]}: {stat} {label}'))
    rows = ''.join(f'<div class="row"><span class="sym" style="--accent:{m(s)["accent"]}">{m(s)["sym"]}</span>'
                   f'<span class="n">{m(s)["name"]}</span><span class="u">mineral.watch/{s}</span></div>' for s, *_ in NINE)
    close = (kicker('One deep-dive per mineral') +
             '<h1 style="font-size:56px">Production, reserves, trade flows, prices and who depends on whom.</h1>'
             f'<div class="list">{rows}</div>')
    slides.append((frame(close, LIME, counter=counter(n, n), src='cited · dated · free to read'),
                   'Closing slide listing the nine dashboards with their mineral.watch URLs.'))
    post('nine-minerals', 'Nine minerals, nine chokepoints', 'carousel', slides,
         '''
Nine minerals. Nine chokepoints. One number for each.

Graphite: China mined 82% of the world's supply in 2025.
Lithium: 88% of it goes into batteries; China converts ~70% of battery-grade chemicals.
Cobalt: 73% mined in the DR Congo, ~79% refined in China.
Nickel: Indonesia mined 66% of the world's total.
Rare earths: 94% of sintered NdFeB magnets are made in China.
Copper: the 2026 benchmark treatment charge settled at $0/t, the lowest on record.
Manganese: China mines ~4% of the ore and refines ~95% of battery-grade sulphate.
Uranium: Russia holds 43% of enrichment capacity.
Antimony: China, Russia and Tajikistan mine more than 85%.

Sources: USGS Mineral Commodity Summaries 2026, IEA, Cobalt Institute, WNA, EIA. Each mineral has its own interactive dashboard with maps, charts and timelines at mineral.watch (link in bio).
''',
         ['#criticalminerals', '#rareearths', '#cobalt', '#lithium', '#nickel', '#graphite', '#copper', '#manganese',
          '#uranium', '#antimony', '#supplychain', '#energytransition', '#opendata', '#mineralwatch'],
         'mineral.watch')


# ---- 03 US import reliance ----------------------------------------------------
def p03():
    rows = [('Graphite', 100, '100%'), ('Manganese', 100, '100%'), ('Antimony', 85, '~85%'), ('Cobalt', 79, '79%'),
            ('Rare earths', 67, '67%'), ('Copper (refined)', 57, '57%'), ('Lithium', 50, '>50%'), ('Nickel', 41, '41%')]
    body = (kicker('US net import reliance · 2025') +
            '<h1>How much of it does the US import?</h1>'
            '<p class="lede">Share of US apparent consumption met by net imports, by mineral.</p>'
            f'<div class="chart">{hbars(rows, LIME)}</div>'
            '<p class="note">Heavy rare earths: 100%. Nickel is ~100% excluding scrap. No US manganese mine since 1970, '
            'no antimony mine since 2016.</p>')
    html = frame(body, LIME, pill='Dependence', src='USGS Mineral Commodity Summaries 2026')
    post('us-import-reliance', 'How much of it does the US import?', 'single',
         [(html, 'Bar chart of US net import reliance in 2025: graphite and manganese 100%, antimony 85%, cobalt 79%, rare earths 67%, copper 57%, lithium over 50%, nickel 41%.')],
         '''
How much of it does the US import?

US net import reliance in 2025, per USGS:
Graphite 100%
Manganese 100%
Antimony ~85%
Cobalt 79%
Rare earths 67% (heavy rare earths: 100%)
Refined copper 57%
Lithium >50%
Nickel 41% (nearly 100% excluding scrap)

There has been no US manganese mine since 1970 and no antimony mine since 2016. Refined copper, uranium and nickel were all added to or confirmed on the US critical minerals list in late 2025.

Source: USGS Mineral Commodity Summaries 2026. Country-by-country dashboards at mineral.watch (link in bio).
''',
         ['#criticalminerals', '#supplychain', '#usgs', '#graphite', '#manganese', '#antimony', '#cobalt',
          '#rareearths', '#copper', '#lithium', '#nickel', '#geopolitics', '#opendata', '#mineralwatch'],
         'mineral.watch')


# ---- 04 cobalt ---------------------------------------------------------------
def p04():
    mm = m('cobalt')
    segs = [('DR Congo', 73, mm['accent'], '73%'), ('Indonesia', 14, mm['accent'] + 'aa', '14%'), ('rest of world', 13, GRAY_MARK, '13%')]
    body = (kicker('Cobalt · world mine production 2025') +
            '<div class="hero">73%</div>'
            '<div class="herolabel">of the world’s cobalt was mined in one country: the DR Congo. '
            '<span>And ~79% of it was refined in another: China.</span></div>'
            f'<div class="chart">{sharebar(segs)}</div>'
            f'<div class="kpis two">{kpi("310,000 t", "World mine output in 2025, an all-time high. Nearly all of it a by-product of copper or nickel.")}'
            f'{kpi("96,600 t/yr", "DRC export quota for 2026 and 2027, about half of 2024 volumes. Unused quota is forfeited to a state stockpile.")}</div>')
    html = frame(body, mm['accent'], pill='Co · cobalt', visit_path='cobalt', src='USGS MCS 2026 · Cobalt Institute · ARECOMS')
    post('cobalt-drc', 'Cobalt: 73% from one country', 'single',
         [(html, 'Cobalt post: 73% of world cobalt mined in the DR Congo in 2025, 14% in Indonesia; stacked share bar and two stat tiles.')],
         '''
73% of the world's cobalt was mined in one country in 2025. About 79% of it was refined in another.

DR Congo: ~230,000 t of a record ~310,000 t world total (USGS). Indonesia: ~44,000 t and rising. China: ~79% of the ~240,000 t of refined cobalt (Cobalt Institute).

Since February 2025 the DRC has first banned, then capped cobalt exports: 96,600 t a year for 2026 and 2027, roughly half of 2024 volumes. CMOC alone mined 117,549 t in 2025 against a 2026 quota of 31,200 t. The rest is stockpiled in-country.

Meanwhile cobalt-free LFP passed 55% of global EV battery deployments.

Map of mines and refineries, price charts and the full quota timeline: mineral.watch/cobalt (link in bio).
''',
         ['#cobalt', '#drc', '#criticalminerals', '#batteries', '#evbattery', '#supplychain', '#mining',
          '#indonesia', '#energytransition', '#opendata', '#mineralwatch'],
         'mineral.watch/cobalt')


# ---- 05 mine vs refinery dumbbell ---------------------------------------------
def p05():
    rows = [('Manganese', 4, 95, '~4%', '~95%'), ('Lithium', 21, 70, '~21%', '~70%'),
            ('Rare earths', 69, 91, '~69%', '~91%'), ('Graphite', 82, 90, '~82%', '~90%')]
    legend = (f'<div class="legend"><span><i style="background:{GRAY_MARK}"></i>share of world mine output</span>'
              f'<span><i style="background:{LIME}"></i>share of refining</span></div>')
    body = (kicker("Where it's mined vs where it's refined") +
            '<h1>The risk isn’t at the mine. It’s at the refinery.</h1>'
            '<p class="lede">China’s share of world mine output against its share of processing, by mineral.</p>'
            f'{legend}<div class="chart" style="margin-top:0">{dumbbell(rows, LIME, GRAY_MARK)}</div>'
            '<p class="note">Refining defined as: manganese, battery-grade sulphate · lithium, battery-grade chemical conversion · '
            'rare earths, refining and separation · graphite, battery-grade refining.</p>')
    html = frame(body, LIME, pill='Supply chain', visit_path='supply-chain', src='USGS MCS 2026 · IEA · 2024-25 estimates')
    post('mine-vs-refinery', 'The risk is at the refinery', 'single',
         [(html, 'Dumbbell chart: China’s share of mine output vs refining for manganese (4% to 95%), lithium (21% to 70%), rare earths (69% to 91%) and graphite (82% to 90%).')],
         '''
The supply-chain risk isn't at the mine. It's at the refinery.

China's share of world mine output vs its share of processing:
Manganese: ~4% mined, ~95% of battery-grade sulphate refined
Lithium: ~21% mined, ~70% of battery-grade chemicals converted
Rare earths: ~69% mined, ~91% refined and separated
Graphite: ~82% mined, ~90% of battery-grade material refined

Diversifying mines does little if the ore still has to go to the same smelters. Our supply-chain map compares mine production against refined output country by country for seven minerals.

Sources: USGS Mineral Commodity Summaries 2026, IEA. Explore the map at mineral.watch/supply-chain (link in bio).
''',
         ['#criticalminerals', '#supplychain', '#refining', '#china', '#manganese', '#lithium', '#rareearths',
          '#graphite', '#energytransition', '#geopolitics', '#dataviz', '#mineralwatch'],
         'mineral.watch/supply-chain')


# ---- 06 lithium price --------------------------------------------------------
def p06():
    mm = m('lithium')
    pts = [dict(label='2021', value=11700), dict(label='2022', value=63700, disp='$63,700'),
           dict(label='2023', value=39000), dict(label='2024', value=11800),
           dict(label='2025', value=9000, disp='$9,000'), dict(label='2026', range=(18000, 23000), disp='$18–23k', note='Aug spot')]
    body = (kicker('Lithium · battery-grade carbonate, US$/t') +
            '<h1>From $63,700 to $9,000. And back up.</h1>'
            '<p class="lede">Annual average price of battery-grade lithium carbonate, 2021–2025, and the August 2026 spot range.</p>'
            f'<div class="chart">{columns(pts, mm["accent"])}</div>'
            '<p class="note">The swing producer of this cycle: CATL’s Jianxiawo mine (~3–6% of world supply) shut in August 2025 '
            'when its permit lapsed and restarted on 29 June 2026.</p>')
    html = frame(body, mm['accent'], pill='Li · lithium', visit_path='lithium', src='USGS MCS 2026 / Benchmark · 2026: spot, August')
    post('lithium-price', 'Lithium: from $63,700 to $9,000 and back up', 'single',
         [(html, 'Column chart of battery-grade lithium carbonate prices: $11,700 in 2021, $63,700 in 2022, $39,000, $11,800, $9,000 in 2025, and an $18,000 to $23,000 spot range in August 2026.')],
         '''
Lithium: from $63,700 to $9,000 and back up.

Battery-grade lithium carbonate, annual average (USGS/Benchmark):
2021: $11,700/t
2022: $63,700/t
2023: $39,000/t
2024: $11,800/t
2025: $9,000/t
August 2026 spot: ~$18,000–23,000/t after Guangzhou futures briefly topped ¥200,000.

The swing producer of this cycle was a single mine. CATL's Jianxiawo lepidolite operation (~3–6% of world supply) was suspended in August 2025 when its permit lapsed, and restarted on 29 June 2026.

World mine output still grew 31% in 2025 to ~290,000 t of lithium content. Australia ~32%, then China, Chile, Zimbabwe and Argentina.

Full price history, map of mines, brines and converters: mineral.watch/lithium (link in bio).
''',
         ['#lithium', '#batteries', '#evbattery', '#criticalminerals', '#commodities', '#energytransition',
          '#mining', '#supplychain', '#dataviz', '#opendata', '#mineralwatch'],
         'mineral.watch/lithium')


# ---- 07 antimony timeline carousel -------------------------------------------
def p07():
    mm = m('antimony')
    a = mm['accent']
    n = 7
    s = []
    cover = (kicker('Antimony · export controls') +
             '<h1>How one export licence doubled a price.</h1>'
             '<p class="lede">China mines ~36% of the world’s antimony and controls most of its smelting. '
             'In August 2024 it started licensing exports. Here is what happened next.</p>'
             f'<div class="spacer"></div><div class="symbig sym" style="width:100%;height:230px;font-size:150px">Sb</div>')
    s.append((frame(cover, a, counter=counter(1, n), visit_path='antimony', src='swipe ›'),
              'Cover: How one export licence doubled a price, with the antimony symbol Sb.'))
    s.append((frame(kicker('15 August 2024') + '<h1>China announces dual-use export licensing for antimony.</h1>'
                    '<p class="lede">Effective 15 September 2024. Every buyer, everywhere, now needs a licence for antimony metal, '
                    'oxides and the ingredients of ammunition primers and night-vision detectors.</p>',
                    a, counter=counter(2, n), visit_path='antimony', src='MOFCOM · USGS', wm='Sb'),
              '15 August 2024: China announces dual-use export licensing for antimony.'))
    s.append((frame(kicker('3 December 2024') + '<h1 class="md">An outright ban on exports to the United States.</h1>'
                    '<div class="spacer"></div><div class="hero">−97%</div>'
                    '<div class="herolabel">US antimony imports from China, August to December 2024. '
                    '<span>Pre-ban, China supplied ~63% of US metal-and-oxide imports.</span></div>',
                    a, counter=counter(3, n), visit_path='antimony', src='USGS MCS 2026 · US trade data', wm='Sb'),
              '3 December 2024: an outright ban on exports to the US; imports from China fall 97%.'))
    s.append((frame(kicker('Spring 2025') + '<h1 class="md">The price peaks.</h1><div class="spacer"></div>'
                    '<div class="hero m">$60,000<small>/t</small></div>'
                    '<div class="herolabel">up from ~$12,000–14,000/t in early 2024 (Rotterdam basis). '
                    '<span>Antimony has no exchange contract; every price is an agency assessment.</span></div>',
                    a, counter=counter(4, n), visit_path='antimony', src='price-agency assessments via mineral.watch/antimony', wm='Sb'),
              'Spring 2025: the antimony price peaks near $60,000 per tonne.'))
    s.append((frame(kicker('9–10 November 2025') + '<h1 class="md">The US-specific ban is suspended until 27 November 2026.</h1>'
                    '<p class="lede">The licensing regime still applies to all buyers. By June 2026 prices had eased to '
                    '<b>$25,000–31,000/t</b>: still roughly double the pre-control level.</p>',
                    a, counter=counter(5, n), visit_path='antimony', src='MOFCOM · USGS MCS 2026', wm='Sb'),
              '9 to 10 November 2025: the US-specific ban is suspended; prices remain about double pre-control levels.'))
    steps = ''.join(f'<div class="step"><i></i><div><div class="t">{esc(t)}</div><div class="d">{esc(d)}</div></div></div>' for t, d in [
        ('Perpetua Resources · Stibnite, Idaho', '$2.9B EXIM loan (May 2026), production targeted 2029, ~35% of US demand. The only identified US antimony reserve.'),
        ('United States Antimony · Thompson Falls, Montana', 'The only operating US smelter; sole-source DLA stockpile contract of ~$245M.'),
        ('Larvotto Resources · Hillgrove, NSW', '~5,000 t/yr planned (~7% of world supply); first antimony-gold production due end of August 2026.'),
        ('Nyrstar · Port Pirie, South Australia', 'Poured Australia’s first antimony metal in November 2025; 2,000 t/yr by end-2026.'),
    ])
    s.append((frame(kicker('The rebuild') + '<h1 class="md">The West restarts its antimony chain.</h1>' + f'<div class="steps">{steps}</div>',
                    a, counter=counter(6, n), visit_path='antimony', src='company disclosures · EXIM · DLA'),
              'The rebuild: Perpetua Stibnite, US Antimony Thompson Falls, Larvotto Hillgrove, Nyrstar Port Pirie.'))
    s.append((frame(kicker('Antimony dashboard') + '<h1>Map, timeline and price charts.</h1>'
                    '<p class="lede">World reserves: ~2 Mt of antimony content, under two decades of supply at current mining rates. '
                    'One of the thinnest cushions of any strategic mineral.</p><div class="spacer"></div>'
                    f'<div class="kpis">{kpi("~110,000 t", "world mine output 2025, down from ~153,000 t in 2020")}'
                    f'{kpi("~85%", "US net import reliance; no domestic mine since 2016")}'
                    f'{kpi("~45%", "of demand is flame retardants (antimony trioxide)")}</div>',
                    a, counter=counter(7, n), visit_path='antimony', src='USGS MCS 2026 · industry estimates'),
              'Closing slide: antimony dashboard, with reserves, output, import reliance and end-use stats.'))
    post('antimony-export-controls', 'Antimony: how one export licence doubled a price', 'carousel', s,
         '''
How one export licence doubled a price. Swipe for the antimony timeline.

15 Aug 2024: China announces dual-use export licensing for antimony (effective 15 Sep).
3 Dec 2024: outright ban on exports to the US. US imports from China fall ~97% between August and December.
Spring 2025: prices peak near $60,000/t, from ~$12,000–14,000/t in early 2024.
9–10 Nov 2025: the US-specific ban is suspended until 27 Nov 2026. Licensing still applies to everyone. By June 2026 prices sit at $25,000–31,000/t, still about double.

The rebuild: Perpetua's Stibnite project in Idaho ($2.9B EXIM loan, production 2029), US Antimony's Thompson Falls smelter, Larvotto's Hillgrove mine in Australia (first production due end-August 2026) and Nyrstar's Port Pirie smelter.

Why it matters: antimony goes into flame retardants, lead-acid batteries, solar glass, ammunition primers and infrared detectors. Reserves are ~2 Mt, under two decades at current mining rates.

Sources: USGS Mineral Commodity Summaries 2026, MOFCOM, company disclosures. Full dashboard: mineral.watch/antimony (link in bio).
''',
         ['#antimony', '#criticalminerals', '#exportcontrols', '#china', '#defence', '#supplychain', '#mining',
          '#geopolitics', '#commodities', '#opendata', '#mineralwatch'],
         'mineral.watch/antimony')


# ---- 08 graphite --------------------------------------------------------------
def p08():
    mm = m('graphite')
    body = (kicker('Graphite · the anode') +
            '<div class="hero m">~50 kg</div>'
            '<div class="herolabel">of graphite in every electric car. <span>It is the largest material by weight in a lithium-ion battery, '
            'and almost nobody outside China makes the battery-grade kind.</span></div>'
            f'<div class="kpis">{kpi("82%", "China’s share of world graphite mine output, 2025")}'
            f'{kpi("~90%", "China’s share of battery-grade graphite refining (~95% of spherical graphite)")}'
            f'{kpi("100%", "US net import reliance on natural graphite")}</div>')
    html = frame(body, mm['accent'], pill='C · graphite', visit_path='graphite', src='USGS MCS 2026 · IEA', wm='C')
    post('graphite-anode', 'Graphite: 50 kg in every EV', 'single',
         [(html, 'Graphite post: about 50 kg of graphite in every EV battery; China 82% of mine output, about 90% of battery-grade refining; US import reliance 100%.')],
         '''
The biggest material in an EV battery isn't lithium. It's graphite: roughly 50 kg per car.

China mined ~82% of the world's ~1.8 Mt of natural graphite in 2025 (USGS) and refines ~90% of battery-grade graphite, including ~95% of spherical graphite for anodes (IEA). US net import reliance: 100%.

World reserves are ~310 Mt, so this is not a scarcity story. It is a processing story: the anode-grade purification and coating steps sit almost entirely in one country.

Map of mines, processing and anode plants, plus the refining explainer: mineral.watch/graphite (link in bio).
''',
         ['#graphite', '#batteries', '#evbattery', '#anode', '#criticalminerals', '#supplychain', '#china',
          '#energytransition', '#mining', '#opendata', '#mineralwatch'],
         'mineral.watch/graphite')


# ---- 09 nickel LME carousel ----------------------------------------------------
def p09():
    mm = m('nickel')
    a = mm['accent']
    n = 7
    s = []
    s.append((frame(kicker('Nickel · March 2022') + '<h1>The day nickel broke the LME.</h1>'
                    '<p class="lede">A short squeeze, a cancelled market and a record fine. Swipe for the story, '
                    'then see what the nickel market looks like in 2026.</p>'
                    '<div class="spacer"></div><div class="symbig sym" style="width:100%;height:230px;font-size:150px">Ni</div>',
                    a, counter=counter(1, n), visit_path='nickel', src='swipe ›'),
              'Cover: The day nickel broke the LME, with the nickel symbol Ni.'))
    s.append((frame(kicker('8 March 2022') + '<div class="spacer"></div><div class="hero m">$100,000<small>/t</small></div>'
                    '<div class="herolabel">Nickel more than doubles in hours as Tsingshan’s giant short position unwinds. '
                    '<span>The 2021 annual average had been $18,476/t.</span></div>',
                    a, counter=counter(2, n), visit_path='nickel', src='LME · USGS', wm='Ni'),
              '8 March 2022: nickel passes $100,000 per tonne as a giant short unwinds.'))
    s.append((frame(kicker('The cancellation') + '<div class="spacer"></div><div class="hero">~$12bn</div>'
                    '<div class="herolabel">of trades cancelled by the exchange: roughly 9,000 deals wiped from the record.</div>',
                    a, counter=counter(3, n), visit_path='nickel', src='LME · FCA', wm='Ni'),
              'About $12 billion of trades, roughly 9,000 deals, cancelled by the LME.'))
    s.append((frame(kicker('The suspension') + '<h1>Trading halted for more than a week.</h1>'
                    '<p class="lede">The world’s benchmark nickel contract stopped trading while the exchange rebuilt its market. '
                    'Confidence in the LME price took years to recover.</p>',
                    a, counter=counter(4, n), visit_path='nickel', src='LME', wm='Ni'),
              'The LME suspends nickel trading for more than a week.'))
    s.append((frame(kicker('March 2025') + '<div class="spacer"></div><div class="hero">£9.2M</div>'
                    '<div class="herolabel">FCA fine on the London Metal Exchange: '
                    '<span>the regulator’s first enforcement action against an exchange.</span></div>',
                    a, counter=counter(5, n), visit_path='nickel', src='Financial Conduct Authority, March 2025', wm='Ni'),
              'March 2025: the FCA fines the LME 9.2 million pounds.'))
    s.append((frame(kicker('Nickel in 2026') + '<h1 class="md">Four years on, the market belongs to Indonesia.</h1>'
                    f'<div class="kpis">{kpi("66%", "Indonesia’s share of world mine output, 2025 (2.6 of 3.9 Mt)")}'
                    f'{kpi("~$16,800", "LME cash price per tonne, August 2026")}'
                    f'{kpi("−32,000 t", "INSG forecast for 2026: the first deficit since 2021")}</div>',
                    a, counter=counter(6, n), visit_path='nickel', src='USGS MCS 2026 · LME · INSG April 2026', wm='Ni'),
              'Nickel in 2026: Indonesia 66% of mine output, LME about $16,800 per tonne, INSG forecasts a 32,000 tonne deficit.'))
    s.append((frame(kicker('Nickel dashboard') + '<h1 class="md">Map, quotas, prices and the class-1 divide.</h1>'
                    '<p class="lede">Indonesia and China refined ~76% of the world’s nickel in 2025. Australia’s mine output fell 54% '
                    'in a single year. BHP’s Nickel West is suspended; Koniambo’s furnaces have been cold since August 2024.</p>',
                    a, counter=counter(7, n), visit_path='nickel', src='USGS MCS 2026 · IEA · company disclosures'),
              'Closing slide: nickel dashboard with refining concentration and the Western supply cull.'))
    post('nickel-lme', 'The day nickel broke the LME', 'carousel', s,
         '''
The day nickel broke the LME. Swipe for the story.

8 March 2022: nickel passes $100,000/t as Tsingshan's giant short position unwinds. The 2021 average had been $18,476/t.
The LME cancels ~9,000 trades worth ~$12bn and suspends trading for more than a week.
March 2025: the FCA fines the LME £9.2M, its first enforcement action against an exchange.

Four years on, the market belongs to Indonesia: 66% of world mine output in 2025, and with China ~76% of refining. Australia's output fell 54% in one year; BHP's Nickel West is suspended and Koniambo's furnaces have been cold since August 2024.

LME cash sits near $16,800/t (Aug 2026). INSG has flipped its 2026 forecast to a 32,000 t deficit, the first since 2021, on Indonesia's quota cuts.

Sources: LME, FCA, USGS Mineral Commodity Summaries 2026, INSG, IEA. Full dashboard: mineral.watch/nickel (link in bio).
''',
         ['#nickel', '#lme', '#commodities', '#criticalminerals', '#indonesia', '#stainlesssteel', '#batteries',
          '#supplychain', '#mining', '#markets', '#opendata', '#mineralwatch'],
         'mineral.watch/nickel')


# ---- 10 manganese --------------------------------------------------------------
def p10():
    mm = m('manganese')
    body = (kicker('Manganese · mine vs refinery') +
            '<h1 class="md">One country mines almost none of it and refines almost all of it.</h1>'
            '<div class="twoup">'
            f'<div class="box g"><div class="hero">4%</div><div class="herolabel">of the world’s manganese ore is mined in China</div></div>'
            f'<div class="box"><div class="hero">95%</div><div class="herolabel">of battery-grade manganese sulphate is refined there</div></div>'
            '</div>'
            '<p class="sub">~90% of manganese goes into steel, and USGS lists no satisfactory substitute. '
            'Battery demand is projected to grow more than 8x this decade.</p>')
    html = frame(body, mm['accent'], pill='Mn · manganese', visit_path='manganese', src='USGS MCS 2026 · IEA · Benchmark', wm='Mn')
    post('manganese-4-vs-95', 'Manganese: 4% mined, 95% refined', 'single',
         [(html, 'Manganese post: China mines about 4% of the world’s manganese ore but refines about 95% of battery-grade manganese sulphate.')],
         '''
4% vs 95%.

China mines only ~4% of the world's manganese ore. It refines ~60% of manganese ferroalloys, >90% of electrolytic manganese metal and ~95% of the battery-grade manganese sulphate that new LMR cathodes need (IEA).

The ore comes from South Africa (~38% of 2025 output), Gabon, Ghana and Australia. Gabon bans raw ore exports from 2029. The US has had no manganese mine since 1970 and imports 100% of what it uses.

~90% of manganese still goes into steel, where USGS says it has no satisfactory substitute.

Map of mines, smelters and refineries, plus the price and quota timeline: mineral.watch/manganese (link in bio).
''',
         ['#manganese', '#criticalminerals', '#steel', '#batteries', '#southafrica', '#gabon', '#china',
          '#supplychain', '#mining', '#opendata', '#mineralwatch'],
         'mineral.watch/manganese')


# ---- 11 rare earths grid --------------------------------------------------------
REE = [('Sc', 21, 'scandium'), ('Y', 39, 'yttrium'), ('La', 57, 'lanthanum'), ('Ce', 58, 'cerium'), ('Pr', 59, 'praseodymium'),
       ('Nd', 60, 'neodymium'), ('Pm', 61, 'promethium'), ('Sm', 62, 'samarium'), ('Eu', 63, 'europium'), ('Gd', 64, 'gadolinium'),
       ('Tb', 65, 'terbium'), ('Dy', 66, 'dysprosium'), ('Ho', 67, 'holmium'), ('Er', 68, 'erbium'), ('Tm', 69, 'thulium'),
       ('Yb', 70, 'ytterbium'), ('Lu', 71, 'lutetium')]
CONTROLLED = {'Sm', 'Gd', 'Tb', 'Dy', 'Lu', 'Sc', 'Y'}


def p11():
    mm = m('rare-earths')
    tiles = ''.join(f'<div class="el{" on" if s in CONTROLLED else ""}"><span class="z">{z}</span><div class="s">{s}</div><div class="nm">{nm}</div></div>'
                    for s, z, nm in REE)
    body = (kicker('Rare earths · the 17 elements') +
            '<h1>17 elements. 7 under export control.</h1>'
            f'<div class="legend"><span><i style="background:{mm["accent"]}"></i>subject to China’s export controls since April 2025</span></div>'
            f'<div class="grid17" style="margin-top:0">{tiles}</div>'
            f'<div class="kpis two" style="margin-top:26px">{kpi("~91%", "China’s share of rare earth refining and separation (IEA, 2024)")}'
            f'{kpi("~94%", "China’s share of sintered NdFeB magnet production")}</div>')
    html = frame(body, mm['accent'], pill='REE · rare earths', visit_path='rare-earths', src='USGS MCS 2026 · IEA · MOFCOM')
    post('rare-earths-17', 'Rare earths: 17 elements, 7 under export control', 'single',
         [(html, 'Grid of the 17 rare earth elements with samarium, gadolinium, terbium, dysprosium, lutetium, scandium and yttrium highlighted as export-controlled; China 91% of refining, 94% of magnets.')],
         '''
17 elements. 7 under export control.

Since April 2025 China requires licences to export samarium, gadolinium, terbium, dysprosium, lutetium, scandium and yttrium, and the magnets that contain them. An October 2025 expansion was suspended for one year in November 2025.

Why it bites: China handles ~91% of the world's rare earth refining and separation and makes ~94% of sintered NdFeB magnets (IEA). It mined ~69% of the ~390,000 t of rare-earth oxides produced in 2025 (USGS). US import reliance: 67% overall, 100% for heavy rare earths.

The 17 elements explained, the map of mines, separation plants and magnet factories, and the 2010–2026 export-controls timeline: mineral.watch/rare-earths (link in bio).
''',
         ['#rareearths', '#neodymium', '#dysprosium', '#magnets', '#criticalminerals', '#exportcontrols', '#china',
          '#supplychain', '#defence', '#energytransition', '#opendata', '#mineralwatch'],
         'mineral.watch/rare-earths')


# ---- 12 copper $0 --------------------------------------------------------------
def p12():
    mm = m('copper')
    body = (kicker('Copper · the smelting chokepoint') +
            '<div class="hero">$0<small>/t</small></div>'
            '<div class="herolabel">The 2026 benchmark treatment charge for copper concentrate. '
            '<span>Smelters are now processing ore for nothing, because there are too many smelters chasing too little concentrate.</span></div>'
            f'<div class="kpis">{kpi("$21.25/t", "the 2025 benchmark treatment charge")}'
            f'{kpi("~48%", "China’s share of refined copper output, 2025 (~14 of 29 Mt)")}'
            f'{kpi("~70%", "of 2035 demand covered by existing and announced mines (IEA)")}</div>')
    html = frame(body, mm['accent'], pill='Cu · copper', visit_path='copper', src='USGS MCS 2026 · IEA · LME · benchmark settlements', wm='Cu')
    post('copper-zero-tc', 'Copper: a $0 treatment charge', 'single',
         [(html, 'Copper post: the 2026 benchmark treatment charge is $0 per tonne, down from $21.25 in 2025; China 48% of refined output; IEA sees a 30% supply gap by 2035.')],
         '''
$0. That is the 2026 benchmark treatment charge for copper concentrate, down from $21.25/t in 2025 and the lowest on record.

Treatment charges are what miners pay smelters to turn concentrate into metal. When they hit zero, smelters are working for free, because there are too many smelters (China holds ~50% of world capacity) chasing too little concentrate.

The mine side is tight too: Cobre Panama closed, Grasberg and El Teniente disrupted, and the IEA projects existing and announced mines will cover only ~70% of copper demand by 2035. LME copper hit a record $14,527.50/t on 29 January 2026.

World mine output 2025: ~23 Mt (Chile ~23%). Refined output: ~29 Mt, of which China ~48% (USGS).

Map of mines, smelters and disrupted operations, plus the 2023–2026 timeline: mineral.watch/copper (link in bio).
''',
         ['#copper', '#commodities', '#criticalminerals', '#smelting', '#chile', '#china', '#supplychain',
          '#energytransition', '#mining', '#markets', '#opendata', '#mineralwatch'],
         'mineral.watch/copper')


# ---- 13 uranium meter -----------------------------------------------------------
def p13():
    mm = m('uranium')
    body = (kicker('Uranium · enrichment') +
            '<div class="hero">43%</div>'
            '<div class="herolabel">of the world’s uranium enrichment capacity is Russian. '
            '<span>Rosatom: 27.1M of ~62.9M SWU.</span></div>'
            f'<div class="chart">{meter(43, mm["accent"], label_left="Russia (Rosatom)", label_right="rest of world")}</div>'
            f'<div class="kpis">{kpi("26%", "of US utilities’ enrichment purchases still came from Russia in 2025 (EIA)")}'
            f'{kpi("1 Jan 2028", "waivers on the US ban on Russian enriched uranium expire")}'
            f'{kpi("79", "reactors under construction worldwide, 37 of them in China")}</div>')
    html = frame(body, mm['accent'], pill='U · uranium', visit_path='uranium', src='WNA 2025 · EIA · IAEA PRIS, Aug 2026')
    post('uranium-enrichment', 'Uranium: the Russian enrichment chokepoint', 'single',
         [(html, 'Uranium post: 43% of world enrichment capacity is Russian, shown as a meter; US utilities bought 26% from Russia in 2025; waivers end 1 January 2028; 79 reactors under construction.')],
         '''
43% of the world's uranium enrichment capacity is Russian.

Rosatom controls 27.1M of ~62.9M SWU of global enrichment capacity (WNA 2025). US utilities still bought 26% of their enrichment from Russia in 2025 (EIA). The US ban on Russian enriched uranium allows waivers only until 1 January 2028.

The mine side is concentrated too: Kazakhstan produced ~41% of world uranium in 2025, ahead of Canada and Namibia. Mine output covered ~90% of reactor requirements.

Demand is heading the other way. 441 reactors are operable and 79 under construction, 37 of them in China. Announced US tech-company nuclear deals exceed 9.8 GW. Spot uranium sits near $90/lb, with the long-term price at a record $95.50/lb.

The ore-to-fuel-rod chain explained, the map and the price charts: mineral.watch/uranium (link in bio).
''',
         ['#uranium', '#nuclear', '#nuclearenergy', '#enrichment', '#kazakhstan', '#russia', '#criticalminerals',
          '#energysecurity', '#supplychain', '#opendata', '#mineralwatch'],
         'mineral.watch/uranium')


# ---- 14 how we work carousel -----------------------------------------------------
def p14():
    n = 6
    s = []
    s.append((frame(kicker('About') + '<h1>Open intelligence on strategic minerals.</h1>'
                    '<p class="lede">Independent, source-cited, free to read. Here is how mineral.watch works.</p>'
                    f'<div class="plume-inline"><svg viewBox="0 0 912 330" xmlns="http://www.w3.org/2000/svg">'
                    f'{plume(0, 912, (150, 180), (0, 330))}</svg></div>',
                    LIME, counter=counter(1, n), src='swipe ›'),
              'Cover: Open intelligence on strategic minerals, how mineral.watch works, with the nine-ribbon plume.'))
    steps = ''.join(f'<div class="step"><i></i><div><div class="t">{esc(t)}</div><div class="d">{esc(d)}</div></div></div>' for t, d in [
        ('USGS Mineral Commodity Summaries', 'production, reserves, import reliance, prices'),
        ('BGS World Mineral Statistics', 'long-run mine and smelter series by country'),
        ('UN Comtrade', 'bilateral trade flows'),
        ('IEA Critical Minerals', 'refining concentration and demand scenarios'),
        ('WNA · IAEA · NEA Red Book · US EIA', 'the uranium fuel cycle'),
    ])
    s.append((frame(kicker('Sources') + '<h1 class="md">Every figure is cited and dated. Estimates are flagged as such.</h1>' +
                    f'<div class="steps">{steps}</div>', LIME, counter=counter(2, n), src='primary open datasets'),
              'Sources: USGS, BGS, UN Comtrade, IEA, WNA, IAEA, NEA Red Book, US EIA.'))
    s.append((frame(kicker('Independence') + '<h1>No government. No mining company. No trade body.</h1>'
                    '<p class="lede">mineral.watch is not affiliated with any of them and holds no commercial position in the minerals it covers. '
                    'When a figure is contested, we say so and show both sides.</p>',
                    LIME, counter=counter(3, n), src='hello@mineral.watch for corrections'),
              'Independence: not affiliated with any government, mining company or trade body.'))
    s.append((frame(kicker('Maps & dashboards') + '<h1>Where it’s mined vs where it’s refined.</h1>'
                    '<p class="lede">Interactive world maps of mines, smelters, refineries, disrupted operations and development projects for nine minerals, '
                    'plus a supply-chain map that compares mine output with refined output, country by country.</p>',
                    LIME, counter=counter(4, n), visit_path='supply-chain', src='9 dashboards · 1 supply-chain map · 1 explorer'),
              'Maps and dashboards: interactive world maps for nine minerals plus a supply-chain comparison map.'))
    s.append((frame(kicker('Reuse') + '<h1>Open to quote, cite and build on.</h1>'
                    '<p class="lede">Editorial content and compiled datasets: <b>CC BY-NC-SA 4.0</b>. Source code and dashboards: <b>AGPL-3.0</b>. '
                    'Newsrooms are welcome to quote with attribution.</p>'
                    '<p class="sub">Attribution: Source: mineral.watch (https://mineral.watch) · CC BY-NC-SA 4.0</p>',
                    LIME, counter=counter(5, n), visit_path='terms', src='mineral.watch/terms · LICENSE.txt'),
              'Reuse: content under CC BY-NC-SA 4.0, code under AGPL-3.0, attribution format shown.'))
    s.append((frame(kicker('Get in touch') + '<h1>Spotted an error? Sitting on data?</h1>'
                    '<p class="lede">Corrections and data tips make the dashboards better for everyone. Write to <b>hello@mineral.watch</b>.</p>',
                    LIME, counter=counter(6, n), src='hello@mineral.watch'),
              'Closing slide: corrections and data tips to hello@mineral.watch.'))
    post('how-we-work', 'How mineral.watch works', 'carousel', s,
         '''
How mineral.watch works. Swipe through.

1. Sources. Every figure is cited and dated: USGS Mineral Commodity Summaries, BGS World Mineral Statistics, UN Comtrade, IEA Critical Minerals, plus WNA, IAEA, the NEA Red Book and US EIA for uranium. Estimates are flagged as estimates.

2. Independence. No affiliation with any government, mining company or trade body, and no commercial position in the minerals we cover.

3. Maps and dashboards. Interactive world maps of mines, smelters and refineries for nine minerals, and a supply-chain map that compares where ore is mined with where it is refined.

4. Reuse. Editorial content and compiled datasets are CC BY-NC-SA 4.0; the code is AGPL-3.0. Quote us with attribution: Source: mineral.watch.

5. Corrections and data tips: hello@mineral.watch.

Visit mineral.watch (link in bio).
''',
         ['#opendata', '#datajournalism', '#criticalminerals', '#transparency', '#dataviz', '#usgs', '#supplychain',
          '#mining', '#research', '#mineralwatch'],
         'mineral.watch')


# ---- 15 hire us -------------------------------------------------------------------
def p15():
    body = (kicker('Custom research') +
            '<h1>Need a source-cited report on a mineral supply chain?</h1>'
            '<p class="lede">Ad hoc, data-driven research on production, trade flows, refining concentration and prices, '
            'built on the same open sources as our dashboards and delivered with every figure cited.</p>'
            '<p class="sub">Newsrooms, analysts, NGOs, procurement and policy teams.</p>'
            '<a class="btn">Hire us · hello@mineral.watch</a>'
            '<p class="sub" style="margin-top:26px">Or subscribe at mineral.watch to be notified when the data refreshes.</p>')
    html = frame(body, LIME, pill='Hire us', src='hello@mineral.watch')
    post('hire-us', 'Custom research: hire us', 'single',
         [(html, 'Call to action: Need a source-cited report on a mineral supply chain? Hire us at hello@mineral.watch.')],
         '''
Need a source-cited report on a mineral supply chain?

We do ad hoc, data-driven research on production, reserves, trade flows, refining concentration and prices, built on the same open sources as our dashboards (USGS, BGS, UN Comtrade, IEA) and delivered with every figure cited and dated.

For newsrooms, analysts, NGOs, procurement and policy teams.

Write to hello@mineral.watch, or subscribe at mineral.watch to be notified when a dashboard's data refreshes (link in bio).
''',
         ['#criticalminerals', '#research', '#supplychain', '#duediligence', '#datajournalism', '#mining',
          '#energytransition', '#geopolitics', '#consulting', '#mineralwatch'],
         'mineral.watch')


# ---------------------------------------------------------------- render
def render(html, out_png, tmp):
    page = f'{tmp}/slide.html'
    raw = f'{tmp}/raw.png'
    with open(page, 'w') as f:
        f.write(html)
    subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=2',
                    f'--window-size={W},{H}', f'--screenshot={raw}', '--virtual-time-budget=2500', f'file://{page}'],
                   check=True, capture_output=True)
    Image.open(raw).convert('RGB').resize((W, H), Image.LANCZOS).save(out_png, optimize=True)


def schedule_dates(start, count):
    """Mon/Wed/Fri cadence from `start` (inclusive if it is one of those days)."""
    d, out = start, []
    while len(out) < count:
        if d.weekday() in (0, 2, 4):
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def contact_sheet(covers, path):
    cols, tw, th, gut = 5, 300, 375, 18
    rows = (len(covers) + cols - 1) // cols
    sheet = Image.new('RGB', (gut + cols * (tw + gut), gut + rows * (th + gut + 26)), BG)
    draw = ImageDraw.Draw(sheet)
    for i, (label, png) in enumerate(covers):
        im = Image.open(png).resize((tw, th), Image.LANCZOS)
        x = gut + (i % cols) * (tw + gut)
        y = gut + (i // cols) * (th + gut + 26)
        sheet.paste(im, (x, y))
        draw.text((x, y + th + 6), label, fill=MUTED)
    sheet.save(path, optimize=True)


def main():
    only = {int(a) for a in sys.argv[1:] if a.isdigit()}
    for build in (p01, p02, p03, p04, p05, p06, p07, p08, p09, p10, p11, p12, p13, p14, p15):
        build()
    os.makedirs(OUT, exist_ok=True)
    dates = schedule_dates(dt.date(2026, 9, 4), len(POSTS))
    manifest, covers = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for i, p in enumerate(POSTS, start=1):
            folder = f'{i:02d}-{p["slug"]}'
            os.makedirs(f'{OUT}/{folder}', exist_ok=True)
            files = []
            for j, (html, alt) in enumerate(p['slides'], start=1):
                name = 'post.png' if p['type'] == 'single' else f'slide-{j:02d}.png'
                rel = f'{folder}/{name}'
                if not only or i in only:
                    render(html, f'{OUT}/{rel}', tmp)
                    print(f'  rendered {rel}')
                files.append(dict(file=rel, alt=alt))
            covers.append((f'{i:02d} {p["title"]}', f'{OUT}/{files[0]["file"]}'))
            manifest.append(dict(order=i, date=dates[i - 1].isoformat(), time='12:00', type=p['type'],
                                 slug=p['slug'], title=p['title'], link=f'https://{p["visit"]}',
                                 media=files, caption=p['caption'], first_comment=p['first_comment']))

    with open(f'{OUT}/posts.json', 'w') as f:
        json.dump(dict(account='https://instagram.com/mineralwatch', format='1080x1350 PNG (4:5)',
                       generated=dt.date.today().isoformat(), posts=manifest), f, indent=2, ensure_ascii=False)

    with open(f'{OUT}/schedule.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['post', 'date', 'time', 'type', 'slides', 'media_files', 'caption', 'first_comment', 'link'])
        for p in manifest:
            w.writerow([p['order'], p['date'], p['time'], p['type'], len(p['media']),
                        ';'.join(x['file'] for x in p['media']), p['caption'], p['first_comment'], p['link']])

    with open(f'{OUT}/captions.md', 'w') as f:
        f.write('# mineral.watch · Instagram launch set\n\n')
        f.write(f'{len(manifest)} posts, 1080×1350 (4:5). Suggested cadence: Mon/Wed/Fri at 12:00 from {dates[0]} to {dates[-1]}. '
                'Set the profile link to https://mineral.watch. Paste the hashtags as the first comment.\n\n')
        for p in manifest:
            f.write(f'## {p["order"]:02d} · {p["title"]}\n\n')
            f.write(f'- **Date:** {p["date"]} · **Type:** {p["type"]} ({len(p["media"])} image{"s" if len(p["media"]) > 1 else ""}) · **Link:** {p["link"]}\n')
            f.write('- **Files:** ' + ', '.join(f'`{x["file"]}`' for x in p['media']) + '\n\n')
            f.write('**Caption**\n\n```\n' + p['caption'] + '\n```\n\n')
            f.write('**First comment**\n\n```\n' + p['first_comment'] + '\n```\n\n')
            f.write('**Alt text**\n\n' + ''.join(f'{j}. {x["alt"]}\n' for j, x in enumerate(p['media'], start=1)) + '\n')

    contact_sheet(covers, f'{OUT}/_contact-sheet.png')
    total = sum(len(p['media']) for p in manifest)
    print(f'wrote {len(manifest)} posts / {total} images + posts.json, schedule.csv, captions.md to {OUT}')


if __name__ == '__main__':
    main()
