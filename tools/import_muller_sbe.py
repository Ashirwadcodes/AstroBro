"""Clean OCR text of Max Muller's 'The Upanishads' (Sacred Books of the East, vol. 15, 1884)
from archive.org into AstroBro corpus files. Public domain (translator died 1900).

Run on an isolated download folder:
    python -I tools/import_muller_sbe.py <dir containing sbe15.txt> <corpus_dir>
The OCR is noisy (page headers, footnotes, damaged diacritics). This script drops headers and
footnotes, joins hyphenated words, and splits the text at numbered verses. Names with damaged
diacritics stay damaged; the corpus file's origin line says so."""
import re
import sys
from pathlib import Path

LIMIT = 800
# (name, first_line, last_line) are 1-based line numbers in the archive.org djvu text
SEGMENTS = [
    ("Mundaka Upanishad", 3523, 4145),
    ("Taittiriya Upanishad", 4148, 5309),
    ("Brihadaranyaka Upanishad", 5313, 12788),
    ("Svetasvatara Upanishad", 12792, 14582),
    ("Prasna Upanishad", 14735, 15272),
    ("Maitrayana Upanishad", 15276, None),  # None: stop at the first appendix/index heading
]
HEAD = re.compile(r"(first|second|third|fourth|fifth|sixth|seventh|eighth)\s+"
                  r"(adhy|valli|khanda|brahma|prap|anuv|mund)", re.I)
KIND = {"adhy": "Adhyaya", "vall": "Valli", "khan": "Khanda", "brah": "Brahmana",
        "prap": "Prapathaka", "anuv": "Anuvaka", "mund": "Mundaka"}
ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8}
VERSE = re.compile(r"^(\d{1,3}|[IVXL]{1,4}|l)\s?[\^\*\'\"]?\s*[.,]\s+(.*)", re.S)  # OCR: 4^. 1, I.


LEAK = re.compile(r"(Anandagiri|Sa[nh]kara|5ahkara|Ramatirtha|Comm\.|commentator|Cf\.|MSS?\.|"
                  r"Mund\. Up|Brih\. Ar|Kh?and\. Up|Sacred Books|Sat\.? Br|Ait\. Ar|Colebrooke|Roer|Weber|"
                  r"Deussen|Poley|p\. \d+)")
dropped = []


def alpha_ratio(s):
    t = re.sub(r"\s", "", s)
    return sum(ch.isalpha() for ch in t) / max(len(t), 1)


def good_prose(t):
    """Reject fragments: genealogy lists and heavily damaged OCR."""
    w = t.split()
    if len(w) < 10:
        return False
    odd = sum(1 for x in w if len(x) == 1 and x.lower() not in "ai" or re.search(r"[;\"][a-z]|\w[/?]\w", x))
    return odd / len(w) < 0.12


def is_header(line):
    s = line.strip()
    if re.fullmatch(r"\[?\d*\]?", s):
        return True
    if "UPANISHAD" in s.upper() and len(s) < 55:
        return True
    if re.search(r"(ADHYAYA|MUNDAKA|PRAPA|BRAHMA).{0,12}(VALL|KHANDA|BRAHMA|ANUV)", s, re.I) and len(s) < 60:
        return True
    return False


def clean_text(t):
    t = t.replace("■", " ").replace("'■", " ")
    t = re.sub(r"\^+\d*", " ", t)
    t = re.sub(r"(?<=\w)\*|\s\*\s", " ", t)
    t = re.sub(r"([A-Za-z])-\s+([a-z])", r"\1\2", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([,.;:?!)])", r"\1", t)
    return t


def segment_blocks(lines):
    """Yield text blocks with page headers and footnotes removed."""
    in_foot, cur, out = False, [], []

    def flush():
        if cur:
            out.append(" ".join(cur)); cur.clear()
    for ln in lines:
        s = ln.strip()
        if not s:
            flush(); continue
        if is_header(s):
            flush(); in_foot = False
            if HEAD.fullmatch(s.rstrip(".").strip()) or HEAD.match(s):
                out.append("##" + s)
            continue
        if alpha_ratio(s) < 0.5 and len(s) > 8:  # the divider line before footnotes
            flush(); in_foot = True; continue
        if HEAD.match(s) and len(s) < 40:
            flush(); in_foot = False; out.append("##" + s); continue
        if in_foot and VERSE.match(s):
            in_foot = False  # a numbered verse ends the footnote area
        if not cur and not in_foot and (s[0] in "^*" or re.match(r"^\d{1,2}\s{1,3}[A-Za-z]", s)
                        or re.match(r"^See\b|^Cf\.|^Comm\.", s)):
            in_foot = True
        if not in_foot:
            cur.append(s)
    flush()
    return out


def parse(name, lines):
    path, entries, verse, cur = {}, [], None, []
    sec, last = [1], [0]  # section counter: restarts when verse numbers restart

    def flush():
        if verse is not None and cur:
            ref = f"{name} s{sec[0]}.{verse}"
            txt = clean_text(" ".join(cur))
            if LEAK.search(txt):  # translator's notes, not scripture: drop rather than mis-attribute
                dropped.append(ref)
                return
            for i, piece in enumerate(split_long(txt)):
                if alpha_ratio(piece) > 0.8 and good_prose(piece):
                    entries.append((ref if i == 0 else ref + " (cont.)", piece))
    for b in segment_blocks(lines):
        if b.startswith("##"):
            m = HEAD.match(b[2:].strip())
            if m:
                flush(); verse, cur = None, []
                kind = KIND[m.group(2).lower()[:4]]
                path[kind] = ORD[m.group(1).lower()]
            continue
        m = VERSE.match(b)
        if m:
            flush()
            v = m.group(1)
            verse = int(v) if v.isdigit() else {"I": 1}.get(v, 0)
            if verse and verse <= last[0] and verse < 3:
                sec[0] += 1
            if verse:
                last[0] = verse
            cur = [m.group(2)]
        elif verse is not None:
            cur.append(b)
    flush()
    return entries


def split_long(t):
    if len(t) <= LIMIT:
        return [t]
    out, cur = [], ""
    for s in re.split(r"(?<=[.!?:;])\s+", t):
        if cur and len(cur) + len(s) + 1 > LIMIT:
            out.append(cur); cur = ""
        cur = (cur + " " + s).strip()
    return out + ([cur] if cur else [])


def main(src, out):
    lines = (Path(src) / "sbe15.txt").read_text(encoding="utf-8", errors="replace").split("\n")
    total = 0
    for name, a, b in SEGMENTS:
        if b is None:
            b = next(i for i, l in enumerate(lines) if i > a + 2000 and re.match(r"\s*(APPENDIX|INDEX|ADDITIONS|TRANSLITERATION)", l))
        entries, seen = [], {}
        for r, t in parse(name, lines[a:b]):
            seen[r] = seen.get(r, 0) + 1
            entries.append((r if seen[r] == 1 else f"{r} [{seen[r]}]", t))  # keep ids unique
        slug = name.split()[0].lower()
        head = ("---\nsource: %s (Muller, OCR text)\nlicense: public-domain\n"
                "origin: Max Muller, The Upanishads part II, Sacred Books of the East vol. 15 (Oxford, 1884); "
                "OCR text from archive.org item upanishads02ml, cleaned automatically, so some Sanskrit names have damaged "
                "letters and verse numbers may be slightly off\ntranslator: F. Max Muller\n"
                "tradition: Upanishads\n---\n\n" % name)
        body = "\n\n".join(f"[{r}] {t}" for r, t in entries)
        (Path(out) / f"upanishad_{slug}_muller.md").write_text(head + body + "\n", encoding="utf-8")
        print(name, len(entries), "dropped(notes):", len(dropped)); dropped.clear()
        total += len(entries)
    print("total", total)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
