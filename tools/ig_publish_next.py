#!/usr/bin/env python3
"""Publish the next queued mineral.watch Instagram post (+ first comment + announcement Story)
through the Instagram Graph API. Designed to run unattended once a day (cloud routine).

Prerequisites (one-off, done by the account owner):
  * @mineralwatch is an Instagram Professional account (Business or Creator) linked to a
    Facebook Page; a Meta app with instagram_basic, instagram_content_publish,
    instagram_manage_comments, instagram_manage_insights, pages_read_engagement.
  * A long-lived (60-day) user access token for that app, and the IG user id.
  * Environment variables: IG_ACCESS_TOKEN, IG_USER_ID  (optional: IG_GRAPH_VERSION, IG_TZ,
    IG_QUEUE_URL, IG_BEST_HOUR).
  * The media must be publicly reachable: the queue lists https://mineral.watch/... URLs,
    so the social/instagram/ folder (incl. minerals/ and stories/) must be committed.

Idempotency: the script never keeps state. It reads the account's recent media and treats a
queue item as published when the first line of its caption already appears on the account.
It also refuses to post twice within 20 hours (--min-gap-hours).

Usage:
  python3 tools/ig_publish_next.py                 # dry run: shows what WOULD be posted
  python3 tools/ig_publish_next.py --live          # publish
  python3 tools/ig_publish_next.py --live --respect-best-hour   # for an hourly cron: only
        post once the account's best hour (online_followers insight, fallback IG_BEST_HOUR=11
        local) has been reached today
Exit codes: 0 posted or nothing to do · 2 configuration error · 3 API error.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE_URL = os.environ.get('IG_QUEUE_URL', 'https://mineral.watch/social/instagram/queue.json')
QUEUE_LOCAL = f'{ROOT}/social/instagram/queue.json'
GRAPH = f'https://graph.facebook.com/{os.environ.get("IG_GRAPH_VERSION", "v23.0")}'
TZ = ZoneInfo(os.environ.get('IG_TZ', 'Europe/Rome'))
TOKEN = os.environ.get('IG_ACCESS_TOKEN', '')
IG_USER = os.environ.get('IG_USER_ID', '')


def log(msg):
    print(f'[{dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M %Z")}] {msg}', flush=True)


def api(method, path, **params):
    params['access_token'] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    url = f'{GRAPH}/{path}'
    req = urllib.request.Request(url + ('?' + data.decode() if method == 'GET' else ''), data=None if method == 'GET' else data, method=method)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors='replace')
            try:
                err = json.loads(body).get('error', {})
            except ValueError:
                err = {'message': body[:300]}
            transient = e.code >= 500 or err.get('code') in (1, 2, 4, 17, 32, 613)
            if transient and attempt < 3:
                wait = 15 * (attempt + 1)
                log(f'  transient API error {e.code} {err.get("message")!r}; retry in {wait}s')
                time.sleep(wait)
                continue
            raise SystemExit(f'API error {e.code} on {method} {path}: {err.get("message")} (code {err.get("code")}, subcode {err.get("error_subcode")})') from None


def load_queue():
    try:
        with urllib.request.urlopen(QUEUE_URL, timeout=30) as r:
            q = json.load(r)
            log(f'queue: {QUEUE_URL} ({len(q["queue"])} items)')
            return q
    except Exception as e:  # noqa: BLE001
        log(f'queue URL failed ({e}); using local {QUEUE_LOCAL}')
        return json.load(open(QUEUE_LOCAL))


def first_line(s):
    return (s or '').strip().split('\n', 1)[0].strip().lower()


def published_media():
    out, path, params = [], f'{IG_USER}/media', dict(fields='id,caption,timestamp,permalink,media_type', limit=50)
    for _ in range(4):
        page = api('GET', path, **params)
        out += page.get('data', [])
        nxt = page.get('paging', {}).get('cursors', {}).get('after')
        if not nxt or not page.get('paging', {}).get('next'):
            break
        params['after'] = nxt
    return out


def wait_ready(container_id, what, timeout=180):
    t0 = time.time()
    while True:
        st = api('GET', container_id, fields='status_code,status')
        code = st.get('status_code')
        if code == 'FINISHED':
            return
        if code in ('ERROR', 'EXPIRED'):
            raise SystemExit(f'{what} container {container_id} failed: {st}')
        if time.time() - t0 > timeout:
            raise SystemExit(f'{what} container {container_id} not ready after {timeout}s: {st}')
        time.sleep(5)


def publish_item(item):
    if item['type'] == 'carousel':
        children = []
        for url in item['media']:
            c = api('POST', f'{IG_USER}/media', image_url=url, is_carousel_item='true')
            children.append(c['id'])
            log(f'  child container {c["id"]} <- {url.rsplit("/", 1)[1]}')
        for cid in children:
            wait_ready(cid, 'carousel child')
        cont = api('POST', f'{IG_USER}/media', media_type='CAROUSEL', children=','.join(children), caption=item['caption'])
    else:
        cont = api('POST', f'{IG_USER}/media', image_url=item['media'][0], caption=item['caption'])
    wait_ready(cont['id'], 'post')
    pub = api('POST', f'{IG_USER}/media_publish', creation_id=cont['id'])
    media_id = pub['id']
    info = api('GET', media_id, fields='permalink')
    log(f'  published {item["type"]} -> {info.get("permalink")}')
    return media_id, info.get('permalink')


def publish_comment(media_id, text):
    c = api('POST', f'{media_id}/comments', message=text)
    log(f'  first comment {c.get("id")}')


def publish_story(item):
    if not item.get('story'):
        return None
    try:
        cont = api('POST', f'{IG_USER}/media', media_type='STORIES', image_url=item['story'])
        wait_ready(cont['id'], 'story')
        pub = api('POST', f'{IG_USER}/media_publish', creation_id=cont['id'])
        log(f'  story published {pub["id"]} (link sticker to {item["story_link"]} must be added in the app; the URL is printed on the image)')
        return pub['id']
    except SystemExit as e:
        log(f'  story NOT published: {e}')
        return None


def best_hour():
    """Hour (local) with most followers online, from the online_followers insight; fallback IG_BEST_HOUR."""
    fallback = int(os.environ.get('IG_BEST_HOUR', '11'))
    try:
        ins = api('GET', f'{IG_USER}/insights', metric='online_followers', period='lifetime')
        values = ins['data'][0]['values'][-1]['value']  # {"0": n, ..., "23": n} in UTC
        hour_utc = max(values, key=lambda h: values[h])
        local = dt.datetime.now(dt.timezone.utc).replace(hour=int(hour_utc), minute=0).astimezone(TZ).hour
        return local
    except Exception as e:  # noqa: BLE001
        log(f'  online_followers insight unavailable ({e}); best hour fallback {fallback}:00')
        return fallback


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--live', action='store_true', help='actually publish (default is a dry run)')
    ap.add_argument('--respect-best-hour', action='store_true', help='exit without posting until the best hour of the day has arrived')
    ap.add_argument('--min-gap-hours', type=float, default=20)
    ap.add_argument('--story', dest='story', action='store_true', default=True)
    ap.add_argument('--no-story', dest='story', action='store_false')
    a = ap.parse_args()

    q = load_queue()
    if not TOKEN or not IG_USER:
        log('IG_ACCESS_TOKEN / IG_USER_ID not set -> dry run against the queue only')
        nxt = q['queue'][0] if q['queue'] else None
        if nxt:
            log(f'would publish: {nxt["id"]} ({nxt["type"]}, {len(nxt["media"])} image(s)) -> {nxt["link"]}')
        sys.exit(0 if not a.live else 2)

    media = published_media()
    done = {first_line(m.get('caption')) for m in media}
    last = max((dt.datetime.fromisoformat(m['timestamp'].replace('+0000', '+00:00')) for m in media if m.get('timestamp')), default=None)
    log(f'account has {len(media)} media; last post {last.astimezone(TZ).strftime("%Y-%m-%d %H:%M") if last else "none"}')
    if last and (dt.datetime.now(dt.timezone.utc) - last) < dt.timedelta(hours=a.min_gap_hours):
        log(f'already posted within the last {a.min_gap_hours:g}h -> nothing to do')
        return
    pending = [it for it in q['queue'] if first_line(it['caption']) not in done]
    if not pending:
        log('queue exhausted: everything has been published')
        return
    item = pending[0]
    log(f'next: {item["id"]} ({item["type"]}, {len(item["media"])} image(s)) -> {item["link"]}; {len(pending) - 1} left after this')

    if a.respect_best_hour:
        bh = best_hour()
        now = dt.datetime.now(TZ)
        if now.hour < bh and now.hour < 20:
            log(f'best hour is {bh}:00 local; it is {now:%H:%M} -> waiting for a later run')
            return

    if not a.live:
        log('dry run (add --live to publish). Caption first line: ' + first_line(item['caption']))
        return

    media_id, permalink = publish_item(item)
    if item.get('first_comment'):
        try:
            publish_comment(media_id, item['first_comment'])
        except SystemExit as e:
            log(f'  first comment failed: {e}')
    story_id = publish_story(item) if a.story else None
    print(json.dumps(dict(posted=item['id'], permalink=permalink, media_id=media_id, story_id=story_id,
                          link=item['link'], remaining=len(pending) - 1), indent=2))


if __name__ == '__main__':
    main()
