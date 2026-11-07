"""4단계: words.json (+ extras.csv) → oxford3000.md → oxford3000.html → oxford3000.pdf

열 추가 방법
  extras.csv 에 열을 하나 추가하고(예: '뜻') 값을 채운 뒤 이 스크립트를 다시 실행하면
  표에 그 열이 자동으로 붙는다. 비워 둔 열은 표에 나타나지 않는다.
  extras.csv 의 key/word/pos 열은 행을 찾는 용도이므로 수정하지 말 것.
"""
import csv
import json
import subprocess
from itertools import groupby
from pathlib import Path

import markdown

HERE = Path(__file__).parent
EXTRAS = HERE / "extras.csv"
EXTRAS_FIXED = ["key", "word", "pos"]
SUP = str.maketrans("123", "¹²³")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
LEVEL_DESC = {
    "A1": "입문 (Beginner)", "A2": "초급 (Elementary)",
    "B1": "중급 (Intermediate)", "B2": "중상급 (Upper-intermediate)",
}


def entry_key(w, pos):
    return f"{w['word']}|{w['homograph'] or ''}|{w['sense'] or ''}|{pos}"


def load_extras(words):
    """extras.csv 를 읽는다. 없으면 빈 템플릿을 만든다."""
    if not EXTRAS.exists():
        with open(EXTRAS, "w", newline="", encoding="utf-8-sig") as f:
            cw = csv.writer(f)
            cw.writerow(EXTRAS_FIXED)
            for w in words:
                for p in w["pos"]:
                    cw.writerow([entry_key(w, p["pos"]), w["word"], p["pos"]])
    with open(EXTRAS, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    cols = [c for c in (rows[0].keys() if rows else []) if c not in EXTRAS_FIXED]
    cols = [c for c in cols if any(r[c].strip() for r in rows)]
    return {r["key"]: {c: r[c].strip() for c in cols} for r in rows}, cols


def headword(w):
    s = w["word"] + (str(w["homograph"]).translate(SUP) if w["homograph"] else "")
    return f"**{s}**" + (f" ({w['sense']})" if w["sense"] else "")


def rows_for(w, extras, cols):
    """같은 발음·같은 추가열 값을 가진 품사는 한 줄로 합친다."""
    items = [(p, extras.get(entry_key(w, p["pos"]), {})) for p in w["pos"]]
    distinct = len({p["ipa"] for p, _ in items}) > 1
    groups = []
    for p, ex in items:
        for g in groups:
            if g["ipa"] == p["ipa"] and g["ex"] == ex:
                g["pos"].append(p)
                break
        else:
            groups.append({"ipa": p["ipa"], "ex": ex, "pos": [p]})
    out = []
    for i, g in enumerate(groups):
        # 둘째 줄부터는 단어를 흐리게 (페이지가 넘어가도 어떤 단어인지 알 수 있게)
        word = (headword(w) + (" ⚠" if distinct else "")) if i == 0 \
            else f"<span class='cont'>{w['word']}</span>"
        # 레벨이 섞이면 원본처럼 "prep. A1, conj., adv. A2" 로 품사 옆에 표기, 레벨 열은 최저 레벨
        by_level = [(lv, [p["pos"] for p in ps])
                    for lv, ps in groupby(g["pos"], key=lambda p: p["level"])]
        if len(by_level) == 1:
            pos = ", ".join(by_level[0][1])
        else:
            pos = ", ".join(f"{', '.join(ps)} <small>{lv}</small>" for lv, ps in by_level)
        level = min(p["level"] for p in g["pos"])
        out.append([word, pos, g["ipa"] or "—", level] + [g["ex"].get(c, "") for c in cols])
    return out


def first_letter(w):
    return w["word"][0].upper()


def build_md(words, extras, cols):
    header = ["단어", "품사", "발음 (US)", "레벨"] + cols
    lines = [
        "# Oxford 3000 (American English) 발음 단어장",
        "",
        "발음: Cambridge Dictionary 미국식(US) 발음 · 레벨: CEFR "
        + " / ".join(f"{k} {v}" for k, v in LEVEL_DESC.items()),
        "",
        "⚠ 품사에 따라 발음이 달라지는 단어 · 강/약: 강형(강조할 때)/약형(보통 문장 속) · "
        "¹² 철자가 같은 다른 단어(동형어) · † Cambridge American Dictionary 표기(학습자 사전에 없는 경우) · 품사별 레벨이 다르면 품사 옆에 표기하고 레벨 열에는 가장 낮은 레벨",
        "",
    ]
    for letter, group in groupby(words, key=first_letter):
        lines += [f"## {letter}", "", "| " + " | ".join(header) + " |",
                  "|" + "---|" * len(header)]
        for w in group:
            for r in rows_for(w, extras, cols):
                lines.append("| " + " | ".join(c.replace("|", "\\|") for c in r) + " |")
        lines.append("")
    return "\n".join(lines)


CSS = """
@page { size: A4; margin: 12mm 10mm 14mm;
        @bottom-center { content: counter(page) " / " counter(pages);
                         font: 8pt "Segoe UI", sans-serif; color: #888; } }
body { font-family: "Segoe UI", "Malgun Gothic", sans-serif; font-size: 8.6pt;
       color: #111; margin: 0; }
h1 { font-size: 16pt; margin: 0 0 4px; }
h1 + p, h1 + p + p { font-size: 8pt; color: #444; margin: 2px 0; }
.cols { column-count: 2; column-gap: 7mm; margin-top: 8px; }
h2 { font-size: 11pt; margin: 6px 0 3px; padding: 1px 6px; background: #1f3a5f;
     color: #fff; break-after: avoid; break-inside: avoid; }
table { width: 100%; border-collapse: collapse; margin-bottom: 6px; table-layout: fixed; }
td { overflow-wrap: anywhere; }
th { text-align: left; font-size: 7.5pt; color: #555; border-bottom: 1px solid #888;
     padding: 1px 3px; white-space: nowrap; }
td { padding: 1.5px 3px; border-bottom: 0.5px solid #ddd; vertical-align: top; }
tr { break-inside: avoid; }
td:nth-child(2), td:nth-child(4) { color: #555; }
td:nth-child(2) small { color: #999; font-size: 7pt; }
.cont { color: #bbb; }
td:nth-child(4) { white-space: nowrap; }
td:nth-child(3) { font-family: "Segoe UI", "Lucida Sans Unicode", sans-serif; }
td:nth-child(4) { font-size: 7.5pt; }
"""


COL_WEIGHTS = [25, 21, 44, 10]  # 단어, 품사, 발음, 레벨
EXTRA_WEIGHT = 30               # 추가 열 하나당


def width_css(n_extra):
    """열 너비를 고정해 모든 표가 같은 모양이 되게 한다. 추가 열이 생기면 비율대로 재분배."""
    weights = COL_WEIGHTS + [EXTRA_WEIGHT] * n_extra
    return "".join(f"th:nth-child({i}) {{ width: {w * 100 / sum(weights):.1f}%; }}\n"
                   for i, w in enumerate(weights, 1))


def build_html(md_text, n_extra=0):
    head, _, body = md_text.partition("\n## ")
    body_html = markdown.markdown("## " + body, extensions=["tables"])
    return (f"<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
            f"<title>Oxford 3000 발음 단어장</title>"
            f"<style>{CSS}{width_css(n_extra)}</style></head><body>"
            f"{markdown.markdown(head)}<div class='cols'>{body_html}</div></body></html>")


def main():
    words = json.loads((HERE / "words.json").read_text(encoding="utf8"))
    extras, cols = load_extras(words)
    md_text = build_md(words, extras, cols)
    (HERE / "oxford3000.md").write_text(md_text, encoding="utf8")
    html_path = HERE / "oxford3000.html"
    html_path.write_text(build_html(md_text, len(cols)), encoding="utf8")
    pdf_path = HERE / "oxford3000.pdf"
    subprocess.run([EDGE, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", html_path.as_uri()], check=True)
    print(f"wrote {pdf_path.name} (extra columns: {cols or 'none'})")


if __name__ == "__main__":
    main()
