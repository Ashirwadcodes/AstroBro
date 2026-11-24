"""Security primitives: password hashing, sessions, rate limiting, input hygiene,
audit logging, optional at-rest encryption of birth data. Standard library first."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque

from . import config

# ---------- passwords (scrypt, per-user salt, constant-time compare) ----------
_N, _R, _P = 2 ** 14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return "scrypt$%d$%d$%d$%s$%s" % (_N, _R, _P, salt.hex(), dk.hex())


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, dk = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt),
                              n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc.hex(), dk)
    except Exception:
        return False


def check_password_policy(password: str) -> list:
    problems = []
    if len(password) < config.MIN_PASSWORD_LEN:
        problems.append(f"at least {config.MIN_PASSWORD_LEN} characters")
    if not re.search(r"[a-z]", password) or not re.search(r"[A-Z]", password):
        problems.append("upper and lower case letters")
    if not re.search(r"\d", password):
        problems.append("a digit")
    return problems


# ---------- rate limiting (sliding window, in-memory, thread-safe) ----------
class RateLimiter:
    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_s: int, now: float = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_s:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


limiter = RateLimiter()


# ---------- input hygiene ----------
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INJECTION = re.compile(
    r"(ignore (all |any )?(previous|prior|above) (instructions|rules)|"
    r"disregard (the )?(system|previous)|reveal (your )?(system )?prompt|"
    r"you are now|developer mode|jailbreak)", re.I)


def clean_text(text: str, limit: int = None) -> str:
    text = _CTRL.sub("", text or "").strip()
    return text[: limit or config.MAX_INPUT_CHARS]


def looks_like_injection(text: str) -> bool:
    return bool(_INJECTION.search(text or ""))


def valid_username(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", name or ""))


# ---------- optional encryption of sensitive fields (needs `cryptography`) ----------
def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return None
    if not config.KEY_PATH.exists():
        config.KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.KEY_PATH.write_bytes(Fernet.generate_key())
        try:
            os.chmod(config.KEY_PATH, 0o600)
        except OSError:
            pass
    return Fernet(config.KEY_PATH.read_bytes())


def encrypt_json(obj) -> str:
    raw = json.dumps(obj).encode()
    f = _fernet()
    if f is None:
        return "plain:" + base64.b64encode(raw).decode()  # install cryptography to encrypt
    return "enc:" + f.encrypt(raw).decode()


def decrypt_json(blob: str):
    kind, _, data = blob.partition(":")
    if kind == "plain":
        return json.loads(base64.b64decode(data))
    f = _fernet()
    if f is None:
        raise RuntimeError("cryptography package required to read encrypted data")
    return json.loads(f.decrypt(data.encode()))


def encryption_active() -> bool:
    return _fernet() is not None


# ---------- database, accounts, sessions, audit ----------
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, pw TEXT NOT NULL,
  fails INTEGER DEFAULT 0, locked_until REAL DEFAULT 0, created REAL);
CREATE TABLE IF NOT EXISTS sessions(
  token_hash TEXT PRIMARY KEY, user_id INTEGER, expires REAL);
CREATE TABLE IF NOT EXISTS profiles(
  user_id INTEGER PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notes(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, data TEXT NOT NULL,
  links TEXT NOT NULL DEFAULT '[]', created REAL);
CREATE TABLE IF NOT EXISTS feedback(
  user_id INTEGER NOT NULL, chunk_id TEXT NOT NULL, vote INTEGER NOT NULL,
  PRIMARY KEY(user_id, chunk_id));
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY, ts REAL, user TEXT, event TEXT, detail TEXT);
"""


def connect(path=None) -> sqlite3.Connection:
    path = path or config.DB_PATH
    if str(path) != ":memory:":
        os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def audit(con, user: str, event: str, detail: str = ""):
    con.execute("INSERT INTO audit(ts,user,event,detail) VALUES(?,?,?,?)",
                (time.time(), user, event, detail[:200]))
    con.commit()


class AuthError(Exception):
    pass


def register(con, username: str, password: str):
    if not valid_username(username):
        raise AuthError("Username must be 3-32 chars: letters, digits, _ . -")
    problems = check_password_policy(password)
    if problems:
        raise AuthError("Password needs " + ", ".join(problems))
    try:
        con.execute("INSERT INTO users(username,pw,created) VALUES(?,?,?)",
                    (username, hash_password(password), time.time()))
        con.commit()
    except sqlite3.IntegrityError:
        raise AuthError("Username unavailable")
    audit(con, username, "register")


def login(con, username: str, password: str) -> str:
    """Returns a session token. Generic errors avoid revealing which part failed."""
    if not limiter.allow("login:" + username.lower(), *config.LOGIN_RATE):
        raise AuthError("Too many attempts. Try again later.")
    row = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    now = time.time()
    if row is None:
        hash_password(password)  # equalise timing
        raise AuthError("Invalid credentials")
    if row["locked_until"] > now:
        raise AuthError("Account temporarily locked")
    if not verify_password(password, row["pw"]):
        fails = row["fails"] + 1
        locked = now + config.LOGIN_LOCK_S if fails >= config.LOGIN_MAX_FAILS else 0
        con.execute("UPDATE users SET fails=?, locked_until=? WHERE id=?",
                    (0 if locked else fails, locked, row["id"]))
        con.commit()
        audit(con, username, "login_fail")
        raise AuthError("Invalid credentials")
    con.execute("UPDATE users SET fails=0, locked_until=0 WHERE id=?", (row["id"],))
    token = secrets.token_urlsafe(32)
    con.execute("INSERT INTO sessions VALUES(?,?,?)",
                (hashlib.sha256(token.encode()).hexdigest(), row["id"],
                 now + config.SESSION_TTL_S))
    con.commit()
    audit(con, username, "login_ok")
    return token


def user_for_token(con, token: str):
    if not token:
        return None
    h = hashlib.sha256(token.encode()).hexdigest()
    row = con.execute(
        "SELECT u.id, u.username, s.expires FROM sessions s JOIN users u ON u.id=s.user_id "
        "WHERE s.token_hash=?", (h,)).fetchone()
    if row is None or row["expires"] < time.time():
        return None
    return {"id": row["id"], "username": row["username"]}


def logout(con, token: str):
    con.execute("DELETE FROM sessions WHERE token_hash=?",
                (hashlib.sha256(token.encode()).hexdigest(),))
    con.commit()


def save_profile(con, user_id: int, data: dict):
    con.execute("INSERT OR REPLACE INTO profiles VALUES(?,?)", (user_id, encrypt_json(data)))
    con.commit()


def load_profile(con, user_id: int):
    row = con.execute("SELECT data FROM profiles WHERE user_id=?", (user_id,)).fetchone()
    return decrypt_json(row["data"]) if row else None


def delete_all_user_data(con, user_id: int):
    """Right-to-erasure: removes profile, sessions and account."""
    for t, col in (("notes", "user_id"), ("feedback", "user_id"), ("profiles", "user_id"),
                   ("sessions", "user_id"), ("users", "id")):
        con.execute(f"DELETE FROM {t} WHERE {col}=?", (user_id,))
    con.commit()
