#!/usr/bin/env python3
"""Build social/instagram/queue.json: the ordered list of Instagram posts still to publish.

Merges the two manifests (social/instagram/posts.json — launch set; social/instagram/
minerals/posts.json — duotone photo sets), drops what has already been published, and
writes one flat queue with PUBLIC media URLs (the repo is served at mineral.watch, so a
committed file is reachable at https://mineral.watch/<path>). tools/ig_publish_next.py
consumes this file (from the live site or locally) and publishes the next item.

Order interleaves chart posts and photo sets for variety; the two photo sets whose header
photos carry a recorded licence (cobalt, nickel) come before the seven that do not.

Re-run after publishing manually or after adding posts:  python3 tools/build_ig_queue.py
"""
import datetime as dt
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOCIAL = f'{ROOT}/social/instagram'
SITE = 'https://mineral.watch/social/instagram'

# Published by hand from this machine (Claude in Chrome). Keep in sync when posting manually.
PUBLISHED = {'01-launch', '02-nine-minerals', 'minerals/lithium'}

ORDER = ['03-us-import-reliance', 'minerals/cobalt', '04-cobalt-drc', '05-mine-vs-refinery', 'minerals/nickel',
         '06-lithium-price', '07-antimony-export-controls', 'minerals/graphite', '08-graphite-anode', '09-nickel-lme',
         'minerals/copper', '10-manganese-4-vs-95', '11-rare-earths-17', 'minerals/rare-earths', '12-copper-zero-tc',
         '13-uranium-enrichment', 'minerals/manganese', '14-how-we-work', 'minerals/uranium', '15-hire-us',
         'minerals/antimony']

ACCENTS = {'graphite': '#fbbf24', 'lithium': '#fb7185', 'cobalt': '#5b8aff', 'nickel': '#a3e635', 'rare-earths': '#a78bfa',
           'copper': '#e8926a', 'manganese': '#e879f9', 'uranium': '#22d3ee', 'antimony': '#34d399'}


def accent_for(item_id):
    for k, v in ACCENTS.items():
        if k in item_id:
            return v
    return '#c8ff6b'


def main():
    launch = json.load(open(f'{SOCIAL}/posts.json'))['posts']
    minerals = json.load(open(f'{SOCIAL}/minerals/posts.json'))['sets']
    items = {}
    for p in launch:
        folder = p['media'][0]['file'].split('/')[0]
        items[folder] = dict(
            id=folder, set='launch', type=p['type'], title=p['title'], link=p['link'],
            media=[f'{SITE}/{m["file"]}' for m in p['media']], alt=[m['alt'] for m in p['media']],
            caption=p['caption'], first_comment=p['first_comment'], accent=accent_for(folder))
    for s in minerals:
        key = f'minerals/{s["slug"]}'
        items[key] = dict(
            id=key, set='minerals', type='carousel', title=s['title'], link=s['link'],
            media=[f'{SITE}/minerals/{m["file"]}' for m in s['media']], alt=[m['alt'] for m in s['media']],
            caption=s['caption'], first_comment=s['first_comment'], accent=accent_for(key),
            photo_credit=s['photo_credit'])
    missing = [i for i in ORDER if i not in items]
    assert not missing, f'unknown ids in ORDER: {missing}'
    queue = []
    for i in ORDER:
        if i in PUBLISHED:
            continue
        it = items[i]
        it['story'] = f'{SITE}/stories/{i.replace("/", "-")}.jpg'
        it['story_file'] = f'stories/{i.replace("/", "-")}.jpg'
        it['story_link'] = it['link']
        queue.append(it)
    out = dict(account='https://instagram.com/mineralwatch', generated=dt.date.today().isoformat(),
               published=sorted(PUBLISHED), rule='publish queue[0] whose caption first line is not already on the account',
               queue=queue)
    with open(f'{SOCIAL}/queue.json', 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f'{len(queue)} items queued -> social/instagram/queue.json')
    for it in queue:
        print(f'  {it["id"]:32s} {it["type"]:8s} {len(it["media"])} img  {it["link"]}')


if __name__ == '__main__':
    main()
