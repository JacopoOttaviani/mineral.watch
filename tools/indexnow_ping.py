#!/usr/bin/env python3
"""Tell Bing, Yandex and the other IndexNow engines which pages changed.

IndexNow (https://www.indexnow.org) is a push protocol: instead of waiting for
a crawl, we POST the changed URLs with a key that is also hosted at the site
root, so the engine can verify we own the domain. Google does not use
IndexNow; it picks up sitemap.xml (submit it once in Search Console).

Run AFTER the changes are live on mineral.watch (the key file must be
reachable at https://mineral.watch/<key>.txt or the request is rejected):

    python3 tools/indexnow_ping.py              # every URL in sitemap.xml
    python3 tools/indexnow_ping.py /copper/ /   # just these paths
"""
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://mineral.watch'
KEY = '1239c5173845fe34d1a35d0f7f494605'
ENDPOINT = 'https://api.indexnow.org/indexnow'  # shared endpoint; fans out to all participating engines


def sitemap_urls():
    return re.findall(r'<loc>(.*?)</loc>', open(f'{ROOT}/sitemap.xml').read())


def main():
    paths = sys.argv[1:]
    urls = [f'{SITE}{p}' for p in paths] if paths else sitemap_urls()
    urls += [f'{SITE}/llms.txt', f'{SITE}/llms-full.txt'] if not paths else []
    body = json.dumps({'host': 'mineral.watch', 'key': KEY, 'keyLocation': f'{SITE}/{KEY}.txt', 'urlList': urls}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={'Content-Type': 'application/json; charset=utf-8'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f'IndexNow: HTTP {r.status} — {len(urls)} URLs submitted')
    except urllib.error.HTTPError as e:
        print(f'IndexNow: HTTP {e.code} {e.reason} — {e.read().decode(errors="replace")[:300]}')
        sys.exit(1)


if __name__ == '__main__':
    main()
