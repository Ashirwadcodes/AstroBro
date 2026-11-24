"""Question router + answer orchestration (UI-independent, testable)."""
import re
from datetime import datetime

from . import astro, citations, config, jyotish, llm, memory, security
from .embeddings import HybridRetriever
from .knowledge import Retriever, load_corpus

_CHART = re.compile(r"\b(my|mine)\b.*\b(chart|kundli|kundali|lagna|ascendant|moon|sun|rashi|"
                    r"nakshatra|dasha|antardasha|house|planet|career|marriage|yoga|yogas|dosha|"
                    r"navamsa|tithi|panchanga|transit|retrograde|saturn|jupiter|venus|mars|mercury|"
                    r"rahu|ketu)\b|\b(kundli|janam)\b|sade ?sati", re.I)

_retriever = None
_by_id = None


def retriever():
    global _retriever, _by_id
    if _retriever is None:
        chunks, _ = load_corpus()
        _retriever = HybridRetriever(chunks, use_embeddings=config.USE_EMBEDDINGS)
        _by_id = {c.id: c for c in chunks}
    return _retriever


def classify(q: str) -> str:
    return "chart+knowledge" if _CHART.search(q) else "knowledge"


def gather(q: str, con=None, user_id=None, k: int = 4):
    """Library passages + this user's taught notes (+ passages linked to those notes),
    re-weighted by this user's past feedback."""
    r = retriever()
    cands = {c.id: [s, c] for s, c in r.search(q, k=k + 2)}
    linked_ids = set()
    if con is not None and user_id is not None:
        notes = memory.note_chunks(con, user_id)
        links = memory.note_links(con, user_id)
        if notes:
            nr = Retriever(notes)
            # A handful of notes is too small a corpus to weight words itself, so borrow the
            # library's word weights (unknown words count as rare).
            rare = max(r.idf.values(), default=1.0)
            nr.idf = {t: r.idf.get(t, rare) for t in nr.idf}
            for s, c in nr.search(q, k=2, min_score=0.5):
                cands[c.id] = [s, c]
                for lid in links.get(c.id, []):  # one-hop integration with trusted sources
                    lc = _by_id.get(lid)
                    if lc and lc.id not in cands:
                        cands[lc.id] = [s * 0.5, lc]
                        linked_ids.add(lc.id)
        votes = memory.votes(con, user_id)
        for cid, pair in cands.items():
            pair[0] *= 1 + 0.15 * max(-3, min(3, votes.get(cid, 0)))
    ordered = sorted(cands.values(), key=lambda x: -x[0])
    ranked = ordered[:k]
    # a big library must not squeeze out the trusted passage a taught note was linked to
    if linked_ids and not any(c.id in linked_ids for _, c in ranked):
        extra = next((p for p in ordered[k:] if p[1].id in linked_ids), None)
        if extra:
            ranked = ranked[:k - 1] + [extra]
    return [(s, c) for s, c in ranked]


def _sources_block(hits, numbered=True):
    lines = []
    for i, (_, c) in enumerate(hits, 1):
        tag = " (user note, unverified)" if c.license == "user-own" else ""
        head = f"[{i}] {c.source} {c.ref}{tag}" if numbered else f"[{c.source} {c.ref}]{tag}"
        lines.append(f"{head}: {c.text}")
    return "\n\n".join(lines)


def _history_messages(history):
    msgs = []
    for m in (history or [])[-2 * config.HISTORY_TURNS:]:
        if m.get("role") in ("user", "assistant"):
            msgs.append({"role": m["role"], "content": str(m.get("content", ""))[:400]})
    return msgs


def answer(user: dict, question: str, profile: dict = None, use_llm: bool = True,
           con=None, history=None, style: str = "simple", lang: str = "english") -> dict:
    """Returns {answer, route, sources, source_ids, chart_used, warnings, citation_report}."""
    base = {"sources": [], "source_ids": [], "chart_used": False, "warnings": [],
            "citation_report": None}
    if not security.limiter.allow("chat:%s" % user["id"], *config.CHAT_RATE):
        return {**base, "answer": "Rate limit reached - please wait a minute.", "route": "blocked",
                "warnings": ["rate_limited"]}
    q = security.clean_text(question)
    if not q:
        return {**base, "answer": "Please type a question.", "route": "empty"}
    warnings = []
    if security.looks_like_injection(q):
        warnings.append("injection_suspected")
    route = classify(q)
    hits = gather(q, con, user.get("id"))
    chart_text, chart = "", None
    if route == "chart+knowledge":
        if not profile:
            return {**base, "answer": "I need your birth details first (Profile tab) to discuss your chart.",
                    "route": route, "warnings": warnings}
        chart = astro.compute_chart(datetime.fromisoformat(profile["datetime"]), profile["tz"],
                                    profile["lat"], profile["lon"], profile.get("place", ""))
        chart_text = jyotish.facts_for(chart, q)  # only the sections the question needs
        hits = hits or [(s, c) for s, c in retriever().search("dasha nakshatra lagna " + q, k=3)]

    sources = [{"source": c.source, "ref": c.ref, "license": c.license, "score": round(s, 2)}
               for s, c in hits]
    text, report = None, None
    if use_llm and llm.available():
        prompt = (f"/no_think\nCHART FACTS (computed deterministically):\n{chart_text or 'none'}\n\n"
                  f"SOURCES:\n{_sources_block(hits) or 'none found'}\n\nQUESTION: {q}")
        system = llm.SYSTEM_PROMPT + "\n" + llm.STYLES.get(style, llm.STYLES["simple"]) \
            + "\n" + llm.LANGS.get(lang, llm.LANGS["english"])
        try:
            raw = llm.chat([{"role": "system", "content": system}, *_history_messages(history),
                            {"role": "user", "content": prompt}],
                           max_tokens=320 if style == "simple" else 450)
            chunks = [c for _, c in hits]
            text, report = citations.verify(raw, chunks, retriever().idf)
            text += citations.footer(text, chunks)
            if report["reattributed"] or report["invalid"] or report["unsupported"] or report["bad_quotes"]:
                warnings.append("citations_corrected")
        except Exception as e:  # network/model errors must not crash the UI
            text, warnings = None, warnings + [f"llm_error:{type(e).__name__}"]
    if text is None:  # retrieval-only fallback: still useful, still honest
        parts = []
        if chart_text:
            parts.append("Computed chart facts:\n" + chart_text)
        parts.append("Relevant passages:\n" + (_sources_block(hits, numbered=False)
                                                or "No matching passages in the local library."))
        why = ("the model did not respond in time" if any(w.startswith("llm_error") for w in warnings)
               else "LLM offline")
        parts.append(f"({why} - showing retrieval only.)")
        text = "\n\n".join(parts)
    return {"answer": text, "route": route, "sources": sources,
            "source_ids": [c.id for _, c in hits], "chart_used": chart is not None,
            "warnings": warnings, "citation_report": report}
