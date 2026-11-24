"""AstroBro - Streamlit UI. Run: streamlit run app.py  (binds to localhost only)."""
import re
from datetime import datetime

import streamlit as st

from datetime import date

from bharat import astro, config, jyotish, llm, memory, numerology, security, service

st.set_page_config(page_title="AstroBro", page_icon="📚", layout="centered")


@st.cache_resource
def db():
    return security.connect()


con = db()
S = st.session_state
user = security.user_for_token(con, S.get("token", ""))

st.title("AstroBro")
st.caption("Local Indian knowledge & Jyotish assistant. Astrology is a traditional belief "
           "system, not scientific prediction or professional advice.")

if not user:
    t1, t2 = st.tabs(["Log in", "Register"])
    with t1:
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Log in"):
                try:
                    S["token"] = security.login(con, u.strip(), p)
                    st.rerun()
                except security.AuthError as e:
                    st.error(str(e))
    with t2:
        with st.form("reg"):
            u = st.text_input("Choose username")
            p = st.text_input("Choose password (12+ chars, mixed case, digit)", type="password")
            if st.form_submit_button("Create account"):
                try:
                    security.register(con, u.strip(), p)
                    st.success("Account created. Please log in.")
                except security.AuthError as e:
                    st.error(str(e))
    st.stop()

with st.sidebar:
    st.write(f"Signed in as **{user['username']}**")
    st.write("LLM:", "🟢 Ollama online" if llm.available() else "🟡 offline (retrieval only)")
    st.write("Astro backend:", astro.BACKEND)
    st.write("Data encryption:", "on" if security.encryption_active()
             else "off (pip install cryptography)")
    style = st.radio("Answer style", ["simple", "detailed"], horizontal=True,
                     help="Simple: short, friendly, plain words. Detailed: fuller, with context.")
    langs = list(llm.LANGS)
    lang = st.selectbox("Language", langs, format_func=llm.LANG_LABELS.get,
                        index=langs.index(config.DEFAULT_LANG) if config.DEFAULT_LANG in langs else 0,
                        help="Hinglish = Hindi typed in English letters. Small local models write "
                             "Hindi less well than English, so check important answers.")
    if st.button("Log out"):
        security.logout(con, S.pop("token"))
        st.rerun()
    with st.expander("Delete my data"):
        if st.button("Permanently delete account and data"):
            security.delete_all_user_data(con, user["id"])
            S.pop("token", None)
            st.rerun()

chat_tab, profile_tab, chart_tab, num_tab, learn_tab, teach_tab = st.tabs(
    ["Ask", "Profile", "Kundli", "Numerology", "Learn Gita", "Teach"])
profile = security.load_profile(con, user["id"])

with profile_tab:
    with st.form("profile"):
        d = st.date_input("Birth date", value=datetime(1995, 1, 1), min_value=datetime(1900, 1, 1))
        t = st.time_input("Birth time (local)")
        place = st.text_input("Birth place (label only)", value=(profile or {}).get("place", ""))
        lat = st.number_input("Latitude", -90.0, 90.0, float((profile or {}).get("lat", 28.61)))
        lon = st.number_input("Longitude (east +)", -180.0, 180.0, float((profile or {}).get("lon", 77.21)))
        tz = st.text_input("Timezone (IANA name or UTC offset hours)", value=(profile or {}).get("tz", "5.5"))
        if st.form_submit_button("Save"):
            try:
                dt = datetime.combine(d, t)
                astro.compute_chart(dt, tz, lat, lon)  # validate before saving
                security.save_profile(con, user["id"], {"datetime": dt.isoformat(), "tz": tz,
                                                         "lat": lat, "lon": lon, "place": place})
                st.success("Saved (stored locally).")
                profile = security.load_profile(con, user["id"])
            except Exception as e:
                st.error(f"Invalid details: {e}")

with chart_tab:
    if profile:
        c = astro.compute_chart(datetime.fromisoformat(profile["datetime"]), profile["tz"],
                                profile["lat"], profile["lon"], profile.get("place", ""))
        jyotish.enrich(c)
        a = c["analysis"]
        st.caption(f"Lagna {c['lagna']['rashi']} {c['lagna']['degree_in_rashi']:.1f}° · "
                   f"Navamsa Lagna {a['navamsa_lagna']} · {c['settings']['ayanamsa']}, whole-sign houses")
        st.dataframe([{"Planet": n, "Sign": p["rashi"], "Degree": p["degree_in_rashi"],
                       "House": p["house"], "Nakshatra": f"{p['nakshatra']} {p['pada']}",
                       "Navamsa": a["planets"][n]["navamsa"] + (" (vargottama)" if a["planets"][n]["vargottama"] else ""),
                       "State": ", ".join(x for x in (
                           "retrograde" if a["planets"][n]["retrograde"] and n not in ("Rahu", "Ketu") else "",
                           a["planets"][n]["dignity"], "combust" if a["planets"][n]["combust"] else "") if x)}
                      for n, p in c["planets"].items()], hide_index=True)
        pg = a["panchanga"]
        st.write(f"**Panchanga at birth:** {pg['tithi']} · karana {pg['karana']} · yoga {pg['yoga']} · "
                 f"{pg['vara']} ({pg['note']})")
        lv = a["dasha_levels"]
        st.write("**Running now:** " + " → ".join(f"{k.replace('dasha', ' dasha').title()} {v['lord']}"
                                                    f" ({v['start']} to {v['end']})" for k, v in lv.items()))
        st.markdown("**Yogas** (common textbook definitions; cancellations ignored)")
        for y in a["yogas"] or [{"name": "None of the checked yogas present", "detail": ""}]:
            st.write(f"- {y['name']}: {y['detail']}")
        with st.expander("Aspects (graha drishti)"):
            st.dataframe([{"Planet": n, "Aspects houses": ", ".join(map(str, v["houses"])),
                           "Hits": ", ".join(v["planets"])} for n, v in a["aspects"].items()],
                         hide_index=True)
        with st.expander(f"Antardashas in the {lv['mahadasha']['lord']} Mahadasha"):
            st.dataframe(jyotish.antardasha_table(c), hide_index=True)
        with st.expander("Full Mahadasha timeline"):
            st.dataframe(c["vimshottari"], hide_index=True)
        with st.expander("Transits today"):
            t = jyotish.transits(c)
            st.dataframe([{"Planet": n, "Sign": v["rashi"], "House from Lagna": v["house_from_lagna"],
                           "House from Moon": v["house_from_moon"],
                           "Retrograde": bool(v["retrograde"])} for n, v in t["positions"].items()],
                         hide_index=True)
            st.write("Saturn: " + (t["saturn_status"] or "no Sade Sati or Dhaiya now"))
        st.caption("Traditional calculations, not predictions. Rules differ between lineages.")
        if c["settings"]["backend"] != "swisseph":
            st.warning("Approximate fallback ephemeris: only Sun, Moon, nodes and Lagna. "
                       "Install pyswisseph for all grahas.")
    else:
        st.info("Save your birth details in the Profile tab.")

with chat_tab:
    S.setdefault("history", [])
    for m in S["history"]:
        with st.chat_message(m["role"]):
            st.write(m["content"])
    q = st.chat_input("Ask about the Gita, Upanishads, Jyotish, or your chart...")
    if q:
        S["history"].append({"role": "user", "content": q[:1500]})
        with st.chat_message("user"):
            st.write(q[:1500])
        with st.chat_message("assistant"), st.spinner("Thinking..."):
            r = service.answer(user, q, profile, con=con, history=S["history"][:-1], style=style, lang=lang)
            st.write(r["answer"])
            if r["sources"]:
                st.caption("Looked at: " + "; ".join(f"{s['source']} {s['ref']}" for s in r["sources"]))
            if r["warnings"]:
                st.caption("Notes: " + ", ".join(r["warnings"]))
        S["history"].append({"role": "assistant", "content": r["answer"]})
        S["last_ids"] = r["source_ids"]
    if S.get("last_ids"):
        c1, c2, _ = st.columns([1, 1, 4])
        if c1.button("👍 Helpful"):
            memory.vote(con, user["id"], S.pop("last_ids"), +1)
            st.toast("Thanks - I'll lean on those sources more for you.")
        elif c2.button("👎 Not helpful"):
            memory.vote(con, user["id"], S.pop("last_ids"), -1)
            st.toast("Noted - I'll lean on those sources less for you.")

with num_tab:
    st.caption("Numerology is a belief system, not science. Numbers are computed by code.")
    with st.form("num"):
        nm = st.text_input("Full name (English letters)", max_chars=80)
        nd = st.date_input("Birth date", value=date(1995, 1, 1), min_value=date(1900, 1, 1), key="numdate")
        if st.form_submit_button("Calculate"):
            try:
                R = numerology.report(nm, nd)
                st.write(f"**Life Path:** {R['birth']['life_path']} · **Moolank:** {R['birth']['birth_day']} "
                         f"({R['moolank_graha']}) · **Personal year {date.today().year}:** {R['personal_year']}")
                for sysname in ("pythagorean", "chaldean"):
                    x = R[sysname]
                    st.write(f"**{sysname.title()}** - Destiny {x['destiny']}, Soul Urge {x['soul_urge']}, "
                             f"Personality {x['personality']}")
                for k, v in R["meanings"].items():
                    st.write(f"- {k}: {v}")
                st.caption(R["note"] + " Palmistry: ask in the Ask tab; AstroBro explains palm "
                           "vocabulary but cannot read a photo of a palm.")
            except ValueError as e:
                st.error(str(e))

with learn_tab:
    chunks = service.retriever().chunks
    lessons = sorted((c for c in chunks if c.ref.startswith("Gita Lesson")), key=lambda c: c.ref)
    pick = st.selectbox("Lesson", [c.ref for c in lessons] or ["(none)"])
    for c in lessons:
        if c.ref == pick:
            st.write(c.text)
    m = re.match(r"Gita Lesson (\d+)", pick)
    if m and 1 <= int(m.group(1)) <= 18:
        n = m.group(1)
        with st.expander(f"Read chapter {n} (Arnold translation, public domain)"):
            for c in chunks:
                if c.ref.startswith(f"Gita {n}."):
                    st.write(c.text)
    st.markdown("**Free resources** (I checked these exist; quality is your judgement)")
    st.markdown(
        "- [Swami Sarvapriyananda, full Gita series (Vedanta Society of New York, YouTube)]"
        "(https://www.youtube.com/playlist?list=PL2imXor63HtS4ewIKryBL4ZVeiaH8Ij4R)\n"
        "- [Gita Supersite, IIT Kanpur: Sanskrit, many translations and commentaries, English and Hindi]"
        "(https://heritage.iitk.ac.in/gitasupersite)\n"
        "- [Gita Press, Gorakhpur (Hindi, classic editions)](https://www.gitapress.org/)")
    st.caption("Also worth searching by name (I have not checked their current links): Chinmaya Mission "
               "Gita classes, Swami Mukundananda's Gita lectures, and Hindi talks by Swami Ramsukhdas.")

with teach_tab:
    st.caption("Teach AstroBro your own notes. Add only text you wrote or have the right to use. "
               "Notes are private to you, encrypted on disk, and always labelled unverified. "
               "Each note is linked to the closest library passages so answers can connect them.")
    with st.form("teach", clear_on_submit=True):
        n_title = st.text_input("Title", max_chars=80)
        n_text = st.text_area("What should I learn?", max_chars=2000)
        if st.form_submit_button("Teach"):
            try:
                res = memory.add_note(con, user["id"], n_title, n_text, service.retriever())
                st.success("Learned. Linked to: " + (", ".join(res["links"]) or "nothing in the library yet"))
            except ValueError as e:
                st.error(str(e))
    for n in memory.list_notes(con, user["id"]):
        with st.expander(n["title"]):
            st.write(n["text"])
            st.caption("Linked to: " + (", ".join(n["links"]) or "none"))
            if st.button("Forget this", key=f"del{n['id']}"):
                memory.delete_note(con, user["id"], n["id"])
                st.rerun()
