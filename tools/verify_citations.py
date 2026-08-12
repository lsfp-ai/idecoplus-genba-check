#!/usr/bin/env python3
"""教材が引用している条文を、e-Gov法令検索から1本ずつ取得して実在を確かめる。

目視レビューでは網羅できないので機械で全数を通す。
「条文が取れない」を「異常なし」にしない（取れなければ FAIL）。
"""
import re, json, sys, time, urllib.request, urllib.parse, html, pathlib

HERE = pathlib.Path(__file__).resolve().parent.parent
CACHE = HERE / "tools" / ".egov_cache.json"

# 法令名 → e-Gov の法令番号
LAWNUM = {
 '確定拠出年金法': '平成十三年法律第八十八号',
 '確定拠出年金法施行令': '平成十三年政令第二百四十八号',
 '確定拠出年金法施行規則': '平成十三年厚生労働省令第百七十五号',
 '所得税法': '昭和四十年法律第三十三号',
 '所得税法施行令': '昭和四十年政令第九十六号',
 '法人税法施行令': '昭和四十年政令第九十七号',
 '健康保険法': '大正十一年法律第七十号',
 '厚生年金保険法': '昭和二十九年法律第百十五号',
 '雇用保険法': '昭和四十九年法律第百十六号',
 '労働基準法': '昭和二十二年法律第四十九号',
 '最低賃金法': '昭和三十四年法律第百三十七号',
 '地方税法': '昭和二十五年法律第二百二十六号',
 '国民健康保険法施行令': '昭和三十三年政令第三百六十二号',
 '金融商品取引法': '昭和二十三年法律第二十五号',
 '社会保険労務士法': '昭和四十三年法律第八十九号',
 '相続税法': '昭和二十五年法律第七十三号',
 '労働保険の保険料の徴収等に関する法律': '昭和四十四年法律第八十四号',
 '労働保険徴収法': '昭和四十四年法律第八十四号',
}
K = '〇一二三四五六七八九'
def kanji(n: int) -> str:
    if n <= 10: return ['','一','二','三','四','五','六','七','八','九','十'][n]
    if n < 20: return '十' + (K[n % 10] if n % 10 else '')
    if n < 100:
        t, o = divmod(n, 10)
        return K[t] + '十' + (K[o] if o else '')
    h, r = divmod(n, 100)
    return (K[h] if h > 1 else '') + '百' + (kanji(r) if r else '')

def to_int(s: str) -> int:
    s = s.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    if s.isdigit(): return int(s)
    v = 0; cur = 0
    for ch in s:
        if ch == '十': cur = (cur or 1) * 10; v += cur; cur = 0
        elif ch == '百': cur = (cur or 1) * 100; v += cur; cur = 0
        elif ch in K: cur = K.index(ch)
        else: return 0
    return v + cur

def fetch(lawnum: str, art: str, cache: dict) -> str:
    key = f'{lawnum}|{art}'
    if key in cache: return cache[key]
    url = ('https://laws.e-gov.go.jp/api/1/articles;lawNum='
           + urllib.parse.quote(lawnum) + ';article=' + urllib.parse.quote(art))
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            raw = r.read().decode('utf-8', 'ignore')
    except Exception as e:
        return f'__ERROR__{e}'
    txt = html.unescape(re.sub(r'<[^>]+>', ' ', raw))
    txt = re.sub(r'\s+', ' ', txt).strip()
    cache[key] = txt
    time.sleep(0.35)
    return txt

def main() -> int:
    src = (HERE / 'index.html').read_text(encoding='utf-8')
    bank = json.loads(re.search(r'const BANK=(\[.*?\]);\n', src, re.S).group(1))
    strip = lambda t: re.sub('<[^>]+>', '', t or '')
    names = sorted(LAWNUM, key=len, reverse=True)
    pat = re.compile('(' + '|'.join(map(re.escape, names)) + r')\s*(?:第)?([0-9０-９一二三四五六七八九十百]+)条(?:の([0-9０-９一二三四五六七八九十]+))?')
    cache = json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {}

    seen, fails, ok = {}, [], 0
    for i, q in enumerate(bank):
        for field in ('src', 'ex'):
            for m in pat.finditer(strip(q[field])):
                law, num, sub = m.group(1), m.group(2), m.group(3)
                art = '第' + kanji(to_int(num)) + '条' + (('の' + kanji(to_int(sub))) if sub else '')
                key = (law, art)
                if key not in seen:
                    seen[key] = fetch(LAWNUM[law], art, cache)
                body = seen[key]
                label = f'{law}{num}条' + (f'の{sub}' if sub else '')
                if body.startswith('__ERROR__'):
                    fails.append((i, label, '取得できない: ' + body[9:60]))
                elif '該当する条文内容が存在しません' in body or '未設定又は誤っています' in body:
                    fails.append((i, label, '条文が存在しない'))
                elif len(body) < 60:
                    fails.append((i, label, '本文が短すぎる（取得失敗の疑い）'))
                else:
                    ok += 1
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding='utf-8')

    print(f'照合した引用: {ok + len(fails)} か所 / 実条文 {len(seen)} 本')
    print(f'  実在を確認  : {ok}')
    print(f'  問題あり    : {len(fails)}')
    for i, label, why in fails:
        print(f'   ✗ Q{i} 「{label}」 {why}')
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
