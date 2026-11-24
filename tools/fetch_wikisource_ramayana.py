"""Download Griffith's Ramayana canto pages (public domain, 1870-74) from Wikisource's API.
Run: python -I tools/fetch_wikisource_ramayana.py <output dir>
Polite and resumable: 20 titles per request, 4 s pause, back-off on HTTP 429, generic User-Agent.
Wikisource transcription text is CC BY-SA 4.0."""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://en.wikisource.org/w/api.php"
UA = "PersonalCorpusBuilder/1.0 (private, non-commercial)"


def call(params):
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers={"User-Agent": UA})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 5:
                raise
            time.sleep(min(int(e.headers.get("Retry-After", "60")), 300) + 5)


def main(out):
    out = Path(out); out.mkdir(exist_ok=True)
    titles, cont = [], {}
    while True:
        d = call({"action": "query", "list": "allpages", "apprefix": "The Ramayana/", "aplimit": "500",
                  "format": "json", "formatversion": "2", **cont})
        titles += [p["title"] for p in d["query"]["allpages"]]
        if "continue" not in d:
            break
        cont = d["continue"]
    cache = out / "ramayana.json"
    got = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    for i in range(0, len(titles), 20):
        chunk = [t for t in titles[i:i + 20] if t not in got]
        if not chunk:
            continue
        d = call({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                  "format": "json", "formatversion": "2", "titles": "|".join(chunk)})
        for p in d["query"]["pages"]:
            if "revisions" in p:
                got[p["title"]] = p["revisions"][0]["slots"]["main"]["content"]
        cache.write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
        time.sleep(4)
    print("titles", len(titles), "downloaded", len(got))


if __name__ == "__main__":
    main(sys.argv[1])
