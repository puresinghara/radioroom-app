import os
import json
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone

INNERTUBE_KEY = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'
SEARCH_URL = f'https://www.youtube.com/youtubei/v1/search?key={INNERTUBE_KEY}'
BROWSE_URL = f'https://www.youtube.com/youtubei/v1/browse?key={INNERTUBE_KEY}'

HEADERS = {
    'Content-Type': 'application/json',
    'Accept-Language': 'th-TH,th;q=0.9,en;q=0.5',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
}

OUT_PATHS = ['ghost_episodes.json', 'www/ghost_episodes.json']

# Every (channel, category) group the app shows. A group whose source could not be fetched keeps its previous data.
GROUPS = [
    ('ghost', 'latest'), ('ghost', 'monthly'), ('ghost', 'yearly'), ('ghost', 'alltime'),
    ('gungun', 'latest'), ('gungun', 'popular'),
    ('cloudsphere', 'general'), ('cloudsphere', 'spooky'),
]

MONTHS_ABBR = {'ม.ค.': 1, 'ก.พ.': 2, 'มี.ค.': 3, 'เม.ย.': 4, 'พ.ค.': 5, 'มิ.ย.': 6,
               'ก.ค.': 7, 'ส.ค.': 8, 'ก.ย.': 9, 'ต.ค.': 10, 'พ.ย.': 11, 'ธ.ค.': 12}
MONTHS_FULL = {'มกราคม': 1, 'กุมภาพันธ์': 2, 'มีนาคม': 3, 'เมษายน': 4, 'พฤษภาคม': 5, 'มิถุนายน': 6,
               'กรกฎาคม': 7, 'สิงหาคม': 8, 'กันยายน': 9, 'ตุลาคม': 10, 'พฤศจิกายน': 11, 'ธันวาคม': 12}
_ALL_MONTHS = {**MONTHS_FULL, **MONTHS_ABBR}
# longest names first so "พฤศจิกายน" is tried before "พ.ย." etc.
_MONTH_ALT = '|'.join(re.escape(m) for m in sorted(_ALL_MONTHS, key=len, reverse=True))
DATE_TEXT_RE = re.compile(r'(\d{1,2})\s*(' + _MONTH_ALT + r')\s*(\d{2,4})')
DATE_NUM_RE = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4})')
WEEKDAY_RE = re.compile(r'วัน(?:จันทร์|อังคาร|พุธ|พฤหัสบดี|ศุกร์|เสาร์|อาทิตย์)ที่')


def to_ce_year(y):
    """Thai pages use Buddhist years (2569 or the short 69); convert to a Gregorian year."""
    if y < 100:
        y += 2500
    if y > 2400:
        y -= 543
    return y


def find_title_date(text):
    """First absolute date written in a title (Thai month names or d/m/yyyy), as a UTC datetime, else None."""
    for m in DATE_TEXT_RE.finditer(text or ''):
        try:
            return datetime(to_ce_year(int(m.group(3))), _ALL_MONTHS[m.group(2)], int(m.group(1)), 12, tzinfo=timezone.utc)
        except ValueError:
            continue
    for m in DATE_NUM_RE.finditer(text or ''):
        try:
            return datetime(to_ce_year(int(m.group(3))), int(m.group(2)), int(m.group(1)), 12, tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def is_date_like(s):
    s = (s or '').strip()
    if not s:
        return False
    if not (DATE_TEXT_RE.search(s) or DATE_NUM_RE.search(s)):
        return False
    rest = DATE_NUM_RE.sub('', DATE_TEXT_RE.sub('', s))
    rest = WEEKDAY_RE.sub('', rest).strip(' |-•')
    return len(rest) <= 3


_REL_RE = re.compile(r'(\d+)\s*(นาที|ชั่วโมง|วัน|สัปดาห์|เดือน|ปี)')
_REL_UNIT = {
    'นาที': (timedelta(minutes=1), 3),
    'ชั่วโมง': (timedelta(hours=1), 3),
    'วัน': (timedelta(days=1), 3),
    'สัปดาห์': (timedelta(weeks=1), 10),
    'เดือน': (timedelta(days=30), 45),
    'ปี': (timedelta(days=365), 400),
}


def rel_to_dt(text, now):
    """"3 วันที่ผ่านมา" -> (datetime, tolerance_days). None if the text has no relative age."""
    m = _REL_RE.search(text or '')
    if not m:
        return None
    unit, tol = _REL_UNIT[m.group(2)]
    return now - unit * int(m.group(1)), tol


def make_ts(raw_title, published_text, now):
    """Best estimate of when the video was published, as an ISO UTC string.

    The relative age YouTube gives ("2 months ago") is only as precise as its unit, so when the title carries an
    exact date that agrees with it, the title date wins.
    """
    rel = rel_to_dt(published_text, now)
    title_dt = find_title_date(raw_title)
    dt = None
    if title_dt and title_dt <= now + timedelta(days=1):
        if rel is None or abs(title_dt - rel[0]) <= timedelta(days=rel[1]):
            dt = title_dt
    if dt is None and rel is not None:
        dt = rel[0]
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ') if dt else ''


def parse_views_num(view_str):
    if not view_str:
        return 0
    s = view_str.replace('การดู', '').replace('ครั้ง', '').replace(',', '').strip()
    mult = 1.0
    if 'ล้าน' in s:
        mult = 1000000.0
        s = s.replace('ล้าน', '').strip()
    elif 'แสน' in s:
        mult = 100000.0
        s = s.replace('แสน', '').strip()
    elif 'หมื่น' in s:
        mult = 10000.0
        s = s.replace('หมื่น', '').strip()
    elif 'พัน' in s:
        mult = 1000.0
        s = s.replace('พัน', '').strip()
    try:
        return float(s) * mult
    except Exception:
        return 0


def clean_ghost_title_author(raw_title):
    t = raw_title
    for suffix in [
        '| The Ghost Radio เรื่องเล่าผีเดอะโกส',
        '| THE GHOST RADIO เรื่องเล่าผีเดอะโกส',
        '| The Ghost Radio',
        '| THE GHOST RADIO',
        'TheGhostRadio',
        'เรื่องเล่าผีเดอะโกส'
    ]:
        t = t.replace(suffix, '')

    t = t.strip(' |-\t\n\r')
    author = 'The Ghost Radio'
    clean_title = t

    if 'คุณ' in t:
        idx = t.find('คุณ')
        clean_title = t[:idx].strip(' |-•')
        author_part = t[idx:]
        author = author_part.split('|')[0].strip()
    elif '|' in t:
        parts = [p.strip(' |-•\t') for p in t.split('|')]
        parts = [p for p in parts if p]
        clean_title = parts[0] if parts else t
        rest = parts[1:]
        # The remaining segments are either the author or just a date / boilerplate
        for p in rest:
            if is_date_like(p) or p.startswith(('สนับสนุน', 'I', 'ฟัง')):
                continue
            author = p
            break
        # Titles like "THE GHOST RADIO | ฟังย้อนหลัง | วันอาทิตย์ที่ 1 พฤศจิกายน 2569": the real title is in the
        # later segments, so keep them instead of the bare channel name.
        if clean_title.replace(' ', '').lower() == 'theghostradio':
            extra = [p for p in rest if p and not p.lower().replace(' ', '').startswith('theghostradio')]
            if extra:
                clean_title = ' • '.join(extra)
                author = 'The Ghost Radio'

    # A date can never be an author
    if is_date_like(author):
        author = 'The Ghost Radio'
    clean_title = clean_title.strip(' |-•')
    if not clean_title:
        clean_title = raw_title

    return clean_title, author


def post_json(url, payload, tries=3):
    data = json.dumps(payload).encode('utf-8')
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    print(f"Request failed after {tries} tries: {last}")
    return None


def web_context(version='2.20261026.01.00'):
    return {'client': {'clientName': 'WEB', 'clientVersion': version, 'hl': 'th', 'gl': 'TH'}}


def browse_lockups(browse_id, version='2.20261026.01.00'):
    data = post_json(BROWSE_URL, {'context': web_context(version), 'browseId': browse_id})
    if not data:
        return []
    items = []
    for tab in data.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', []):
        for sec in tab.get('tabRenderer', {}).get('content', {}).get('sectionListRenderer', {}).get('contents', []):
            items.extend(sec.get('itemSectionRenderer', {}).get('contents', []))
    out = []
    for it in items:
        lvm = it.get('lockupViewModel')
        if not lvm:
            continue
        vid = lvm.get('contentId')
        if not vid and 'contentImage' in lvm:
            for ov in lvm['contentImage'].get('thumbnailViewModel', {}).get('overlays', []):
                for b in ov.get('thumbnailBottomOverlayViewModel', {}).get('badges', []):
                    target = b.get('thumbnailBadgeViewModel', {}).get('animationActivationTargetId')
                    if target:
                        vid = target
                        break
        meta = lvm.get('metadata', {}).get('lockupMetadataViewModel', {})
        raw_title = meta.get('title', {}).get('content', '')
        views = ''
        published = ''
        rows = meta.get('metadata', {}).get('contentMetadataViewModel', {}).get('metadataRows', [])
        if len(rows) >= 2:
            parts = rows[1].get('metadataParts', [])
            if len(parts) >= 1:
                views = parts[0].get('text', {}).get('content', '')
            if len(parts) >= 2:
                published = parts[1].get('text', {}).get('content', '')
        if vid and raw_title:
            out.append({'id': vid, 'raw_title': raw_title, 'views_text': views, 'published': published})
    return out


def make_episode(channel, cat, raw, title, author, now):
    return {
        'channel': channel,
        'cat': cat,
        'title': title,
        'author': author,
        'id': raw['id'],
        'tag': raw['views_text'],
        'date': raw['published'],
        'views': int(parse_views_num(raw['views_text'])),
        'ts': make_ts(raw['raw_title'], raw['published'], now),
    }


def dedupe(episodes):
    seen = set()
    out = []
    for e in episodes:
        if e['id'] in seen:
            continue
        seen.add(e['id'])
        out.append(e)
    return out


def ghost_from_raw(raws, cat, now):
    eps = []
    for r in raws:
        title, author = clean_ghost_title_author(r['raw_title'])
        eps.append(make_episode('ghost', cat, r, title, author, now))
    return eps


def fetch_ghost_uploads(now, max_count=100):
    raws = browse_lockups('VLUUM246zZ4qNNmFQ2WHnP_CRA')
    return ghost_from_raw(raws[:max_count], 'latest', now)


def search_videos(query):
    data = post_json(SEARCH_URL, {'context': web_context(), 'query': query})
    if not data:
        return []
    out = []
    contents = data.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', [])
    for section in contents:
        for item in section.get('itemSectionRenderer', {}).get('contents', []):
            vr = item.get('videoRenderer')
            if not vr:
                continue
            vid = vr.get('videoId')
            raw_title = vr.get('title', {}).get('runs', [{}])[0].get('text', '')
            if vid and raw_title:
                out.append({
                    'id': vid,
                    'raw_title': raw_title,
                    'views_text': vr.get('viewCountText', {}).get('simpleText', ''),
                    'published': vr.get('publishedTimeText', {}).get('simpleText', ''),
                })
    return out


def fetch_ghost_search(queries, cat, now):
    raws = []
    for q in queries:
        raws.extend(search_videos(q))
    return dedupe(ghost_from_raw(raws, cat, now))


def parse_ts(ep):
    try:
        return datetime.strptime(ep.get('ts', ''), '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except Exception:
        return None


def by_views(episodes):
    return sorted(episodes, key=lambda e: e.get('views', 0), reverse=True)


def as_cat(episodes, cat):
    out = []
    for e in episodes:
        c = dict(e)
        c['cat'] = cat
        out.append(c)
    return out


def fetch_gungun_episodes(now):
    print("Fetching Gun Gun episodes from channel...")
    raws = browse_lockups('VLUUKKAr1SG8RZta9NLquSP_ig')
    eps = [make_episode('gungun', 'latest', r, r['raw_title'], 'GUN GUN', now) for r in raws]
    # NOTE: "popular" is ranked among the newest uploads the channel page returns (not the whole channel)
    return {
        ('gungun', 'latest'): as_cat(eps[:20], 'latest'),
        ('gungun', 'popular'): as_cat(by_views(eps)[:20], 'popular'),
    }, len(eps)


def fetch_cloudsphere_playlist(pl_id, cat, now, limit=20):
    raws = browse_lockups(f'VL{pl_id}', version='2.20241025.01.00')
    eps = [make_episode('cloudsphere', cat, r, r['raw_title'], 'CLOUDSPHERE', now) for r in raws[:limit]]
    print(f"CloudSphere ({cat}): {len(eps)} episodes")
    return eps


def load_previous():
    for path in OUT_PATHS:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
        except Exception:
            continue
    return []


def main():
    print("Fetching fresh The Ghost Radio, Gun Gun & CloudSphere episodes...")
    now = datetime.now(timezone.utc)
    fresh = {}      # (channel, cat) -> episodes, only for groups whose source answered
    year = now.year
    be_year = year + 543

    # 1. Ghost Radio uploads: "latest" is the newest 20; "monthly" is the most-viewed of the last 31 days
    uploads = fetch_ghost_uploads(now, 100)
    if len(uploads) < 5:
        print("Uploads page returned too little, falling back to search")
        uploads = fetch_ghost_search(['The Ghost Radio ตอนล่าสุด'], 'latest', now)
    if uploads:
        fresh[('ghost', 'latest')] = uploads[:20]
        cutoff = now - timedelta(days=31)
        recent = [e for e in uploads if (parse_ts(e) or now) >= cutoff]
        fresh[('ghost', 'monthly')] = as_cat(by_views(recent)[:20], 'monthly')
    print(f"Ghost: latest {len(fresh.get(('ghost', 'latest'), []))}, monthly {len(fresh.get(('ghost', 'monthly'), []))}")

    # 2. Ghost Radio - best of this year (search, then keep only this year's, most viewed first)
    pool = fetch_ghost_search([
        'The Ghost Radio เรื่องยอดนิยม ประจำปี',
        f'The Ghost Radio เรื่องยอดนิยม ปี {be_year}',
        f'The Ghost Radio เรื่องหลอน ยอดนิยม {be_year}',
    ], 'yearly', now)
    if pool:
        this_year = [e for e in pool if (parse_ts(e) or now).year == year]
        fresh[('ghost', 'yearly')] = by_views(this_year)[:20]
    print(f"Ghost: yearly {len(fresh.get(('ghost', 'yearly'), []))} (from {len(pool)} candidates)")

    # 3. Ghost Radio - all-time classics
    classics = fetch_ghost_search(['The Ghost Radio เรื่องดัง หลอนตลอดกาล'], 'alltime', now)
    if classics:
        fresh[('ghost', 'alltime')] = by_views(classics)[:20]
    print(f"Ghost: alltime {len(fresh.get(('ghost', 'alltime'), []))}")

    # 4. Gun Gun
    gg, gg_count = fetch_gungun_episodes(now)
    if gg_count:
        fresh.update(gg)
    print(f"Gun Gun: {len(gg.get(('gungun', 'latest'), []))} latest, {len(gg.get(('gungun', 'popular'), []))} popular")

    # 5. CloudSphere
    for cat, pl in (('general', 'PLunG2ZUbd-Yyc0SLUjSI1fBFFrnUxkX4O'), ('spooky', 'PLunG2ZUbd-YyHFGS3BEm_SM7Od6bxfO7D')):
        eps = fetch_cloudsphere_playlist(pl, cat, now)
        if eps:
            fresh[('cloudsphere', cat)] = eps

    # A group whose source failed keeps its previous data instead of dropping the whole update
    previous = load_previous()
    all_episodes = []
    stale_groups = []
    for key in GROUPS:
        items = fresh.get(key)
        if items is None:
            items = [e for e in previous if (e.get('channel') or 'ghost') == key[0] and e.get('cat') == key[1]]
            stale_groups.append(f"{key[0]}/{key[1]} ({len(items)} kept)")
        all_episodes.extend(items)

    if stale_groups:
        print("Kept previous data for: " + ", ".join(stale_groups))
    print(f"Fresh groups: {len(fresh)}/{len(GROUPS)}; total episodes: {len(all_episodes)}")
    if not fresh:
        print("Nothing could be fetched, keeping previous JSON untouched.")
        return

    for out_path in OUT_PATHS:
        try:
            folder = os.path.dirname(out_path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(all_episodes, f, ensure_ascii=False, indent=2)
            print(f"Successfully saved {len(all_episodes)} episodes to {out_path}")
        except Exception as e:
            print(f"Error writing to {out_path}: {e}")


if __name__ == '__main__':
    main()
