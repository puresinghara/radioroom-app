import os
import json
import re
import urllib.request

INNERTUBE_KEY = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'
SEARCH_URL = f'https://www.youtube.com/youtubei/v1/search?key={INNERTUBE_KEY}'
BROWSE_URL = f'https://www.youtube.com/youtubei/v1/browse?key={INNERTUBE_KEY}'

HEADERS = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
}

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
        if '|' in author_part:
            author = author_part.split('|')[0].strip()
        else:
            author = author_part.strip()
    elif '|' in t:
        parts = t.split('|')
        clean_title = parts[0].strip(' |-•')
        if len(parts) > 1:
            p1 = parts[1].strip()
            if not (p1.startswith('สนับสนุน') or p1.startswith('I') or p1.startswith('ฟัง')):
                author = p1
    
    if not clean_title:
        clean_title = raw_title
    
    return clean_title, author

def fetch_ghost_uploads(browse_id='VLUUM246zZ4qNNmFQ2WHnP_CRA', max_count=20):
    payload = {
        'context': {
            'client': {
                'clientName': 'WEB',
                'clientVersion': '2.20261026.01.00',
                'hl': 'th',
                'gl': 'TH'
            }
        },
        'browseId': browse_id
    }
    req = urllib.request.Request(BROWSE_URL, data=json.dumps(payload).encode('utf-8'), headers=HEADERS)
    episodes = []
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            tabs = data.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', [])
            items = []
            for tab in tabs:
                sec_list = tab.get('tabRenderer', {}).get('content', {}).get('sectionListRenderer', {}).get('contents', [])
                for sec in sec_list:
                    items.extend(sec.get('itemSectionRenderer', {}).get('contents', []))
            
            for it in items:
                if 'lockupViewModel' in it:
                    lvm = it['lockupViewModel']
                    vid = lvm.get('contentId')
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
                        c_title, c_author = clean_ghost_title_author(raw_title)
                        episodes.append({
                            'channel': 'ghost',
                            'cat': 'latest',
                            'title': c_title,
                            'author': c_author,
                            'id': vid,
                            'tag': views,
                            'date': published
                        })
                        if len(episodes) >= max_count:
                            break
    except Exception as e:
        print(f"Error fetching channel uploads: {e}")
    return episodes

def fetch_ghost_category(query, cat_name, max_count=20):
    payload = {
        'context': {
            'client': {
                'clientName': 'WEB',
                'clientVersion': '2.20261026.01.00',
                'hl': 'th',
                'gl': 'TH'
            }
        },
        'query': query
    }
    req = urllib.request.Request(SEARCH_URL, data=json.dumps(payload).encode('utf-8'), headers=HEADERS)
    episodes = []
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            contents = data.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', [])
            for section in contents:
                items = section.get('itemSectionRenderer', {}).get('contents', [])
                for item in items:
                    vr = item.get('videoRenderer')
                    if not vr:
                        continue
                    vid = vr.get('videoId')
                    raw_title = vr.get('title', {}).get('runs', [{}])[0].get('text', '')
                    views = vr.get('viewCountText', {}).get('simpleText', '')
                    published = vr.get('publishedTimeText', {}).get('simpleText', '')
                    
                    if vid and raw_title:
                        c_title, c_author = clean_ghost_title_author(raw_title)
                        episodes.append({
                            'channel': 'ghost',
                            'cat': cat_name,
                            'title': c_title,
                            'author': c_author,
                            'id': vid,
                            'tag': views,
                            'date': published
                        })
                        if len(episodes) >= max_count:
                            break
                if len(episodes) >= max_count:
                    break
    except Exception as e:
        print(f"Error fetching category {cat_name}: {e}")
    return episodes

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
    except:
        return 0

def fetch_gungun_episodes():
    print("Fetching Gun Gun episodes from channel...")
    payload = {
        'context': {
            'client': {
                'clientName': 'WEB',
                'clientVersion': '2.20261026.01.00',
                'hl': 'th',
                'gl': 'TH'
            }
        },
        'browseId': 'VLUUKKAr1SG8RZta9NLquSP_ig'
    }
    req = urllib.request.Request(BROWSE_URL, data=json.dumps(payload).encode('utf-8'), headers=HEADERS)
    raw_list = []
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            tabs = data.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', [])
            items = []
            for tab in tabs:
                sec_list = tab.get('tabRenderer', {}).get('content', {}).get('sectionListRenderer', {}).get('contents', [])
                for sec in sec_list:
                    items.extend(sec.get('itemSectionRenderer', {}).get('contents', []))
            
            for it in items:
                if 'lockupViewModel' in it:
                    lvm = it['lockupViewModel']
                    vid = lvm.get('contentId')
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
                        raw_list.append({
                            'channel': 'gungun',
                            'title': raw_title,
                            'author': 'GUN GUN',
                            'id': vid,
                            'tag': views,
                            'date': published,
                            '_view_num': parse_views_num(views)
                        })
    except Exception as e:
        print(f"Error fetching Gun Gun: {e}")
    
    latest = []
    for ep in raw_list[:20]:
        item = dict(ep)
        item['cat'] = 'latest'
        item.pop('_view_num', None)
        latest.append(item)
    
    sorted_popular = sorted(raw_list, key=lambda x: x['_view_num'], reverse=True)
    popular = []
    for ep in sorted_popular[:20]:
        item = dict(ep)
        item['cat'] = 'popular'
        item.pop('_view_num', None)
        popular.append(item)
    
    print(f"Gun Gun: {len(latest)} latest, {len(popular)} popular")
    return latest + popular

def main():
    print("Fetching fresh The Ghost Radio & Gun Gun episodes...")
    all_episodes = []
    
    # 1. Ghost Radio - Latest
    latest_eps = fetch_ghost_uploads('VLUUM246zZ4qNNmFQ2WHnP_CRA', 20)
    if not latest_eps or len(latest_eps) < 5:
        latest_eps = fetch_ghost_category('The Ghost Radio ตอนล่าสุด', 'latest', 20)
    print(f"Fetched {len(latest_eps)} episodes for Ghost: latest")
    all_episodes.extend(latest_eps)
    
    # 2. Ghost Radio - Curated
    other_categories = [
        ('The Ghost Radio เรื่องยอดนิยม ประจำเดือน', 'monthly'),
        ('The Ghost Radio เรื่องยอดนิยม ประจำปี', 'yearly'),
        ('The Ghost Radio เรื่องดัง หลอนตลอดกาล', 'alltime')
    ]
    for query, cat in other_categories:
        eps = fetch_ghost_category(query, cat, 20)
        print(f"Fetched {len(eps)} episodes for Ghost: {cat}")
        all_episodes.extend(eps)
    
    # 3. Gun Gun - Latest & Popular
    gungun_eps = fetch_gungun_episodes()
    all_episodes.extend(gungun_eps)
    
    print(f"Total collected episodes: {len(all_episodes)}")
    if len(all_episodes) >= 40:
        for out_path in ['ghost_episodes.json', 'www/ghost_episodes.json']:
            try:
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(all_episodes, f, ensure_ascii=False, indent=2)
                print(f"Successfully saved {len(all_episodes)} episodes to {out_path}")
            except Exception as e:
                print(f"Error writing to {out_path}: {e}")
    else:
        print("Fetch resulted in insufficient items, keeping previous JSON.")

if __name__ == '__main__':
    main()
