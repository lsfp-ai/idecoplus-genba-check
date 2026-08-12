#!/usr/bin/env python3
"""選択肢に「答えが透けて見える手がかり」が無いかを機械で検査する。

目視レビューでは毎回すり抜けたので、機械で全数を通す。
検査するのは中身の正しさではなく、形から答えが割れてしまう作りかどうか。
"""
import re, json, sys, statistics, pathlib
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent.parent

# これまで実際に作ってしまった不自然な言い回し。再発したら止める。
BANNED = ['置ける額', '動かせないお金', '年金だけ乗り', '分が乗り', '形に乗ら', '分は乗ら',
          '報酬を得ます', '事故', '地雷', '危険な発言', '加藤 博確定',
          # 詰める言い回し（撤去したのにマークの理由へ残っていたもの）
          '分かっていない人に見える', '信用を失', '見抜か', '責められ', '取り返しがつかない',
          '放棄している', '矛先', '引受先']

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
    #    ⚠ 以前は line/ask/ex/opts しか見ておらず、**マークの理由と根拠が検査から漏れていた**。
    #      実際に「分かっていない人に見える」「信用を失う」「乗らない」がそこに残っていた。
    #      利用者の目に入る文字列は全部入れる。
    for i, q in enumerate(bank):
        parts = [q.get('line') or '', q.get('ask') or '', q.get('scene') or '',
                 q.get('ex') or '', q.get('src') or '']
        for sub, why in (q.get('m') or []):
            parts += [sub, why]
        for o in (q.get('opts') or []):
            parts.append(o['x'])
            for sub, why in (o.get('m') or []):
                parts += [sub, why]
        blob = ' '.join(parts)
        for w in BANNED:
            if w in blob: fails.append(f'Q{i} に「{w}」が再発している')

    # ④-2 マークの理由が短すぎて何を指すか分からないもの
    for i, q in enumerate(bank):
        reasons = [why for _, why in (q.get('m') or [])]
        for o in (q.get('opts') or []):
            reasons += [why for _, why in (o.get('m') or [])]
        for why in reasons:
            if len(why) < 10:
                fails.append(f'Q{i} のマークの理由「{why}」が短すぎる（何を指すか分からない）')
            if why.startswith('同上'):
                fails.append(f'Q{i} のマークの理由が「同上」で始まる（並びは毎回変わるので何を指すか分からない）')

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

    # ⑥-2 手がかりの総当たり検査
    #     「長い方を選ぶ」で81%当たる、といった穴を人が思いつく前に機械で潰す。
    #     私が思いついた手がかりだけ潰しても、別の手がかりが残る。だから総当たりする。
    CUES = [
        ('一番長い', lambda q, o: len(o['x']) == max(len(x['x']) for x in q['opts'])),
        ('一番短い', lambda q, o: len(o['x']) == min(len(x['x']) for x in q['opts'])),
        ('句点あり', lambda q, o: '。' in o['x']),
        ('句点なし', lambda q, o: '。' not in o['x']),
        ('読点あり', lambda q, o: '、' in o['x']),
        ('読点なし', lambda q, o: '、' not in o['x']),
        ('はい始まり', lambda q, o: o['x'].startswith('はい')),
        ('数字あり', lambda q, o: re.search(r'[0-9０-９]', o['x']) is not None),
        ('ませんを含む', lambda q, o: 'ません' in o['x']),
        ('ご〜を含む', lambda q, o: 'ご' in o['x']),
        ('確認を含む', lambda q, o: '確認' in o['x']),
        ('ただし逆接', lambda q, o: re.search(r'(^|。|、)ただ(し|、)', o['x']) is not None),
        ('ですで終わる', lambda q, o: o['x'].endswith('です')),
        ('ますで終わる', lambda q, o: o['x'].endswith('ます')),
        ('カギ括弧あり', lambda q, o: '「' in o['x']),
        ('しょうで終わる', lambda q, o: o['x'].endswith('しょう')),
    ]
    worst = []
    for name, f in CUES:
        hit = used = 0
        for q in sjt:
            c = [o for o in q['opts'] if f(q, o)]
            if len(c) == 1:
                used += 1
                hit += (c[0]['r'] == 'ok')
        if used >= 10:
            r = hit / used * 100
            worst.append((r, name, hit, used))
            if r > 55:
                fails.append(f'「{name}方を選ぶ」だけで {hit}/{used} ({r:.0f}%) 当たる。偶然は33%')
    worst.sort(reverse=True)

    # ⑥-3 同じ言い回しが特定の役割にだけ繰り返し出ていないか
    #     不正解に足した定型句（「気にしなくて大丈夫です」等）が3問に並ぶと、
    #     それ自体が新しい手がかりになる。人が思いつく前に機械で止める。
    from collections import defaultdict
    phr = defaultdict(list)
    for q in sjt:
        for o in q['opts']:
            body = o['x']
            for L in (8, 10):
                for k in range(len(body) - L + 1):
                    phr[body[k:k + L]].append(o['r'])
    for ph, roles in phr.items():
        if len(roles) >= 3:
            s_ok = sum(1 for r in roles if r == 'ok')
            if s_ok == 0 or s_ok == len(roles):
                side = '正解' if s_ok else '不正解'
                fails.append(f'「{ph}」が{side}の選択肢だけに{len(roles)}回出ている（言い回しが手がかりになる）')
                break

    # ⑦ 画面の見出し・説明に、指す先が画面に無い指示語が入っていないか
    #    「そう聞かれたら」「こう聞かれます」を2回作ってしまったので機械で止める。
    ui = re.sub(r'const BANK=\[.*?\];\n', '', src, flags=re.S)
    for w in ['そう聞か', 'こう聞か', 'そう言われ', 'こう言われ', 'この発言', 'その質問', '先ほど', '前述', '上記の']:
        if w in ui:
            fails.append(f'画面の文言に指示語「{w}」がある。指す先が画面に無いと読み手が迷う')

    # ⑦-2 解説が選択肢を「番号」で指していないか
    #     選択肢は毎回並びが変わるので、番号は画面のどれとも対応しない。
    #     ⚠ 以前の式は直前が「。、空白」のときしか見ておらず、「）3も誤り」を素通りさせた。
    numref = re.compile(r'(?<![0-9０-９第条項号年月日回])([1-3１-３])(?:も|は|が|を|と)(?:誤り|正しい|不正解|正解|言い過ぎ|違い|ダメ)')
    for i, q in enumerate(bank):
        t = re.sub('<[^>]+>', '', q.get('ex') or '')
        mm = numref.search(t)
        if mm:
            fails.append(f'Q{i} の解説が選択肢を番号「{mm.group(1)}」で指している（並びは毎回変わるので対応しない）')

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
    if worst:
        top = worst[:3]
        print('  手がかりの最悪3件: ' + ' / '.join(f'{n} {h}/{u}({r:.0f}%)' for r, n, h, u in top))
    print(f'  問題あり       : {len(fails)}')
    for f in fails: print('   ✗ ' + f)
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
