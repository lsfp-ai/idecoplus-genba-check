#!/usr/bin/env python3
"""選択肢に「答えが透けて見える手がかり」が無いかを機械で検査する。

目視レビューでは毎回すり抜けたので、機械で全数を通す。
検査するのは中身の正しさではなく、形から答えが割れてしまう作りかどうか。
"""
import re, json, sys, statistics, pathlib
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent.parent

# これまで実際に作ってしまった不自然な言い回し。再発したら止める。
BANNED = ['置ける額', '動かせないお金', '年金だけ乗り', '分が乗り', '形に乗ら',
          '報酬を得ます', '事故', '地雷', '危険な発言', '加藤 博確定']

def main() -> int:
    src = (HERE / 'index.html').read_text(encoding='utf-8')
    bank = json.loads(re.search(r'const BANK=(\[.*?\]);\n', src, re.S).group(1))
    sjt = [q for q in bank if q['t'] == 'sjt']
    fails = []

    # ① 文末の句点が特定の役割に偏っていないか（付いている側が答えになる）
    per = Counter()
    for q in sjt:
        for o in q['opts']:
            if o['x'].rstrip().endswith('。'): per[o['r']] += 1
    if sum(per.values()):
        fails.append(f'文末の句点が付いた選択肢がある（役割別 {dict(per)}）。付いている側が手がかりになる')

    # ② 正解だけが最長になっている割合（偶然なら33%）
    longest = sum(1 for q in sjt
                  if [len(o['x']) for o in q['opts'] if o['r'] == 'ok'][0]
                  > max(len(o['x']) for o in q['opts'] if o['r'] != 'ok'))
    rate = longest / len(sjt) * 100
    if rate > 40:
        fails.append(f'正解だけが最長の設問が {longest}/{len(sjt)}（{rate:.1f}%）。40%を超えると長さで当たる')

    # ③ 正解と不正解の平均文字数の開き
    lo = [len(o['x']) for q in sjt for o in q['opts'] if o['r'] == 'ok']
    ot = [len(o['x']) for q in sjt for o in q['opts'] if o['r'] != 'ok']
    ratio = statistics.mean(lo) / statistics.mean(ot)
    if ratio > 1.2:
        fails.append(f'正解の平均が不正解の {ratio:.2f}倍（{statistics.mean(lo):.1f}字 / {statistics.mean(ot):.1f}字）')

    # ④ 一度直した不自然な言い回しの再発
    for i, q in enumerate(bank):
        blob = ' '.join([q.get('line') or '', q.get('ask') or '', q.get('ex') or ''] +
                        [o['x'] for o in (q.get('opts') or [])])
        for w in BANNED:
            if w in blob: fails.append(f'Q{i} に「{w}」が再発している')

    # ⑤ ○×の答えの偏り（全部×で通るか）
    ox = [q for q in bank if q['t'] == 'ox']
    x = sum(1 for q in ox if q['ans'] == '×')
    if x / len(ox) > 0.80:
        fails.append(f'○×が×に偏りすぎ（{x}/{len(ox)} = {x/len(ox)*100:.0f}%）。全部×で通ってしまう')

    # ⑥ 毎回必ず出る「言葉」枠が同じ答えに揃っていないか
    kot = [q for q in ox if q['dom'] == '言葉']
    kx = sum(1 for q in kot if q['ans'] == '×')
    if kot and (kx == len(kot) or kx == 0):
        fails.append(f'「言葉」枠 {len(kot)}問の答えが全部同じ（×={kx}）。毎回1問必ず出るので確実に当たる')

    # ⑦ 画面の見出し・説明に、指す先が画面に無い指示語が入っていないか
    #    「そう聞かれたら」「こう聞かれます」を2回作ってしまったので機械で止める。
    ui = re.sub(r'const BANK=\[.*?\];\n', '', src, flags=re.S)
    for w in ['そう聞か', 'こう聞か', 'そう言われ', 'こう言われ', 'この発言', 'その質問', '先ほど', '前述', '上記の']:
        if w in ui:
            fails.append(f'画面の文言に指示語「{w}」がある。指す先が画面に無いと読み手が迷う')

    # ⑧ マークの語句が本文に実在するか（色が付かない＝機能していない）
    for i, q in enumerate(bank):
        if q['t'] == 'ox':
            for sub, _ in (q.get('m') or []):
                if sub not in q['line']: fails.append(f'Q{i} のマーク「{sub}」が本文に無い')
        else:
            for o in q['opts']:
                for sub, _ in (o.get('m') or []):
                    if sub not in o['x']: fails.append(f'Q{i} のマーク「{sub}」が選択肢に無い')

    print(f'セリフ判定 {len(sjt)}問 / 選択肢 {sum(len(q["opts"]) for q in sjt)}本 / ○× {len(ox)}問')
    print(f'  正解だけが最長 : {longest}/{len(sjt)} ({rate:.1f}%)  ※偶然なら33%')
    print(f'  正解/不正解の字数比: {ratio:.2f}倍')
    print(f'  ○×の×比率     : {x/len(ox)*100:.0f}%')
    print(f'  問題あり       : {len(fails)}')
    for f in fails: print('   ✗ ' + f)
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
