"""Download Griffith's Rigveda hymn pages (public-domain 1896 translation) from Wikisource's API.
Run: python -I tools/fetch_wikisource_rigveda.py <empty output dir>
Polite: 40 titles per request, 1 s pause, generic User-Agent, read-only. The Wikisource transcription
is CC BY-SA 4.0; the underlying translation is public domain."""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://en.wikisource.org/w/api.php"
UA = "PersonalCorpusBuilder/1.0 (private, non-commercial)"
HYMNS = {1: 191, 2: 43, 3: 62, 4: 58, 5: 87, 6: 75, 7: 104, 8: 103, 9: 114, 10: 191}


def fetch(titles):
    q = urllib.parse.urlencode({"action": "query", "prop": "revisions", "rvprop": "content|ids",
                                "rvslots": "main", "format": "json", "formatversion": "2",
                                "titles": "|".join(titles)})
    req = urllib.request.Request(API + "?" + q, headers={"User-Agent": UA})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)["query"]["pages"]
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 5:
                raise
            wait = int(e.headers.get("Retry-After", "60"))
            print("rate limited; waiting", wait, "s", flush=True)
            time.sleep(min(wait, 300) + 5)


def main(out):
    out = Path(out); out.mkdir(exist_ok=True)
    allt = [f"The Hymns of the Rigveda/Book {b}/Hymn {h}" for b, n in HYMNS.items() for h in range(1, n + 1)]
    cache = out / "rv_hymns.json"
    got = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}  # resumable
    missing = []
    for i in range(0, len(allt), 40):
        if all(t in got for t in allt[i:i + 40]):
            continue
        for p in fetch(allt[i:i + 40]):
            if p.get("missing") or "revisions" not in p:
                missing.append(p["title"])
            else:
                got[p["title"]] = p["revisions"][0]["slots"]["main"]["content"]
        cache.write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
        time.sleep(4)
    print("hymns", len(got), "missing", len(missing), missing[:5])
    # a few hymn pages only transclude proofread book pages; fetch those pages too
    import re
    want = set()
    for c in got.values():
        m = re.search(r'<pages index="The Hymns of the Rigveda Vol (\d)\.djvu" include="([\d,-]+)"', c)
        if m:
            for part in m.group(2).split(","):
                a, _, b = part.partition("-")
                want.update((m.group(1), n) for n in range(int(a), int(b or a) + 1))
    pages = {}
    for vol, n in sorted(want):
        for p in fetch([f"Page:The Hymns of the Rigveda Vol {vol}.djvu/{n}"]):
            if "revisions" in p:
                pages[f"{vol}/{n}"] = p["revisions"][0]["slots"]["main"]["content"]
        time.sleep(4)
    (out / "rv_pages.json").write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    print("transcluded pages", len(pages))


if __name__ == "__main__":
    main(sys.argv[1])
