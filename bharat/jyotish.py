"""Higher-level Jyotish analysis on top of astro.compute_chart. All deterministic.

Many rules here (combustion orbs, which yogas count, aspects of the nodes) differ between
lineages. We use common textbook definitions, state them, and never treat them as prediction.
Anything needing Mars..Saturn is skipped when only the built-in approximate ephemeris exists.
"""
import re
from datetime import datetime, timedelta, timezone

from . import astro
from .astro import DASHA_ORDER, NAK_SPAN, RASHIS, YEAR_DAYS

OWN = {"Sun": [4], "Moon": [3], "Mars": [0, 7], "Mercury": [2, 5], "Jupiter": [8, 11],
       "Venus": [1, 6], "Saturn": [9, 10]}
EXALT = {"Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5, "Jupiter": 3, "Venus": 11, "Saturn": 6}
COMBUST_ORB = {"Moon": 12, "Mars": 17, "Mercury": 14, "Jupiter": 11, "Venus": 10, "Saturn": 15}
ASPECTS = {"Mars": (4, 7, 8), "Jupiter": (5, 7, 9), "Saturn": (3, 7, 10)}  # others: 7th only
KENDRA = (1, 4, 7, 10)
MAHAPURUSHA = {"Mars": "Ruchaka", "Mercury": "Bhadra", "Jupiter": "Hamsa", "Venus": "Malavya",
               "Saturn": "Shasha"}
TITHIS = ["Pratipada", "Dvitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami",
          "Ashtami", "Navami", "Dashami", "Ekadashi", "Dvadashi", "Trayodashi", "Chaturdashi"]
KARANA_MOVABLE = ["Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti"]
KARANA_FIXED = ["Shakuni", "Chatushpada", "Naga"]
NITYA_YOGA = ["Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda", "Sukarma",
              "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
              "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva", "Siddha", "Sadhya", "Shubha",
              "Shukla", "Brahma", "Indra", "Vaidhriti"]
VARA = ["Somavara (Monday)", "Mangalavara (Tuesday)", "Budhavara (Wednesday)",
        "Guruvara (Thursday)", "Shukravara (Friday)", "Shanivara (Saturday)",
        "Ravivara (Sunday)"]


# ---------- dignity, combustion, navamsa ----------
def dignity(name: str, rashi_index: int) -> str:
    if name in EXALT:
        if rashi_index == EXALT[name]:
            return "exalted"
        if rashi_index == (EXALT[name] + 6) % 12:
            return "debilitated"
        if rashi_index in OWN[name]:
            return "own sign"
    return ""


def angular_distance(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def is_combust(name: str, lon: float, sun_lon: float, retrograde: bool = False) -> bool:
    orb = COMBUST_ORB.get(name)
    if orb is None:
        return False
    if retrograde and name == "Mercury":
        orb = 12
    if retrograde and name == "Venus":
        orb = 8
    return angular_distance(lon, sun_lon) <= orb


def navamsa_index(lon: float) -> int:
    """Each 30-degree sign splits into nine 3d20' parts; counting runs continuously from Mesha."""
    return int((lon % 360) * 9 / 30) % 12


# ---------- aspects ----------
def aspect_houses(name: str, house: int) -> list:
    return [((house + n - 2) % 12) + 1 for n in ASPECTS.get(name, (7,))]


def aspects(planets: dict) -> dict:
    """Graha drishti by house. Rahu/Ketu are left out because lineages disagree."""
    out = {}
    occupants = {}
    for n, p in planets.items():
        occupants.setdefault(p["house"], []).append(n)
    for n, p in planets.items():
        if n in ("Rahu", "Ketu"):
            continue
        hs = aspect_houses(n, p["house"])
        out[n] = {"houses": hs, "planets": [x for h in hs for x in occupants.get(h, []) if x != n]}
    return out


# ---------- yogas ----------
def yogas(planets: dict, lagna_index: int) -> list:
    found = []
    P = planets

    def have(*names):
        return all(n in P for n in names)

    if have("Jupiter", "Moon"):
        if (P["Jupiter"]["rashi_index"] - P["Moon"]["rashi_index"]) % 12 in (0, 3, 6, 9):
            found.append({"name": "Gajakesari", "detail": "Jupiter is in a kendra (1/4/7/10) from the Moon."})
    if have("Sun", "Mercury") and P["Sun"]["rashi_index"] == P["Mercury"]["rashi_index"]:
        found.append({"name": "Budha-Aditya", "detail": "Sun and Mercury share a sign."})
    if have("Moon", "Mars") and P["Moon"]["rashi_index"] == P["Mars"]["rashi_index"]:
        found.append({"name": "Chandra-Mangala", "detail": "Moon and Mars share a sign."})
    for planet, yname in MAHAPURUSHA.items():
        if planet in P and dignity(planet, P[planet]["rashi_index"]) in ("own sign", "exalted") \
                and P[planet]["house"] in KENDRA:
            found.append({"name": f"{yname} (Pancha Mahapurusha)",
                          "detail": f"{planet} is in its own or exalted sign and in a kendra from the Lagna."})
    if "Mars" in P:
        from_lagna = P["Mars"]["house"]
        bad = (1, 2, 4, 7, 8, 12)
        if from_lagna in bad:
            found.append({"name": "Mangal dosha (from Lagna)",
                          "detail": f"Mars is in house {from_lagna}. Traditions list many cancellations."})
        if "Moon" in P:
            from_moon = (P["Mars"]["rashi_index"] - P["Moon"]["rashi_index"]) % 12 + 1
            if from_moon in bad:
                found.append({"name": "Mangal dosha (from Moon)",
                              "detail": f"Mars is in house {from_moon} counted from the Moon."})
    if all(n in P for n in ("Rahu", "Ketu", "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")):
        rahu = P["Rahu"]["longitude"]
        span = [(P[n]["longitude"] - rahu) % 360 for n in
                ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")]
        if all(s < 180 for s in span) or all(s > 180 for s in span):
            found.append({"name": "Kaal Sarp dosha (by longitude)",
                          "detail": "All seven planets lie on one side of the Rahu-Ketu axis. "
                                    "Not in the classical texts; many modern teachers use it, others reject it."})
    if all(n in P for n in ("Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")):
        moon = P["Moon"]["rashi_index"]
        near = [n for n in ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")
                if (P[n]["rashi_index"] - moon) % 12 in (0, 1, 11)]
        if not near:
            found.append({"name": "Kemadruma",
                          "detail": "No planet (besides Sun/nodes) in the Moon's sign or the signs "
                                    "either side. Cancellations exist."})
    return found


# ---------- panchanga ----------
def panchanga(sun_lon: float, moon_lon: float) -> dict:
    elong = (moon_lon - sun_lon) % 360
    t = int(elong // 12) + 1  # 1..30
    paksha = "Shukla" if t <= 15 else "Krishna"
    in_paksha = t if t <= 15 else t - 15
    tithi = ("Purnima" if t == 15 else "Amavasya" if t == 30 else TITHIS[in_paksha - 1])
    n = int(elong // 6) + 1  # karana number 1..60
    if n == 1:
        karana = "Kimstughna"
    elif n <= 57:
        karana = KARANA_MOVABLE[(n - 2) % 7]
    else:
        karana = KARANA_FIXED[n - 58]
    nitya = NITYA_YOGA[int(((sun_lon + moon_lon) % 360) // (360 / 27))]
    return {"tithi_number": t, "tithi": f"{paksha} {tithi}", "karana": karana, "yoga": nitya,
            "elongation": round(elong, 2)}


def vara(chart: dict):
    """Vedic weekday runs sunrise to sunrise, so a birth before sunrise belongs to the day before.
    Needs pyswisseph for sunrise; otherwise returns the civil weekday and says so."""
    inp = chart["input"]
    local = datetime.fromisoformat(inp["local_time"])
    if not astro.swe:
        return {"vara": VARA[local.weekday()], "note": "civil weekday (sunrise not computed)"}
    swe = astro.swe
    jd = inp["jd"]
    sunrise = None
    for start in (jd - 1.5, jd - 0.5):  # latest sunrise at or before birth
        r = swe.rise_trans(start, swe.SUN, swe.CALC_RISE, (inp["lon"], inp["lat"], 0),
                           1013.25, 15.0, swe.FLG_MOSEPH)
        if r[0] == 0 and r[1][0] <= jd:
            sunrise = r[1][0]
    if sunrise is None:
        return {"vara": VARA[local.weekday()], "note": "civil weekday (no sunrise found)"}
    rise_local = datetime(2000, 1, 1, 12) + timedelta(days=sunrise - 2451545.0) \
        + timedelta(hours=inp["utc_offset_h"])
    return {"vara": VARA[rise_local.weekday()], "note": f"sunrise about {rise_local:%H:%M} local"}


# ---------- Vimshottari levels ----------
def maha_timeline(moon_lon: float, birth_utc: datetime) -> list:
    elapsed = (moon_lon % NAK_SPAN) / NAK_SPAN
    idx = int(moon_lon // NAK_SPAN) % 9
    out, t = [], birth_utc
    for i in range(9):
        lord, years = DASHA_ORDER[(idx + i) % 9]
        remaining = years * (1 - elapsed) if i == 0 else years
        full_start = t - timedelta(days=years * elapsed * YEAR_DAYS) if i == 0 else t
        end = t + timedelta(days=remaining * YEAR_DAYS)
        out.append({"lord": lord, "start": t, "end": end, "full_start": full_start,
                    "full_days": years * YEAR_DAYS})
        t = end
    return out


def sub_periods(lord: str, start: datetime, total_days: float) -> list:
    """Nine sub-periods in Vimshottari order from `lord`, each proportional to its years/120."""
    idx = [l for l, _ in DASHA_ORDER].index(lord)
    out, t = [], start
    for i in range(9):
        l, y = DASHA_ORDER[(idx + i) % 9]
        days = total_days * y / 120
        out.append({"lord": l, "start": t, "end": t + timedelta(days=days), "days": days})
        t += timedelta(days=days)
    return out


def _d(dt: datetime) -> str:
    return dt.date().isoformat()


def dasha_levels(chart: dict, on: datetime = None) -> dict:
    birth = datetime.fromisoformat(chart["input"]["utc"])
    on = on or datetime.now(timezone.utc)
    timeline = maha_timeline(chart["planets"]["Moon"]["longitude"], birth)
    m = next((x for x in timeline if x["start"] <= on < x["end"]),
             timeline[0] if on < timeline[0]["start"] else timeline[-1])
    antars = sub_periods(m["lord"], m["full_start"], m["full_days"])
    a = next((x for x in antars if x["start"] <= on < x["end"]), antars[-1])
    prat = sub_periods(a["lord"], a["start"], a["days"])
    p = next((x for x in prat if x["start"] <= on < x["end"]), prat[-1])
    return {"mahadasha": {"lord": m["lord"], "start": _d(m["start"]), "end": _d(m["end"])},
            "antardasha": {"lord": a["lord"], "start": _d(a["start"]), "end": _d(a["end"])},
            "pratyantardasha": {"lord": p["lord"], "start": _d(p["start"]), "end": _d(p["end"])}}


def antardasha_table(chart: dict, maha_lord: str = None, on: datetime = None) -> list:
    birth = datetime.fromisoformat(chart["input"]["utc"])
    timeline = maha_timeline(chart["planets"]["Moon"]["longitude"], birth)
    on = on or datetime.now(timezone.utc)
    if maha_lord is None:
        maha_lord = dasha_levels(chart, on)["mahadasha"]["lord"]
    m = next(x for x in timeline if x["lord"] == maha_lord)
    return [{"mahadasha": maha_lord, "antardasha": a["lord"], "start": _d(a["start"]),
             "end": _d(a["end"]), "before_birth": a["end"] <= birth}
            for a in sub_periods(m["lord"], m["full_start"], m["full_days"])]


# ---------- transits / Sade Sati ----------
def sade_sati(moon_rashi: int, saturn_rashi: int) -> str:
    d = (saturn_rashi - moon_rashi) % 12
    return {11: "Sade Sati, first phase (Saturn in the 12th sign from the Moon)",
            0: "Sade Sati, middle phase (Saturn over the Moon's sign)",
            1: "Sade Sati, last phase (Saturn in the 2nd sign from the Moon)",
            3: "Small Panoti / Dhaiya (Saturn in the 4th from the Moon)",
            7: "Ashtama Shani / Dhaiya (Saturn in the 8th from the Moon)"}.get(d, "")


def transits(chart: dict, when: datetime = None) -> dict:
    when = when or datetime.now(timezone.utc)
    sid, retro, _ = astro.sidereal_positions(astro.julian_day(when))
    lagna = chart["lagna"]["rashi_index"]
    moon = chart["planets"]["Moon"]["rashi_index"]
    pos = {}
    for n, l in sid.items():
        p = astro.position(l)
        pos[n] = {"rashi": p["rashi"], "degree": p["degree_in_rashi"], "retrograde": retro.get(n),
                  "house_from_lagna": (p["rashi_index"] - lagna) % 12 + 1,
                  "house_from_moon": (p["rashi_index"] - moon) % 12 + 1}
    ss = sade_sati(moon, astro.position(sid["Saturn"])["rashi_index"]) if "Saturn" in sid else ""
    return {"date": when.date().isoformat(), "positions": pos, "saturn_status": ss}


# ---------- one call to enrich a chart ----------
def enrich(chart: dict) -> dict:
    P, sun = chart["planets"], chart["planets"]["Sun"]["longitude"]
    a = {"planets": {}}
    for n, p in P.items():
        ni = navamsa_index(p["longitude"])
        a["planets"][n] = {"retrograde": p.get("retrograde"),
                           "dignity": dignity(n, p["rashi_index"]),
                           "combust": is_combust(n, p["longitude"], sun, bool(p.get("retrograde"))),
                           "navamsa": RASHIS[ni], "vargottama": ni == p["rashi_index"]}
    a["navamsa_lagna"] = RASHIS[navamsa_index(chart["lagna"]["longitude"])]
    a["aspects"] = aspects(P)
    a["yogas"] = yogas(P, chart["lagna"]["rashi_index"])
    a["panchanga"] = {**panchanga(sun, P["Moon"]["longitude"]), **vara(chart)}
    a["dasha_levels"] = dasha_levels(chart)
    chart["analysis"] = a
    return chart


# ---------- compact facts for the LLM prompt (context window is small) ----------
_TOPICS = [
    ("dasha", re.compile(r"dasha|antar|period|mahadasha|timing", re.I)),
    ("yoga", re.compile(r"yoga|dosha|manglik|mangal|kemadruma", re.I)),
    ("navamsa", re.compile(r"navamsa|d9|spouse|marriage|partner|vargottama", re.I)),
    ("aspect", re.compile(r"aspect|drishti|glance", re.I)),
    ("panchanga", re.compile(r"panchang|tithi|karana|vara\b|weekday", re.I)),
    ("transit", re.compile(r"transit|gochar|sade ?sati|saturn|now|current|today", re.I)),
    ("strength", re.compile(r"retro|combust|exalt|debilit|dignity|strong|weak", re.I)),
]


def facts_for(chart: dict, question: str) -> str:
    if "analysis" not in chart:
        enrich(chart)
    a = chart["analysis"]
    topics = {t for t, rx in _TOPICS if rx.search(question)}
    lines = [astro.chart_summary(chart)]
    if "dasha" in topics:
        d = a["dasha_levels"]
        lines.append("Dasha levels now: " + "; ".join(
            f"{k} {v['lord']} ({v['start']} to {v['end']})" for k, v in d.items()))
    if "yoga" in topics:
        lines.append("Yogas: " + ("; ".join(f"{y['name']} - {y['detail']}" for y in a["yogas"])
                                   or "none of the checked yogas are present")
                     + " (common textbook definitions)")
    if "navamsa" in topics:
        lines.append(f"Navamsa (D9) Lagna: {a['navamsa_lagna']}. " + ", ".join(
            f"{n} {v['navamsa']}{' (vargottama)' if v['vargottama'] else ''}"
            for n, v in a["planets"].items()))
    if "aspect" in topics:
        lines.append("Aspects (graha drishti): " + "; ".join(
            f"{n} -> houses {v['houses']}" + (f" hitting {', '.join(v['planets'])}" if v["planets"] else "")
            for n, v in a["aspects"].items()))
    if "panchanga" in topics:
        pg = a["panchanga"]
        lines.append(f"Panchanga at birth: {pg['tithi']}, karana {pg['karana']}, yoga {pg['yoga']}, {pg['vara']}")
    if "strength" in topics:
        lines.append("Planet states: " + "; ".join(
            f"{n}: " + ", ".join(x for x in (
                "retrograde" if v["retrograde"] and n not in ("Rahu", "Ketu") else "",
                v["dignity"], "combust" if v["combust"] else "") if x) for n, v in a["planets"].items()
            if (v["retrograde"] and n not in ("Rahu", "Ketu")) or v["dignity"] or v["combust"]))
    if "transit" in topics:
        t = transits(chart)
        lines.append(f"Transits on {t['date']}: " + ", ".join(
            f"{n} {v['rashi']} (house {v['house_from_lagna']} from Lagna)" for n, v in t["positions"].items())
            + (f". Saturn: {t['saturn_status']}" if t["saturn_status"] else ". No Sade Sati/Dhaiya now"))
    return "\n".join(lines)
