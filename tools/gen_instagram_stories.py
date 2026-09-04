#!/usr/bin/env python3
"""Story cards (1080x1920) announcing each queued Instagram post -> social/instagram/stories/.

One JPEG per item in social/instagram/queue.json: the site chrome, a "New post" kicker,
the post's cover slide framed in the post's accent colour, the title, and the destination
URL printed large (mineral.watch or the dashboard sub-link). The URL is printed on the
image because the Instagram API cannot attach a link sticker — the publisher posts this
image as a Story and the link sticker, if wanted, is added by hand in the app.

Content stays inside Instagram's story safe zone (roughly 250px from the top and bottom).

Run after tools/build_ig_queue.py:  python3 tools/gen_instagram_stories.py
"""
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_instagram_posts as base  # noqa: E402

ROOT = base.ROOT
SOCIAL = f'{ROOT}/social/instagram'
OUT = f'{SOCIAL}/stories'
W, H = 1080, 1920

CSS = f'''
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;background:{base.BG}}}
body{{color:{base.INK};font-family:{base.SANS};-webkit-font-smoothing:antialiased}}
.frame{{position:relative;width:{W}px;height:{H}px;overflow:hidden;--accent:#c8ff6b;
  background:radial-gradient(90% 55% at 50% 38%,color-mix(in srgb,var(--accent) 14%,{base.BG2}) 0%,{base.BG} 60%,#090d12 100%)}}
.lock{{position:absolute;left:84px;top:300px;display:flex;align-items:center;gap:14px;font-size:32px;font-weight:800;letter-spacing:-.02em}}
.lock b{{color:var(--accent)}} .lock svg{{width:46px;height:46px}}
.pill{{position:absolute;right:84px;top:300px;font-family:{base.MONO};font-size:20px;color:var(--accent);border:1.5px solid color-mix(in srgb,var(--accent) 45%,transparent);border-radius:99px;padding:10px 20px;letter-spacing:.08em}}
.card{{position:absolute;left:172px;top:410px;width:736px;height:920px;border-radius:26px;overflow:hidden;border:3px solid var(--accent);
  box-shadow:0 40px 90px rgba(0,0,0,.55),0 0 0 14px rgba(13,17,23,.6)}}
.card img{{display:block;width:100%;height:100%;object-fit:cover}}
.copy{{position:absolute;left:84px;right:84px;top:1378px;display:flex;flex-direction:column;align-items:flex-start}}
.kicker{{display:flex;align-items:center;gap:14px;color:var(--accent);text-transform:uppercase;letter-spacing:.2em;font-size:22px;font-weight:700}}
.kicker i{{display:block;width:34px;height:2px;background:var(--accent)}}
h1{{font-size:46px;line-height:1.1;font-weight:800;letter-spacing:-.03em;margin-top:16px;max-width:912px}}
.url{{margin-top:22px;display:inline-flex;align-items:center;gap:16px;background:var(--accent);color:{base.BG};font-weight:800;font-size:34px;
  padding:18px 32px;border-radius:99px;letter-spacing:-.01em}}
.url i{{display:block;width:12px;height:12px;border-radius:50%;background:{base.BG}}}
.hint{{margin-top:20px;font-family:{base.MONO};font-size:19px;color:{base.MUTED};letter-spacing:.03em}}
'''


def story_html(item, cover_path):
    short = item['link'].replace('https://', '')
    title = item['title']
    return (f'<!doctype html><meta charset="utf-8"><style>{CSS}</style>'
            f'<div class="frame" style="--accent:{item["accent"]}">'
            f'<div class="lock">{base.MARK}<span>mineral<b>.watch</b></span></div><div class="pill">New post</div>'
            f'<div class="card"><img src="file://{cover_path}"></div>'
            f'<div class="copy"><div class="kicker"><i></i>{"Swipe through" if item["type"] == "carousel" else "New on the grid"}</div>'
            f'<h1>{base.esc(title)}</h1>'
            f'<div class="url"><i></i>{short}</div>'
            f'<div class="hint">visit {short} · link in bio</div></div></div>')


def render(html, out_jpg, tmp):
    page, raw = f'{tmp}/story.html', f'{tmp}/story.png'
    open(page, 'w').write(html)
    subprocess.run([base.CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=2',
                    f'--window-size={W},{H}', f'--screenshot={raw}', '--virtual-time-budget=2500', f'file://{page}'],
                   check=True, capture_output=True)
    Image.open(raw).convert('RGB').resize((W, H), Image.LANCZOS).save(out_jpg, quality=90, optimize=True, subsampling=0)


def main():
    q = json.load(open(f'{SOCIAL}/queue.json'))
    os.makedirs(OUT, exist_ok=True)
    only = set(sys.argv[1:])
    with tempfile.TemporaryDirectory() as tmp:
        for it in q['queue']:
            if only and it['id'] not in only:
                continue
            cover = f'{SOCIAL}/' + it['media'][0].split('/social/instagram/')[1]
            out = f'{SOCIAL}/{it["story_file"]}'
            render(story_html(it, cover), out, tmp)
            print(f'  rendered {it["story_file"]}')
    print(f'stories -> {OUT}')


if __name__ == '__main__':
    main()
