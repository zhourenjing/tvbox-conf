#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_boss_tvbox.py — BOSS 自建 TVBox 聚合配置生成器（2026-09-14）

合并 5 源: 小雅(my_ext_jar) + 小盒子(xhz) + 小盒子4K(h4k) + 高天(gao) + 采集之王(cjzw)
输出: <work>/boss_tvbox.json（压缩 JSON）

用法（在 NAS 上，配置文件已在 /tmp/tvbox 下载好）:
  python3 build_boss_tvbox.py /tmp/tvbox
重跑即全量重新同步（含小雅最新 my_ext_jar），输出后复制到
/vol1/1000/小雅/配置/data/boss_tvbox.json 即完成发版（小雅 5678 web 根直接服务）。

策略:
- 每站点显式 jar（自带 > 源全局 spider），各源互不干扰；全局 spider=高天 pg.jar（兜 Parse 类解析）
- 相对路径（jar/api/ext）全部按各自源 base 改绝对 URL，保留 ;md5; 校验
- 小雅 jar 去 md5（上游每天发版 jar 内容变、URL 不变，去 md5 才不会失效）
- xiaoya 站点 key/name 原样；其余源 key 加 tag 前缀、name 加【源】前缀，杜绝 key 冲突
- lives 双线路：内网 1905（默认）+ 公网 iptv.zrj-ai.icu 外线（302 跳上游直连不占云机带宽）；parses 并集去重；rules 取小雅的
- storeHouse 存原始接口清单，App 内可一键切回任一原接口
"""
import json, re, sys, os, urllib.parse

# IPTV 令牌（从 /root/.iptv-token-url 读取；该文件在仓库之外，令牌不会进配置仓库）
IPTV_TOKEN = ""
try:
    _m = re.search(r'/u/([^/]+)/', open('/root/.iptv-token-url').read().strip())
    IPTV_TOKEN = _m.group(1) if _m else ""
except Exception:
    IPTV_TOKEN = ""


try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

WORK = sys.argv[1] if len(sys.argv) > 1 else '/tmp/tvbox'
OUT = os.path.join(WORK, 'boss_tvbox.json')

SOURCES = [
    ("xy",  "xiaoya.json", "http://192.168.100.150:5678/tvbox/my_ext_jar.json", ""),
    ("xhz", "xhz.json",    "http://xhztv.top/xhz/", "盒"),
    ("h4k", "xhz4k.json",  "http://xhztv.top/4k.json", "4K"),
    ("gao", "gao.json",    "https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json", "高天"),
    ("cj",  "cjzw.json",   "https://raw.githubusercontent.com/jiushizhe/daozhang/main/drpy_dzlive6.21/index.json", "采集"),
]

REL = re.compile(r'^(\.{1,2}/|/(?!/))')


def tolerant_load(path):
    t = open(path, encoding='utf-8', errors='replace').read()
    s = '\n'.join(l for l in t.splitlines() if not l.lstrip().startswith('//'))
    s = re.sub(r',\s*([}\]])', r'\1', s)
    return json.loads(s, strict=False)


def urljoin(base, u):
    try:
        return urllib.parse.urljoin(base, u)
    except Exception:
        return u


def abs_url(u, base):
    """字符串 URL 绝对化：只动明显相对路径，保留 ;md5; 校验尾。"""
    if not isinstance(u, str) or not u:
        return u
    m = re.match(r'^([^;]+)((?:;md5;[^;]*)+)$', u, re.I)
    if m:
        return abs_url(m.group(1), base) + m.group(2)
    if re.match(r'^https?://', u, re.I) or u.startswith(('csp_', 'Parse:')):
        return u
    # 仅 ./ ../ / 开头才算相对路径；像 tvfan/Cloud-drive.txt 这类是 jar 内部标识，绝不改写
    if REL.match(u):
        return urljoin(base, u)
    return u


def fix_query(u, base):
    """ext 里 ?params=./json/x.json 这类 query 内相对路径也要绝对化。"""
    if '?' not in u or not isinstance(u, str):
        return u
    head, q = u.split('?', 1)

    def rep(m):
        v = m.group(2)
        if v.startswith(('./', '../', '/')) and not v.startswith('//'):
            return m.group(1) + '=' + abs_url(v, base)
        return m.group(0)

    return head + '?' + re.sub(r'(params|ext|url|json)=([^&]*)', rep, q)


def abs_any(v, base):
    if isinstance(v, str):
        return fix_query(abs_url(v, base), base)
    if isinstance(v, list):
        return [abs_any(x, base) for x in v]
    if isinstance(v, dict):
        return {k: abs_any(x, base) for k, x in v.items()}
    return v


def main():
    merged, seen_keys = [], set()
    all_parses, seen_parse = [], set()
    flags = set()
    spider_global = None
    rules_pick = None
    wallpaper = None
    stat = {}

    for tag, fname, base, prefix in SOURCES:
        p = os.path.join(WORK, fname)
        try:
            d = tolerant_load(p)
        except Exception as e:
            print(f"[WARN] {fname} 解析失败，跳过: {type(e).__name__} {e}")
            stat[tag] = 'SKIP(解析失败)'
            continue
        kept = 0
        sp = abs_url(d.get('spider', ''), base)
        for s in d.get('sites', []) or []:
            if not isinstance(s, dict) or not s.get('api'):
                continue
            key = s.get('key') or s.get('name') or f'site_{len(merged)}'
            if prefix:
                key = f"{tag}_{key}"
            if key in seen_keys:
                key = f"{tag}2_{key}"
            name = str(s.get('name') or key)
            if prefix and not name.startswith(prefix):
                name = f"【{prefix}】{name}"
            ns = dict(s)
            ns['key'], ns['name'] = key, name
            if ns.get('jar'):
                ns['jar'] = abs_url(ns['jar'], base)
            elif sp:
                ns['jar'] = sp
            else:
                ns.pop('jar', None)
            if ns.get('api'):
                ns['api'] = abs_url(ns['api'], base)
            if 'ext' in ns:
                ns['ext'] = abs_any(ns.get('ext'), base)
            ns['_src'] = tag
            merged.append(ns)
            seen_keys.add(key)
            kept += 1
        stat[tag] = f"{kept} 站"
        for pa in d.get('parses', []) or []:
            if not isinstance(pa, dict) or not pa.get('name'):
                continue
            pk = (str(pa.get('name')), str(pa.get('url')), str(pa.get('ext')))
            if pk in seen_parse:
                continue
            np = dict(pa)
            if np.get('url'):
                np['url'] = abs_url(np['url'], base)
            if np.get('ext'):
                np['ext'] = abs_any(np['ext'], base)
            all_parses.append(np)
            seen_parse.add(pk)
        for f in d.get('flags', []) or []:
            flags.add(f)
        if tag == 'gao' and sp:
            spider_global = sp
        if tag == 'xy':
            wallpaper = d.get('wallpaper') or wallpaper
            if isinstance(d.get('rules'), list) and d['rules']:
                rules_pick = d['rules']
        if rules_pick is None and isinstance(d.get('rules'), list) and d['rules']:
            rules_pick = d['rules']

    # 小雅 jar 去 md5：上游每天发版 jar 内容会变，URL 不变，去 md5 才不会失效
    for s in merged:
        j = s.get('jar')
        if isinstance(j, str) and 'xiaoya_proxy.jar' in j:
            s['jar'] = j.split(';')[0]

    # ---- jar 测活（家宽视角）：死 jar 的站点整站剔除 ----
    import ssl, urllib.request, urllib.error
    import concurrent.futures as cf
    from collections import Counter

    def jar_alive(url):
        url = url.split(';')[0]
        attempts = [
            {'User-Agent': 'okhttp/4.9.3', 'Range': 'bytes=0-2047'},
            {'User-Agent': 'okhttp/4.9.3'},
            {'User-Agent': 'Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36'},
        ]
        ctx = ssl._create_unverified_context()
        for hd in attempts:
            try:
                req = urllib.request.Request(url, headers=hd)
                with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
                    r.read(2048)
                    return True
            except urllib.error.HTTPError as e:
                if e.code in (403, 405, 416):
                    continue
                return False
            except Exception:
                continue
        return False

    jar_urls = sorted({s['jar'].split(';')[0] for s in merged if s.get('jar')})
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        alive = set(u for u, ok in zip(jar_urls, ex.map(jar_alive, jar_urls)) if ok)
    dead = [u for u in jar_urls if u not in alive]
    keep = [s for s in merged if not s.get('jar') or s['jar'].split(';')[0] in alive]
    dropped = [s for s in merged if s.get('jar') and s['jar'].split(';')[0] not in alive]
    print(f"jar 测活: {len(alive)}/{len(jar_urls)} 活，死 {len(dead)} 个；剔除站点 {len(dropped)} 个")
    if dead:
        dcnt = Counter(s['jar'].split(';')[0] for s in dropped)
        for u in dead:
            print(f"  死({dcnt.get(u, 0)}站): {u[:100]}")
    merged = keep
    post = Counter(s.pop('_src', '?') for s in merged)
    name_map = {'xy': '小雅', 'xhz': '小盒子', 'h4k': '小盒子4K', 'gao': '高天', 'cj': '采集之王'}
    print("剔除后各源:", {name_map.get(k, k): v for k, v in post.items()})

    out = {
        "spider": spider_global,
        "wallpaper": wallpaper,
        "sites": merged,
        "parses": all_parses,
        "flags": sorted(flags),
        "rules": rules_pick,
        "lives": [
            {"name": "🏠家庭直播", "type": 0,
             "url": f"http://192.168.100.150:1905/u/{IPTV_TOKEN}/interface.m3u"},
            {"name": "🏠家庭直播·外线", "type": 0,
             "url": f"https://iptv.zrj-ai.icu/u/{IPTV_TOKEN}/interface.m3u"}
        ],
        "storeHouse": [
            {"sourceName": "小雅官方", "sourceUrl": "http://192.168.100.150:5678/tvbox/my_ext_jar.json"},
            {"sourceName": "小盒子", "sourceUrl": "http://xhztv.top/xhz"},
            {"sourceName": "小盒子4K", "sourceUrl": "http://xhztv.top/4k.json"},
            {"sourceName": "高天", "sourceUrl": "https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json"},
            {"sourceName": "采集之王", "sourceUrl": "https://raw.githubusercontent.com/jiushizhe/daozhang/main/drpy_dzlive6.21/index.json"}
        ]
    }
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

    # ---- 校验 ----
    d2 = json.load(open(OUT, encoding='utf-8'))
    keys = [s['key'] for s in d2['sites']]
    dup = len(keys) - len(set(keys))
    noapi = [s['key'] for s in d2['sites'] if not s.get('api')]
    rel_jar = [s['key'] for s in d2['sites'] if isinstance(s.get('jar'), str) and not s['jar'].startswith('http')]
    rel_api = [s['key'] for s in d2['sites']
               if isinstance(s.get('api'), str) and not re.match(r'^(https?://|csp_|Parse:)', s['api'])]
    rel_ext = [s['key'] for s in d2['sites']
               if isinstance(s.get('ext'), str) and re.match(r'^\.{1,2}/', s['ext'])]
    jars = {}
    for s in d2['sites']:
        j = s.get('jar') or '(全局)'
        jars[j] = jars.get(j, 0) + 1
    size = os.path.getsize(OUT)
    print(f"OK {OUT}  {size/1024:.0f}KB")
    print(f"各源站点: {stat}")
    print(f"sites={len(keys)} parses={len(all_parses)} flags={len(flags)} rules={'有' if rules_pick else '无'} spider={spider_global}")
    print(f"key重复={dup} 无api={len(noapi)} 相对jar={len(rel_jar)} 相对api={len(rel_api)} 相对ext={len(rel_ext)}")
    for k in (noapi[:3], rel_jar[:3], rel_api[:3], rel_ext[:3]):
        if k:
            print("  样例:", k[:3])
    print("jar 分布:")
    for j, c in sorted(jars.items(), key=lambda x: -x[1]):
        print(f"  {c:4d}  {j[:110]}")


if __name__ == '__main__':
    main()
