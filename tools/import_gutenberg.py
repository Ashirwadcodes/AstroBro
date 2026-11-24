"""Turn Project Gutenberg plain-text files into AstroBro corpus files.

Run on an isolated download folder:
    python -I tools/import_gutenberg.py <download_dir> <corpus_dir>
Expects pg2388.txt (Gita, Arnold), pg2526.txt (Yoga Sutras, Johnston),
pg12894.txt (Wilson 1900: Vedic Hymns + Kaushitaki Upanishad).
All three are public domain in the US (translators died long ago).
"""
import re
import sys
from pathlib import Path

MAXC = 650  # keep chunks short: the model context is small
PG = "Project Gutenberg eBook #%s"


def body(path):
    t = Path(path).read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    a = t.find("*** START")
    a = t.find("\n", a) + 1 if a >= 0 else 0
    b = t.find("*** END")
    return t[a:b if b > 0 else None].split("\n")


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def blocks(lines):
    cur, out = [], []
    for ln in lines:
        if ln.strip():
            cur.append(ln.strip())
        elif cur:
            out.append(" ".join(cur)); cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def _split(p, limit):
    if len(p) <= limit:
        return [p]
    out, cur = [], ""
    for sent in re.split(r"(?<=[.!?\"])\s+", p):
        if cur and len(cur) + len(sent) + 1 > limit:
            out.append(cur); cur = ""
        cur = (cur + " " + sent).strip()
    return out + ([cur] if cur else [])


def pack(parts, limit=MAXC):
    out, cur = [], ""
    parts = [x for p in parts for x in _split(p, limit)]
    for p in parts:
        if cur and len(cur) + len(p) + 1 > limit:
            out.append(cur); cur = ""
        cur = (cur + " " + p).strip()
    if cur:
        out.append(cur)
    return out


def emit(path, front, entries):
    head = "---\n" + "".join(f"{k}: {v}\n" for k, v in front.items()) + "---\n\n"
    seen, uniq = {}, []
    for ref, text in entries:  # every reference must be unique: it becomes the passage id
        seen[ref] = seen.get(ref, 0) + 1
        uniq.append((ref if seen[ref] == 1 else f"{ref} [{seen[ref]}]", text))
    body_ = "\n\n".join(f"[{ref}] {norm(text)}" for ref, text in uniq)
    Path(path).write_text(head + body_ + "\n", encoding="utf-8")
    return len(entries)


def gita(src, out):
    lines = body(src / "pg2388.txt")
    idx = [i for i, l in enumerate(lines) if re.fullmatch(r"\s*CHAPTER [IVXL]+\s*", l)]
    roman = lambda s: {"I":1,"V":5,"X":10,"L":50}  # noqa
    entries = []
    for n, i in enumerate(idx, 1):
        end = idx[n] if n < len(idx) else len(lines)
        bl = [b for b in blocks(lines[i + 1:end]) if not b.upper().startswith("HERE ENDETH")]
        for k, c in enumerate(pack(bl), 1):
            entries.append((f"Gita {n}.{k}", c))
    return emit(out / "gita_arnold.md", {
        "source": "Bhagavad Gita (Arnold, 'The Song Celestial')", "license": "public-domain",
        "origin": PG % 2388 + ", translation by Sir Edwin Arnold (1885); Project Gutenberg Licence applies if redistributed",
        "translator": "Sir Edwin Arnold", "tradition": "Vedanta / Gita"}, entries)


def yoga(src, out):
    lines = body(src / "pg2526.txt")
    book, entries, cur_ref, cur = 0, [], None, []
    roman = {1: "I", 2: "II", 3: "III", 4: "IV"}
    skip_intro = False

    def flush():
        if cur_ref and cur:
            for k, c in enumerate(pack(cur, 700)):
                entries.append((cur_ref if k == 0 else f"{cur_ref} (cont.)", c))
    for b in blocks(lines):
        if re.fullmatch(r"INTRODUCTION TO BOOK [IV]+", b):
            flush(); cur_ref, cur, skip_intro = None, [], True; continue
        m = re.fullmatch(r"BOOK (I|II|III|IV)", b)
        if m:
            flush(); book = {"I":1,"II":2,"III":3,"IV":4}[m.group(1)]; cur_ref, cur, skip_intro = None, [], False; continue
        if skip_intro or not book:
            continue
        m = re.match(r"(\d+)\. (.*)", b)
        if m:
            flush(); cur_ref = f"Yoga Sutras {roman[book]}.{m.group(1)}"; cur = [m.group(2)]
        elif cur_ref:
            cur.append(b)
    flush()
    return emit(out / "yoga_sutras_johnston.md", {
        "source": "Yoga Sutras of Patanjali (Johnston)", "license": "public-domain",
        "origin": PG % 2526 + ", translation and commentary by Charles Johnston (1912, Theosophical-leaning commentary); Project Gutenberg Licence applies if redistributed",
        "translator": "Charles Johnston", "tradition": "Yoga"}, entries)


def hymns_upanishad(src, out):
    lines = body(src / "pg12894.txt")
    # line numbers refer to the full file; header offset
    full = (src / "pg12894.txt").read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").split("\n")
    def seg(a, b):
        return full[a - 1:b - 1]
    def split_titled(seg_lines, prefix, cap_re):
        entries, title, cur, n = [], None, [], 0
        def flush():
            nonlocal n
            if title and cur:
                for k, c in enumerate(pack(cur)):
                    n += 1
                    entries.append((f"{prefix}: {title.title()} {k+1}", c))
        for b in blocks(seg_lines):
            if cap_re.fullmatch(b) and len(b) < 70:
                flush(); title, cur = re.sub(r"\[\d+\]", "", b).strip(), []
            elif b.startswith("[Footnote") or re.fullmatch(r"[IVXL]+", b):
                continue  # translator footnotes and verse numerals are not text
            elif title:
                cur.append(re.sub(r"\[\d+\]", "", b))
        flush()
        return entries
    cap = re.compile(r"[A-ZÂ][A-ZÂ ,.'-]{5,}(\[\d+\])?")
    h = split_titled(seg(226, 1493), "Vedic Hymn", cap)
    h = [(r.replace("Vedic Hymn: ", "Vedic Hymns, ").strip(), t) for r, t in h]
    # Upanishad: one title block then prose
    u_lines = seg(6023, 6588)
    ub = [re.sub(r'\[\d+\]', '', b) for b in blocks(u_lines) if not b.startswith('[Footnote')]
    ents_u = [(f"Kaushitaki Upanishad {k+1}", c) for k, c in enumerate(pack(ub[1:] if ub else []))]
    n1 = emit(out / "vedic_hymns_wilson.md", {
        "source": "Vedic Hymns (Max Muller, in Wilson's 'World's Great Classics')", "license": "public-domain",
        "origin": PG % 12894 + ", anthology ed. Epiphanius Wilson (1900), Rigveda translations by F. Max Muller; Project Gutenberg Licence applies if redistributed",
        "translator": "F. Max Muller", "tradition": "Vedic"}, h)
    n2 = emit(out / "kaushitaki_upanishad.md", {
        "source": "Kaushitaki Upanishad (Muller)", "license": "public-domain",
        "origin": PG % 12894 + ", translation by F. Max Muller (1879) in Wilson (1900); Project Gutenberg Licence applies if redistributed",
        "translator": "F. Max Muller", "tradition": "Upanishads"}, ents_u)
    return n1, n2


def upanishads_paramananda(src, out):
    """pg3283: Isa, Katha, Kena (Swami Paramananda, 1919). Verses are Roman-numeral headed;
    the translator's commentary follows each verse and is kept with it."""
    lines = body(src / "pg3283.txt")
    def last(pat):
        return max(i for i, l in enumerate(lines) if re.fullmatch(pat, l.strip(), re.I))
    def first_after(pat, a):
        return min(i for i, l in enumerate(lines) if i > a and re.fullmatch(pat, l.strip(), re.I))
    a_isa, a_katha, a_kena = last(r"Isa-Upanishad"), last(r"Katha-Upanishad"), last(r"Kena-Upanishad")
    segs = [("Isa Upanishad", a_isa, first_after(r"Katha-Upanishad", a_isa), False),
            ("Katha Upanishad", a_katha, first_after(r"Kena-Upanishad", a_katha), True),
            ("Kena Upanishad", a_kena, len(lines), True)]
    parts = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6}
    n = 0
    for name, a, b, has_parts in segs:
        entries, part, verse, cur = [], 0 if has_parts else 1, None, []
        def flush():
            if verse and cur:
                ref = f"{name} {part}.{verse}" if has_parts else f"{name} {verse}"
                for k, c in enumerate(pack(cur, 800)):
                    entries.append((ref if k == 0 else ref + " (cont.)", c))
        vnum = 0
        for blk in blocks(lines[a + 1:b]):
            m = re.fullmatch(r"Part (First|Second|Third|Fourth|Fifth|Sixth)", blk, re.I)
            if m:
                flush(); part, vnum, verse, cur = parts[m.group(1).lower()], 0, None, []
            elif re.fullmatch(r"[IVXL]+", blk):
                flush(); vnum += 1; verse, cur = vnum, []
            elif blk.lower().startswith(("here ends", "om! peace", "peace chant")):
                continue
            elif verse:
                cur.append(blk)
        flush()
        slug = name.split()[0].lower()
        n += emit(out / f"upanishad_{slug}_paramananda.md", {
            "source": f"{name} (Paramananda)", "license": "public-domain",
            "origin": PG % 3283 + ", translation and commentary by Swami Paramananda (1919, Vedanta Centre, Boston); Project Gutenberg Licence applies if redistributed",
            "translator": "Swami Paramananda", "tradition": "Upanishads"}, entries)
    return n


if __name__ == "__main__":
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(exist_ok=True)
    if (src / "pg3283.txt").exists() and not (len(sys.argv) > 3 and sys.argv[3] == "only-old"):
        print("paramananda upanishads", upanishads_paramananda(src, out))
    if (src / "pg2388.txt").exists():
        print("gita", gita(src, out), "yoga", yoga(src, out), "hymns/upanishad", hymns_upanishad(src, out))
