#!/usr/bin/env python3
"""日本語の「向き」と「立場」を機械で検査する。

## なぜ要るか

2026-08-13、加藤 博から日本語の指摘が3件続いた。**いずれも既存ゲートは全部緑だった。**

1. 傷病手当金「始めて1年たつと**満額で効いてきます**」
   → 起きるのは減額。「効く」は良い方向に作用する語なので、聞いた従業員は
     「1年たてば満額もらえる」と受け取る。**減る話を、得な話に聞こえる言葉で書いていた。**
2. 「届出がなくても、**本人の掛金が自動で下がります**」
   → 本人の掛金が減る話が、経営者には「手間がかからず便利」に聞こえた。
3. 一人法人の代表「私も上乗せ**もらえるの？**」
   → 代表は**自分が事業主**。自分で自分に出すのに、もらう側の言葉になっていた。
     しかも選択肢は3つとも「対象になります」で、**問いと答えが噛み合っていなかった。**

既存の verify_citations.py は条文の実在、verify_options.py は選択肢の手がかりしか見ない。
**日本語の意味・立場・向きを見る網が1枚も無かった。**

## 何を検査するか（機械で判定できるものに限る）

意味の正しさは機械では分からない。**構造として矛盾している形**だけを拾う。

- J1 話者と語の立場ずれ … 事業主・経営者が話しているのに、受け取る側の語（もらえる等）
- J2 減る話とプラス語の共起 … 同じ段落に「減る／下がる」と「効く／満額／フルに」
- J3 問いと答えの語ずれ … 設問文の述語が、どの選択肢にも現れない
- J4 条件付きなのに無条件に聞こえる … 正解肢が「大丈夫／安心／問題ありません」で
     終わっているのに、解説に条件（ただし／限り／場合）がある
- J5 禁止語 … 大げさな語・AI造語（既存の禁止語はここへ集約）

**拾えないもの**（人と別視点のAIが読むしかない）：
事実の当否、主語の取り違えのうち文面に現れないもの、言い回しの自然さ。
このゲートが緑でも「日本語を検証した」とは言わない。
"""
import json, re, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent.parent

def load():
    s = (HERE / "index.html").read_text(encoding="utf-8")
    i = s.find("const BANK=[")
    j = s.find("\n", i)
    return json.loads(s[i + len("const BANK="):j].rstrip(";"))

def strip(h):
    return re.sub(r"<[^>]+>", "", h or "")

# 段落＝<br><br> で区切られたかたまり
def paras(h):
    return [strip(p) for p in re.split(r"(?:<br\s*/?>\s*){2,}", h or "")]

# 事業主・経営者が話している場面か
EMPLOYER = re.compile(r"経営者|事業主|社長|代表")
# 受け取る側の語。ただし「同意をもらう」「書類をもらう」は正しい用法なので除く
RECEIVE = re.compile(r"もらえ|貰え|いただけ|頂け|支給され|くれるの")
RECEIVE_OK = re.compile(r"同意|署名|書類|承諾|証明|印|回答|連絡")
# 減ることが起きる給付（DCで賃金・標準報酬が下がると減る側）
BENEFIT = re.compile(r"傷病手当金|出産手当金|育児休業給付|介護休業給付|基本手当|失業給付|"
                     r"休業補償給付|遺族|障害給付|老齢厚生年金|将来の年金")
# 良い方向に作用する語
PLUS = re.compile(r"効く|効いて|効きま|満額|フルに|活きる|活きて|お得|得になり")
# 無条件に聞こえる締め
CALM = re.compile(r"大丈夫です|安心です|問題ありません|心配いりません|心配ありません")
# 条件を示す語
COND = re.compile(r"ただし|限り|場合|とはいえ|ただ、|例外")
# 禁止語（大げさ・AI造語）
BANNED = ["事故", "地雷"]   # 加藤 博が実際に撤去させた語のみ。推測で足さない
# 設問文の述語（これが選択肢に1つも無ければ噛み合っていない）
PRED = re.compile(r"(もらえ|できる|なる|かかる|要る|いる|変わる|下がる|上がる|使える|選べる|出せる)")

def main():
    B = load()
    ng, info = [], []
    for q in B:
        no = q.get("no", "?")
        ask = q.get("ask") or ""
        line = q.get("line") or ""
        ex = q.get("ex") or ""
        opts = q.get("opts") or []
        head = ask or line

        # J1 話者が事業主側なのに、受け取る側の語で聞いている
        if ask and EMPLOYER.search(ask) and RECEIVE.search(ask) and not RECEIVE_OK.search(ask):
            ng.append(f"No.{no} J1 話者が事業主側なのに受け取る側の語：{ask}")

        # J2 減る側の給付に、良い方向へ作用する語を当てている
        #    （旧Q13「傷病手当金は…1年たつと満額で効いてきます」がこの形。
        #      旧文は「減る」と一度も書いていなかったので、減る語との共起では拾えない）
        for p in paras(ex) + [o.get("x","") for o in opts]:
            t = strip(p)
            if BENEFIT.search(t) and PLUS.search(t):
                ng.append(f"No.{no} J2 減る側の給付にプラス語：…{t[:56]}…")
                break

        # J3 設問文の述語が、どの選択肢にも現れない
        if ask and opts:
            preds = set(PRED.findall(ask))
            if preds:
                body = "".join(o.get("x", "") for o in opts)
                miss = [p for p in preds if p not in body]
                # 「なる」は言い換えが効きやすいので単独では鳴らさない
                miss = [p for p in miss if p != "なる"] or ([] if "なる" in preds and len(preds) == 1 else miss)
                if miss and len(miss) == len(preds):
                    info.append(f"No.{no} 問いの述語「{'／'.join(miss)}」が選択肢に無い：{ask}")

        # J4 無条件に聞こえる正解肢なのに、解説に条件がある
        for o in opts:
            if o.get("r") == "ok" and CALM.search(o.get("x", "")) and COND.search(strip(ex)):
                ng.append(f"No.{no} J4 条件付きなのに無条件に聞こえる正解肢：{o['x']}")

        # J5 禁止語
        blob = json.dumps(q, ensure_ascii=False)
        for w in BANNED:
            if w in blob:
                ng.append(f"No.{no} J5 禁止語「{w}」")

    print(f"検査した設問: {len(B)} 問")
    print(f"  問題あり  : {len(ng)}")
    for x in ng:
        print("   ✗ " + x)
    if info:
        print(f"  参考（誤検出が多いので判定に使わない）: {len(info)} 件")
        for x in info[:3]:
            print("   ・ " + x)
        if len(info) > 3:
            print(f"   ・ ほか {len(info)-3} 件")
    print()
    print("※ このゲートは構造として矛盾している形しか拾えない。")
    print("   事実の当否・言い回しの自然さは拾えないので、緑でも「日本語を検証した」とは言わない。")
    return 1 if ng else 0

if __name__ == "__main__":
    sys.exit(main())
