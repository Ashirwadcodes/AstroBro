"""Compare BM25 with hybrid (BM25 + embeddings) on hand-written questions.
Run: .venv/Scripts/python.exe tools/eval_search.py"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bharat.embeddings import HybridRetriever  # noqa: E402
from bharat.knowledge import Retriever, load_corpus  # noqa: E402

CASES = [
    ("what is yoga, control of the fluctuations of the mind", ["Yoga Sutras I.2", "Yoga Sutra 1.2"]),
    ("who is the unknown god, the golden child", ["Vedic Hymns, To The Unknown God"]),
    ("hymn to the storm gods the Maruts", ["Vedic Hymns, To The Maruts"]),
    ("Rudra with his strong bow and swift arrows", ["Vedic Hymns, To Rudra"]),
    ("the wind god brings healing medicine", ["Vedic Hymns, To V"]),
    ("Kitra asks Svetaketu about the world after death", ["Kaushitaki Upanishad"]),
    ("life breath prana is consciousness, Pratardana and Indra", ["Kaushitaki Upanishad"]),
    ("what is Navamsa", ["Navamsa"]),
    ("how long is an antardasha sub period", ["Antardasha"]),
    ("what is Sade Sati", ["Sade Sati"]),
    ("Mars in the seventh house and marriage", ["Mangal dosha"]),
    ("what is Kaal Sarp dosha", ["Kaal Sarp dosha"]),
    ("how is the life path number calculated", ["Life Path number"]),
    ("what do the head line, heart line and life line mean in a palm", ["Main lines"]),
    ("sattva rajas tamas three qualities of nature", ["Gita Lesson 14", "Gita 14."]),
    ("how to calm a restless mind in meditation", ["Gita Lesson 6", "Gita 6."]),
    ("a leaf, a flower, fruit or water offered with love", ["Gita Lesson 9", "Gita 9."]),
    ("Arjuna sees the cosmic form and is terrified", ["Gita Lesson 11", "Gita 11."]),
    ("how should I begin studying the Gita", ["Gita Lesson 0"]),
    ("eight limbs of yoga", ["Yoga Sutras II.2"]),
    ("order and years of the Vimshottari dasha planets", ["Vimshottari Dasha"]),
    ("what is the Lahiri ayanamsa", ["Ayanamsa"]),
    ("meaning of dharma, karma and moksha", ["Gita Lesson - Terms"]),
    ("you have a right to action but never to its fruits", ["Gita 2.47"]),
    ("the soul is never born and never dies", ["Gita 2."]),
    # paraphrases that share few words with the source
    ("is it wrong to fight your own relatives", ["Gita Lesson 1", "Gita 1."]),
    ("how do I stop worrying about outcomes of my work", ["Gita 2.47", "Gita Lesson 2", "Gita Lesson 3", "Gita 2.", "Gita 3."]),
    ("what happens at the moment of death according to the Gita", ["Gita Lesson 8", "Gita 8."]),
    ("which planet period runs first after birth", ["Vimshottari Dasha", "Nakshatra"]),
    ("when is a planet considered strong or weak in a sign", ["Dignity"]),
    ("what does the hand type fire or water mean", ["Hand shapes"]),
    ("birth number linked to the Sun or Moon in Indian numerology", ["Moolank and Bhagyank"]),
    ("tests of discipline when Saturn goes over the Moon", ["Sade Sati"]),
    ("ancient prayer asking which deity to worship", ["Vedic Hymns, To The Unknown God"]),
    ("Nachiketas asks Yama what happens after death", ["Katha Upanishad"]),
    ("how the Lord covers everything, do not covet others' wealth", ["Isa Upanishad"]),
    ("what is it that makes the mind think and the eyes see", ["Kena Upanishad"]),
    ("higher knowledge and lower knowledge of Brahman", ["Mundaka Upanishad"]),
    ("whence are we born, is Brahman the cause", ["Svetasvatara Upanishad"]),
    ("in the beginning there was nothing but death, hunger", ["Brihadaranyaka Upanishad"]),
    ("six questions asked of Pippalada about creation and prana", ["Prasna Upanishad"]),
    ("then was not non-existent nor existent, hymn of creation", ["Rigveda 10.129"]),
    ("a thousand heads hath Purusa, the cosmic man sacrifice", ["Rigveda 10.90"]),
    ("I laud Agni the chosen priest", ["Rigveda 1.1."]),
    ("Indra slew the dragon and released the waters", ["Rigveda 1.32"]),
    ("Varuna, what was my chief transgression, free us from sin", ["Rigveda 7.86"]),
    ("gambler laments dice and his wife", ["Rigveda 10.34"]),
    ("does the self survive after the body dies", ["Gita 2.", "Gita Lesson 2", "Kaushitaki"]),
    ("Valmiki asks Narad who is the perfect virtuous man", ["Ramayana I.1."]),
    ("Dasaratha sends Rama into exile because of Kaikeyi's boon", ["Ramayana II."]),
    ("Ravan carries Sita away in his chariot", ["Ramayana III."]),
    ("Draupadi is staked in the game of dice and dragged into the assembly", ["Mahabharata 2."]),
    ("Ashvatthama kills the sleeping Pandava camp at night", ["Mahabharata 10."]),
    ("Yaksha questions Yudhishthira at the lake", ["Mahabharata 3."]),
    ("Bhishma lying on a bed of arrows instructs Yudhishthira on kingly duty", ["Mahabharata 12.", "Mahabharata 13."]),
]


def score(r):
    hit, rr = 0, 0.0
    for q, want in CASES:
        found = False
        res = r.search(q, k=4)
        for rank, (_, c) in enumerate(res, 1):
            if any(c.ref.startswith(w) or f"{c.source}, {c.ref}".startswith(w) or w in c.ref for w in want):
                hit += 1
                rr += 1 / rank
                found = True
                break
        if not found:
            print("   miss:", q[:60], "->", [c.ref for _, c in res][:4])
    return hit, rr / len(CASES)


chunks, _ = load_corpus()
t = time.time()
b = Retriever(chunks)
print("BM25   hit@4 %d/%d  MRR %.2f" % (*score(b)[:1], len(CASES), score(b)[1]))
t = time.time()
h = HybridRetriever(chunks)
print("index time %.0fs, embeddings active: %s %s" % (time.time() - t, h.vecs is not None, h.error or ""))
s = score(h)
print("Hybrid hit@4 %d/%d  MRR %.2f" % (s[0], len(CASES), s[1]))
