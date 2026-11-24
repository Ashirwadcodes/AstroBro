# AstroBro (local Vedic knowledge + Jyotish assistant)

Runs fully on your machine. Standard-library core; Streamlit for the UI.

## Run
```
C:\Users\KIIT\anaconda3\python.exe -m pytest -q
C:\Users\KIIT\anaconda3\python.exe -m streamlit run app.py --server.address 127.0.0.1
```
Optional upgrades (use a venv): `pip install pyswisseph cryptography` (all 9 grahas, encrypted birth data).
LLM: install Ollama, `ollama pull qwen3:4b`. Without it the app answers by retrieval only.

## Design
- `bharat/astro.py` deterministic Lahiri/whole-sign chart, nakshatra, Vimshottari. LLM never calculates.
- `bharat/knowledge.py` licence-gated corpus (`corpus/*.md` needs front matter with an allowed licence) + BM25 retrieval, verse-level chunks.
- `bharat/service.py` router, rate limit, injection flagging, source-grounded prompt, retrieval-only fallback.
- `bharat/security.py` scrypt passwords, lockout, sliding-window rate limits, hashed expiring session tokens, audit log, optional Fernet encryption, erasure.
- `bharat/llm.py` loopback-only Ollama client.

## Security notes (honest limits)
- Single-user local use. Streamlit has no native cookie API; sessions live in `st.session_state` (token hashed in DB). For multi-user/internet use put it behind a reverse proxy with TLS and move to FastAPI with HttpOnly/SameSite cookies.
- Without `cryptography`, profiles are only base64-encoded, not encrypted.
- Prompt-injection detection is heuristic; the real defence is the system prompt treating sources as data and having no tools/network for the model.
- Not done: "reverse engineering" of Melooha/AstroTalk. Unnecessary and legally risky; this uses published classical methods.

## Copyright
Only add texts that are public domain / CC / your own. Many English translations (e.g. Gita As It Is, most Parashara translations) are copyrighted; GRETIL/Muktabodha terms vary. Record `origin` and `license` for each file.

## Roadmap
1. Install pyswisseph; add Navamsa (D9), yogas, aspects, Panchanga, Antardasha, kundli matching (Ashtakoota).
2. Add public-domain texts: Sanskrit Gita/Upanishads from GRETIL (check per-file terms), Griffith's Rigveda (PD), Sacred-texts PD translations.
3. Replace BM25 with ChromaDB + BGE-M3 hybrid; build 100-question eval set (verse existence, calc cross-check against Jagannatha Hora).
4. Optional LoRA for tone only; FastAPI + React, HttpOnly cookies, CSRF, TLS if shared.
