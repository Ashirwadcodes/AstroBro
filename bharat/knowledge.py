"""Licence-gated corpus ingestion + BM25 retrieval (pure Python, no downloads).

Each corpus file is Markdown with front matter:
---
source: Bhagavad Gita
license: public-domain        # must be in config.ALLOWED_LICENSES
origin: where the text came from
translator: (optional)
tradition: (optional)
---
Blank-line separated entries. Start an entry with "[2.47]" to set its reference.
Entries are never split mid-verse.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass
class Chunk:
    id: str
    text: str
    source: str
    ref: str
    license: str
    origin: str


class IngestError(Exception):
    pass


def _parse(path: Path):
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
    if not m:
        raise IngestError(f"{path.name}: missing front matter")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.split("#")[0].strip()
    lic = meta.get("license", "").lower()
    if lic not in config.ALLOWED_LICENSES:
        raise IngestError(f"{path.name}: licence '{lic}' not allowed (copyright guard)")
    if not meta.get("source") or not meta.get("origin"):
        raise IngestError(f"{path.name}: 'source' and 'origin' are required")
    return meta, m.group(2)


def load_corpus(directory: Path = None, strict: bool = False):
    chunks, skipped = [], []
    for path in sorted(Path(directory or config.CORPUS_DIR).rglob("*.md")):
        try:
            meta, body = _parse(path)
        except IngestError as e:
            if strict:
                raise
            skipped.append(str(e))
            continue
        for i, entry in enumerate(re.split(r"\n\s*\n", body.strip())):
            entry = entry.strip()
            if not entry:
                continue
            m = re.match(r"\[([^\]]+)\]\s*(.*)", entry, re.S)
            ref, text = (m.group(1), m.group(2)) if m else (str(i + 1), entry)
            chunks.append(Chunk(f"{path.stem}:{ref}", text, meta["source"], ref,
                                meta["license"], meta["origin"]))
    return chunks, skipped


_TOKEN = re.compile(r"[\wऀ-ॿ]+", re.U)


def _tok(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))  # fold diacritics: dharma == dharma
    return _TOKEN.findall(s)


class Retriever:
    """Okapi BM25. Swap for ChromaDB + BGE-M3 embeddings later (same .search API)."""

    def __init__(self, chunks, k1=1.5, b=0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.docs = [Counter(_tok(c.source + " " + c.ref + " " + c.text)) for c in chunks]
        self.len = [sum(d.values()) for d in self.docs]
        self.avg = (sum(self.len) / len(self.len)) if self.len else 0
        df = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 4, min_score: float = 0.5):
        q = _tok(query)
        scored = []
        for i, d in enumerate(self.docs):
            s = 0.0
            for t in q:
                f = d.get(t, 0)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            if s >= min_score:
                scored.append((s, self.chunks[i]))
        scored.sort(key=lambda x: -x[0])
        return scored[:k]
