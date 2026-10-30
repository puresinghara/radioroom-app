import os
import json
import re
import urllib.request

INNERTUBE_KEY = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'
SEARCH_URL = f'https://www.youtube.com/youtubei/v1/search?key={INNERTUBE_KEY}'

HEADERS = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
}

def fetch_youtube_category(query, cat_name):
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
                    
                    # Clean up title and author
                    # Pattern example: เรื่อง... คุณ... | The Ghost Radio
                    clean_title = raw_title.replace('| The Ghost Radio', '').replace('| THE GHOST RADIO', '').strip()
                    author = 'The Ghost Radio'
                    if 'คุณ' in clean_title:
                        parts = clean_title.split('คุณ')
                        clean_title = parts[0].strip()
                        author = 'คุณ' + parts[1].strip()
                    
                    views = vr.get('viewCountText', {}).get('simpleText', '')
                    published = vr.get('publishedTimeText', {}).get('simpleText', '')
                    
                    if vid and clean_title:
                        episodes.append({
                            'cat': cat_name,
                            'title': clean_title,
                            'author': author,
                            'id': vid,
                            'tag': views,
                            'date': published
                        })
                        if len(episodes) >= 20:
                            break
                if len(episodes) >= 20:
                    break
    except Exception as e:
        print(f"Error fetching {query}: {e}")
    return episodes

def main():
    print("Fetching fresh The Ghost Radio episodes...")
    categories = [
        ('The Ghost Radio ตอนล่าสุด', 'latest'),
        ('The Ghost Radio ประจำเดือน เรื่องยอดนิยม', 'monthly'),
        ('The Ghost Radio ยอดนิยม ประจำปี', 'yearly'),
        ('The Ghost Radio เรื่องดัง หลอนตลอดกาล', 'alltime')
    ]
    
    all_episodes = []
    for query, cat in categories:
        eps = fetch_youtube_category(query, cat)
        print(f"Fetched {len(eps)} episodes for category: {cat}")
        all_episodes.extend(eps)
    
    if len(all_episodes) >= 20:
        json_path = 'ghost_episodes.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(all_episodes, f, ensure_ascii=False, indent=2)
        print(f"Successfully saved {len(all_episodes)} episodes to {json_path}")
    else:
        print("Fetch resulted in insufficient items, keeping previous JSON.")

if __name__ == '__main__':
    main()
