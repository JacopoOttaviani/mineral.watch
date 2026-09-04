#!/usr/bin/env python3
"""Build the shared social-preview card at brand/og-image.png.

Renders a 1200x630 card: the wordmark on the left, and on the right a Sankey
plume of nine ribbons, one per tracked mineral, each ribbon's width set by that
mineral's top-producer share of world mine production. Uses the same palette as
gen_portfolio_sankey.py. Headless Chrome renders at 2x, then it downsamples to
1200x630 so the type stays crisp.

Re-run after a palette or copy change:  python3 tools/gen_og_image.py
"""
import os
import subprocess
import tempfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = f'{ROOT}/brand/og-image.png'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
W, H = 1200, 630

# (colour, top producer's share of 2024 world mine production) — see the
# homepage portfolio Sankey for the underlying BGS figures.
MINERALS = [
    ('#c8ff6b', 74.9),   # rare earths — China
    ('#84a5f0', 74.6),   # cobalt      — DR Congo
    ('#e6b95e', 73.9),   # graphite    — China
    ('#ff7d9c', 62.2),   # lithium     — Australia
    ('#34d399', 61.0),   # nickel      — Indonesia
    ('#f0abfc', 42.8),   # antimony    — China
    ('#4cc9f0', 37.3),   # uranium     — Kazakhstan
    ('#c08ad6', 36.9),   # manganese   — South Africa
    ('#e08256', 24.0),   # copper      — Chile
]

# The plume starts as a tight bundle just right of the wordmark and fans to a
# full-bleed spread at the right edge. Ribbons keep their order at both ends, so
# none of them cross.
X0, X1 = 470, 1268
ORIGIN = (262, 372)
SPREAD = (-46, 676)
GAP_ORIGIN, GAP_SPREAD = 1.6, 8.0


def fan():
    total = sum(v for _, v in MINERALS)
    so = ((ORIGIN[1] - ORIGIN[0]) - GAP_ORIGIN * (len(MINERALS) - 1)) / total
    sd = ((SPREAD[1] - SPREAD[0]) - GAP_SPREAD * (len(MINERALS) - 1)) / total
    c1, c2 = X0 + (X1 - X0) * .44, X0 + (X1 - X0) * .58
    yo, yd, out = ORIGIN[0], SPREAD[0], []
    for colour, share in MINERALS:
        ho, hd = share * so, share * sd
        out.append(
            f'<path d="M{X0},{yo:.1f} C{c1:.0f},{yo:.1f} {c2:.0f},{yd:.1f} '
            f'{X1},{yd:.1f} L{X1},{yd + hd:.1f} C{c2:.0f},{yd + hd:.1f} '
            f'{c1:.0f},{yo + ho:.1f} {X0},{yo + ho:.1f} Z" fill="{colour}"/>')
        yo += ho + GAP_ORIGIN
        yd += hd + GAP_SPREAD
    return '\n'.join(out)


MARK = '''<g stroke="#e6edf3" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" fill="none">
  <path d="M20 12 H44"/><path d="M20 12 L6 26"/><path d="M44 12 L58 26"/><path d="M6 26 H58"/>
  <path d="M6 26 L32 56"/><path d="M58 26 L32 56"/><path d="M20 12 L32 26"/><path d="M44 12 L32 26"/><path d="M32 26 V56"/>
</g><g fill="#0d1117" stroke="#e6edf3" stroke-width="3">
  <circle cx="20" cy="12" r="4.4"/><circle cx="44" cy="12" r="4.4"/><circle cx="6" cy="26" r="4.4"/>
  <circle cx="58" cy="26" r="4.4"/><circle cx="32" cy="56" r="4.4"/>
</g><circle cx="32" cy="26" r="6" fill="#c8ff6b"/>'''

PAGE = '''<!doctype html><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1200px;height:630px;overflow:hidden}
body{background:#0d1117;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased;font-kerning:normal;font-feature-settings:"kern" 1,"liga" 1}
.frame{position:relative;width:1200px;height:630px;overflow:hidden;
  background:radial-gradient(130%% 140%% at 18%% 45%%,#161f2c 0%%,#0d1117 52%%,#080c11 100%%),#0d1117}
.art{position:absolute;inset:0;filter:blur(.4px)}
.art svg{display:block;width:1200px;height:630px}
.fan{opacity:.82}
.scrim{position:absolute;inset:0;background:
  linear-gradient(92deg,#0d1117 0%%,#0d1117 38%%,rgba(13,17,23,.94) 45%%,rgba(13,17,23,.35) 53%%,rgba(13,17,23,0) 61%%)}
.vig{position:absolute;inset:0;background:
  linear-gradient(180deg,rgba(8,12,17,.9) 0%%,rgba(8,12,17,0) 19%%,rgba(8,12,17,0) 76%%,rgba(8,12,17,.92) 100%%),
  radial-gradient(80%% 120%% at 108%% 50%%,rgba(8,12,17,.55) 0%%,rgba(8,12,17,0) 60%%)}
.copy{position:absolute;left:76px;top:0;height:630px;width:470px;display:flex;flex-direction:column;justify-content:center}
.kick{display:flex;align-items:center;gap:11px;font-size:11.5px;white-space:nowrap;letter-spacing:.24em;text-transform:uppercase;font-weight:700;color:#8b98a5;margin-bottom:26px}
.kick i{display:block;width:26px;height:1px;background:#3a4859}
.lock{display:flex;align-items:center;gap:18px}
h1{font-size:63px;line-height:.95;font-weight:800;letter-spacing:-.036em;white-space:nowrap}
h1 b{color:#c8ff6b}
p{margin-top:22px;font-size:22px;line-height:1.42;color:#a9b6c4;max-width:400px;letter-spacing:-.008em}
.rule{margin-top:28px;width:84px;height:3px;background:#c8ff6b;border-radius:2px}
.foot{position:absolute;left:78px;bottom:44px;font-size:13.5px;color:#78868f;letter-spacing:.04em;
  font-family:"SF Mono",ui-monospace,Menlo,monospace}
</style>
<div class="frame">
  <div class="art"><svg viewBox="0 0 1200 630" xmlns="http://www.w3.org/2000/svg"><g class="fan">%(fan)s</g></svg></div>
  <div class="scrim"></div><div class="vig"></div>
  <div class="copy">
    <div class="kick"><i></i>Open data &middot; Minerals &middot; Oil &amp; gas &middot; Green transition</div>
    <div class="lock"><svg width="62" height="62" viewBox="-2 4 68 58">%(mark)s</svg><h1>mineral<b>.watch</b></h1></div>
    <p>Who produces it, who refines it, and where the chokepoints are.</p>
    <div class="rule"></div>
  </div>
  <div class="foot">USGS &middot; BGS &middot; UN Comtrade &middot; IEA &middot; EIA &middot; OPEC</div>
</div>'''


def main():
    with tempfile.TemporaryDirectory() as tmp:
        page = f'{tmp}/og.html'
        raw = f'{tmp}/raw.png'
        with open(page, 'w') as f:
            f.write(PAGE % {'fan': fan(), 'mark': MARK})
        subprocess.run([
            CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars',
            '--force-device-scale-factor=2', f'--window-size={W},{H}',
            f'--screenshot={raw}', '--virtual-time-budget=3000',
            f'file://{page}',
        ], check=True, capture_output=True)
        Image.open(raw).convert('RGB').resize((W, H), Image.LANCZOS).save(
            OUT, optimize=True)
    print(f'wrote {OUT} ({os.path.getsize(OUT) // 1024} KB)')


if __name__ == '__main__':
    main()
