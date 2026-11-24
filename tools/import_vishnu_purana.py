"""Build corpus files from Project Gutenberg #66208, 'A Prose English Translation of Vishnupuranam'
(Manmatha Nath Dutt, 1896, based on H. H. Wilson's 1840 translation).
Run on an isolated download folder:
    python -I tools/import_vishnu_purana.py <dir with pg66208.txt> <corpus_dir>
Six parts, each with SECTION headings; footnotes at the end of the book are dropped and [n] markers removed."""
import re
import sys
from pathlib import Path

LIMIT = 700
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
PART = re.compile(r"^PART ([IVX]+)\.\s*$")
SEC = re.compile(r"^SECTION ([IVXLC]+)\.?\s*$")
END = re.compile(r"^THE END OF PART ([IVX]+)\.?\s*$")
FOOT = re.compile(r"^\[1\] ")


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


def main(src, out):
    t = (Path(src) / "pg66208.txt").read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    a = t.find("*** START"); a = t.find("\n", a) + 1
    b = t.find("*** END")
    lines = t[a:b].split("\n")
    # the body starts at the last 'PART I.' heading that is followed by 'SECTION I.' (the contents also lists parts)
    start = next(i for i, l in enumerate(lines) if PART.match(l.strip()) and l.strip() == "PART I."
                 and any(SEC.match(x.strip()) for x in lines[i + 1:i + 6]))
    part, sec, cur, paras, res = None, None, [], [], []

    def flush_para():
        if cur:
            paras.append(re.sub(r"\s+", " ", " ".join(cur)).strip()); cur.clear()

    def close():
        flush_para()
        if part and sec and paras:
            res.append((part, sec, list(paras)))
        paras.clear()
    for ln in lines[start:]:
        s = ln.strip()
        if FOOT.match(s):
            break  # the footnote section starts here
        m = PART.match(s)
        if m:
            close(); part, sec = rom(m.group(1)), None; continue
        if END.match(s):
            close(); sec = None; continue
        m = SEC.match(s)
        if m:
            close(); sec = rom(m.group(1)); continue
        if sec is None:
            continue
        if not s:
            flush_para(); continue
        cur.append(s)
    close()
    per_part, seen = {}, set()
    for part, sec, ps in res:
        if (part, sec) in seen:
            continue
        seen.add((part, sec))
        ps = [re.sub(r"\s+", " ", re.sub(r"\[\d+\]", "", p)).strip() for p in ps]
        ps = [p for p in ps if len(p) > 15]
        for k, c in enumerate(pack(ps), 1):
            lead = f"(Part {part}, section {sec}) " if k == 1 else ""
            per_part.setdefault(part, []).append((f"Vishnu Purana {part}.{sec}.{k}", lead + c))
    total = 0
    for part, ents in sorted(per_part.items()):
        head = ("---\nsource: Vishnu Purana Part %d (Dutt after Wilson)\nlicense: public-domain\n"
                "origin: Manmatha Nath Dutt, A Prose English Translation of Vishnupuranam (Calcutta, 1896), based on H. H. Wilson's "
                "1840 translation; Project Gutenberg eBook #66208 (transcriber corrected the scan); public domain in the US and, "
                "as both translators died long ago, expected free in India too [verify]; Project Gutenberg Licence applies if "
                "redistributed. Translator's footnotes are left out. References are Vishnu Purana part.section.piece\n"
                "translator: Manmatha Nath Dutt (after H. H. Wilson)\ntradition: Purana / Vishnu Purana\n---\n\n" % part)
        body = "\n\n".join(f"[{r}] {x}" for r, x in ents)
        (Path(out) / f"vishnu_purana_part{part}_dutt.md").write_text(head + body + "\n", encoding="utf-8")
        total += len(ents)
        print("Part", part, "sections", len({s for p, s in seen if p == part}), "passages", len(ents))
    print("passages", total)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1], sys.argv[2])
