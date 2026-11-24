"""Build corpus files from the downloaded Wikisource pages of Griffith's Rigveda (1896).
Run: python -I tools/import_rigveda.py <dir with rv_hymns.json and rv_pages.json> <corpus_dir>"""
import json
import re
import sys
from pathlib import Path

LIMIT = 700
BOOKNAME = {1: "01", 2: "02", 3: "03", 4: "04", 5: "05", 6: "06", 7: "07", 8: "08", 9: "09", 10: "10"}


def strip_markup(t):
    t = re.sub(r"<ref[^>]*>.*?</ref>", "", t, flags=re.S)
    t = re.sub(r"<section[^>]*/>", "", t)
    t = re.sub(r"\{\{sc\|([^}]*)\}\}", r"\1", t)
    t = re.sub(r"\{\{(?:gap|rule|c|l|xl|rh|float right|header|smallrefs)[^{}]*\}\}", "", t)
    t = re.sub(r"<br\s*/?>", "", t)
    t = re.sub(r"</?(?:div|pre|poem|noinclude|includeonly)[^>]*>", "", t)
    t = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\{\{SIC\|[^|}]*\|([^}]*)\}\}", r"\1", t)   # keep the corrected spelling
    t = re.sub(r"\s:(?:Translation|Note)[^\n]*", "", t)     # contributor notes, not scripture
    t = re.sub(r"\{\{ISBN\|[^}]*\}\}", "", t)
    t = t.replace("''", "").replace("&nbsp;", " ")
    return t


def stanzas_plain(content):
    body = content.split("}}", 1)[1] if content.lstrip().startswith("{{header") else content
    out, cur, n = [], None, 0
    for ln in strip_markup(body).split("\n"):
        m = re.match(r"^ {0,1}(\d+)[.,]?\s+(.*)", ln)
        if m is None and cur is None and re.match(r"^\s+[Il1]\s+[A-Z]", ln):  # OCR: stanza 1 labelled 'I'
            m = re.match(r"^\s+[Il1]\s+(.*)", ln)
            if m:
                cur = [1, m.group(1).strip()]
                continue
        if m:
            if cur:
                out.append(cur)
            cur = [int(m.group(1)), m.group(2).strip()]
        elif cur and ln.strip():
            cur[1] += " " + ln.strip()
    if cur:
        out.append(cur)
    return out


def section_slice(text, frm, to):
    def idx(kind, name, start=0):
        nm = r"\s*".join(map(re.escape, "".join(name.split())))
        pat = re.compile(r'<section %s="\s*%s\s*"' % (kind, nm), re.I)
        m = pat.search(text, start)
        return m.start() if m else None
    a = idx("begin", frm) if frm else 0
    if a is None:
        a = 0
    b = idx("end", to, a) if to else None
    return text[a:b] if b else text[a:]


def stanzas_transcluded(content, pages):
    m = re.search(r'<pages index="The Hymns of the Rigveda Vol (\d)\.djvu" include="([\d,-]+)"(?: fromsection="([^"]+)")?(?: tosection="([^"]+)")?', content)
    vol, inc, frm, to = m.groups()
    nums = []
    for part in inc.split(","):
        a, _, b = part.partition("-")
        nums += list(range(int(a), int(b or a) + 1))
    text = "\n".join(pages.get(f"{vol}/{n}", "") for n in nums)
    text = section_slice(text, frm, to)
    text = strip_markup(text).replace("{{ppoem|start=stanza|", "").replace("{{ppoem|end=stanza|", "").replace("}}", "")
    text = re.sub(r'\S*" ?/>', " ", text)          # leftovers of <section ... user="x" /> tags
    text = re.sub(r"\{\{[a-z]*\|*", " ", text)      # leftover template openers
    parts = re.split(r"^\s*(\d+) <<<\s*", text, flags=re.M)
    out = []
    first = parts[0].strip()
    first = re.sub(r"^.*?(?=[A-Z])", "", first, count=1, flags=re.S) if first else first
    if first:
        first = re.sub(r"\s+", " ", first)
        first = re.sub(r"^(?:HYMN [IVXL]+\.?\s*)?(?:[A-Z][a-z]+\.\s+)?(?:[Il1],\s+)?", "", first) if len(first) > 20 else first
        out.append([1, first])
    for i in range(1, len(parts) - 1, 2):
        out.append([int(parts[i]), re.sub(r"\s+", " ", parts[i + 1]).strip()])
    return out


def pack(st, limit=LIMIT):
    chunks, cur, first, last = [], "", None, None
    for n, t in st:
        piece = f"{n}. {t}"
        if cur and len(cur) + len(piece) + 1 > limit:
            chunks.append((first, last, cur)); cur, first = "", None
        cur = (cur + " " + piece).strip()
        first = n if first is None else first
        last = n
    if cur:
        chunks.append((first, last, cur))
    return chunks


def main(src, out):
    src, out = Path(src), Path(out)
    hymns = json.loads((src / "rv_hymns.json").read_text(encoding="utf-8"))
    pages = json.loads((src / "rv_pages.json").read_text(encoding="utf-8"))
    per_book, gaps, total = {}, [], 0
    for title, content in hymns.items():
        m = re.search(r"Book (\d+)/Hymn (\d+)$", title)
        b, h = int(m.group(1)), int(m.group(2))
        st = stanzas_transcluded(content, pages) if "<pages index" in content else stanzas_plain(content)
        nums = [n for n, _ in st]
        if not st or nums != list(range(1, len(nums) + 1)):
            gaps.append((b, h, nums[:12]))
        for a, z, text in pack(st):
            ref = f"Rigveda {b}.{h}.{a}" if a == z else f"Rigveda {b}.{h}.{a}-{z}"
            per_book.setdefault(b, []).append((ref, text))
    for b, ents in sorted(per_book.items()):
        head = ("---\nsource: Rigveda Book %d (Griffith)\nlicense: cc-by-sa\n"
                "origin: Ralph T. H. Griffith, The Hymns of the Rigveda (1889-92, 2nd ed. 1896; public domain). Text from English "
                "Wikisource (en.wikisource.org/wiki/The_Hymns_of_the_Rigveda), CC BY-SA 4.0; credit Wikisource contributors and "
                "keep this licence if the corpus is shared. Verse numbers are Rigveda book.hymn.stanza; the translation is "
                "poetic and the deity names are not given on these pages\n"
                "translator: Ralph T. H. Griffith\ntradition: Vedic\n---\n\n" % b)
        body = "\n\n".join(f"[{r}] {t}" for r, t in ents)
        (out / f"rigveda_book{BOOKNAME[b]}_griffith.md").write_text(head + body + "\n", encoding="utf-8")
        total += len(ents)
    print("passages", total, "hymns with irregular stanza numbering:", len(gaps))
    for g in gaps[:15]:
        print("  ", g)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
