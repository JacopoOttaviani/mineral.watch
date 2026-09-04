# mineral.watch · Instagram launch set

15 ready-to-schedule posts for [instagram.com/mineralwatch](https://instagram.com/mineralwatch):
11 single images and 4 carousels (42 images in total), every slide 1080×1350 (4:5) PNG, built from the
site's own palette (`#0d1117` background, `#e6edf3` ink, lime `#c8ff6b`, and each dashboard's accent
colour) with the network-diamond mark and a "visit mineral.watch" footer on every slide.

## What's in this folder

| File | Use |
|---|---|
| `NN-slug/post.png` | single-image post |
| `NN-slug/slide-01.png` … | carousel slides, in swipe order |
| `captions.md` | caption, first-comment hashtags and alt text for each post, human-readable |
| `posts.json` | the same data as a manifest for automation (order, date, type, media files, caption, first comment, link) |
| `schedule.csv` | one row per post: `post, date, time, type, slides, media_files (semicolon-separated), caption, first_comment, link` |
| `_contact-sheet.png` | all 15 covers at a glance |

## Suggested cadence

Mon / Wed / Fri at 12:00, from 2026-09-04 to 2026-10-07 (dates in `schedule.csv`; set the timezone in
your scheduler). Post 01 is the launch card, 02 the nine-minerals carousel, 15 the "hire us" call to
action; the middle posts alternate single infographics and story carousels so no two consecutive posts
share a mineral or a format.

## Automating

- **Meta Business Suite / Creator Studio:** upload each folder's PNGs as a post (carousel folders as one
  multi-image post, slides in numeric order), paste the caption from `captions.md`, schedule to the
  date in `schedule.csv`, then add the hashtag line as the first comment.
- **Buffer, Later, Metricool, Hootsuite:** most accept a CSV bulk upload. Map `date`+`time` to the
  schedule column, `caption` to the post text and attach the files listed in `media_files`
  (some tools need public URLs: upload the PNGs somewhere first, or commit this folder so they are
  served at `https://mineral.watch/social/instagram/...`). Carousels usually have to be created by hand.
- **Instagram Graph API:** `posts.json` has everything a script needs: `media[].file` (public URL
  required by the API), `caption`, `first_comment` and `date`.

Profile link: `https://mineral.watch`. Every caption ends with the dashboard URL and "link in bio".

## Regenerating

```bash
python3 tools/gen_instagram_posts.py          # all 15 posts
python3 tools/gen_instagram_posts.py 04 07    # only posts 4 and 7
```

Requires Google Chrome (headless render at 2×) and Pillow. Copy, figures and colours live in the
`POSTS` builders in `tools/gen_instagram_posts.py`; the figures mirror `llms.txt`, so update both when a
dashboard's data refreshes.
