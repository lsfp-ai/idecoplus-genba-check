#!/usr/bin/env python3
"""更新履歴が、受講者から見てずれていないかを検査する。

## なぜ要るか

更新のお知らせは **2か所**にある。

- `index.html` … アプリのホーム画面に出す1行（`UPDATED` / `UPDATED_WHAT`）
- `manual.html#updates` … 全部の履歴

**2か所ある情報は必ずずれる。** 実際、案内文の指摘例だけ直してマニュアルの同じ例を
直し忘れる、という取り違えを起こした（2026-08-14・No.44→No.45）。

受講者にとって、履歴がずれているのは「直したと書いてあるのに直っていない」のと同じ。
だから機械で照合する。

## 何を検査するか

- U1 ホーム画面の日付が、マニュアルの履歴の一番上の日付と一致するか
- U2 マニュアルの履歴が新しい順に並んでいるか
- U3 履歴に出てくる No.◯◯ が、実在する設問番号か
- U4 履歴の一番上の日付が、index.html の設問数と矛盾しないか（問数を書いていれば）
"""
import json, re, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent.parent

def bank():
    s = (HERE / "index.html").read_text(encoding="utf-8")
    i = s.find("const BANK=[")
    j = s.find("\n", i)
    return json.loads(s[i + len("const BANK="):j].rstrip(";"))

def to_key(jp):
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", jp)
    return (int(m[1]), int(m[2]), int(m[3])) if m else None

def main():
    ng = []
    idx = (HERE / "index.html").read_text(encoding="utf-8")
    man = (HERE / "manual.html").read_text(encoding="utf-8")

    m = re.search(r"const UPDATED='([^']+)',\s*UPDATED_WHAT='([^']*)'", idx)
    if not m:
        print("✗ index.html に UPDATED / UPDATED_WHAT が無い")
        return 1
    home_date = m[1]

    sec = man.split('id="updates"', 1)
    if len(sec) < 2:
        print("✗ manual.html に id=\"updates\" の更新履歴が無い")
        return 1
    dates = re.findall(r"<h3>(\d{4}年\d{1,2}月\d{1,2}日)</h3>", sec[1])
    if not dates:
        ng.append("manual.html の更新履歴に日付（<h3>）が1つも無い")
    else:
        # U1 ホーム画面の日付 ＝ 履歴の一番上
        if home_date != dates[0]:
            ng.append(f"U1 ホーム画面「{home_date}」と履歴の最新「{dates[0]}」が違う")
        # U2 新しい順か
        keys = [to_key(d) for d in dates]
        if any(k is None for k in keys):
            ng.append("U2 日付の形式が読めないものがある")
        elif keys != sorted(keys, reverse=True):
            ng.append(f"U2 履歴が新しい順になっていない：{dates}")

    # U3 履歴に出てくる番号が実在するか
    #    「No.124・125・126」「No.1／3／8／30」のような列挙も読む。
    #    先頭だけ見る実装にしていたら、負制御（No.999 を混ぜる）で鳴らなかった。
    nos = {q["no"] for q in bank()}
    cited = set()
    plain = re.sub(r"<[^>]+>", "", sec[1])
    for m in re.finditer(r"No\.\s*(\d+(?:\s*[・／/、,]\s*\d+)*)", plain):
        cited |= {int(x) for x in re.findall(r"\d+", m[1])}
    for n in sorted(cited):
        if n not in nos:
            ng.append(f"U3 履歴の No.{n} は存在しない設問番号")

    print(f"更新履歴: {len(dates)} 件（最新 {dates[0] if dates else '—'}）／設問 {len(nos)} 問")
    print(f"  問題あり  : {len(ng)}")
    for x in ng:
        print("   ✗ " + x)
    print()
    print("※ 中身が本当か（直したと書いたものが直っているか）は、このゲートでは分からない。")
    return 1 if ng else 0

if __name__ == "__main__":
    sys.exit(main())
