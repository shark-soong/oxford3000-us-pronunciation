"""1단계: Oxford 3000 PDF 텍스트 → words.json

입력: oxford3000_raw.txt  (pdftotext -raw -enc UTF-8 American_Oxford_3000.pdf 결과)
출력: words.json          (단어/의미구분/동형어번호/품사별 레벨)
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
LEVEL = r"[ABC][12]"
POS = (r"(?:modal v\.|auxiliary v\.|indefinite article|definite article|"
       r"infinitive marker|number(?:/[a-z]+\.)?|[a-z]+\.(?:/[a-z]+\.?)?)")

# 원본 표기 → 표준 약어
POS_FIX = {"noun.": "n.", "det./number": "det./number"}
# 원본 PDF 오타 수정 (근거: Oxford 3000 공식 목록)
ENTRY_FIX = {"produce": [("v.", "A2"), ("n.", "B2")]}


def read_entries():
    """줄바꿈으로 잘린 항목을 이어 붙여 한 항목 = 한 줄로 만든다."""
    entries, buf = [], ""
    for line in (HERE / "oxford3000_raw.txt").read_text(encoding="utf8").splitlines():
        line = line.strip()
        if not line or "Oxford" in line or re.fullmatch(r"\d+ / \d+", line):
            continue
        buf = buf + line if buf.endswith("/") else (buf + " " + line).strip()
        if re.search(LEVEL + "$", buf):
            entries.append(buf)
            buf = ""
    assert not buf, buf
    return entries


def parse(entry):
    m = re.match(r"^(.+?)(\d)?(?: \((.+?)\))? (" + POS + r"[\s\S]*)$", entry)
    word, homo, sense, rest = m.groups()
    rest = re.sub(r"\.(" + LEVEL + ")", r". \1", rest)  # "adj.B1" → "adj. B1"
    pos_list = []
    for group, level in re.findall(r"(.+?)\s*(" + LEVEL + r")(?:,\s*|$)", rest):
        for p in group.split(","):
            p = p.strip()
            if p:
                pos_list.append({"pos": POS_FIX.get(p, p), "level": level})
    if word in ENTRY_FIX and not homo:
        pos_list = [{"pos": p, "level": l} for p, l in ENTRY_FIX[word]]
    return {
        "word": word.strip(),
        "homograph": int(homo) if homo else None,
        "sense": sense,
        "pos": pos_list,
        "extra": {},  # 추가 열(뜻, 예문 등)은 여기에
    }


def main():
    words = [parse(e) for e in read_entries()]
    for i, w in enumerate(words, 1):
        w["id"] = i
    (HERE / "words.json").write_text(
        json.dumps(words, ensure_ascii=False, indent=1), encoding="utf8")
    print(f"{len(words)} entries, {sum(len(w['pos']) for w in words)} pos rows")


if __name__ == "__main__":
    main()
