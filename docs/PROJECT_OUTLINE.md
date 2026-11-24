# AstroBro - project outline

AstroBro is a local, privacy-first assistant for Indian knowledge texts and Vedic astrology (Jyotish).
Folder: `BHARAT_AI/` (old name kept so the venv paths do not break). Python package: `bharat/`.

## 1. Core idea (the rule everything follows)
- Code calculates (chart, nakshatra, dasha). The LLM only explains.
- The LLM may only use retrieved passages and computed chart facts, and must cite them.
- Everything stays on this machine. The LLM client refuses non-loopback addresses.

## 2. Request flow
User question -> `service.answer()` ->
1. rate limit (10 per 60 s per user) -> clean text (1500 chars, strip control chars) -> flag prompt injection
2. `classify()` -> "knowledge" or "chart+knowledge"
3. BM25 retrieval over `corpus/` (top 4 passages)
4. if chart question: load saved birth profile -> `astro.compute_chart()` -> `chart_summary()`
5. prompt = chart facts + sources + question -> `llm.chat()` (Ollama, qwen3:4b)
6. if the model is down or times out: show retrieved passages and chart facts only
Returns: answer, route, sources, chart_used, warnings.

## 3. Files
| Path | Job |
|---|---|
| `app.py` | Streamlit UI: login/register, Ask, Profile, Kundli tabs, sidebar status |
| `bharat/config.py` | paths, model name, limits, allowed licences |
| `bharat/security.py` | scrypt passwords, lockout, rate limiter, hashed expiring sessions, audit log, encrypted birth data, delete-my-data |
| `bharat/astro.py` | Lahiri sidereal chart, whole-sign houses, Lagna, 27 nakshatras and padas, Vimshottari dasha. Uses pyswisseph (installed) |
| `bharat/knowledge.py` | licence-gated corpus loader, BM25 retriever |
| `bharat/citations.py` | checks and corrects the model's [n] citations and quotes |
| `bharat/memory.py` | taught notes, auto-linking to the library, feedback votes |
| `bharat/llm.py` | Ollama client, system prompt, loopback guard |
| `bharat/service.py` | router and orchestration |
| `corpus/*.md` | knowledge files; front matter needs source, origin, licence |
| `tests/test_all.py` | 15 tests (astro, corpus guard, auth, rate limit, encryption, service) |
| `database/` | runtime only: `bharat.db`, `field.key` (git-ignored) |

## 4. Status
Done and tested: astrology engine (exact via Swiss Ephemeris), auth and security layer, licence guard, retrieval, offline fallback, Ollama connection.
Not verified: the Streamlit UI has never been launched or clicked through.
Model: default is now `qwen3:4b-instruct-2507-q4_K_M` (installed). Clean 3-part answers, about 60 s per reply on this CPU. The old thinking variant `qwen3:4b` leaked its reasoning and is no longer used.
Citations: fixed in code (`bharat/citations.py`). Sources are numbered; each cited claim is checked against its source. A wrong citation is re-attributed to the passage that supports it, unsupported ones become [unsupported], citations to missing sources are dropped, and Sanskrit quotes not found in the sources are withheld. Tested with the exact mis-citation seen earlier.
Learning (`bharat/memory.py`): no weight training. (1) Teach tab: private, encrypted user notes, labelled unverified, auto-linked to the closest library passages so answers combine them. (2) Thumbs up/down re-weights which passages are retrieved for that user. (3) Last 3 turns of chat are passed to the model. Plain "simple" and "detailed" answer styles.
Astrology added (`bharat/jyotish.py`): retrograde, dignity, combustion, Navamsa (D9) and vargottama, graha drishti aspects, yogas (Gajakesari, Budha-Aditya, Chandra-Mangala, Pancha Mahapurusha, Mangal dosha, Kemadruma), Panchanga (tithi, karana, nitya yoga, vara from real sunrise), Antardasha and Pratyantardasha, transits and Sade Sati/Dhaiya. Only the sections a question needs go into the model prompt (small context window). Not built: Ashtakoota matching (scoring tables differ between sources; needs a vetted reference), PDF report, Rahu/Ketu aspects, Raja/Dhana yogas, other divisional charts.
UI verified headlessly (register, login, teach, profile, Kundli tab, chart question with the real model). 47 tests pass.
Open weakness: the "My reading" part of an answer can go beyond the sources (inference is labelled but not checked). Needs the evaluation set (item 6).
Hardware limits: Intel Iris Xe, 16 GB RAM with about 1-1.5 GB free. Close other apps before running.

Texts (`corpus/`, about 800 passages): Bhagavad Gita (Arnold 1885, all 18 chapters), Yoga Sutras with Johnston's commentary (1912), 135 Vedic hymn passages (Max Muller, via Wilson 1900), Kaushitaki Upanishad (Muller, 68 passages), 6 Sanskrit verses, the Jyotish primer. All Project Gutenberg public domain; origin lines name the eBook number. `tools/import_gutenberg.py` rebuilds them from the downloaded files (run with `python -I`). If the app or corpus is ever shared, include the Project Gutenberg licence text. Johnston's commentary is Theosophical in outlook and Arnold's Gita is poetic, so answers should say "this translation". Not added: Zend-Avesta, Koran, Buddha (other traditions in the same anthology), copyrighted modern translations.

Also added: language setting (English, Hinglish, Hindi; default via `BHARAT_LANG`, small models write Hindi weakly), `bharat/numerology.py` (Pythagorean and Chaldean, Moolank, personal year), Kaal Sarp check, primers for numerology, palmistry and doshas, a Gita lesson path with a Learn Gita tab and verified free resources. Roadmap, text-licensing rules and who to consult before going public: `docs/ROADMAP_AND_LEGAL.md`.

Upanishads added: Isa, Katha, Kena (Swami Paramananda 1919, Gutenberg #3283, 224 passages with his commentary) plus the Kaushitaki. Mueller SBE vol. 15 (1884) is also in, from archive.org OCR cleaned by `tools/import_muller_sbe.py`: Mundaka, Taittiriya, Brihadaranyaka, Svetasvatara, Prasna, Maitrayana (724 passages after review). Sources are labelled "(Muller, OCR text)". Known flaws: damaged Sanskrit name letters, a few verses still missing (the tolerant verse-number reader raised passages from 685 to 886; a filter then dropped about 30 passages that were translator footnotes and about 130 broken fragments), section numbers `sN.M` counted automatically (not the book's own), and a little translator footnote text may still slip through. Treat quotes from these as unverified until checked against a clean edition. Not yet imported: SBE vol. 1 (Chandogya, Kena, Aitareya, Kaushitaki, Isa).

Rigveda added: all 10 books of Griffith's translation (about 10,500 stanzas in 3,185 passages, refs like `Rigveda 10.129.1-3`), from English Wikisource's transcription via its API (`tools/fetch_wikisource_rigveda.py`, `tools/import_rigveda.py`). Licence tag cc-by-sa: the 1896 translation is public domain but the Wikisource transcription is CC BY-SA 4.0, so credit Wikisource contributors and share the corpus under the same terms if you ever publish it. Griffith's footnotes and commentary are not included, and deity names are mostly missing. 13 of 1,028 hymns have OCR stanza-number glitches (a first stanza dropped or mislabelled). 10.34 once carried a contributor's revision note, which the importer strips.

Search: BM25 plus local embeddings (`nomic-embed-text` via Ollama, cached in `database/embeddings.npz`), fused by `bharat/embeddings.py`; falls back to keyword search if Ollama or the model is missing, or with `BHARAT_EMBED=0`. `tools/eval_search.py` scores both on 35 questions: keyword 31/35, hybrid 32/35 (small gain; the misses are paraphrases the small model does not catch). Phase A of the roadmap is done; next is Phase B texts.

## 5. Work to do (priority order)
1. Fix the model: pull an instruct model (`qwen3:4b-instruct-2507-q4_K_M`, about 2.5 GB, tag unverified) and set `BHARAT_MODEL`. Then re-test answer quality.
2. Run the UI once end to end: register, login, save profile, ask, check Kundli tab.
3. Add city -> latitude/longitude/timezone lookup (offline list).
4. Astrology: Antardasha, Navamsa (D9), aspects, yogas, planet strength, panchanga, transits, Ashtakoota matching, PDF report.
5. Corpus: add only public-domain or CC texts with verified licence; write original summaries for copyrighted works. Then ChromaDB plus an embedding model (`bge-m3` or `nomic-embed-text`) in place of BM25 (same `search()` API).
6. Evaluation set: 100 questions (verse exists, citation correct, refusal when unknown, chart numbers checked against Jagannatha Hora).
7. Hardening if shared beyond you: FastAPI with HttpOnly/SameSite cookies, CSRF, TLS, TOTP or email verification, log files, backups, pinned `requirements.txt`.
8. Git: nothing from this project is committed yet.

## 6. Rules to keep
- Never let the LLM compute positions, dashas, or invent verses.
- Every corpus file needs an allowed licence (public-domain, cc0, cc-by, cc-by-sa, own-work).
- Astrology is presented as a traditional belief system, not prediction or advice.
- No cloud calls with birth data. No scraping of other products. Do not copy Melooha or AstroTalk content.
- Swiss Ephemeris is AGPL or commercial: fine for personal use, check before distributing.

## 7. Commands
Tests: `.venv/Scripts/python.exe -m pytest -q`
Run: `.venv/Scripts/python.exe -m streamlit run app.py --server.address 127.0.0.1`
Model: `ollama pull <model>`; choose it with the `BHARAT_MODEL` environment variable.

Ramayana added (partial): Griffith's verse translation (1870-74) from English Wikisource, Books I-III (Bala, Ayodhya, Aranya) in 1,717 passages, refs like `Ramayana II.9.1` (book.canto.part), via `tools/fetch_wikisource_ramayana.py` and `tools/import_ramayana.py`. Licence tag cc-by-sa (Wikisource transcription, CC BY-SA 4.0; credit contributors and keep the licence if shared). Gaps: Books IV-VI (Kishkindha, Sundara, Yuddha) are not on Wikisource, 52 Book III cantos (L onward) exist only as empty header pages, and footnotes are left out. Cantos are cut into ~700-character passages at sentence ends, so a passage can start mid-scene.

Mahabharata added (all 18 parvas): Ganguli's English prose translation (1883-96) from Project Gutenberg ebooks 15474-15477, 24,507 passages in `mahabharata_bookNN_ganguli.md`, refs like `Mahabharata 6.25.1` (book.section.part), imported by `tools/import_mahabharata.py`. Licence public-domain (US; translator died 1908, so expected free in India too [Verify]). Footnotes are dropped and `[n]` markers removed. Section counts match the usual numbering for most parvas but a few differ by a handful (Adi 235, Drona 200, Shanti 362, Svargarohanika 6), so treat section numbers as approximate and check against the book before quoting. The Bhishma Parva section 25-42 text is Ganguli's own Gita translation, a second Gita besides Arnold's; one editor's note by J. B. Hare (sacred-texts) is inside 6.25.1. This is the Ganguli text: prose, long, repetitive, and older English (Kaurava names spelled his way). The first run downloads were cut off by the mirror, so the files were resumed and checked to end with the Gutenberg licence footer.

Vishnu Purana added: Manmatha Nath Dutt's prose translation (Calcutta 1896, based on H. H. Wilson 1840) from Project Gutenberg #66208, 1,483 passages in `vishnu_purana_partN_dutt.md`, refs like `Vishnu Purana 1.5.2` (part.section.piece), via `tools/import_vishnu_purana.py`. Public domain in the US; both translators died long ago, so expected free in India too [Verify]. This is Dutt's adaptation after Wilson, not Wilson's own wording or his scholarly footnotes; translator footnotes are dropped. Section counts follow the usual structure (22, 16, 18, 24, 37, 8) except Part V, which has one fewer than the usual 38, so a section may be missing there. It is one Purana of eighteen; the other Puranas are not in.
