"""3단계: 캐시된 Cambridge 페이지 → words.json 에 품사별 미국식 발음(ipa) 기입

우선순위
  1. overrides.json (사람이 확인해서 넣은 값)
  2. Cambridge Advanced Learner's Dictionary(cald4)의 US 발음
  3. 같은 단어, 다른 품사의 cald4 발음 (품사 블록에 발음이 생략된 경우)
  4. Cambridge American Dictionary(cacd)의 발음 (표기 방식이 달라 review 대상)
판단이 애매한 항목은 review.csv 로 출력한다.
"""
import csv
import gzip
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

from bs4 import BeautifulSoup

HERE = Path(__file__).parent
CACHE = HERE / "cache"
fetch = __import__("2_fetch")  # slug(), variants() 재사용

POS_MAP = {
    "n.": ["noun"], "v.": ["verb"], "adj.": ["adjective"], "adv.": ["adverb"],
    "prep.": ["preposition"], "pron.": ["pronoun"], "conj.": ["conjunction"],
    "det.": ["determiner"], "exclam.": ["exclamation"], "number": ["number"],
    "modal v.": ["modal verb", "verb"], "auxiliary v.": ["auxiliary verb", "verb"],
    "indefinite article": ["determiner", "indefinite article"],
    "definite article": ["determiner", "definite article"],
    "infinitive marker": ["infinitive marker", "preposition"],
}
LABEL_KO = {"strong": "강", "weak": "약"}


def cambridge_pos(oxford_pos):
    out = []
    for p in oxford_pos.split("/"):
        p = p if p.endswith(".") or " " in p or p == "number" else p + "."
        out += POS_MAP.get(p, [])
    return out


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower().replace("’", "'").strip())
    return "".join(c for c in s if not unicodedata.combining(c))  # café → cafe


def header_prons(header):
    """pos-header 안의 US 발음들 [(label, ipa)] — 약형은 .us 바깥 형제 span에 있다."""
    out = []
    if header is None:
        return out
    for pron in header.select(".pron"):
        if pron.find_parent(class_="irreg-infls"):  # 복수형·과거형 등 변화형 발음 제외
            continue
        region = pron.find_parent(class_="dpron-i") or pron.find_previous(class_="dpron-i")
        if region is None or "us" not in region.get("class", []):
            continue
        ipa = pron.select_one(".ipa")
        lab = pron.select_one(".lab")
        if ipa:
            out.append((lab.get_text(strip=True) if lab else "", ipa.get_text().strip()))
    return out


@lru_cache(maxsize=None)
def load_entries(slug):
    path = CACHE / f"{slug}.html.gz"
    if not path.exists():
        return None
    soup = BeautifulSoup(gzip.decompress(path.read_bytes()).decode("utf8"), "html.parser")
    entries = []
    for d in soup.select("div.pr.dictionary"):
        for e in d.select("div.entry-body__el"):
            header = e.select_one(".pos-header") or e.select_one(".di-head")
            hw = e.select_one(".headword")
            entries.append({
                "dict": d.get("data-id"),
                "headword": norm(hw.get_text()) if hw else "",
                "pos": [p.get_text(strip=True) for p in header.select(".pos")] if header else [],
                "guide": [g.get_text(" ", strip=True).strip("() ") for g in e.select(".guideword")],
                "us": header_prons(header),
            })
    return entries


def uniq(prons_list):
    """[[(label, ipa)...], ...] 에서 중복 제거 (순서 유지)"""
    seen, out = set(), []
    for prons in prons_list:
        key = tuple(prons)
        if prons and key not in seen:
            seen.add(key)
            out.append(prons)
    return out


def lookup(word, oxford_pos):
    """한 표제어(변형 하나) + 옥스포드 품사 → (후보 발음 목록, 출처)"""
    entries = load_entries(fetch.slug(word))
    if entries is None:
        return [], "not-fetched"
    w = norm(word)
    cpos = cambridge_pos(oxford_pos)

    def pos_exact(e):
        return set(e["pos"]) & set(cpos)

    def pos_loose(e):  # "plural noun" ⊃ noun, "phrasal verb" ⊃ verb
        return any(c in p for p in e["pos"] for c in cpos)

    # cald4-us = 같은 학습자 사전의 미국 철자 표제어(afterward, kilometer …)
    for family, dict_ids in (("cald4", ("cald4-us", "cald4")), ("cacd", ("cacd",))):
        pool = [e for e in entries if e["dict"] in dict_ids]
        exact_hw = [e for e in pool if e["headword"] == w]
        phrase_hw = [e for e in pool if e["headword"].startswith(w + " ")]  # rely on …
        hit = uniq(e["us"] for e in exact_hw if pos_exact(e))
        if hit:
            return hit, family
        if family == "cald4":
            any_pos = uniq(e["us"] for e in exact_hw)
            if len(any_pos) == 1:  # 품사 블록에 발음이 없지만 단어 전체 발음이 하나뿐
                return any_pos, "cald4-otherpos"
        for cands in (exact_hw, phrase_hw):
            hit = uniq(e["us"] for e in cands if pos_loose(e))
            if hit:
                return hit, family + "-loose"
    return [], "missing"


def fmt(prons, src=""):
    parts, prev = [], None
    for lab, ipa in prons:
        ko = LABEL_KO.get(lab, lab)
        parts.append(f"{ko} /{ipa}/" if ko and ko != prev else f"/{ipa}/")  # 같은 라벨 반복 생략
        prev = ko
    mark = " †" if src.startswith("cacd") else ""  # Cambridge American Dictionary 표기
    return ", ".join(parts) + mark


def entry_key(w, pos):
    return f"{w['word']}|{w['homograph'] or ''}|{w['sense'] or ''}|{pos}"


def main():
    words = json.loads((HERE / "words.json").read_text(encoding="utf8"))
    ov_path = HERE / "overrides.json"
    overrides = json.loads(ov_path.read_text(encoding="utf8")) if ov_path.exists() else {}
    review = []
    for w in words:
        multi = len(fetch.variants(w["word"])) > 1
        for p in w["pos"]:
            key = entry_key(w, p["pos"])
            if key in overrides:
                p["ipa"], p["src"] = overrides[key], "manual"
                continue
            texts, srcs, alts = [], [], []
            for v in fetch.variants(w["word"]):
                cands, src = lookup(v, p["pos"])
                srcs.append(src)
                if cands:
                    texts.append((f"{v}: " if multi else "") + fmt(cands[0], src))
                    alts += [fmt(c, src) for c in cands[1:]]
            p["ipa"] = " · ".join(texts)
            p["src"] = "+".join(dict.fromkeys(srcs))
            reason = []
            if not texts:
                reason.append("발음 없음")
            if alts:
                reason.append("후보 여러 개")
            if any(s not in ("cald4",) for s in srcs):
                reason.append(f"출처 {p['src']}")
            if reason:
                review.append([key, p["ipa"], " | ".join(alts), ", ".join(reason)])
    (HERE / "words.json").write_text(
        json.dumps(words, ensure_ascii=False, indent=1), encoding="utf8")
    with open(HERE / "review.csv", "w", newline="", encoding="utf-8-sig") as f:
        cw = csv.writer(f)
        cw.writerow(["key", "chosen", "alternatives", "reason"])
        cw.writerows(review)
    print(f"review: {len(review)} rows")


if __name__ == "__main__":
    main()
