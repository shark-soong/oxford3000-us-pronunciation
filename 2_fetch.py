"""2단계: Cambridge Dictionary 페이지 수집 → cache/<slug>.html.gz

- 단어당 1회만 요청하고, 사전 본문(div.pr.dictionary)만 압축 저장한다.
- 이미 캐시가 있으면 건너뛰므로 중단 후 다시 실행해도 된다.
- 개인 학습용. 요청 간격을 두어 서버에 부담을 주지 않는다.
"""
import gzip
import json
import random
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HERE = Path(__file__).parent
CACHE = HERE / "cache"
URL = "https://dictionary.cambridge.org/dictionary/english/{}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
DELAY = (1.0, 2.0)  # 초


def variants(word):
    """'a, an' 처럼 쉼표로 묶인 표제어는 각각 따로 찾는다."""
    return [v.strip() for v in word.split(",")]


def slug(word):
    return word.lower().replace("’", "-").replace("'", "-").replace(" ", "-")


def fetch(session, s):
    for attempt in range(4):
        try:
            r = session.get(URL.format(s), timeout=30)
            if r.status_code == 200:
                return r.text
            print(f"  {s}: HTTP {r.status_code}")
        except requests.RequestException as e:
            print(f"  {s}: {e}")
        time.sleep(10 * (attempt + 1))
    return None


def main():
    CACHE.mkdir(exist_ok=True)
    words = json.loads((HERE / "words.json").read_text(encoding="utf8"))
    slugs = list(dict.fromkeys(slug(v) for w in words for v in variants(w["word"])))
    todo = [s for s in slugs if not (CACHE / f"{s}.html.gz").exists()]
    print(f"{len(slugs)} slugs, {len(todo)} to fetch")

    session = requests.Session()
    session.headers["User-Agent"] = UA
    for i, s in enumerate(todo, 1):
        html = fetch(session, s)
        if html is None:
            print(f"  FAILED {s}")
            continue
        dicts = BeautifulSoup(html, "html.parser").select("div.pr.dictionary")
        body = "\n".join(str(d) for d in dicts)  # 빈 문자열 = 사전에 없음
        (CACHE / f"{s}.html.gz").write_bytes(gzip.compress(body.encode("utf8")))
        if i % 50 == 0:
            print(f"{i}/{len(todo)}", flush=True)
        time.sleep(random.uniform(*DELAY))
    print("done")


if __name__ == "__main__":
    main()
