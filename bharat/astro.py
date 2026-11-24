"""Deterministic Jyotish calculations. The LLM never computes any of this.

Backend: pyswisseph if installed (accurate, all grahas). Otherwise a built-in
low-precision fallback (Sun, Moon, mean node, Lagna; ~0.1-0.3 deg) that is
clearly flagged in the output as approximate. Ayanamsa: Lahiri. Houses: whole-sign.
"""
import math
from datetime import datetime, timedelta, timezone

RASHIS = ["Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya", "Tula",
          "Vrischika", "Dhanu", "Makara", "Kumbha", "Meena"]
NAKSHATRAS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
              "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
              "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
              "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
              "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]
DASHA_ORDER = [("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10), ("Mars", 7),
               ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17)]
NAK_SPAN = 360.0 / 27
YEAR_DAYS = 365.25

try:
    import swisseph as swe  # type: ignore
    BACKEND = "swisseph"
except ImportError:
    swe = None
    BACKEND = "builtin-approx"


def _rad(x): return math.radians(x)
def _norm(x): return x % 360.0


def julian_day(dt_utc: datetime) -> float:
    y, m = dt_utc.year, dt_utc.month
    d = dt_utc.day + (dt_utc.hour + (dt_utc.minute + dt_utc.second / 60) / 60) / 24
    if m <= 2:
        y, m = y - 1, m + 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5


def lahiri_ayanamsa(jd: float) -> float:
    t = (jd - 2451545.0) / 36525.0
    return 23.853056 + 1.396 * t  # ~50.3"/yr precession from the J2000 Lahiri value


def _sun_trop(jd):
    t = (jd - 2451545.0) / 36525.0
    l0 = 280.46646 + 36000.76983 * t
    m = _rad(357.52911 + 35999.05029 * t)
    c = ((1.914602 - 0.004817 * t) * math.sin(m) + 0.019993 * math.sin(2 * m)
         + 0.000289 * math.sin(3 * m))
    return _norm(l0 + c)


def _moon_trop(jd):
    t = (jd - 2451545.0) / 36525.0
    lp = 218.3164477 + 481267.88123421 * t
    d = _rad(297.8501921 + 445267.1114034 * t)
    m = _rad(357.5291092 + 35999.0502909 * t)
    mp = _rad(134.9633964 + 477198.8675055 * t)
    f = _rad(93.2720950 + 483202.0175233 * t)
    s = math.sin
    lon = (lp + 6.288774 * s(mp) + 1.274027 * s(2 * d - mp) + 0.658314 * s(2 * d)
           + 0.213618 * s(2 * mp) - 0.185116 * s(m) - 0.114332 * s(2 * f)
           + 0.058793 * s(2 * d - 2 * mp) + 0.057066 * s(2 * d - m - mp)
           + 0.053322 * s(2 * d + mp) + 0.045758 * s(2 * d - m))
    return _norm(lon)


def _rahu_trop(jd):
    t = (jd - 2451545.0) / 36525.0
    return _norm(125.0445479 - 1934.1362891 * t)


def _ascendant_trop(jd, lat, lon_east):
    t = (jd - 2451545.0) / 36525.0
    gmst = _norm(280.46061837 + 360.98564736629 * (jd - 2451545.0))
    ramc = _rad(_norm(gmst + lon_east))
    eps = _rad(23.4392911 - 0.0130042 * t)
    asc = math.atan2(math.cos(ramc),
                     -(math.sin(ramc) * math.cos(eps) + math.tan(_rad(lat)) * math.sin(eps)))
    return _norm(math.degrees(asc))


def position(lon_sidereal: float) -> dict:
    lon = _norm(lon_sidereal)
    nak = int(lon // NAK_SPAN)
    return {"longitude": round(lon, 4), "rashi": RASHIS[int(lon // 30)],
            "rashi_index": int(lon // 30), "degree_in_rashi": round(lon % 30, 3),
            "nakshatra": NAKSHATRAS[nak],
            "pada": int((lon % NAK_SPAN) // (NAK_SPAN / 4)) + 1}


def to_utc(local_dt: datetime, tz: str) -> datetime:
    """tz: IANA name (e.g. Asia/Kolkata) or numeric UTC offset hours (e.g. 5.5)."""
    try:
        return local_dt.replace(tzinfo=timezone(timedelta(hours=float(tz)))).astimezone(timezone.utc)
    except ValueError:
        from zoneinfo import ZoneInfo
        return local_dt.replace(tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)


def vimshottari(moon_lon: float, birth_utc: datetime, levels_years: float = 120) -> list:
    nak = int(moon_lon // NAK_SPAN)
    elapsed = (moon_lon % NAK_SPAN) / NAK_SPAN
    idx = nak % 9
    out, start = [], birth_utc
    for i in range(9):
        lord, years = DASHA_ORDER[(idx + i) % 9]
        length = years * (1 - elapsed) if i == 0 else years
        end = start + timedelta(days=length * YEAR_DAYS)
        out.append({"lord": lord, "start": start.date().isoformat(),
                    "end": end.date().isoformat(), "years": round(length, 3)})
        start = end
    return out


def current_dasha(dashas: list, on: datetime = None) -> dict:
    d = (on or datetime.now(timezone.utc)).date().isoformat()
    for x in dashas:
        if x["start"] <= d < x["end"]:
            return x
    return dashas[-1]


def sidereal_positions(jd: float):
    """Sidereal longitudes, retrograde flags and ayanamsa for a Julian day (UT).
    Without pyswisseph only Sun, Moon and the nodes are available."""
    if swe:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags = swe.FLG_SIDEREAL | swe.FLG_MOSEPH | swe.FLG_SPEED
        ids = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
               "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN,
               "Rahu": swe.MEAN_NODE}
        res = {k: swe.calc_ut(jd, v, flags)[0] for k, v in ids.items()}
        sid = {k: r[0] for k, r in res.items()}
        retro = {k: r[3] < 0 for k, r in res.items()}
        ay = swe.get_ayanamsa_ut(jd)
    else:
        ay = lahiri_ayanamsa(jd)
        sid = {"Sun": _norm(_sun_trop(jd) - ay), "Moon": _norm(_moon_trop(jd) - ay),
               "Rahu": _norm(_rahu_trop(jd) - ay)}
        retro = {}
    sid["Ketu"] = _norm(sid["Rahu"] + 180)
    retro.update({"Sun": False, "Moon": False, "Rahu": True, "Ketu": True})  # nodes: mean node
    return sid, retro, ay


def compute_chart(local_dt: datetime, tz, lat: float, lon: float, place: str = "") -> dict:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("latitude/longitude out of range")
    utc = to_utc(local_dt, str(tz))
    jd = julian_day(utc)
    sid, retro, ay = sidereal_positions(jd)
    if swe:
        asc = _norm(swe.houses_ex(jd, lat, lon, b"W", swe.FLG_SIDEREAL)[1][0])
    else:
        asc = _norm(_ascendant_trop(jd, lat, lon) - ay)
    lagna = position(asc)
    planets = {}
    for name, l in sid.items():
        p = position(l)
        p["house"] = (p["rashi_index"] - lagna["rashi_index"]) % 12 + 1  # whole-sign
        p["retrograde"] = retro.get(name)
        planets[name] = p
    dashas = vimshottari(sid["Moon"], utc)
    return {
        "input": {"local_time": local_dt.isoformat(), "tz": str(tz), "lat": lat,
                  "lon": lon, "place": place, "utc": utc.isoformat(), "jd": jd,
                  "utc_offset_h": (local_dt.replace(tzinfo=None)
                                   - utc.replace(tzinfo=None)).total_seconds() / 3600},
        "settings": {"ayanamsa": f"Lahiri ({ay:.4f} deg)", "houses": "whole-sign",
                     "zodiac": "sidereal", "backend": BACKEND,
                     "precision": "high" if swe else "approximate (Sun/Moon/nodes/Lagna only)"},
        "lagna": lagna, "planets": planets,
        "moon_sign": planets["Moon"]["rashi"], "janma_nakshatra": planets["Moon"]["nakshatra"],
        "vimshottari": dashas, "current_dasha": current_dasha(dashas),
    }


def chart_summary(c: dict) -> str:
    """Compact text handed to the LLM as ground truth."""
    lines = [f"[Chart settings: {c['settings']['ayanamsa']}, {c['settings']['houses']}, "
             f"precision {c['settings']['precision']}]",
             f"Lagna: {c['lagna']['rashi']} {c['lagna']['degree_in_rashi']:.1f} deg"]
    for n, p in c["planets"].items():
        lines.append(f"{n}: {p['rashi']} {p['degree_in_rashi']:.1f} deg, house {p['house']}, "
                     f"{p['nakshatra']} pada {p['pada']}")
    cd = c["current_dasha"]
    lines.append(f"Current Vimshottari Mahadasha: {cd['lord']} ({cd['start']} to {cd['end']})")
    return "\n".join(lines)
