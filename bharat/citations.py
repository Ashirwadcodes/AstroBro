"""Post-hoc citation verification. The LLM cites numbered sources like [2]; this module checks
those claims in plain code so a fluent but wrongly-cited answer cannot slip through.

Rules (deterministic, no LLM):
1. A citation to a source number that does not exist is removed.
2. If a different source supports the sentence clearly better than the cited one, the citation
   is re-attributed to it.
3. If no source supports the sentence, the citation becomes [unsupported].
4. A quoted Sanskrit/IAST string that does not appear in any source is withheld.
"""
import re

from .knowledge import _tok

_STOP = set("""the a an of to and or in on is are was were be it this that for with as by at from not
no you your they their can will which who what when how why do does did has have had but if then so
than also one one's its into about more most such these those there here very may might should would
could our out up all any each other source sources text says say said""".split())
_CITE = re.compile(r"\[(\d{1,2})\]")
_QUOTE = re.compile(r"\*([^*\n]{12,}?)\*|\"([^\"\n]{12,}?)\"|“([^”\n]{12,}?)”")
_SENT = re.compile(r"(?<=[.!?])\s+")


def _content(s: str):
    return [t for t in _tok(_CITE.sub(" ", s)) if len(t) > 2 and t not in _STOP]


def _score(sent_toks, src_toks, idf) -> float:
    total = sum(idf.get(t, 1.0) for t in sent_toks)
    if not total:
        return 0.0
    return sum(idf.get(t, 1.0) for t in sent_toks if t in src_toks) / total


def _verify_quotes(text, sources, report):
    corpus = " ".join(_tok(" ".join(s.text for s in sources)))

    def repl(m):
        q = next(g for g in m.groups() if g)
        if all(ord(c) < 128 for c in q):  # only police Sanskrit / IAST-looking quotes
            return m.group(0)
        if " ".join(_tok(q)) in corpus:
            return m.group(0)
        report["bad_quotes"].append(q[:40])
        return "(quotation withheld: not found in the sources)"

    return _QUOTE.sub(repl, text)


def verify(text: str, sources, idf, min_support: float = 0.15, margin: float = 1.3):
    """Returns (corrected_text, report). `sources` is a list of Chunk-like objects; the
    citation [n] refers to sources[n-1]."""
    report = {"reattributed": [], "invalid": 0, "unsupported": [], "bad_quotes": []}
    toks = [set(_content(s.text)) for s in sources]
    out_lines = []
    for line in text.split("\n"):
        sents = _SENT.split(line)
        fixed, prev = [], ""
        for sent in sents:
            if not _CITE.search(sent):
                fixed.append(sent)
                prev = sent
                continue
            st = _content(sent)
            if len(st) < 5 and prev:  # short sentence: judge it together with the one before
                st = _content(prev + " " + sent)
            scores = [_score(st, t, idf) for t in toks]
            best = max(range(len(scores)), key=scores.__getitem__) if scores else None

            def repl(m, scores=scores, best=best):
                n = int(m.group(1))
                if not 1 <= n <= len(sources):
                    report["invalid"] += 1
                    return ""
                sc = scores[n - 1]
                if best is not None and best != n - 1 and scores[best] >= max(min_support, margin * sc):
                    report["reattributed"].append((n, best + 1))
                    return f"[{best + 1}]"
                if sc < min_support:
                    report["unsupported"].append(n)
                    return "[unsupported]"
                return m.group(0)

            new = _CITE.sub(repl, sent)
            new = re.sub(r"(\[\d{1,2}\])(\s*\1)+", r"\1", new)  # collapse duplicates
            fixed.append(new)
            prev = sent
        out_lines.append(" ".join(fixed))
    return _verify_quotes("\n".join(out_lines), sources, report), report


def footer(text: str, sources) -> str:
    used = sorted({int(n) for n in _CITE.findall(text) if 1 <= int(n) <= len(sources)})
    if not used:
        return ""
    return "\n\nSources: " + "; ".join(f"[{n}] {sources[n - 1].source} {sources[n - 1].ref}" for n in used)
