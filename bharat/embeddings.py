"""Local embedding search (Ollama, loopback only) fused with BM25.

Vectors are cached on disk (database/embeddings.npz, keyed by a hash of each passage) so only
new or changed passages are embedded. If the embedding model is missing or Ollama is off,
HybridRetriever silently behaves exactly like plain BM25."""
import hashlib
import json
import urllib.request

import numpy as np

from . import config, llm
from .knowledge import Retriever

EMBED_MODEL = getattr(config, "EMBED_MODEL", "nomic-embed-text")
CACHE = config.ROOT / "database" / "embeddings.npz"
BATCH = 16
W_VEC = 1.3


def _embed(texts, prefix, timeout=120):
    llm._check_local(config.OLLAMA_URL)
    body = json.dumps({"model": EMBED_MODEL, "input": [prefix + t for t in texts],
                       "truncate": True}).encode()
    req = urllib.request.Request(config.OLLAMA_URL + "/api/embed", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        v = np.array(json.load(r)["embeddings"], dtype=np.float32)
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)


def _key(chunk):
    return hashlib.sha1(f"{EMBED_MODEL}|{chunk.id}|{chunk.text}".encode("utf-8")).hexdigest()


def _load_cache():
    try:
        z = np.load(CACHE, allow_pickle=False)
        return dict(zip(z["keys"].tolist(), z["vecs"]))
    except Exception:
        return {}


def _save_cache(cache):
    try:
        CACHE.parent.mkdir(exist_ok=True)
        keys = list(cache)
        np.savez(CACHE, keys=np.array(keys), vecs=np.stack([cache[k] for k in keys]))
    except Exception:
        pass  # cache is an optimisation only


class HybridRetriever(Retriever):
    """BM25 + embedding cosine, merged by reciprocal-rank fusion."""

    def __init__(self, chunks, use_embeddings=True):
        super().__init__(chunks)
        self.vecs = None
        self.error = None
        if use_embeddings and chunks:
            try:
                self._build()
            except Exception as e:  # model missing, Ollama off, timeout...
                self.vecs, self.error = None, f"{type(e).__name__}: {e}"

    def _build(self):
        cache = _load_cache()
        keys = [_key(c) for c in self.chunks]
        todo = [i for i, k in enumerate(keys) if k not in cache]
        for s in range(0, len(todo), BATCH):
            idx = todo[s:s + BATCH]
            vecs = _embed([self.chunks[i].text for i in idx], "search_document: ")
            for i, v in zip(idx, vecs):
                cache[keys[i]] = v
            if (s // BATCH) % 25 == 24:
                _save_cache(cache)  # keep progress if a long first build is interrupted
        if todo:
            _save_cache(cache)
        self.vecs = np.stack([cache[k] for k in keys])

    def search(self, query, k=4, min_score=0.0):
        bm = super().search(query, k=max(k * 5, 20), min_score=min_score)
        if self.vecs is None:
            return bm[:k]
        try:
            q = _embed([query], "search_query: ", timeout=20)[0]
        except Exception:
            return bm[:k]
        sims = self.vecs @ q
        top = np.argsort(-sims)[:max(k * 5, 20)]
        pos = {c.id: i for i, c in enumerate(self.chunks)}
        fused = {}
        # A weak keyword match (low top BM25 score) should not outvote meaning-based hits.
        w_bm = min(1.0, (bm[0][0] if bm else 0.0) / 12.0)
        for r, (_, c) in enumerate(bm):
            fused[c.id] = fused.get(c.id, 0) + w_bm / (60 + r)
        for r, i in enumerate(top):
            if sims[i] > 0.35:  # ignore clearly unrelated vector hits
                cid = self.chunks[i].id
                fused[cid] = fused.get(cid, 0) + W_VEC / (60 + r)
        if not fused:
            return []
        scale = (bm[0][0] if bm else 10.0) / max(fused.values())  # keep BM25-like scale
        by_id = {c.id: c for c in self.chunks}
        ranked = sorted(fused.items(), key=lambda x: -x[1])[:k]
        return [(v * scale, by_id[cid]) for cid, v in ranked]
