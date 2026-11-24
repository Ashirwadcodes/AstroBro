"""Numerology (Pythagorean and Chaldean). Pure arithmetic - the LLM never computes these.
A traditional/modern belief system, not science."""
import re
from datetime import date

MASTER = (11, 22, 33)
PYTH = {c: (i % 9) + 1 for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")}
CHALDEAN = {}
for _n, _letters in {1: "aijqy", 2: "bkr", 3: "cgls", 4: "dmt", 5: "eh nx", 6: "uvw", 7: "oz", 8: "fp"}.items():
    for _c in _letters.replace(" ", ""):
        CHALDEAN[_c] = _n
VOWELS = set("aeiou")


def reduce(n: int, keep_master: bool = True) -> int:
    while n > 9 and not (keep_master and n in MASTER):
        n = sum(int(d) for d in str(n))
    return n


def _letters(name: str):
    return [c for c in re.sub(r"[^a-z ]", "", name.lower()) if c != " "]


def name_numbers(name: str, system: str = "pythagorean") -> dict:
    table = PYTH if system == "pythagorean" else CHALDEAN
    ls = _letters(name)
    if not ls:
        raise ValueError("name needs Latin letters (type it in English letters)")
    tot = sum(table[c] for c in ls)
    # 'y' counted as a consonant for the soul/personality split (simple common rule)
    soul = sum(table[c] for c in ls if c in VOWELS)
    pers = sum(table[c] for c in ls if c not in VOWELS)
    return {"system": system, "destiny": reduce(tot), "soul_urge": reduce(soul),
            "personality": reduce(pers), "raw_total": tot}


def life_path(d: date) -> int:
    return reduce(reduce(d.day) + reduce(d.month) + reduce(sum(int(x) for x in str(d.year))))


def birth_numbers(d: date) -> dict:
    return {"life_path": life_path(d), "birth_day": reduce(d.day, keep_master=False),
            "driver_psychic": reduce(d.day, keep_master=False)}  # Indian 'moolank'


def personal_year(d: date, year: int) -> int:
    return reduce(reduce(d.day) + reduce(d.month) + reduce(year))


MEANINGS = {
    1: "independence, initiative, leadership", 2: "cooperation, sensitivity, balance",
    3: "expression, creativity, sociability", 4: "discipline, structure, hard work",
    5: "change, freedom, curiosity", 6: "care, responsibility, harmony",
    7: "reflection, study, inner search", 8: "ambition, authority, material effort",
    9: "compassion, completion, idealism", 11: "intuition and inspiration (master number)",
    22: "large-scale building (master number)", 33: "selfless teaching (master number)"}

# Indian numerology (Ank Jyotish) ties each root number to a graha.
GRAHA = {1: "Surya (Sun)", 2: "Chandra (Moon)", 3: "Guru (Jupiter)", 4: "Rahu", 5: "Budha (Mercury)",
         6: "Shukra (Venus)", 7: "Ketu", 8: "Shani (Saturn)", 9: "Mangala (Mars)"}


def report(name: str, birth: date, today: date = None) -> dict:
    today = today or date.today()
    b = birth_numbers(birth)
    py = name_numbers(name, "pythagorean")
    ch = name_numbers(name, "chaldean")
    root = reduce(birth.day, keep_master=False)
    return {"birth": b, "pythagorean": py, "chaldean": ch,
            "moolank_graha": GRAHA[root], "personal_year": personal_year(birth, today.year),
            "meanings": {k: MEANINGS[k] for k in {b["life_path"], py["destiny"], root} if k in MEANINGS},
            "note": "Numerology is a belief system without scientific support."}
