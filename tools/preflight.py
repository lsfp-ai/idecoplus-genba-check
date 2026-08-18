#!/usr/bin/env python3
"""One-shot wrapper for the 2026-08-18 No.42/No.44 patch.
Runs the patch, restores the canonical preflight.py from origin/main, then executes it.
This file restores itself before the workflow commits.
"""
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()

# 1) Patch index.html: No.42, No.44, and the home update notice.
p = HERE / "index.html"
s = p.read_text(encoding="utf-8")

old42 = "（経営者）業績次第で掛金を増やしたり減らしたりできる？"
new42 = "（経営者）iDeCo＋の掛金は、業績次第で増やしたり減らしたりできる？"
if old42 in s:
    if s.count(old42) != 1:
        raise SystemExit(f"No.42 old wording count={s.count(old42)}")
    s = s.replace(old42, new42, 1)
elif new42 not in s:
    raise SystemExit("No.42 wording not found")

pairs = [
    ("3〜4か月はみてください", "4〜5か月はみてください"),
    ("3〜4か月という目安は言える", "4〜5か月という目安は言える"),
    ("書類だけでは始まらない。3〜4か月はかかる", "書類だけでは始まらない。4〜5か月はかかる"),
    ("全員が未加入の会社なら3か月以上みる。経営者に「来月から」と言われても、この見通しをそのままお伝えする。",
     "全員が未加入の会社なら4〜5か月はみる。3か月での開始は見込まない。経営者に「来月から」と言われても、この見通しをそのままお伝えする。"),
    ("ただし一律ではない。未加入の方のiDeCo加入手続に通常1〜2か月、これに労使合意・事業所登録・開始届の準備が乗る。すでに加入済みの方が多ければ短くなる。",
     "未加入の方のiDeCo加入手続に通常1〜2か月かかり、これに労使合意・事業所登録・開始届の準備が乗る。すでに加入済みの方が多い場合でも、実務上の案内は4〜5か月を基本とする。"),
]
for old, new in pairs:
    if old in s:
        if s.count(old) != 1:
            raise SystemExit(f"No.44 wording count mismatch: {old!r} -> {s.count(old)}")
        s = s.replace(old, new, 1)
    elif new not in s:
        raise SystemExit(f"Neither old nor new No.44 wording found: {old!r}")

notice_pat = r"const UPDATED='[^']+', UPDATED_WHAT='[^']*';"
notice_new = "const UPDATED='2026年8月18日', UPDATED_WHAT='No.42・No.44を修正しました。';"
if not re.search(notice_pat, s):
    raise SystemExit("UPDATED / UPDATED_WHAT not found")
s = re.sub(notice_pat, notice_new, s, count=1)
p.write_text(s, encoding="utf-8")

# 2) Patch manual.html update history with both fixes under the same date.
mp = HERE / "manual.html"
m = mp.read_text(encoding="utf-8")
entry = '''<h3>2026年8月18日</h3>
<ul>
<li><b>No.42の質問文に「iDeCo＋」を明記しました。</b>「業績次第で掛金を増やしたり減らしたりできる？」だけでは何の掛金か分かりにくいため、「iDeCo＋の掛金は」と明示しました。回答内容は変えていません。</li>
<li><b>No.44の開始目安を「4〜5か月」に修正しました。</b>「3〜4か月」「3か月以上」という案内をやめ、正解・よくある言い間違い・解説・誤答の補足をすべて4〜5か月基準に統一しました。実務上は3か月での開始を見込まない前提で案内します。</li>
</ul>

'''
if "<h3>2026年8月18日</h3>" in m:
    start = m.index("<h3>2026年8月18日</h3>")
    end = m.find("<h3>", start + len("<h3>2026年8月18日</h3>"))
    if end == -1:
        raise SystemExit("Could not locate end of 2026-08-18 history block")
    m = m[:start] + entry + m[end:]
else:
    marker = "<h3>2026年8月14日</h3>"
    if marker not in m:
        raise SystemExit("2026-08-14 history marker not found")
    m = m.replace(marker, entry + marker, 1)
mp.write_text(m, encoding="utf-8")

# 3) Restore canonical preflight.py before validation/commit.
orig = subprocess.run(
    ["git", "show", "origin/main:tools/preflight.py"],
    cwd=HERE, capture_output=True, text=True, check=True
).stdout
# origin/main currently contains the temporary workflow commits but the canonical
# preflight itself is unchanged. Guard against accidentally restoring this wrapper.
if "One-shot wrapper for the 2026-08-18" in orig:
    raise SystemExit("origin/main preflight is not canonical")
SELF.write_text(orig, encoding="utf-8")

# 4) Execute the canonical preflight in this process with its canonical __file__.
g = {"__name__": "__main__", "__file__": str(SELF)}
exec(compile(orig, str(SELF), "exec"), g, g)
