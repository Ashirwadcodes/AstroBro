"""Per-user learning without retraining the model.

AstroBro "learns" in three controllable ways:
1. Taught notes: the user adds their own notes. They are stored encrypted, private to that
   user, labelled "unverified", and automatically LINKED to the closest library passages so
   later answers can combine the note with trusted sources.
2. Feedback: thumbs up/down raise or lower how often a passage is retrieved for that user.
3. Conversation history is passed by the caller (see service.answer).

Nothing here changes model weights, and notes are treated as data, never as instructions.
"""
import json
import time

from . import config, security
from .knowledge import Chunk


def add_note(con, user_id: int, title: str, text: str, retriever) -> dict:
    title = security.clean_text(title, 80)
    text = security.clean_text(text, config.MAX_NOTE_CHARS)
    if len(text) < 10:
        raise ValueError("Note is too short to learn from (10+ characters).")
    if not title:
        title = text[:40]
    if security.looks_like_injection(title) or security.looks_like_injection(text):
        raise ValueError("That looks like instructions for the AI, not knowledge. Rejected.")
    if not security.limiter.allow("note:%s" % user_id, 20, 3600):
        raise ValueError("Too many notes this hour. Try later.")
    count = con.execute("SELECT count(*) FROM notes WHERE user_id=?", (user_id,)).fetchone()[0]
    if count >= config.MAX_NOTES:
        raise ValueError(f"Note limit reached ({config.MAX_NOTES}). Delete some first.")
    hits = retriever.search(title + " " + text, k=3, min_score=1.0)
    links = [{"id": c.id, "label": f"{c.source} {c.ref}"} for _, c in hits]
    cur = con.execute("INSERT INTO notes(user_id,data,links,created) VALUES(?,?,?,?)",
                      (user_id, security.encrypt_json({"title": title, "text": text}),
                       json.dumps(links), time.time()))
    con.commit()
    return {"id": cur.lastrowid, "links": [l["label"] for l in links]}


def list_notes(con, user_id: int) -> list:
    out = []
    for r in con.execute("SELECT id,data,links FROM notes WHERE user_id=? ORDER BY id DESC", (user_id,)):
        d = security.decrypt_json(r["data"])
        out.append({"id": r["id"], "title": d["title"], "text": d["text"],
                    "links": [l["label"] for l in json.loads(r["links"])]})
    return out


def delete_note(con, user_id: int, note_id: int):
    con.execute("DELETE FROM notes WHERE id=? AND user_id=?", (note_id, user_id))
    con.commit()


def note_chunks(con, user_id: int) -> list:
    return [Chunk(f"note:{n['id']}", n["text"], "Your notes", n["title"], "user-own",
                  "user-provided (unverified)") for n in list_notes(con, user_id)]


def note_links(con, user_id: int) -> dict:
    return {f"note:{r['id']}": [l["id"] for l in json.loads(r["links"])]
            for r in con.execute("SELECT id,links FROM notes WHERE user_id=?", (user_id,))}


def vote(con, user_id: int, chunk_ids, delta: int):
    for cid in chunk_ids or []:
        row = con.execute("SELECT vote FROM feedback WHERE user_id=? AND chunk_id=?",
                          (user_id, cid)).fetchone()
        net = max(-5, min(5, (row["vote"] if row else 0) + delta))
        con.execute("INSERT OR REPLACE INTO feedback VALUES(?,?,?)", (user_id, cid, net))
    con.commit()


def votes(con, user_id: int) -> dict:
    return {r["chunk_id"]: r["vote"]
            for r in con.execute("SELECT chunk_id,vote FROM feedback WHERE user_id=?", (user_id,))}
