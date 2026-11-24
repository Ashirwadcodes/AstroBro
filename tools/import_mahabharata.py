"""Build corpus files from Project Gutenberg's text of K. M. Ganguli's Mahabharata (1883-96).
Run on an isolated download folder:
    python -I tools/import_mahabharata.py <dir with pg*.txt> <corpus_dir>
Handles every pgNNNN.txt in the folder; each holds one or more 'BOOK n' parts. Footnotes are dropped,
[n] markers removed, sections ('SECTION I' or a bare number) become the reference unit."""
import re
import sys
from pathlib import Path

LIMIT = 700
PARVA = {1: "Adi", 2: "Sabha", 3: "Vana", 4: "Virata", 5: "Udyoga", 6: "Bhishma", 7: "Drona", 8: "Karna",
         9: "Shalya", 10: "Sauptika", 11: "Stri", 12: "Shanti", 13: "Anushasana", 14: "Ashvamedhika",
         15: "Ashramavasika", 16: "Mausala", 17: "Mahaprasthanika", 18: "Svargarohanika"}
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
BOOK = re.compile(r"^BOOK (\d+)\s*$")
SEC = re.compile(r"^(?:SECTION )([IVXLC]+)\s*$|^(\d{1,3})\s*$")


def rom(s):
    n = 0
    for a, b in zip(s, s[1:] + " "):
        v = ROMAN[a]
        n += -v if b != " " and ROMAN.get(b, 0) > v else v
    return n


def split_long(p, limit):
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
    for p in [y for x in paras for y in split_long(x, limit)]:
        if cur and len(cur) + len(p) + 1 > limit:
            out.append(cur); cur = ""
        cur = (cur + " " + p).strip()
    return out + ([cur] if cur else [])


def body_lines(path):
    t = Path(path).read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    a = t.find("*** START")
    a = t.find("\n", a) + 1 if a >= 0 else 0
    b = t.find("*** END")
    return t[a:b if b > 0 else None].split("\n")


def parse_file(path):
    """Yield (book, section, paragraphs) for every section."""
    lines = body_lines(path)
    book, sec, paras, cur, in_foot, sub = None, None, [], [], False, ""
    started = False

    def flush_para():
        if cur:
            paras.append(re.sub(r"\s+", " ", " ".join(cur)).strip()); cur.clear()

    def close():
        flush_para()
        if book and sec and paras:
            res.append((book, sec, sub, list(paras)))
        paras.clear()
    res = []
    for ln in lines:
        s = ln.strip()
        m = BOOK.match(s)
        if m:  # a book heading ends the previous book (and its footnote area)
            close(); book, sec, in_foot = int(m.group(1)), None, False
            continue
        if s == "FOOTNOTES":
            close(); sec, in_foot = None, True
            continue
        if in_foot or book is None:
            continue
        ms = SEC.match(s)
        if ms and (ms.group(1) or ms.group(2)):
            close()
            sec = rom(ms.group(1)) if ms.group(1) else int(ms.group(2))
            sub = ""
            continue
        if sec is None:
            continue  # book title page before the first section
        if not s:
            flush_para(); continue
        if re.fullmatch(r"\([A-Za-z' -]+\)", s) and not paras and not cur:
            sub = s.strip("()"); continue
        cur.append(s)
    close()
    return res


def clean(p):
    p = re.sub(r"\[\d+\]", "", p)
    p = p.replace("_", "")
    return re.sub(r"\s+", " ", p).strip()


def main(src, out):
    src, out = Path(src), Path(out)
    per_book, seen = {}, {}
    for f in sorted(src.glob("pg*.txt")):
        for book, sec, sub, paras in parse_file(f):
            key = (book, sec)
            if key in seen:  # same section in two ebooks: keep the first
                continue
            seen[key] = f.name
            paras = [clean(p) for p in paras]
            paras = [p for p in paras if len(p) > 15]
            for k, c in enumerate(pack(paras), 1):
                lead = f"({PARVA.get(book, '?')} Parva, section {sec}{': ' + sub if sub else ''}) " if k == 1 else ""
                per_book.setdefault(book, []).append((f"Mahabharata {book}.{sec}.{k}", lead + c))
    total = 0
    for book, ents in sorted(per_book.items()):
        secs = len({k for k in seen if k[0] == book})
        head = ("---\nsource: Mahabharata Book %d - %s Parva (Ganguli)\nlicense: public-domain\n"
                "origin: Kisari Mohan Ganguli, The Mahabharata of Krishna-Dwaipayana Vyasa translated into English prose "
                "(1883-96), Project Gutenberg (volumes 15474-15477 and others); public domain in the US and, as the translator "
                "died in 1908, expected to be in India too [verify]; Project Gutenberg Licence applies if redistributed. "
                "Footnotes are left out. References are Mahabharata book.section.part\n"
                "translator: Kisari Mohan Ganguli\ntradition: Itihasa / Mahabharata\n---\n\n" % (book, PARVA.get(book, "?")))
        body = "\n\n".join(f"[{r}] {t}" for r, t in ents)
        (out / f"mahabharata_book{book:02d}_ganguli.md").write_text(head + body + "\n", encoding="utf-8")
        total += len(ents)
        print("Book", book, PARVA.get(book), "sections", secs, "passages", len(ents))
    print("passages", total)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1], sys.argv[2])
