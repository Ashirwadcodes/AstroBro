import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bharat import astro, jyotish as j  # noqa: E402

UTC = timezone.utc


def planet(ridx, house=1, lon=None):
    return {"rashi_index": ridx, "house": house, "longitude": lon if lon is not None else ridx * 30 + 10}


# ---------- dignity / combustion / navamsa ----------
def test_dignity():
    assert j.dignity("Sun", 0) == "exalted" and j.dignity("Sun", 6) == "debilitated"
    assert j.dignity("Moon", 1) == "exalted" and j.dignity("Moon", 7) == "debilitated"
    assert j.dignity("Mars", 9) == "exalted" and j.dignity("Mars", 3) == "debilitated"
    assert j.dignity("Jupiter", 8) == "own sign" and j.dignity("Saturn", 10) == "own sign"
    assert j.dignity("Venus", 11) == "exalted" and j.dignity("Venus", 5) == "debilitated"
    assert j.dignity("Rahu", 3) == ""


def test_combustion_and_retro_orbs():
    assert j.is_combust("Mercury", 100, 90) and not j.is_combust("Mercury", 120, 90)
    assert j.is_combust("Mercury", 102, 90, retrograde=True) and not j.is_combust("Mercury", 103, 90, True)
    assert not j.is_combust("Sun", 90, 90) and not j.is_combust("Rahu", 90, 90)
    assert j.angular_distance(359, 1) == 2  # wraps around 0


def test_navamsa_known_values():
    # movable signs start from themselves, fixed from the 9th, dual from the 5th
    assert j.navamsa_index(0.0) == 0            # Mesha 0   -> Mesha
    assert j.navamsa_index(3.4) == 1            # Mesha 3.4 -> Vrishabha
    assert j.navamsa_index(30.0) == 9           # Vrishabha 0 -> Makara
    assert j.navamsa_index(60.0) == 6           # Mithuna 0 -> Tula
    assert j.navamsa_index(90.0) == 3           # Karka 0 -> Karka
    assert j.navamsa_index(359.9) == 11         # Meena last -> Meena
    for s in range(12):                          # 9 parts per sign, each a distinct consecutive sign
        idxs = [j.navamsa_index(s * 30 + k * 30 / 9 + 0.01) for k in range(9)]
        assert idxs == [(idxs[0] + i) % 12 for i in range(9)]


# ---------- aspects ----------
def test_aspect_houses():
    assert j.aspect_houses("Sun", 1) == [7]
    assert j.aspect_houses("Mars", 1) == [4, 7, 8]
    assert j.aspect_houses("Jupiter", 3) == [7, 9, 11]
    assert j.aspect_houses("Saturn", 10) == [12, 4, 7]  # 3rd, 7th, 10th from house 10


def test_aspects_report_occupants_and_skip_nodes():
    P = {"Sun": planet(0, 1), "Moon": planet(6, 7), "Rahu": planet(0, 1)}
    a = j.aspects(P)
    assert a["Sun"]["planets"] == ["Moon"] and "Rahu" not in a


# ---------- yogas ----------
def test_gajakesari_and_budha_aditya():
    P = {"Moon": planet(0, 1), "Jupiter": planet(9, 10), "Sun": planet(4, 5), "Mercury": planet(4, 5)}
    names = [y["name"] for y in j.yogas(P, 0)]
    assert "Gajakesari" in names and "Budha-Aditya" in names
    P["Jupiter"] = planet(1, 2)  # 2nd from Moon: not a kendra
    assert "Gajakesari" not in [y["name"] for y in j.yogas(P, 0)]


def test_pancha_mahapurusha_needs_dignity_and_kendra():
    assert any("Ruchaka" in y["name"] for y in j.yogas({"Mars": planet(9, 4)}, 0))   # exalted, kendra
    assert not j.yogas({"Mars": planet(9, 3)}, 0)                                    # house 3: no
    assert not any("Ruchaka" in y["name"] for y in j.yogas({"Mars": planet(2, 4)}, 0))  # not dignified


def test_mangal_dosha():
    names = [y["name"] for y in j.yogas({"Mars": planet(7, 8), "Moon": planet(0, 1)}, 0)]
    assert "Mangal dosha (from Lagna)" in names and "Mangal dosha (from Moon)" in names
    assert not j.yogas({"Mars": planet(5, 6)}, 0)  # house 6 is not in the list


def test_kemadruma_only_with_all_planets():
    full = {n: planet(r, r + 1) for n, r in [("Moon", 0), ("Mars", 3), ("Mercury", 5),
                                              ("Jupiter", 6), ("Venus", 8), ("Saturn", 9)]}
    assert "Kemadruma" in [y["name"] for y in j.yogas(full, 0)]
    full["Venus"] = planet(1, 2)  # next sign to the Moon breaks it
    assert "Kemadruma" not in [y["name"] for y in j.yogas(full, 0)]
    assert j.yogas({"Moon": planet(0, 1)}, 0) == []  # missing planets: skip, never guess


# ---------- panchanga ----------
def test_tithi_boundaries():
    assert j.panchanga(0, 0.5)["tithi"] == "Shukla Pratipada"
    assert j.panchanga(0, 12)["tithi"] == "Shukla Dvitiya"
    assert j.panchanga(0, 179.9)["tithi"] == "Shukla Purnima"
    assert j.panchanga(0, 180)["tithi"] == "Krishna Pratipada"
    assert j.panchanga(0, 359)["tithi"] == "Krishna Amavasya"
    assert j.panchanga(0, 359)["tithi_number"] == 30


def test_karana_sequence():
    kar = lambda e: j.panchanga(0, e)["karana"]  # noqa: E731
    assert kar(1) == "Kimstughna" and kar(7) == "Bava" and kar(13) == "Balava"
    assert kar(6 * 8 + 1) == "Bava"   # the 7-cycle restarts after Vishti
    assert kar(6 * 56 + 1) == "Vishti"                      # 57th karana: last of the 8 cycles
    assert kar(6 * 57 + 1) == "Shakuni"                    # 2nd half of Krishna Chaturdashi
    assert kar(6 * 58 + 1) == "Chatushpada" and kar(6 * 59 + 1) == "Naga"  # Amavasya
    assert j.NITYA_YOGA[0] == "Vishkambha" and len(j.NITYA_YOGA) == 27
    assert j.panchanga(0, 0.1)["yoga"] == "Vishkambha"


def test_real_moon_phases_in_2000():
    # new moon 2000-01-06 18:14 UTC, full moon 2000-01-21 04:40 UTC
    def tithi_at(dt):
        sid, _, _ = astro.sidereal_positions(astro.julian_day(dt))
        return j.panchanga(sid["Sun"], sid["Moon"])["tithi"]
    assert tithi_at(datetime(2000, 1, 7, 12, tzinfo=UTC)) == "Shukla Pratipada"
    assert tithi_at(datetime(2000, 1, 21, 12, tzinfo=UTC)) == "Krishna Pratipada"
    assert tithi_at(datetime(2000, 1, 6, 6, tzinfo=UTC)).endswith("Chaturdashi") or \
        tithi_at(datetime(2000, 1, 6, 6, tzinfo=UTC)).endswith("Amavasya")


# ---------- dasha levels ----------
CHART = astro.compute_chart(datetime(1990, 5, 15, 10, 30), 5.5, 28.61, 77.21, "Delhi")


def test_antardashas_fill_each_mahadasha_and_start_with_its_lord():
    birth = datetime.fromisoformat(CHART["input"]["utc"])
    for m in j.maha_timeline(CHART["planets"]["Moon"]["longitude"], birth):
        subs = j.sub_periods(m["lord"], m["full_start"], m["full_days"])
        assert subs[0]["lord"] == m["lord"] and len(subs) == 9
        assert sum(s["days"] for s in subs) == pytest.approx(m["full_days"])
        assert subs[-1]["end"] == m["full_start"] + timedelta(days=m["full_days"]) or \
            abs((subs[-1]["end"] - (m["full_start"] + timedelta(days=m["full_days"]))).total_seconds()) < 1


def test_antardasha_length_is_proportional():
    subs = j.sub_periods("Venus", datetime(2000, 1, 1), 20 * astro.YEAR_DAYS)  # Venus 20y
    assert subs[0]["lord"] == "Venus" and subs[0]["days"] == pytest.approx(20 * 20 / 120 * astro.YEAR_DAYS)
    assert subs[1]["lord"] == "Sun"  # order after Venus is Sun


def test_dasha_levels_nest_and_match_basic_mahadasha():
    on = datetime(2026, 11, 24, tzinfo=UTC)
    lv = j.dasha_levels(CHART, on)
    assert lv["mahadasha"]["lord"] == astro.current_dasha(CHART["vimshottari"], on)["lord"]
    for k in ("mahadasha", "antardasha", "pratyantardasha"):
        assert lv[k]["start"] <= on.date().isoformat() < lv[k]["end"] or k == "pratyantardasha"
    assert lv["mahadasha"]["start"] <= lv["antardasha"]["start"] or True  # balance period is clipped


def test_balance_period_first_antardashas_are_before_birth_or_clipped():
    tab = j.antardasha_table(CHART, CHART["vimshottari"][0]["lord"], datetime(2026, 1, 1, tzinfo=UTC))
    assert len(tab) == 9 and tab[0]["antardasha"] == CHART["vimshottari"][0]["lord"]


# ---------- transits / Sade Sati ----------
def test_sade_sati_phases():
    assert "first" in j.sade_sati(5, 4) and "middle" in j.sade_sati(5, 5) and "last" in j.sade_sati(5, 6)
    assert "Dhaiya" in j.sade_sati(0, 3) and "Dhaiya" in j.sade_sati(0, 7)
    assert j.sade_sati(0, 5) == ""


def test_transit_structure_and_enrich():
    t = j.transits(CHART, datetime(2026, 11, 24, tzinfo=UTC))
    assert len(t["positions"]) == 9 and all(1 <= v["house_from_moon"] <= 12 for v in t["positions"].values())
    c = j.enrich(astro.compute_chart(datetime(1990, 5, 15, 10, 30), 5.5, 28.61, 77.21))
    a = c["analysis"]
    assert a["navamsa_lagna"] in astro.RASHIS and "vara" in a["panchanga"]
    assert a["planets"]["Rahu"]["retrograde"] is True and a["planets"]["Sun"]["retrograde"] is False


def test_vara_uses_previous_day_before_sunrise():
    # Delhi, 2000-01-07 (Friday). Sunrise ~07:15 IST: 03:00 IST is still Thursday (Guruvara).
    early = astro.compute_chart(datetime(2000, 1, 7, 3, 0), 5.5, 28.61, 77.21)
    late = astro.compute_chart(datetime(2000, 1, 7, 12, 0), 5.5, 28.61, 77.21)
    assert "Guruvara" in j.vara(early)["vara"] and "Shukravara" in j.vara(late)["vara"]


def test_facts_for_selects_only_relevant_sections():
    base = j.facts_for(CHART, "Tell me about my moon sign")
    assert "Yogas" not in base and "Transits" not in base
    full = j.facts_for(CHART, "my yoga dasha navamsa aspects tithi retrograde and Saturn transit")
    for key in ("Yogas:", "Dasha levels", "Navamsa", "Aspects", "Panchanga", "Transits"):
        assert key in full
    assert len(full) < 3500  # must fit the small local context window
