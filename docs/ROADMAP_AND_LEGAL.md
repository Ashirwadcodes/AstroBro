# AstroBro - roadmap, text-licensing rules, and who to talk to before going public

This is planning guidance, not legal advice. Items tagged **[Verify]** need a qualified lawyer or the named office to confirm. Today AstroBro is for one person on one laptop, so almost none of this is triggered yet. It becomes real the day you let other people use it, charge money, or share the corpus.

## 1. Roadmap (build one thing at a time; Hindu traditions first)

**Done:** security layer, chart engine (Lahiri, dashas, Navamsa, yogas, panchanga, transits), citation checker, notes and learning, Gita, Yoga Sutras, some Rigveda hymns, Kaushitaki Upanishad, English / Hinglish / Hindi replies, numerology, palmistry and dosha primers, Gita lessons.

**Phase A - search quality (next).** Add embedding search (for example `bge-m3` or `nomic-embed-text` run locally through Ollama) next to BM25, and combine both. Reason: with more texts, word matching alone returns wrong passages (seen in the Gita test). Needs RAM: only about 1-1.5 GB is free on this laptop, so start with the small `nomic-embed-text` model and measure. Add the evaluation set (about 100 questions) before and after, so we can see if search got better.

**Phase B - Hindu texts, one at a time.** For each: check licence, download into an isolated folder, import, test retrieval, write the origin line.
1. Upanishads: Max Muller's *Sacred Books of the East* vols. 1 and 15 (Project Gutenberg / Wikisource, check each volume).
2. Rigveda (Griffith) DONE via Wikisource (CC BY-SA text), then Yajurveda (Griffith 1899), Samaveda (Griffith 1893/95), Atharvaveda (Griffith 1895-96). STATUS: not imported. English Wikisource has only the Samaveda preface (25% proofread) and no Griffith Yajurveda or Atharvaveda; the full texts sit on sacred-texts.com (whose bulk-use terms I could not find, so I did not scrape it) and as scanned OCR on archive.org (noisy, like the Muller volumes). Decide per source before importing.
3. Ramayana (Griffith verse translation): Books I-III DONE via Wikisource (CC BY-SA text; 52 later Book III cantos are blank there). Books IV-VI are not on Wikisource; Gutenberg or archive.org OCR would be the next option, decide per source.
4. Mahabharata (Ganguli, 1883-96): DONE, all 18 parvas from Project Gutenberg (public domain in the US; confirm India status for any public release).
5. Puranas: Vishnu Purana DONE (Dutt after Wilson, Gutenberg #66208; the Wilson original with footnotes is on archive.org, not imported); Manmatha Nath Dutt's translations of other Puranas (check each for date and rights holder).
6. Yugas, Manusmriti (Buhler), Dharmashastra, Arthashastra (Shamasastry, 1915), Jyotish classics with a verified public-domain translation. Surya Siddhanta (Burgess, 1860).
Every text must be tagged public-domain with a source link, or written by us as our own summary.

**Phase C - Jyotish depth.** Ashtakoota matching, other divisional charts, Raja/Dhana yogas, PDF report, city lookup.

**Phase D (future plan, not started).**
- Daily/weekly **horoscope** (computed from transits by code, text from our own wording).
- **Tarot** card system (our own card meanings; see licensing note below).
- **Scriptures of other common religions**: Bible, Quran, Guru Granth Sahib, Dhammapada and Buddhist suttas, Torah, Avesta, Tao Te Ching, Jain agamas and others. We start only after Hindu texts are in good shape.

**Phase E - going public** (only if you decide to): web app with proper login (cookies, CSRF, TLS, email or TOTP verification), privacy policy, backups, legal review. See section 4.

## 2. Rules for adding any text

1. Only public-domain texts, texts under an explicit open licence (CC0, CC-BY, CC-BY-SA), or our own writing. The code already refuses anything else.
2. **A text can be public domain in one country and not in another.** Project Gutenberg texts are cleared for the **US**. India's copyright term is the author's life plus 60 years (Copyright Act, 1957) [Verify]; the translators we use died long ago, so they should be free in India too, but check each new one.
3. **The Sanskrit original is old, but a modern edition is not.** Critical editions (for example BORI's Mahabharata), modern translations, commentaries, footnotes and typesetting can all be copyrighted. Prefer 19th and early 20th century translations.
4. **Do not ingest**: Gita Press editions, the Bhaktivedanta Book Trust's *Bhagavad-gita As It Is*, Chinmaya Mission, Ramakrishna Math, Swami Sivananda or other modern commentaries, Sadhguru, or any paid course. Link to free lectures instead (see the Learn Gita tab).
5. Record in the file's origin line: the source site, eBook or page number, translator, year. Keep the isolated raw download so a licence question can be answered later.
6. Websites such as Sacred-Texts, Wikisource, GRETIL (Sanskrit etexts) and Archive.org each set their own terms; read them per text. Respect robots.txt and bot blocks (ibiblio refused us, so we used the Foundation mirror).
7. If the corpus or app is ever redistributed, include the Project Gutenberg licence text where a PG file is used.

## 3. Third-party items that carry terms

| Item | Terms | Action |
|---|---|---|
| Swiss Ephemeris (`pyswisseph`) | AGPL, or paid professional licence | Fine for personal use. If you offer AstroBro as a public service, either publish the whole source under AGPL or buy the licence from **Astrodienst AG (Zurich, astro.com)**. |
| Ollama | MIT | Keep the licence notice if redistributed. |
| Qwen3 model | Apache 2.0 for this family [Verify on the model card] | Keep the notice; check again when you change model. |
| Streamlit, cryptography, others | Open-source | List them in a NOTICE file before sharing. |
| Tarot | The 1909 Rider-Waite-Smith deck is public domain in the US; many modern decks and the Thoth deck are not [Verify] | Use our own written meanings. Do not copy deck images or published card descriptions. |
| Melooha / AstroTalk | Their content is copyrighted | Do not copy, scrape or imitate it. |

## 4. Who to talk to if AstroBro goes public (India assumed)

| Topic | Authority / person | Why |
|---|---|---|
| Copyright of texts and translations | A copyright / IP lawyer; the **Copyright Office, Government of India** (under DPIIT) for registration and queries; each publisher or rights holder directly | Confirm that each translation is free, get written permission where it is not. |
| Personal data (birth date, time, place, notes) | **Digital Personal Data Protection Act, 2023** and its rules; supervised by the **Data Protection Board of India**; a data-protection lawyer | Birth details are personal data. You would need a notice, consent, a way to delete data, and security. Delete-my-data and encryption already exist in the code [Verify the current rules]. |
| Claims about results, remedies and money | **Central Consumer Protection Authority (CCPA)** under the Consumer Protection Act, 2019; the **Advertising Standards Council of India (ASCI)**; the Drugs and Magic Remedies (Objectionable Advertisements) Act, 1954 | Do not promise results, cures, or "guaranteed" outcomes. Selling gemstones, pujas or remedies makes this more serious. |
| Superstition-related laws | State laws such as Maharashtra's 2013 Act and Karnataka's 2017 Act, with a local lawyer | These target exploitative practices; keep AstroBro informational and avoid fear-based selling [Verify]. |
| Online platform duties | **MeitY**, the IT Act 2000 and IT Rules 2021, plus current AI advisories | Applies if users can post content or if you run a public platform. |
| Payments (only if charging) | RBI-regulated payment aggregators; GST registration; a chartered accountant | Do not handle card data yourself. |
| Religious sensitivity | Relevant community and scholarly bodies; a lawyer on the Bharatiya Nyaya Sanhita provisions about outraging religious feelings | Matters most for Phase D: for Sikh scripture consult the **SGPC** / Akal Takht practice on printing and handling Gurbani; for the Quran and Bible consult a scholar or a community body on translation and presentation. Never alter or paraphrase scripture text as if it were the original. |
| If a university project | KIIT's research office or IP cell | Your institution may have rules on ownership and publication. |

## 5. A short checklist before sharing with even one other person

- [ ] Each corpus file has licence, origin, and translator.
- [ ] NOTICE file lists all third-party software and texts.
- [ ] Disclaimer shown: astrology, numerology, palmistry and tarot are belief systems, not science, and not medical, legal or financial advice.
- [ ] No claim of prediction, cure or guaranteed result anywhere.
- [ ] Users can see, export and delete their data; privacy notice written.
- [ ] Swiss Ephemeris licence decision made.
- [ ] Lawyer has read this file and the licence list.
