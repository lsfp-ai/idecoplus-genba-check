#!/usr/bin/env python3
"""merge の前に必ず通す。**公開してから読む**のをやめるための検査。

## なぜ要るか

2026-08-14、公開したあとに公開中の実物を読んで、自分の誤りを**6件**続けて見つけた。

1. No.44 の不遜な言い回し（自分で禁じた型）
2. 案内文の指摘例が No.44 を指していた（中身は No.45）
3. **マニュアルの同じ例も No.44 のままだった**（案内文だけ直した＝型2）
4. マニュアルの「30回前後」（測っていない数字＝型13）
5. マニュアルの「34〜47回」（**同じ日にまた測る前に書いた**）
6. No.32 の置換が空振り（根拠欄だけ直り、本文が古いまま＝型12）

**全部すでに docs/lessons.md に書いてある型。** 記録はあったが、出す前に自分へ当てていなかった。
だから機械にする。

## 何を見るか（既存3ゲートが見ていない場所）

- P1 **顧客到達物に散らばる「No.◯◯」の参照**と、その設問の中身を並べて出す
      → 参照先の取り違え（上記2・3）が目で分かる
- P2 **顧客到達物に書かれた数字**を全部列挙する
      → 「これは測ったか」を1つずつ自分に問うため（上記4・5）
- P3 **main と比べて中身が変わった設問**の全文を出す
      → 出す前に読むため。置換の空振り（上記6）もここで見える
- P4 既存3ゲート（条文・選択肢・日本語）と更新履歴ゲートをまとめて実行

⚠️ このスクリプトは**読むべきものを並べるだけ**で、正しさは判定しない。
   判定するのは人。「preflight を流した」を「確認した」と言わない。
"""
import json, re, subprocess, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent.parent
REACH = ["index.html", "manual.html", "README.md", "docs/announcement.md"]

def bank_from(text):
    i = text.find("const BANK=[")
    j = text.find("\n", i)
    return json.loads(text[i + len("const BANK="):j].rstrip(";"))

def strip(h):
    return re.sub(r"<[^>]+>", "", h or "")

def head(q, n=40):
    return strip(q.get("ask") or q.get("line") or "")[:n]

def main():
    cur = bank_from((HERE / "index.html").read_text(encoding="utf-8"))
    byno = {q["no"]: q for q in cur}

    print("=" * 72)
    print("P1  顧客到達物の「No.◯◯」参照と、その設問の中身")
    print("    ※ 参照先が言いたい内容と合っているかは、人が読んで確かめる")
    print("=" * 72)
    for f in REACH:
        fp = HERE / f
        if not fp.exists():
            continue
        txt = strip(fp.read_text(encoding="utf-8"))
        seen, dup = [], set()
        for m in re.finditer(r"No\.\s*(\d+(?:\s*[・／/、,]\s*\d+)*)", txt):
            ctx = txt[max(0, m.start() - 34):m.start()].replace("\n", " ")
            # 制度資料の番号（厚労省「確定拠出年金Q&A」No.70 など）は設問番号ではない。
            # これを混ぜると出力が埋まって読まれなくなる＝鳴りすぎるゲートは無いのと同じ。
            if re.search(r"Q&(?:amp;)?A[^。]{0,12}$|Q＆A[^。]{0,12}$|国税庁[^。]{0,10}$|タックスアンサー[^。]{0,10}$", ctx):
                continue
            for x in re.findall(r"\d+", m[1]):
                n = int(x)
                if (n, ctx[-18:]) in dup:
                    continue
                dup.add((n, ctx[-18:]))
                seen.append((n, ctx))
        if not seen:
            continue
        print(f"\n--- {f} ---")
        for n, ctx in seen:
            q = byno.get(n)
            mark = "  " if q else "✗ 存在しない番号"
            print(f"{mark}No.{n:<4}〔本文〕…{ctx}")
            if q:
                print(f"       〔設問〕{head(q, 52)}")

    print()
    print("=" * 72)
    print("P2  顧客到達物に書いた数字（1つずつ「これは測ったか」を確かめる）")
    print("=" * 72)
    for f in REACH:
        fp = HERE / f
        if not fp.exists():
            continue
        raw = fp.read_text(encoding="utf-8")
        raw = re.sub(r"<style[\s\S]*?</style>|<script[\s\S]*?</script>", "", raw)
        txt = strip(raw)
        hits = []
        for m in re.finditer(r"[0-9０-９][0-9０-９,，．.〜～\-]*\s*(問|回|分|か所)", txt):
            hits.append(txt[max(0, m.start() - 26):m.end()].replace("\n", " "))
        if hits:
            print(f"\n--- {f} ---")
            for h in dict.fromkeys(hits):
                print("   ・…" + h)

    print()
    print("=" * 72)
    print("P3  main と比べて中身が変わった設問（出す前に全文を読む）")
    print("=" * 72)
    try:
        old = subprocess.run(["git", "show", "main:index.html"], cwd=HERE,
                             capture_output=True, text=True, check=True).stdout
        prev = {q["no"]: q for q in bank_from(old)}
    except Exception as e:
        print(f"   main と比較できない（{e}）")
        prev = None
    if prev is not None:
        changed = [n for n, q in byno.items()
                   if n not in prev or json.dumps(prev[n], ensure_ascii=False, sort_keys=True)
                   != json.dumps(q, ensure_ascii=False, sort_keys=True)]
        if not changed:
            print("   変更なし")
        for n in sorted(changed):
            q = byno[n]
            tag = "新規" if n not in prev else "変更"
            print(f"\n--- No.{n}（{tag}・{q.get('dom')}） ---")
            print("問  " + strip(q.get("ask") or q.get("line")))
            for o in (q.get("opts") or []):
                print(f"  {o['r']:<6}{o['x']}")
                for mm in (o.get("m") or []):
                    print(f"         ↳「{mm[0]}」→ {mm[1]}")
            if q.get("ans"):
                print("答  " + q["ans"])
            print("解説 " + strip(q["ex"]))
            print("根拠 " + strip(q.get("src", "")))

    print()
    print("=" * 72)
    print("P4  既存のゲート")
    print("=" * 72)
    ng = 0
    for t in ("verify_citations.py", "verify_options.py",
              "verify_japanese.py", "verify_update_log.py"):
        r = subprocess.run([sys.executable, str(HERE / "tools" / t)],
                           capture_output=True, text=True)
        line = next((l for l in r.stdout.splitlines() if "問題あり" in l), "(出力なし)")
        print(f"   {t:<24}{line.strip()}")
        if r.returncode:
            ng += 1
            for l in r.stdout.splitlines():
                if l.strip().startswith("✗"):
                    print("      " + l.strip())
    print()
    print("※ P1〜P3 は読むべきものを並べただけ。正しさは判定していない。")
    print("※ 「preflight を流した」を「確認した」と言わない。")
    return 1 if ng else 0

if __name__ == "__main__":
    sys.exit(main())
