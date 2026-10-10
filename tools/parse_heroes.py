#!/usr/bin/env python3
"""
parse_heroes.py — แปลง HTML ดิบจาก rovmeta → heroes.json + hero_icons.json
"""
import argparse, json, os, re
from html.parser import HTMLParser
from pathlib import Path


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks = []
        self.skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ['script','style','noscript']: self.skip = True
    def handle_endtag(self, tag):
        if tag in ['script','style','noscript']: self.skip = False
    def handle_data(self, data):
        if not self.skip and data.strip():
            self.blocks.append(data.strip())


def normalize_id(name):
    return name.lower().replace(' ', '-').replace("'", '-').replace('\u2019', '-')


def parse_hero(path):
    with open(path, encoding='utf-8', errors='ignore') as f:
        html = f.read()
    p = TextExtractor()
    p.feed(html)
    lines = p.blocks
    result = {}

    # patch notes
    patch_status, patch_version, patch_changes = None, None, []
    for i, line in enumerate(lines):
        if line in ('Buffed','Nerfed','Adjusted','New','Reworked') and not patch_status:
            patch_status = line
        if line == 'Patch' and i+1 < len(lines) and re.match(r'[\d.]+', lines[i+1]):
            patch_version = lines[i+1].strip()
    in_patch = False
    for i, line in enumerate(lines):
        if line == 'Patch' and i+1 < len(lines) and re.match(r'[\d.]+', lines[i+1]):
            in_patch = True; continue
        if in_patch:
            if line == '•' and i+1 < len(lines): patch_changes.append(lines[i+1])
            elif line in ('ความเห็นทีมงาน','Pro play','Ranked') and patch_changes: break
    if patch_status: result['patchStatus'] = patch_status
    if patch_version: result['patchVersion'] = patch_version
    if patch_changes: result['patchChanges'] = patch_changes

    # จุดแข็ง
    strengths, in_s = [], False
    for i, line in enumerate(lines):
        if line == 'จุดแข็ง': in_s = True; continue
        if in_s:
            if line == 'จุดอ่อน': break
            if line == '✓' and i+1 < len(lines):
                parts, j = [], i+1
                while j < len(lines) and lines[j] not in ('✓','✕','จุดอ่อน','การเจอตัว'):
                    parts.append(lines[j]); j += 1
                if parts: strengths.append(' '.join(parts))
    if strengths: result['strengths'] = strengths

    # จุดอ่อน
    weaknesses, in_w = [], False
    for i, line in enumerate(lines):
        if line == 'จุดอ่อน': in_w = True; continue
        if in_w:
            if line in ('การเจอตัว','ชุดสกิล','กลัวเจอ'): break
            if line == '✕' and i+1 < len(lines):
                parts, j = [], i+1
                while j < len(lines) and lines[j] not in ('✓','✕','การเจอตัว','ชุดสกิล'):
                    parts.append(lines[j]); j += 1
                if parts: weaknesses.append(' '.join(parts))
    if weaknesses: result['weaknesses'] = weaknesses

    # counters / weakTo / synergies
    weak_to, counters, synergies = [], [], []
    state = None
    for line in lines:
        if 'กลัวเจอ' in line: state = 'weak'; continue
        if 'แข็งใส่' in line: state = 'counter'; continue
        if 'เข้าขาดีสุด' in line: state = 'syn'; continue
        if line in ('ชุดสกิล','สกิล','ลำดับสกิล','บิลด์'): state = None; continue
        if state and line and len(line) > 1 and line != '→':
            nid = normalize_id(line)
            if state == 'weak': weak_to.append(nid)
            elif state == 'counter': counters.append(nid)
            elif state == 'syn': synergies.append(nid)
    if weak_to: result['weakTo'] = list(dict.fromkeys(weak_to[:6]))
    if counters: result['counters'] = list(dict.fromkeys(counters[:6]))
    if synergies: result['synergies'] = list(dict.fromkeys(synergies[:6]))

    # skills
    skill_keys = {'PASSIVE':'passive','SKILL 1':'skill1','SKILL 2':'skill2',
                  'SKILL 3':'skill3','ULTIMATE':'ultimate'}
    skills, seen = [], set()
    for i, line in enumerate(lines):
        slot = skill_keys.get(line)
        if slot and slot not in seen and i+1 < len(lines):
            name = lines[i+1]
            desc = lines[i+2].strip('"').strip() if i+2 < len(lines) else ''
            if len(name) > 1 and not name.startswith('•'):
                skills.append({'slot': slot, 'name': name, 'desc': desc})
                seen.add(slot)
    if skills: result['skills'] = skills

    # icon URL จาก portrait
    m = re.search(r'<img src="(https://cdn-webth[^"]+)" alt="[^"]*portrait[^"]*" width="88"', html, re.I)
    if not m:
        m = re.search(r'<img src="(https://cdn-webth[^"]+)"[^>]*width="88"[^>]*height="88"', html)
    if not m:
        m = re.search(r'<img src="(https://cdn-webth[^"]+)" alt="[^"]+ portrait"', html)
    if not m:
        m = re.search(r'<img src="(https://cdn-webth\.garenanow\.com/webth/cdn/gth/rov/[^"]+)"', html)
    if m: result['iconUrl'] = m.group(1)

    # tier + stats
    for line in lines:
        mt = re.search(r'เทียร์\s+([S+\w]+)', line)
        if mt and 'tier' not in result:
            t = mt.group(1)
            result['tier'] = 'S+' if '+' in t and t.startswith('S') else t
            break
    for i, line in enumerate(lines):
        if 'วินเรตโปร' in line and i+1 < len(lines):
            try: result['proWinRate'] = float(lines[i+1])
            except: pass
        if line.strip() == 'พิกเรต' and i+1 < len(lines):
            try: result['proPickRate'] = float(lines[i+1])
            except: pass
        if line.strip() == 'แบนเรต' and i+1 < len(lines):
            try: result['proBanRate'] = float(lines[i+1])
            except: pass

    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--html', default='out/rovmeta_raw')
    ap.add_argument('--base', default='data/heroes_base.json')
    ap.add_argument('--out',  default='out/heroes.json')
    ap.add_argument('--icons-out', default='out/hero_icons.json')
    args = ap.parse_args()

    html_dir = Path(args.html)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(args.base, encoding='utf-8') as f:
        base = json.load(f)

    hero_map = {h['id']: h for h in base['heroes']}
    icons = {}

    ok = err = 0
    for html_file in sorted(html_dir.glob('*.html')):
        if html_file.name.startswith('_'): continue
        slug = html_file.stem
        try:
            extra = parse_hero(html_file)
            icon_url = extra.pop('iconUrl', None)
            if icon_url:
                icons[slug] = icon_url
            if slug in hero_map:
                hero_map[slug].update(extra)
            else:
                entry = {'id': slug, 'name': slug.replace('-',' ').title(),
                         'aliases': [], 'role': 'UNKNOWN', 'lanes': [],
                         'damage': 'PHYSICAL', 'tags': []}
                entry.update(extra)
                base['heroes'].append(entry)
                hero_map[slug] = entry
            ok += 1
        except Exception as e:
            print(f'  WARN {slug}: {e}'); err += 1

    patches = [h.get('patchVersion') for h in base['heroes'] if h.get('patchVersion')]
    if patches:
        base['patch'] = max(set(patches), key=patches.count)

    base['heroes'].sort(key=lambda h: h['name'])

    # บันทึก heroes.json
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(base, f, ensure_ascii=False, indent=1)

    # บันทึก hero_icons.json
    icons_out = Path(args.icons_out)
    icons_data = {
        'patch': base.get('patch', '?'),
        'total': len(icons),
        'heroes': {slug: {'icon_url': url} for slug, url in sorted(icons.items())}
    }
    with open(icons_out, 'w', encoding='utf-8') as f:
        json.dump(icons_data, f, ensure_ascii=False, indent=1)

    has = lambda k: sum(1 for h in base['heroes'] if h.get(k))
    print(f'✅ heroes.json: {len(base["heroes"])} heroes (ok={ok} err={err})')
    print(f'   patch={base["patch"]}  strengths={has("strengths")}  skills={has("skills")}  synergies={has("synergies")}')
    print(f'✅ hero_icons.json: {len(icons)} icons')


if __name__ == '__main__':
    main()
