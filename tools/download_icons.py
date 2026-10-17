#!/usr/bin/env python3
"""
download_icons.py — ดาวน์โหลด icon ทุก hero จาก rovmeta HTML แล้วบันทึกเป็น <heroId>.jpg
ใช้ใน GitHub Action ก่อน parse_heroes.py
"""
import json, os, re, time, requests
from pathlib import Path
from html.parser import HTMLParser


class ImgExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.imgs = []
        self.skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ['script','style']: self.skip = True
        if tag == 'img':
            d = dict(attrs)
            src = d.get('src','')
            if 'cdn-webth' in src:
                self.imgs.append((src, d.get('alt',''), d.get('width',''), d.get('height','')))
    def handle_endtag(self, tag):
        if tag in ['script','style']: self.skip = False


def best_icon_url(html: str) -> str | None:
    p = ImgExtractor()
    p.feed(html)
    # img CDN แรกสุดในหน้าคือรูปของ hero นั้นเสมอ
    for src, alt, w, h in p.imgs:
        if 'cdn-webth' in src:
            return src
    return None


def main():
    html_dir  = Path('out/rovmeta_raw')
    icons_dir = Path('out/icons')
    icons_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36',
        'Referer': 'https://rovmeta.com/',
        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
    })

    results = {}
    ok = fail = skip = 0

    for html_file in sorted(html_dir.glob('*.html')):
        if html_file.name.startswith('_'): continue
        slug = html_file.stem
        dest = icons_dir / f'{slug}.jpg'

        html = html_file.read_text(encoding='utf-8', errors='ignore')
        url = best_icon_url(html)

        if not url:
            print(f'  NO URL  {slug}')
            fail += 1
            continue

        if dest.exists() and dest.stat().st_size > 2000:
            print(f'  cached  {slug}')
            results[slug] = url
            skip += 1
            continue

        try:
            r = session.get(url, timeout=12)
            if r.status_code == 200 and len(r.content) > 1000:
                dest.write_bytes(r.content)
                results[slug] = url
                print(f'  ok      {slug}  ({len(r.content)//1024}KB)')
                ok += 1
            else:
                print(f'  HTTP {r.status_code}  {slug}')
                fail += 1
        except Exception as e:
            print(f'  ERROR   {slug}: {e}')
            fail += 1

        time.sleep(0.25)  # ไม่ spam server

    # บันทึก icon_map.json สำหรับ parse_heroes.py
    icon_map_path = Path('out/icon_map.json')
    with open(icon_map_path, 'w') as f:
        json.dump(results, f, indent=1)

    print(f'\n✅ ok={ok}  skip={skip}  fail={fail}')
    print(f'   icons → {icons_dir}  ({len(list(icons_dir.glob("*.jpg")))} files)')


if __name__ == '__main__':
    main()
