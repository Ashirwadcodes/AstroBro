"""Build corpus files from Wikisource pages of Griffith's Ramayana (1870-74, metrical).
Run: python -I tools/import_ramayana.py <dir with ramayana.json> <corpus_dir>"""
import json
import re
import sys
from pathlib import Path

LIMIT = 700
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
BOOKS = {"I": "Bala", "II": "Ayodhya", "III": "Aranya", "IV": "Kishkindha", "V": "Sundara", "VI": "Yuddha"}


def rom(s):
    n = 0
    for a, b in zip(s, s[1:] + " "):
        v = ROMAN[a]
        n += -v if b != " " and ROMAN.get(b, 0) > v else v
    return n


def clean(t):
    t = re.sub(r"<ref[^>]*/>", "", t)
    t = re.sub(r"<ref[^>]*>.*?</ref>", "", t, flags=re.S)
    t = re.sub(r"\{\{ppoem\|[^\n]*", "\n", t)       # keep the poem inside {{ppoem| ... }}
    t = re.sub(r"\{\{[^{}\n]*\}\}", "", t)          # drop one-line templates
    t = t.replace("}}", "\n")
    t = re.sub(r"</?(?:poem|div|span|small|center)[^>]*>", "\n", t)
    t = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", t)
    t = t.replace("''", "").replace("&nbsp;", " ")
    return t


def _split(p, limit):
    if len(p) <= limit:
        return [p]
    out, cur = [], ""
    for s in re.split(r"(?<=[.!?:;'\"])\s+(?=[A-Z'\"])", p):
        if cur and len(cur) + len(s) + 1 > limit:
            out.append(cur); cur = ""
        cur = (cur + " " + s).strip()
    out += [cur] if cur else []
    return [w for x in out for w in ([x] if len(x) <= limit * 1.6 else
            [x[i:i + limit] for i in range(0, len(x), limit)])]


def pack(paras, limit=LIMIT):
    out, cur = [], ""
    for p in [y for x in paras for y in _split(x, limit)]:
        if cur and len(cur) + len(p) + 1 > limit:
            out.append(cur); cur = ""
        cur = (cur + " " + p).strip()
    return out + ([cur] if cur else [])


def main(src, out):
    d = json.loads((Path(src) / "ramayana.json").read_text(encoding="utf-8"))
    per_book, q = {}, []
    for title in sorted(d):
        m = re.match(r"The Ramayana/Book ([IVX]+)/Canto ([IVXLC]+): (.*)$", title)
        if not m:
            continue
        book, canto, name = m.group(1), rom(m.group(2)), m.group(3)
        raw = d[title]
        qm = re.search(r"TextQuality\|(\d+)", raw)
        q.append(int(qm.group(1)) if qm else 0)
        body = raw.split("}}", 1)[1] if raw.lstrip().startswith(("{{TextQuality", "{{header")) else raw
        body = body.split("}}", 1)[1] if body.lstrip().startswith("{{header") or "| translator" in body[:200] else body
        text = clean(body)
        paras = [re.sub(r"\s+", " ", " ".join(x.split("\n"))).strip() for x in re.split(r"\n\s*\n|\n(?=\s{2,}\S)", text)]
        paras = [p for p in paras if len(p) > 20 and not p.startswith("sa:") and "रामायण" not in p]
        for k, c in enumerate(pack(paras), 1):
            lead = f"(Canto {canto}: {name}) " if k == 1 else ""
            per_book.setdefault(book, []).append((f"Ramayana {book}.{canto}.{k}", lead + c))
    total = 0
    for book, ents in sorted(per_book.items(), key=lambda x: rom(x[0])):
        head = ("---\nsource: Ramayana Book %s - %s Kanda (Griffith)\nlicense: cc-by-sa\n"
                "origin: Ralph T. H. Griffith, The Ramayan of Valmiki translated into English verse (1870-74; public domain). "
                "Text from English Wikisource (en.wikisource.org/wiki/The_Ramayana), CC BY-SA 4.0; credit Wikisource "
                "contributors and keep this licence if the corpus is shared. Only Books I-III and the last canto of Book VI are on "
                "Wikisource; footnotes are left out. Verse translation in couplets, free rather than literal\n"
                "translator: Ralph T. H. Griffith\ntradition: Itihasa / Ramayana\n---\n\n" % (book, BOOKS[book]))
        body = "\n\n".join(f"[{r}] {t}" for r, t in ents)
        (Path(out) / f"ramayana_book{rom(book)}_griffith.md").write_text(head + body + "\n", encoding="utf-8")
        total += len(ents)
        print("Book", book, len(ents))
    print("passages", total, "text quality labels:", {x: q.count(x) for x in sorted(set(q))})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
