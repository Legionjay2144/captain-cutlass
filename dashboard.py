import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import time
from http import cookies
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DB_PATH = os.getenv("DATABASE_PATH", "/app/data/captain.db")
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8787"))
DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN", "").strip()
DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME", "").strip()
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "").strip()
DASHBOARD_USERS = os.getenv("DASHBOARD_USERS", "").strip()
DASHBOARD_USERS_FILE = os.getenv("DASHBOARD_USERS_FILE", "/app/data/dashboard_users.json").strip()
DASHBOARD_SESSION_SECRET = (
    os.getenv("DASHBOARD_SESSION_SECRET", "").strip()
    or DASHBOARD_TOKEN
    or secrets.token_urlsafe(32)
)
DASHBOARD_SESSION_SECONDS = int(os.getenv("DASHBOARD_SESSION_SECONDS", "86400"))
DASHBOARD_COOKIE_NAME = "cutlass_dashboard_session"
DASHBOARD_ASSETS = {
    "/assets/cutlass.png": Path(__file__).with_name("cutlass.png"),
    "/assets/banner.png": Path(__file__).with_name("banner.png"),
}
PASSWORD_HASH_ITERATIONS = 260000

TEXT_LIMIT = 500
LIST_LIMIT = 200


def db_connect():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    uri = "file:" + DB_PATH + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def db_write_connect():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn, table):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def rows(conn, sql, params=()):
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def one(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def scalar(conn, sql, params=(), default=0):
    row = conn.execute(sql, params).fetchone()
    if not row:
        return default
    value = row[0]
    return default if value is None else value


def clean_text(value, limit=TEXT_LIMIT):
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def dashboard_user_map():
    users = {}
    if DASHBOARD_USERS:
        for item in DASHBOARD_USERS.split(","):
            if not item.strip() or ":" not in item:
                continue
            username, password = item.split(":", 1)
            username = username.strip()
            password = password.strip()
            if username and password:
                users[username] = {"password": password, "role": "admin"}
    if DASHBOARD_USERNAME and DASHBOARD_PASSWORD:
        users[DASHBOARD_USERNAME] = {"password": DASHBOARD_PASSWORD, "role": "admin"}
    return users


def hash_dashboard_password(password):
    salt = secrets.token_urlsafe(18)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def verify_dashboard_password(password, stored_hash):
    try:
        algorithm, iterations, salt, digest = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()
        return hmac.compare_digest(candidate, digest)
    except Exception:
        return False


def normalize_dashboard_access(record):
    role = record.get("role", "user") if isinstance(record, dict) else "user"
    access = record.get("access", {}) if isinstance(record, dict) else {}
    if role == "admin":
        return {"all": True, "global": True, "guild_ids": []}
    if not isinstance(access, dict):
        access = {}
    return {
        "all": bool(access.get("all", False)),
        "global": bool(access.get("global", False)),
        "guild_ids": sorted(str(guild_id) for guild_id in access.get("guild_ids", []) if str(guild_id).strip()),
    }


def dashboard_user_can_global(user):
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    access = user.get("access") or normalize_dashboard_access(user)
    return bool(access.get("all") or access.get("global"))


def dashboard_user_can_guild(user, guild_id):
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    access = user.get("access") or normalize_dashboard_access(user)
    return bool(access.get("all") or str(guild_id) in set(access.get("guild_ids", [])))


def require_dashboard_access(user, guild_id=None, global_required=False):
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    if global_required:
        return dashboard_user_can_global(user)
    if guild_id is not None:
        return dashboard_user_can_guild(user, guild_id)
    return True


def load_dashboard_users():
    path = Path(DASHBOARD_USERS_FILE)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {}
    users = data.get("users", {}) if isinstance(data, dict) else {}
    clean = {}
    for username, record in users.items():
        if not isinstance(record, dict) or not record.get("password_hash"):
            continue
        role = "admin" if record.get("role") == "admin" else "user"
        clean[str(username)] = {
            "password_hash": str(record.get("password_hash")),
            "role": role,
            "created_at": record.get("created_at"),
            "access": normalize_dashboard_access({**record, "role": role}),
        }
    return clean


def save_dashboard_users(users):
    path = Path(DASHBOARD_USERS_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_users = {
        username: {
            "password_hash": record["password_hash"],
            "role": "admin" if record.get("role") == "admin" else "user",
            "created_at": record.get("created_at") or int(time.time()),
            "access": normalize_dashboard_access(record),
        }
        for username, record in sorted(users.items())
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({"users": safe_users}, indent=2, sort_keys=True))
    tmp.replace(path)


def ensure_dashboard_users():
    users = load_dashboard_users()
    changed = False
    for username, seed in dashboard_user_map().items():
        password = seed.get("password")
        if not username or not password:
            continue
        created_at = users.get(username, {}).get("created_at") or int(time.time())
        users[username] = {
            "password_hash": hash_dashboard_password(password),
            "role": seed.get("role", "admin"),
            "created_at": created_at,
            "access": normalize_dashboard_access({"role": seed.get("role", "admin"), "access": users.get(username, {}).get("access", {})}),
        }
        changed = True
    if changed:
        save_dashboard_users(users)
    return users


def dashboard_public_users():
    return [
        {
            "username": username,
            "role": record.get("role", "user"),
            "created_at": record.get("created_at"),
            "access": normalize_dashboard_access(record),
        }
        for username, record in sorted(load_dashboard_users().items())
    ]


def dashboard_user_record(username):
    return load_dashboard_users().get(username)


def verify_dashboard_login(username, password):
    record = dashboard_user_record(username)
    if not record:
        return None
    if not verify_dashboard_password(password, record.get("password_hash", "")):
        return None
    return {"username": username, "role": record.get("role", "user"), "access": normalize_dashboard_access(record)}


def create_dashboard_user(username, password, role="user", access=None):
    username = re.sub(r"[^A-Za-z0-9_.@-]", "", str(username or "").strip())
    if len(username) < 2:
        raise ValueError("Username must be at least 2 characters.")
    if len(str(password or "")) < 8:
        raise ValueError("Password must be at least 8 characters.")
    users = load_dashboard_users()
    if username in users:
        raise ValueError("That dashboard user already exists.")
    role = "admin" if role == "admin" else "user"
    users[username] = {
        "password_hash": hash_dashboard_password(password),
        "role": role,
        "created_at": int(time.time()),
        "access": normalize_dashboard_access({"role": role, "access": access or {"all": False, "global": False, "guild_ids": []}}),
    }
    save_dashboard_users(users)
    return {"username": username, "role": users[username]["role"], "created_at": users[username]["created_at"], "access": users[username]["access"]}


def delete_dashboard_user(username):
    users = load_dashboard_users()
    record = users.get(username)
    if not record:
        raise ValueError("That dashboard user does not exist.")
    admin_count = sum(1 for item in users.values() if item.get("role") == "admin")
    if record.get("role") == "admin" and admin_count <= 1:
        raise ValueError("Cannot remove the last dashboard admin.")
    del users[username]
    save_dashboard_users(users)


def update_dashboard_user_access(username, role=None, access=None):
    users = load_dashboard_users()
    record = users.get(username)
    if not record:
        raise ValueError("That dashboard user does not exist.")
    current_role = record.get("role", "user")
    next_role = "admin" if role == "admin" else "user" if role == "user" else current_role
    if current_role == "admin" and next_role != "admin":
        admin_count = sum(1 for item in users.values() if item.get("role") == "admin")
        if admin_count <= 1:
            raise ValueError("Cannot demote the last dashboard admin.")
    record["role"] = next_role
    record["access"] = normalize_dashboard_access({"role": next_role, "access": access if access is not None else record.get("access", {})})
    users[username] = record
    save_dashboard_users(users)
    return {"username": username, "role": record["role"], "created_at": record.get("created_at"), "access": record["access"]}


ensure_dashboard_users()


def dashboard_login_enabled():
    return bool(load_dashboard_users())


def make_session_token(username):
    expires = str(int(time.time()) + DASHBOARD_SESSION_SECONDS)
    payload = f"{username}|{expires}"
    signature = hmac.new(
        DASHBOARD_SESSION_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    raw = f"{payload}|{signature}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def verify_session_token(token):
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        username, expires, signature = raw.rsplit("|", 2)
        if int(expires) < int(time.time()):
            return None
    except Exception:
        return None

    payload = f"{username}|{expires}"
    expected = hmac.new(
        DASHBOARD_SESSION_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    if not dashboard_user_record(username):
        return None
    return username


def dashboard_cookie_header(username):
    morsel = cookies.SimpleCookie()
    morsel[DASHBOARD_COOKIE_NAME] = make_session_token(username)
    morsel[DASHBOARD_COOKIE_NAME]["httponly"] = True
    morsel[DASHBOARD_COOKIE_NAME]["path"] = "/"
    morsel[DASHBOARD_COOKIE_NAME]["samesite"] = "Lax"
    morsel[DASHBOARD_COOKIE_NAME]["max-age"] = str(DASHBOARD_SESSION_SECONDS)
    return morsel.output(header="").strip()


def expired_dashboard_cookie_header():
    morsel = cookies.SimpleCookie()
    morsel[DASHBOARD_COOKIE_NAME] = ""
    morsel[DASHBOARD_COOKIE_NAME]["httponly"] = True
    morsel[DASHBOARD_COOKIE_NAME]["path"] = "/"
    morsel[DASHBOARD_COOKIE_NAME]["samesite"] = "Lax"
    morsel[DASHBOARD_COOKIE_NAME]["max-age"] = "0"
    return morsel.output(header="").strip()


PERSONALITY_ARCHETYPES = {
    "Shipwright Strategist": {
        "keywords": ("build", "built", "creator", "shipwright", "feature", "upgrade", "system", "server", "automation", "practical", "fix", "work", "maintain", "improve"),
        "traits": ("builder", "planner", "systems-minded", "improvement-driven"),
    },
    "Jester of the Crew": {
        "keywords": ("joke", "jokes", "pun", "puns", "funny", "laugh", "humor", "banter", "comedy", "quip", "tease"),
        "traits": ("playful", "humorous", "banter-friendly", "morale-lifting"),
    },
    "Treasure-Seeker": {
        "keywords": ("treasure", "loot", "doubloon", "gold", "reward", "hunt", "adventure", "explore", "discovery", "map"),
        "traits": ("adventurous", "reward-focused", "curious", "exploration-minded"),
    },
    "Loyal Deckhand": {
        "keywords": ("loyal", "trusted", "friend", "crew", "crewmate", "help", "helpful", "support", "donated", "contribution", "ship", "together"),
        "traits": ("loyal", "supportive", "crew-first", "dependable"),
    },
    "Chaos Spark": {
        "keywords": ("chaos", "mutiny", "trouble", "wild", "storm", "mischief", "dramatic", "bold", "lively"),
        "traits": ("energetic", "unpredictable", "bold", "high-spirited"),
    },
    "Quiet Newcomer": {
        "keywords": ("new", "joined", "welcome", "welcomed", "learning", "fresh", "new crewmate"),
        "traits": ("new", "developing", "lightly-known", "needs-more-context"),
    },
    "Lorekeeper": {
        "keywords": ("story", "stories", "tale", "lore", "memory", "remember", "old", "history", "canon", "legend"),
        "traits": ("story-driven", "memory-rich", "nostalgic", "lore-curious"),
    },
}


def collect_member_signal_text(conn, guild_id, user_id, base=None):
    parts = []

    if base:
        for key in ("relationship_type", "nickname", "opinion", "summary"):
            value = base.get(key)
            if value:
                parts.append(str(value))

    signal_queries = (
        ("user_memories", "memory", "ORDER BY confidence DESC, id DESC LIMIT 8"),
        ("running_jokes", "joke", "ORDER BY id DESC LIMIT 5"),
        ("relationship_events", "event", "ORDER BY importance DESC, id DESC LIMIT 6"),
        ("achievements", "achievement || ' ' || COALESCE(description, '')", "ORDER BY id DESC LIMIT 8"),
        ("messages", "content", "ORDER BY id ASC"),
    )

    for table, column, order in signal_queries:
        if not table_exists(conn, table):
            continue
        for row in conn.execute(
            f"SELECT {column} AS text FROM {table} WHERE guild_id=? AND user_id=? {order}",
            (guild_id, user_id),
        ):
            if row["text"]:
                parts.append(str(row["text"]))

    return "\n".join(parts)


def infer_personality_type(signal_text, base=None):
    text = str(signal_text or "").lower()
    base = base or {}
    scores = {}
    evidence = {}

    for name, config in PERSONALITY_ARCHETYPES.items():
        score = 0
        hits = []
        for keyword in config["keywords"]:
            count = text.count(keyword)
            if count:
                score += count
                hits.append(keyword)
        scores[name] = score
        evidence[name] = hits[:6]

    familiarity = safe_int(base.get("familiarity"), 0)
    memory_count = safe_int(base.get("memory_count"), 0)
    joke_count = safe_int(base.get("joke_count"), 0)
    work_runs = safe_int(base.get("work_runs"), 0)
    ship_contributed = safe_int(base.get("ship_contributed"), 0)
    achievement_count = safe_int(base.get("achievement_count"), 0)
    message_count = safe_int(base.get("message_count"), 0)

    if familiarity >= 75:
        scores["Loyal Deckhand"] += 2
    if memory_count >= 5:
        scores["Lorekeeper"] += 1
    if joke_count >= 3:
        scores["Jester of the Crew"] += 2
    if work_runs >= 2 or ship_contributed > 0:
        scores["Loyal Deckhand"] += 2
    if achievement_count >= 5:
        scores["Treasure-Seeker"] += 1
    if message_count >= 50:
        scores["Loyal Deckhand"] += 1
    if message_count >= 150:
        scores["Lorekeeper"] += 1

    best_name, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score <= 0:
        best_name = "Quiet Newcomer"
        best_score = 1

    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    secondary = [name for name, score in sorted_scores[1:4] if score > 0]
    confidence = min(95, 25 + (best_score * 7) + min(20, memory_count + joke_count + achievement_count + (message_count // 25)))
    traits = list(PERSONALITY_ARCHETYPES[best_name]["traits"])
    if secondary:
        traits.extend(PERSONALITY_ARCHETYPES[secondary[0]]["traits"][:2])

    # Preserve order while deduplicating.
    deduped_traits = []
    for trait in traits:
        if trait not in deduped_traits:
            deduped_traits.append(trait)

    return {
        "label": best_name,
        "confidence": confidence,
        "traits": deduped_traits[:6],
        "secondary": secondary,
        "evidence": evidence.get(best_name, []),
        "signal_count": len([line for line in str(signal_text or "").splitlines() if line.strip()]),
    }


def global_member_signal_text(conn, user_id):
    parts = []
    signal_queries = (
        ("relationships", "relationship_type || ' ' || COALESCE(nickname, '') || ' ' || COALESCE(opinion, '')", "ORDER BY updated_at ASC"),
        ("user_profiles", "summary", "AND summary IS NOT NULL AND summary != '' ORDER BY updated_at ASC"),
        ("user_memories", "memory", "ORDER BY guild_id ASC, confidence DESC, id ASC"),
        ("running_jokes", "joke", "ORDER BY guild_id ASC, id ASC"),
        ("relationship_events", "event", "ORDER BY guild_id ASC, importance DESC, id ASC"),
        ("achievements", "achievement || ' ' || COALESCE(description, '')", "ORDER BY guild_id ASC, id ASC"),
        ("messages", "content", "AND content IS NOT NULL AND content != '' ORDER BY id ASC"),
    )
    for table, column, order in signal_queries:
        if not table_exists(conn, table):
            continue
        for row in conn.execute(
            f"SELECT {column} AS text FROM {table} WHERE user_id=? {order}",
            (user_id,),
        ):
            if row["text"]:
                parts.append(str(row["text"]))
    return "\n".join(parts)


def global_member_profile(conn, user_id):
    def count(table):
        if not table_exists(conn, table):
            return 0
        return scalar(conn, f"SELECT COUNT(*) FROM {table} WHERE user_id=?", (user_id,))

    guild_ids = set()
    for table in ("messages", "relationships", "user_profiles", "user_memories", "running_jokes", "achievements"):
        if not table_exists(conn, table):
            continue
        for row in conn.execute(f"SELECT DISTINCT guild_id FROM {table} WHERE user_id=?", (user_id,)):
            if row[0] is not None:
                guild_ids.add(row[0])

    usernames = []
    for table in ("messages", "relationships", "user_profiles"):
        if not table_exists(conn, table):
            continue
        for row in conn.execute(f"SELECT DISTINCT username FROM {table} WHERE user_id=? AND username IS NOT NULL AND username != '' LIMIT 10", (user_id,)):
            if row[0] and row[0] not in usernames:
                usernames.append(row[0])

    base = {
        "user_id": user_id,
        "guild_count": len(guild_ids),
        "guild_ids": sorted(guild_ids),
        "usernames": usernames[:5],
        "message_count": count("messages"),
        "memory_count": count("user_memories"),
        "joke_count": count("running_jokes"),
        "achievement_count": count("achievements"),
        "work_runs": scalar(conn, "SELECT COALESCE(SUM(total_runs), 0) FROM crew_work_stats WHERE user_id=?", (user_id,)) if table_exists(conn, "crew_work_stats") else 0,
        "ship_contributed": scalar(conn, "SELECT COALESCE(SUM(amount), 0) FROM ship_contributions WHERE user_id=?", (user_id,)) if table_exists(conn, "ship_contributions") else 0,
    }
    base["messages_analyzed"] = base["message_count"]
    signal_text = global_member_signal_text(conn, user_id)
    return {
        "base": base,
        "personality_type": infer_personality_type(signal_text, base),
    }


def attach_personality_types(conn, guild_id, members):
    for member in members:
        user_id = safe_int(member.get("user_id"))
        signal_text = collect_member_signal_text(conn, guild_id, user_id, member)
        member["personality_type"] = infer_personality_type(signal_text, member)
    return members


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


ID_FIELDS = {
    "guild_id",
    "user_id",
    "channel_id",
    "welcome_channel_id",
    "chronicle_channel_id",
    "captured_by",
    "discovered_by",
}


def json_safe_ids(value):
    if isinstance(value, list):
        return [json_safe_ids(item) for item in value]
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            if key in ID_FIELDS and item is not None:
                safe[key] = str(item)
            else:
                safe[key] = json_safe_ids(item)
        return safe
    return value


def guild_ids(conn):
    ids = set()
    for table in (
        "guild_settings",
        "ships",
        "relationships",
        "user_profiles",
        "economy",
        "ship_history",
        "world_discoveries",
        "history_imports",
    ):
        if table_exists(conn, table):
            for row in conn.execute(f"SELECT DISTINCT guild_id FROM {table}"):
                ids.add(row[0])
    return sorted(ids)


def import_rows(conn, guild_id=None, limit=LIST_LIMIT):
    if not table_exists(conn, "history_imports"):
        return []
    if guild_id is None:
        return rows(
            conn,
            """
            SELECT guild_id, channel_id, status, last_message_id, imported_count, scanned_count, started_at, updated_at, stopped_at
            FROM history_imports
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        )
    return rows(
        conn,
        """
        SELECT guild_id, channel_id, status, last_message_id, imported_count, scanned_count, started_at, updated_at, stopped_at
        FROM history_imports
        WHERE guild_id=?
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (guild_id, limit),
    )


def import_summary(conn, guild_id=None):
    imports = import_rows(conn, guild_id=guild_id, limit=10000)
    by_status = {}
    for item in imports:
        status = item.get("status") or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "channels": len(imports),
        "imported": sum(safe_int(item.get("imported_count")) for item in imports),
        "scanned": sum(safe_int(item.get("scanned_count")) for item in imports),
        "by_status": by_status,
        "running": by_status.get("running", 0) + by_status.get("stopping", 0),
        "complete": by_status.get("complete", 0),
        "paused": by_status.get("paused", 0),
        "failed": by_status.get("failed", 0),
    }


def dashboard_counts(conn, guild_id):
    def count(table, where="guild_id=?"):
        if not table_exists(conn, table):
            return 0
        return scalar(conn, f"SELECT COUNT(*) FROM {table} WHERE {where}", (guild_id,))

    return {
        "members": len(member_rows(conn, guild_id, limit=10000)),
        "profiles": count("user_profiles"),
        "memories": count("user_memories"),
        "running_jokes": count("running_jokes"),
        "relationship_events": count("relationship_events"),
        "achievements": count("achievements"),
        "ship_history": count("ship_history"),
        "voyages": count("ship_voyages"),
        "discoveries": count("world_discoveries"),
        "world_history": count("world_history"),
        "crew_work_runs": count("crew_work_runs"),
        "messages": count("messages"),
        "captured_ships": count("captured_ships"),
        "history_import_channels": import_summary(conn, guild_id).get("channels", 0),
        "history_imported": import_summary(conn, guild_id).get("imported", 0),
    }


def member_rows(conn, guild_id, limit=LIST_LIMIT):
    if not table_exists(conn, "relationships") and not table_exists(conn, "user_profiles"):
        return []

    sql = """
        SELECT
            COALESCE(r.guild_id, p.guild_id, e.guild_id) AS guild_id,
            COALESCE(r.user_id, p.user_id, e.user_id) AS user_id,
            COALESCE(r.username, p.username, sc.username, e.user_id) AS username,
            COALESCE(r.relationship_type, 'New Crewmate') AS relationship_type,
            COALESCE(r.familiarity, 0) AS familiarity,
            COALESCE(r.nickname, '') AS nickname,
            COALESCE(r.opinion, '') AS opinion,
            COALESCE(p.summary, '') AS summary,
            COALESCE(p.gender, '') AS gender,
            COALESCE(p.pronouns, '') AS pronouns,
            COALESCE(e.doubloons, 0) AS doubloons,
            COALESCE(sc.amount, 0) AS ship_contributed,
            COALESCE(a.achievement_count, 0) AS achievement_count,
            COALESCE(m.memory_count, 0) AS memory_count,
            COALESCE(j.joke_count, 0) AS joke_count,
            COALESCE(cw.total_runs, 0) AS work_runs,
            COALESCE(cw.payout_total, 0) AS work_payout,
            COALESCE(cw.repair_hull_total, 0) AS repair_hull_total,
            COALESCE(msg.message_count, 0) AS message_count,
            COALESCE(gseen.guild_count, 0) AS global_guild_count
        FROM relationships r
        FULL OUTER JOIN user_profiles p
            ON p.guild_id = r.guild_id AND p.user_id = r.user_id
        LEFT JOIN economy e
            ON e.guild_id = COALESCE(r.guild_id, p.guild_id)
            AND e.user_id = COALESCE(r.user_id, p.user_id)
        LEFT JOIN ship_contributions sc
            ON sc.guild_id = COALESCE(r.guild_id, p.guild_id)
            AND sc.user_id = COALESCE(r.user_id, p.user_id)
        LEFT JOIN (
            SELECT guild_id, user_id, COUNT(*) AS achievement_count
            FROM achievements
            GROUP BY guild_id, user_id
        ) a ON a.guild_id = COALESCE(r.guild_id, p.guild_id)
           AND a.user_id = COALESCE(r.user_id, p.user_id)
        LEFT JOIN (
            SELECT guild_id, user_id, COUNT(*) AS memory_count
            FROM user_memories
            GROUP BY guild_id, user_id
        ) m ON m.guild_id = COALESCE(r.guild_id, p.guild_id)
           AND m.user_id = COALESCE(r.user_id, p.user_id)
        LEFT JOIN (
            SELECT guild_id, user_id, COUNT(*) AS joke_count
            FROM running_jokes
            GROUP BY guild_id, user_id
        ) j ON j.guild_id = COALESCE(r.guild_id, p.guild_id)
           AND j.user_id = COALESCE(r.user_id, p.user_id)
        LEFT JOIN (
            SELECT guild_id, user_id,
                   SUM(total_runs) AS total_runs,
                   SUM(payout_total) AS payout_total,
                   SUM(repair_hull_total) AS repair_hull_total
            FROM crew_work_stats
            GROUP BY guild_id, user_id
        ) cw ON cw.guild_id = COALESCE(r.guild_id, p.guild_id)
            AND cw.user_id = COALESCE(r.user_id, p.user_id)
        LEFT JOIN (
            SELECT guild_id, user_id, COUNT(*) AS message_count
            FROM messages
            GROUP BY guild_id, user_id
        ) msg ON msg.guild_id = COALESCE(r.guild_id, p.guild_id)
            AND msg.user_id = COALESCE(r.user_id, p.user_id)
        LEFT JOIN (
            SELECT user_id, COUNT(DISTINCT guild_id) AS guild_count
            FROM messages
            GROUP BY user_id
        ) gseen ON gseen.user_id = COALESCE(r.user_id, p.user_id)
        WHERE COALESCE(r.guild_id, p.guild_id, e.guild_id) = ?
        ORDER BY familiarity DESC, doubloons DESC, username COLLATE NOCASE
        LIMIT ?
    """

    try:
        data = rows(conn, sql, (guild_id, limit))
    except sqlite3.OperationalError:
        # Older SQLite versions may not support FULL OUTER JOIN.
        data = rows(
            conn,
            """
            SELECT
                r.guild_id,
                r.user_id,
                r.username,
                r.relationship_type,
                r.familiarity,
                r.nickname,
                r.opinion,
                COALESCE(p.summary, '') AS summary,
                COALESCE(p.gender, '') AS gender,
                COALESCE(p.pronouns, '') AS pronouns,
                COALESCE(e.doubloons, 0) AS doubloons,
                COALESCE(sc.amount, 0) AS ship_contributed,
                COALESCE(a.achievement_count, 0) AS achievement_count,
                COALESCE(m.memory_count, 0) AS memory_count,
                COALESCE(j.joke_count, 0) AS joke_count,
                COALESCE(cw.total_runs, 0) AS work_runs,
                COALESCE(cw.payout_total, 0) AS work_payout,
                COALESCE(cw.repair_hull_total, 0) AS repair_hull_total,
                COALESCE(msg.message_count, 0) AS message_count,
                COALESCE(gseen.guild_count, 0) AS global_guild_count
            FROM relationships r
            LEFT JOIN user_profiles p ON p.guild_id = r.guild_id AND p.user_id = r.user_id
            LEFT JOIN economy e ON e.guild_id = r.guild_id AND e.user_id = r.user_id
            LEFT JOIN ship_contributions sc ON sc.guild_id = r.guild_id AND sc.user_id = r.user_id
            LEFT JOIN (
                SELECT guild_id, user_id, COUNT(*) AS achievement_count
                FROM achievements GROUP BY guild_id, user_id
            ) a ON a.guild_id = r.guild_id AND a.user_id = r.user_id
            LEFT JOIN (
                SELECT guild_id, user_id, COUNT(*) AS memory_count
                FROM user_memories GROUP BY guild_id, user_id
            ) m ON m.guild_id = r.guild_id AND m.user_id = r.user_id
            LEFT JOIN (
                SELECT guild_id, user_id, COUNT(*) AS joke_count
                FROM running_jokes GROUP BY guild_id, user_id
            ) j ON j.guild_id = r.guild_id AND j.user_id = r.user_id
            LEFT JOIN (
                SELECT guild_id, user_id,
                       SUM(total_runs) AS total_runs,
                       SUM(payout_total) AS payout_total,
                       SUM(repair_hull_total) AS repair_hull_total
                FROM crew_work_stats GROUP BY guild_id, user_id
            ) cw ON cw.guild_id = r.guild_id AND cw.user_id = r.user_id
            LEFT JOIN (
                SELECT guild_id, user_id, COUNT(*) AS message_count
                FROM messages GROUP BY guild_id, user_id
            ) msg ON msg.guild_id = r.guild_id AND msg.user_id = r.user_id
            LEFT JOIN (
                SELECT user_id, COUNT(DISTINCT guild_id) AS guild_count
                FROM messages GROUP BY user_id
            ) gseen ON gseen.user_id = r.user_id
            WHERE r.guild_id = ?
            ORDER BY familiarity DESC, doubloons DESC, username COLLATE NOCASE
            LIMIT ?
            """,
            (guild_id, limit),
        )

    for item in data:
        for key in ("summary", "opinion", "nickname"):
            item[key] = clean_text(item.get(key), 220)
    return data


def is_dashboard_bot_user(conn, user_id):
    names = []
    for table in ("messages", "relationships", "user_profiles"):
        if not table_exists(conn, table):
            continue
        for row in conn.execute(f"SELECT DISTINCT username FROM {table} WHERE user_id=?", (user_id,)):
            if row[0]:
                names.append(str(row[0]).lower())
    return any(name in ("captain-cutlass", "captain cutlass") or name.startswith("captain-cutlass#") for name in names)


def global_user_ids(conn):
    ids = set()
    for table in ("messages", "relationships", "user_profiles", "user_memories", "running_jokes", "achievements", "economy", "crew_work_stats"):
        if not table_exists(conn, table):
            continue
        for row in conn.execute(f"SELECT DISTINCT user_id FROM {table} WHERE user_id IS NOT NULL"):
            ids.add(row[0])
    return sorted(user_id for user_id in ids if not is_dashboard_bot_user(conn, user_id))


def global_counts(conn):
    def count(table):
        if not table_exists(conn, table):
            return 0
        return scalar(conn, f"SELECT COUNT(*) FROM {table}")

    return {
        "global_users": len(global_user_ids(conn)),
        "servers": len(guild_ids(conn)),
        "messages": count("messages"),
        "profiles": count("user_profiles"),
        "memories": count("user_memories"),
        "running_jokes": count("running_jokes"),
        "relationship_events": count("relationship_events"),
        "achievements": count("achievements"),
        "crew_work_runs": count("crew_work_runs"),
        "history_import_channels": import_summary(conn).get("channels", 0),
        "history_imported": import_summary(conn).get("imported", 0),
    }


def global_user_rows(conn, limit=LIST_LIMIT):
    result = []
    for user_id in global_user_ids(conn)[: limit * 3]:
        profile = global_member_profile(conn, user_id)
        base = profile["base"]
        name = base.get("usernames", [str(user_id)])
        username = name[0] if name else str(user_id)
        result.append({
            "user_id": user_id,
            "username": username,
            "guild_count": base.get("guild_count", 0),
            "message_count": base.get("message_count", 0),
            "memory_count": base.get("memory_count", 0),
            "joke_count": base.get("joke_count", 0),
            "achievement_count": base.get("achievement_count", 0),
            "work_runs": base.get("work_runs", 0),
            "usernames": base.get("usernames", []),
            "guild_ids": base.get("guild_ids", []),
            "personality_type": profile.get("personality_type"),
        })
    result.sort(key=lambda item: (item["guild_count"], item["message_count"], item["memory_count"]), reverse=True)
    return result[:limit]


def global_member_payload(user_id):
    with db_connect() as conn:
        profile = global_member_profile(conn, user_id)
        base = profile["base"]
        local_profiles = []
        for guild_id in base.get("guild_ids", []):
            local_profiles.append({
                "guild_id": guild_id,
                "profile": one(conn, "SELECT username, summary, gender, pronouns, updated_at FROM user_profiles WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "user_profiles") else None,
                "relationship": one(conn, "SELECT username, nickname, relationship_type, familiarity, opinion, updated_at FROM relationships WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "relationships") else None,
                "economy": one(conn, "SELECT doubloons FROM economy WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "economy") else None,
                "message_count": scalar(conn, "SELECT COUNT(*) FROM messages WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "messages") else 0,
                "memory_count": scalar(conn, "SELECT COUNT(*) FROM user_memories WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "user_memories") else 0,
                "achievement_count": scalar(conn, "SELECT COUNT(*) FROM achievements WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "achievements") else 0,
            })
        return {
            "user_id": user_id,
            "global_profile": profile,
            "local_profiles": local_profiles,
            "recent_messages": rows(conn, "SELECT guild_id, username, content, timestamp FROM messages WHERE user_id=? ORDER BY id DESC LIMIT 50", (user_id,)) if table_exists(conn, "messages") else [],
            "memories": rows(conn, "SELECT guild_id, memory, confidence, created_at, updated_at FROM user_memories WHERE user_id=? ORDER BY id DESC LIMIT 80", (user_id,)) if table_exists(conn, "user_memories") else [],
            "running_jokes": rows(conn, "SELECT guild_id, joke, created_at FROM running_jokes WHERE user_id=? ORDER BY id DESC LIMIT 50", (user_id,)) if table_exists(conn, "running_jokes") else [],
            "achievements": rows(conn, "SELECT guild_id, achievement, description, awarded_at FROM achievements WHERE user_id=? ORDER BY id DESC LIMIT 80", (user_id,)) if table_exists(conn, "achievements") else [],
        }


DASHBOARD_GUILD_BOOLEAN_FIELDS = {
    "quiet": "quiet",
    "event_mode": "event_mode",
    "welcome_enabled": "welcome_enabled",
    "returning_enabled": "returning_enabled",
    "chronicle_enabled": "chronicle_enabled",
}

DASHBOARD_SHIP_BOOLEAN_FIELDS = {
    "ship_world_enabled": "enabled",
}


def dashboard_control_payload(guild_id, control, value):
    guild_id = safe_int(guild_id)
    if control in DASHBOARD_GUILD_BOOLEAN_FIELDS:
        field = DASHBOARD_GUILD_BOOLEAN_FIELDS[control]
        next_value = 1 if value else 0
        with db_write_connect() as conn:
            if not table_exists(conn, "guild_settings"):
                raise ValueError("guild_settings table is missing")
            conn.execute("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
            conn.execute(f"UPDATE guild_settings SET {field}=?, updated_at=CURRENT_TIMESTAMP WHERE guild_id=?", (next_value, guild_id))
            conn.commit()
        return {"ok": True, "control": control, "value": next_value}

    if control in DASHBOARD_SHIP_BOOLEAN_FIELDS:
        field = DASHBOARD_SHIP_BOOLEAN_FIELDS[control]
        next_value = 1 if value else 0
        with db_write_connect() as conn:
            if not table_exists(conn, "ship_settings"):
                raise ValueError("ship_settings table is missing")
            conn.execute("INSERT OR IGNORE INTO ship_settings (guild_id) VALUES (?)", (guild_id,))
            conn.execute(f"UPDATE ship_settings SET {field}=?, updated_at=CURRENT_TIMESTAMP WHERE guild_id=?", (next_value, guild_id))
            conn.commit()
        return {"ok": True, "control": control, "value": next_value}

    raise ValueError("Unknown dashboard control.")


def dashboard_set_ship_channel(guild_id, channel_id):
    guild_id = safe_int(guild_id)
    channel_id = safe_int(channel_id)
    if channel_id < 0:
        raise ValueError("Channel ID must be 0 or a positive Discord channel ID.")
    with db_write_connect() as conn:
        if not table_exists(conn, "ship_settings"):
            raise ValueError("ship_settings table is missing")
        conn.execute("INSERT OR IGNORE INTO ship_settings (guild_id) VALUES (?)", (guild_id,))
        conn.execute("UPDATE ship_settings SET channel_id=?, updated_at=CURRENT_TIMESTAMP WHERE guild_id=?", (channel_id, guild_id))
        conn.commit()
    return {"ok": True, "channel_id": channel_id}


def dashboard_set_chronicle_channel(guild_id, channel_id):
    guild_id = safe_int(guild_id)
    channel_id = safe_int(channel_id)
    if channel_id < 0:
        raise ValueError("Channel ID must be 0 or a positive Discord channel ID.")
    with db_write_connect() as conn:
        if not table_exists(conn, "guild_settings"):
            raise ValueError("guild_settings table is missing")
        conn.execute("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
        conn.execute("UPDATE guild_settings SET chronicle_channel_id=?, updated_at=CURRENT_TIMESTAMP WHERE guild_id=?", (channel_id, guild_id))
        conn.commit()
    return {"ok": True, "channel_id": channel_id}


def dashboard_set_welcome_channel(guild_id, channel_id):
    guild_id = safe_int(guild_id)
    channel_id = safe_int(channel_id)
    if channel_id < 0:
        raise ValueError("Channel ID must be 0 or a positive Discord channel ID.")
    with db_write_connect() as conn:
        if not table_exists(conn, "guild_settings"):
            raise ValueError("guild_settings table is missing")
        conn.execute("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
        conn.execute("UPDATE guild_settings SET welcome_channel_id=?, updated_at=CURRENT_TIMESTAMP WHERE guild_id=?", (channel_id, guild_id))
        conn.commit()
    return {"ok": True, "channel_id": channel_id}


def dashboard_set_mood(guild_id, mood):
    guild_id = safe_int(guild_id)
    mood = clean_text(str(mood or "").strip(), 60)
    if not mood:
        raise ValueError("Mood cannot be empty.")
    with db_write_connect() as conn:
        if not table_exists(conn, "guild_settings"):
            raise ValueError("guild_settings table is missing")
        conn.execute("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
        conn.execute("UPDATE guild_settings SET mood=?, updated_at=CURRENT_TIMESTAMP WHERE guild_id=?", (mood, guild_id))
        conn.commit()
    return {"ok": True, "mood": mood}


def global_payload():
    with db_connect() as conn:
        users = global_user_rows(conn)
        return {
            "counts": global_counts(conn),
            "users": users,
            "multi_server_users": [user for user in users if user.get("guild_count", 0) > 1],
            "history_imports": import_rows(conn, limit=200),
            "history_import_summary": import_summary(conn),
        }


def guild_summary(conn, guild_id):
    settings = one(conn, "SELECT * FROM guild_settings WHERE guild_id=?", (guild_id,)) if table_exists(conn, "guild_settings") else None
    ship = one(conn, "SELECT * FROM ships WHERE guild_id=?", (guild_id,)) if table_exists(conn, "ships") else None
    ship_settings = one(conn, "SELECT * FROM ship_settings WHERE guild_id=?", (guild_id,)) if table_exists(conn, "ship_settings") else None
    return {
        "guild_id": guild_id,
        "guild_name": (settings or {}).get("guild_name") or "Server " + str(guild_id),
        "settings": settings,
        "ship_settings": ship_settings,
        "ship": ship,
        "counts": dashboard_counts(conn, guild_id),
    }


def overview_payload(user=None):
    with db_connect() as conn:
        ids = guild_ids(conn)
        if user is not None:
            ids = [guild_id for guild_id in ids if dashboard_user_can_guild(user, guild_id)]
        guilds = [guild_summary(conn, guild_id) for guild_id in ids]
        guilds.sort(
            key=lambda item: (
                item["counts"].get("members", 0),
                item["counts"].get("profiles", 0),
                item["counts"].get("memories", 0),
                item["counts"].get("ship_history", 0),
                item["counts"].get("discoveries", 0),
            ),
            reverse=True,
        )
        return {
            "database": DB_PATH,
            "guilds": guilds,
            "can_view_global": dashboard_user_can_global(user) if user is not None else True,
        }


def dashboard_access_options_payload():
    with db_connect() as conn:
        return {"guilds": [guild_summary(conn, guild_id) for guild_id in guild_ids(conn)]}


def guild_payload(guild_id):
    with db_connect() as conn:
        payload = guild_summary(conn, guild_id)
        members = attach_personality_types(
            conn,
            guild_id,
            member_rows(conn, guild_id),
        )
        payload.update(
            {
                "members": members,
                "top_doubloons": rows(
                    conn,
                    """
                    SELECT e.user_id, COALESCE(r.username, p.username, e.user_id) AS username, e.doubloons
                    FROM economy e
                    LEFT JOIN relationships r ON r.guild_id=e.guild_id AND r.user_id=e.user_id
                    LEFT JOIN user_profiles p ON p.guild_id=e.guild_id AND p.user_id=e.user_id
                    WHERE e.guild_id=?
                    ORDER BY e.doubloons DESC
                    LIMIT 10
                    """,
                    (guild_id,),
                ) if table_exists(conn, "economy") else [],
                "top_contributors": rows(
                    conn,
                    """
                    SELECT user_id, username, amount
                    FROM ship_contributions
                    WHERE guild_id=?
                    ORDER BY amount DESC
                    LIMIT 10
                    """,
                    (guild_id,),
                ) if table_exists(conn, "ship_contributions") else [],
                "recent_history": rows(
                    conn,
                    """
                    SELECT event_type, content, created_at
                    FROM ship_history
                    WHERE guild_id=?
                    ORDER BY id DESC
                    LIMIT 15
                    """,
                    (guild_id,),
                ) if table_exists(conn, "ship_history") else [],
                "recent_world_history": rows(
                    conn,
                    """
                    SELECT event_type, content, importance, created_at
                    FROM world_history
                    WHERE guild_id=?
                    ORDER BY id DESC
                    LIMIT 15
                    """,
                    (guild_id,),
                ) if table_exists(conn, "world_history") else [],
                "voyages": rows(
                    conn,
                    """
                    SELECT destination, risk, status, result, started_at, completed_at
                    FROM ship_voyages
                    WHERE guild_id=?
                    ORDER BY id DESC
                    LIMIT 10
                    """,
                    (guild_id,),
                ) if table_exists(conn, "ship_voyages") else [],
                "discoveries": rows(
                    conn,
                    """
                    SELECT location_key, discovered_by_name, discovered_at, visits
                    FROM world_discoveries
                    WHERE guild_id=?
                    ORDER BY discovered_at DESC
                    LIMIT 100
                    """,
                    (guild_id,),
                ) if table_exists(conn, "world_discoveries") else [],
                "captured_ships": rows(
                    conn,
                    """
                    SELECT enemy_name, captured_by_name, reward, xp_reward, status, notes, created_at
                    FROM captured_ships
                    WHERE guild_id=?
                    ORDER BY id DESC
                    LIMIT 20
                    """,
                    (guild_id,),
                ) if table_exists(conn, "captured_ships") else [],
                "history_imports": import_rows(conn, guild_id=guild_id),
                "history_import_summary": import_summary(conn, guild_id),
                "crew_work": rows(
                    conn,
                    """
                    SELECT job_label,
                           SUM(total_runs) AS total_runs,
                           SUM(success_count) AS success_count,
                           SUM(failure_count) AS failure_count,
                           SUM(rare_count) AS rare_count,
                           SUM(payout_total) AS payout_total,
                           SUM(ship_bonus_total) AS ship_bonus_total,
                           SUM(repair_hull_total) AS repair_hull_total
                    FROM crew_work_stats
                    WHERE guild_id=?
                    GROUP BY job_label
                    ORDER BY total_runs DESC, job_label
                    LIMIT 20
                    """,
                    (guild_id,),
                ) if table_exists(conn, "crew_work_stats") else [],
            }
        )
        return payload


def member_payload(guild_id, user_id, include_global=True):
    with db_connect() as conn:
        profile = one(conn, "SELECT * FROM user_profiles WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "user_profiles") else None
        relationship = one(conn, "SELECT * FROM relationships WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "relationships") else None
        economy = one(conn, "SELECT * FROM economy WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "economy") else None
        contribution = one(conn, "SELECT * FROM ship_contributions WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "ship_contributions") else None
        base = {}
        if relationship:
            base.update(relationship)
        if profile:
            base.update(profile)
        if economy:
            base.update(economy)
        if contribution:
            base["ship_contributed"] = contribution.get("amount", 0)

        base.update({
            "memory_count": scalar(conn, "SELECT COUNT(*) FROM user_memories WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "user_memories") else 0,
            "joke_count": scalar(conn, "SELECT COUNT(*) FROM running_jokes WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "running_jokes") else 0,
            "achievement_count": scalar(conn, "SELECT COUNT(*) FROM achievements WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "achievements") else 0,
            "work_runs": scalar(conn, "SELECT COALESCE(SUM(total_runs), 0) FROM crew_work_stats WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "crew_work_stats") else 0,
            "message_count": scalar(conn, "SELECT COUNT(*) FROM messages WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "messages") else 0,
        })
        personality_type = infer_personality_type(
            collect_member_signal_text(conn, guild_id, user_id, base),
            base,
        )
        global_profile = global_member_profile(conn, user_id) if include_global else None

        return {
            "guild_id": guild_id,
            "user_id": user_id,
            "personality_type": personality_type,
            "global_profile": global_profile,
            "profile": profile,
            "relationship": relationship,
            "economy": economy,
            "ship_contribution": contribution,
            "memories": rows(conn, "SELECT memory, confidence, created_at, updated_at FROM user_memories WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 50", (guild_id, user_id)) if table_exists(conn, "user_memories") else [],
            "running_jokes": rows(conn, "SELECT joke, created_at FROM running_jokes WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 30", (guild_id, user_id)) if table_exists(conn, "running_jokes") else [],
            "relationship_events": rows(conn, "SELECT event, importance, created_at FROM relationship_events WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 40", (guild_id, user_id)) if table_exists(conn, "relationship_events") else [],
            "achievements": rows(conn, "SELECT achievement, description, awarded_at FROM achievements WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 50", (guild_id, user_id)) if table_exists(conn, "achievements") else [],
            "crew_work": rows(conn, "SELECT * FROM crew_work_stats WHERE guild_id=? AND user_id=? ORDER BY total_runs DESC, job_label LIMIT 50", (guild_id, user_id)) if table_exists(conn, "crew_work_stats") else [],
            "recent_work_runs": rows(conn, "SELECT job_label, result_type, payout, ship_bonus_type, ship_bonus_value, repair_hull, details, created_at FROM crew_work_runs WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 30", (guild_id, user_id)) if table_exists(conn, "crew_work_runs") else [],
            "recent_messages": rows(conn, "SELECT content, timestamp FROM messages WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 30", (guild_id, user_id)) if table_exists(conn, "messages") else [],
        }


INDEX_HTML = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Captain Cutlass Quarterdeck</title>
  <style>
    :root { color-scheme: dark; --bg:#020506; --void:#000; --panel:#071114; --panel2:#0c1b20; --steel:#1c2529; --steel2:#2d3437; --text:#f4f7f4; --muted:#8eb6bd; --cyan:#10e7ef; --cyan2:#00a6b8; --gold:#d7a23a; --gold2:#8f6420; --red:#9d2f2f; --green:#65e49a; --line:rgba(16,231,239,.42); --dimline:rgba(16,231,239,.18); }
    * { box-sizing: border-box; }
    body { margin:0; font-family: 'Trebuchet MS', Inter, ui-sans-serif, system-ui, sans-serif; color:var(--text); background:
      radial-gradient(circle at 22% 12%, rgba(16,231,239,.18), transparent 30%),
      radial-gradient(circle at 86% 6%, rgba(215,162,58,.12), transparent 24%),
      linear-gradient(90deg, rgba(16,231,239,.05) 1px, transparent 1px) 0 0/48px 48px,
      linear-gradient(0deg, rgba(16,231,239,.035) 1px, transparent 1px) 0 0/48px 48px,
      linear-gradient(180deg, #061014 0%, var(--bg) 58%, #000 100%); }
    body::before { content:''; position:fixed; inset:0; pointer-events:none; background:radial-gradient(ellipse at center, transparent 38%, rgba(0,0,0,.68) 100%), linear-gradient(180deg, rgba(16,231,239,.04), transparent 18%, rgba(0,0,0,.4)); z-index:-1; }
    header { min-height:300px; padding:26px clamp(16px,4vw,52px); border-bottom:1px solid var(--line); background:
      linear-gradient(90deg, rgba(0,0,0,.32), rgba(0,0,0,.05) 38%, rgba(0,0,0,.76) 78%),
      linear-gradient(180deg, rgba(0,0,0,.08), rgba(0,0,0,.82)),
      url('/assets/banner.png') center/cover no-repeat; position:relative; overflow:hidden; box-shadow:0 18px 58px rgba(0,0,0,.62), inset 0 -1px rgba(16,231,239,.35); }
    header::before { content:''; position:absolute; inset:0; pointer-events:none; background:linear-gradient(90deg, transparent, rgba(16,231,239,.16), transparent) top/100% 1px no-repeat, linear-gradient(90deg, transparent, rgba(16,231,239,.11), transparent) bottom/100% 1px no-repeat; }
    header::after { content:'SYSTEM ONLINE   •   CREW: DASHBOARD   •   STATUS: UNSTOPPABLE'; position:absolute; right:clamp(16px,4vw,52px); top:22px; color:var(--cyan); font:700 12px/1.4 'Courier New', monospace; letter-spacing:.08em; text-shadow:0 0 10px rgba(16,231,239,.8); opacity:.88; }
    .brand { position:relative; min-height:240px; display:flex; align-items:flex-end; gap:18px; max-width:900px; }
    .brand-mark { width:120px; height:120px; border-radius:50%; object-fit:cover; border:2px solid var(--cyan); background:#000; box-shadow:0 0 0 4px rgba(0,0,0,.55), 0 0 34px rgba(16,231,239,.72); }
    .brand-copy { padding:18px 20px; border:1px solid var(--line); background:linear-gradient(90deg, rgba(0,0,0,.72), rgba(4,16,20,.42)); box-shadow:inset 0 0 0 1px rgba(215,162,58,.14), 0 10px 34px rgba(0,0,0,.42); clip-path:polygon(0 0, calc(100% - 18px) 0, 100% 18px, 100% 100%, 18px 100%, 0 calc(100% - 18px)); }
    .hero-kicker { display:flex; align-items:center; gap:10px; color:var(--gold); font:800 13px/1 'Courier New', monospace; letter-spacing:.22em; text-transform:uppercase; margin-bottom:8px; text-shadow:0 0 12px rgba(215,162,58,.45); }
    .hero-kicker::before, .hero-kicker::after { content:''; width:42px; height:2px; background:linear-gradient(90deg, transparent, var(--cyan)); box-shadow:0 0 10px rgba(16,231,239,.75); }
    .hero-kicker::after { background:linear-gradient(90deg, var(--cyan), transparent); }
    .hero-title { margin:0; display:grid; gap:0; line-height:.86; text-transform:uppercase; }
    .hero-title .captain { color:#f6f2e8; font-size:clamp(34px,4.8vw,64px); letter-spacing:.08em; font-weight:900; text-shadow:0 3px 0 #000, 0 0 20px rgba(255,255,255,.28); }
    .hero-title .cutlass { color:var(--cyan); font-size:clamp(48px,7.6vw,104px); letter-spacing:.025em; font-weight:1000; font-style:italic; transform:skewX(-9deg); text-shadow:0 4px 0 #001417, 0 0 18px rgba(16,231,239,.95), 0 0 42px rgba(16,231,239,.45); }
    .hero-motto { margin-top:12px; display:inline-flex; align-items:center; gap:10px; color:#f6f2e8; font:800 15px/1.2 'Courier New', monospace; letter-spacing:.12em; text-transform:uppercase; text-shadow:0 0 14px rgba(16,231,239,.3); }
    .hero-motto::before, .hero-motto::after { content:''; width:32px; height:3px; background:var(--cyan); box-shadow:0 0 12px rgba(16,231,239,.8); }
    .hero-desc { max-width:760px; margin:12px 0 0; color:#c8e8ed; font-size:16px; line-height:1.45; letter-spacing:.035em; text-shadow:0 1px 0 #000; }
    .hero-chips { display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }
    .hero-chip { border:1px solid rgba(16,231,239,.36); background:rgba(0,0,0,.32); color:#9ff8ff; padding:6px 10px; border-radius:4px; font:800 12px/1 'Courier New', monospace; letter-spacing:.08em; text-transform:uppercase; box-shadow:inset 0 0 12px rgba(16,231,239,.06); }
    h1 { margin:0; font-size: clamp(34px, 5vw, 66px); letter-spacing:.045em; color:#f6f2e8; text-transform:uppercase; text-shadow:0 3px 0 #000, 0 0 22px rgba(16,231,239,.55); }
    h1::before, h1::after { content:''; }
    h2 { margin:0 0 14px; font-size:21px; color:#f6f2e8; text-shadow:0 1px 0 #000, 0 0 12px rgba(16,231,239,.3); text-transform:uppercase; letter-spacing:.03em; }
    h3 { margin:0 0 8px; font-size:16px; color:var(--cyan); letter-spacing:.08em; text-transform:uppercase; text-shadow:0 0 10px rgba(16,231,239,.55); }
    .sub { color:#c8e8ed; margin-top:8px; letter-spacing:.03em; text-shadow:0 1px 0 #000; }
    main { padding:24px clamp(16px,4vw,48px) 60px; display:grid; gap:20px; }
    .toolbar { display:flex; gap:12px; flex-wrap:wrap; align-items:center; }
    select, input, button { background:linear-gradient(180deg, #0b191d, #030708); color:var(--text); border:1px solid var(--line); border-radius:4px; padding:10px 12px; font:inherit; box-shadow:inset 0 1px rgba(255,255,255,.06), 0 0 16px rgba(16,231,239,.08); }
    input::placeholder { color:#638990; }
    button { cursor:pointer; background:linear-gradient(180deg, rgba(16,231,239,.22), rgba(0,107,120,.22)), #071114; color:#dffcff; border-color:rgba(16,231,239,.72); font-weight:800; text-transform:uppercase; letter-spacing:.06em; text-shadow:0 0 8px rgba(16,231,239,.7); }
    button:hover { border-color:var(--gold); color:#fff6d8; box-shadow:0 0 0 2px rgba(16,231,239,.18), 0 0 24px rgba(16,231,239,.24); transform:translateY(-1px); }
    .grid { display:grid; grid-template-columns: repeat(12, 1fr); gap:16px; }
    .card { background:linear-gradient(180deg, rgba(8,20,24,.96), rgba(2,6,8,.98)); border:1px solid var(--line); border-radius:10px; padding:18px; box-shadow:0 14px 42px rgba(0,0,0,.48), inset 0 0 0 1px rgba(215,162,58,.1); position:relative; overflow:hidden; }
    .card::before { content:''; position:absolute; inset:0; pointer-events:none; background:linear-gradient(90deg, transparent, rgba(16,231,239,.045), transparent), radial-gradient(circle at top right, rgba(16,231,239,.12), transparent 34%); }
    .card::after { content:''; position:absolute; left:12px; right:12px; top:0; height:1px; background:linear-gradient(90deg, transparent, var(--cyan), transparent); opacity:.72; }
    .card > * { position:relative; }
    .span-12 { grid-column: span 12; } .span-8 { grid-column: span 8; } .span-6 { grid-column: span 6; } .span-4 { grid-column: span 4; } .span-3 { grid-column: span 3; }
    .stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:10px; }
    .stat { background:linear-gradient(180deg, rgba(16,231,239,.09), rgba(0,0,0,.18)); border:1px solid var(--dimline); border-radius:8px; padding:12px; }
    .stat b { display:block; font-size:25px; color:var(--cyan); text-shadow:0 0 12px rgba(16,231,239,.65); }
    .stat span { color:var(--muted); font-size:13px; text-transform:uppercase; letter-spacing:.05em; }
    table { width:100%; border-collapse:collapse; }
    th,td { padding:10px 8px; border-bottom:1px solid rgba(16,231,239,.12); text-align:left; vertical-align:top; }
    th { color:var(--cyan); font-size:12px; text-transform:uppercase; letter-spacing:.1em; }
    tr.clickable { cursor:pointer; }
    tr.clickable:hover { background:rgba(16,231,239,.08); }
    .pill { display:inline-block; border:1px solid rgba(16,231,239,.28); background:rgba(0,0,0,.24); border-radius:4px; padding:3px 9px; color:#9ff8ff; font-size:12px; margin:2px; }
    .access-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:8px; width:100%; margin-top:8px; }
    .access-grid label, .access-toggle { display:flex; align-items:center; gap:8px; padding:8px 10px; border:1px solid var(--dimline); background:rgba(0,0,0,.18); border-radius:6px; color:var(--muted); margin:0; }
    .access-grid input, .access-toggle input { width:auto; box-shadow:none; }
    .bar { height:10px; background:#071114; border:1px solid rgba(16,231,239,.25); border-radius:999px; overflow:hidden; }
    .bar > i { display:block; height:100%; background:linear-gradient(90deg,var(--cyan2),var(--cyan),var(--gold)); box-shadow:0 0 14px rgba(16,231,239,.5); }
    .muted { color:var(--muted); } .gold { color:var(--gold); } .green { color:var(--green); } .red { color:var(--red); }
    .list { display:grid; gap:8px; max-height:440px; overflow:auto; padding-right:4px; }
    .profile-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:14px; }
    .profile-card { padding:14px; background:linear-gradient(180deg, rgba(16,231,239,.07), rgba(0,0,0,.18)); border:1px solid var(--dimline); border-radius:10px; cursor:pointer; min-height:190px; display:flex; flex-direction:column; gap:10px; }
    .profile-card:hover { border-color:var(--cyan); background:rgba(16,231,239,.1); transform:translateY(-1px); box-shadow:0 0 22px rgba(16,231,239,.14); }
    .profile-head { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }
    .profile-card p { margin:0; color:#d8edef; line-height:1.45; }
    .personality-type { padding:11px; border:1px solid rgba(215,162,58,.38); background:linear-gradient(180deg, rgba(215,162,58,.12), rgba(0,0,0,.14)); border-radius:8px; display:grid; gap:6px; }
    .personality-type strong { color:var(--gold); font-size:15px; }
    .personality-type > span { color:var(--muted); font-size:12px; }
    .item { padding:10px 12px; background:rgba(0,0,0,.22); border:1px solid rgba(16,231,239,.16); border-radius:8px; }
    .item small { color:var(--muted); display:block; margin-top:4px; }
    dialog { width:min(980px, calc(100vw - 28px)); border:1px solid var(--line); border-radius:10px; background:#030708; color:var(--text); padding:0; box-shadow:0 20px 70px rgba(0,0,0,.68), 0 0 34px rgba(16,231,239,.16); }
    dialog::backdrop { background:rgba(0,0,0,.72); backdrop-filter: blur(4px); }
    .modal-head { display:flex; justify-content:space-between; gap:12px; align-items:center; padding:18px; border-bottom:1px solid var(--line); background:linear-gradient(180deg, #0b191d, #030708); }
    .modal-body { padding:18px; max-height:75vh; overflow:auto; }
    pre { white-space:pre-wrap; background:rgba(0,0,0,.32); border:1px solid rgba(16,231,239,.18); padding:12px; border-radius:8px; color:#dffcff; }
    ::selection { background:rgba(16,231,239,.35); }
    @media (max-width: 900px) { header { min-height:230px; } .brand { min-height:170px; align-items:flex-end; } .brand-mark { width:86px; height:86px; } .hero-title .cutlass { font-size:clamp(42px,14vw,72px); } .hero-motto { font-size:12px; } .hero-desc { font-size:14px; } .span-8,.span-6,.span-4,.span-3 { grid-column:span 12; } }
  </style>
</head>
<body>
<header>
  <div class="brand">
    <img class="brand-mark" src="/assets/cutlass.png" alt="Captain Cutlass crest">
    <div class="brand-copy">
      <div class="hero-kicker">Quarterdeck Control</div>
      <div class="hero-title" aria-label="Captain Cutlass">
        <span class="captain">Captain</span>
        <span class="cutlass">Cutlass</span>
      </div>
      <div class="hero-motto">Pirate. Protector. Programmed to Plunder.</div>
      <p class="hero-desc">Command center for crew profiles, Living Ship telemetry, world history, jobs, achievements, and every scrap of trouble the fleet has logged.</p>
      <div class="hero-chips">
        <span class="hero-chip">System Online</span>
        <span class="hero-chip">Fleet Protected</span>
        <span class="hero-chip">Chaos Ready</span>
      </div>
    </div>
  </div>
</header>
<main>
  <section class="toolbar card">
    <label>Server <select id="guildSelect"></select></label>
    <input id="memberSearch" placeholder="Filter crew by name, relationship, summary…" size="42">
    <button id="refreshBtn">Refresh Charts</button>
    <button id="adminBtn" type="button" style="display:none">Crew Access</button>
    <button type="button" onclick="window.location.href='/logout'">Leave Port</button>
    <span id="status" class="muted"></span>
  </section>
  <section id="content" class="grid"></section>
</main>
<dialog id="memberDialog"><div class="modal-head"><h2 id="memberTitle"></h2><button onclick="memberDialog.close()">Close</button></div><div id="memberBody" class="modal-body"></div></dialog>
<dialog id="adminDialog"><div class="modal-head"><h2>Quarterdeck Access</h2><button onclick="adminDialog.close()">Close</button></div><div id="adminBody" class="modal-body"></div></dialog>
<script>
const $ = id => document.getElementById(id);
let overview = null;
let guild = null;
let globalData = null;
let selectedGuild = null;
let currentView = 'server';
const dashboardToken = new URLSearchParams(window.location.search).get('token') || localStorage.getItem('cutlassDashboardToken') || '';
if (dashboardToken) localStorage.setItem('cutlassDashboardToken', dashboardToken);

function esc(value) { return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
function num(value) { return Number(value || 0).toLocaleString(); }
function pct(value, max=100) { const n = Math.max(0, Math.min(100, Number(value || 0) / max * 100)); return n.toFixed(0); }
function withToken(path) {
  if (!dashboardToken) return path;
  const url = new URL(path, window.location.origin);
  url.searchParams.set('token', dashboardToken);
  return url.pathname + url.search;
}
async function api(path, options={}) { const res = await fetch(withToken(path), options); if (!res.ok) throw new Error(await res.text()); return await res.json(); }
async function apiJson(path, payload, method='POST') { return await api(path, { method, headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload || {}) }); }
function card(title, body, cls='span-12') { return `<div class="card ${cls}"><h2>${esc(title)}</h2>${body}</div>`; }
function stat(label, value) { return `<div class="stat"><b>${esc(value)}</b><span>${esc(label)}</span></div>`; }
function item(text, meta='') { return `<div class="item">${esc(text)}${meta ? `<small>${esc(meta)}</small>` : ''}</div>`; }

async function loadOverview() {
  $('status').textContent = 'Loading…';
  const session = await api('/api/session');
  if (session.user && session.user.role === 'admin') $('adminBtn').style.display = '';
  overview = await api('/api/overview');
  const select = $('guildSelect');
  const globalOption = overview.can_view_global ? `<option value="__global__">Global Info — all servers and matched users</option>` : '';
  const serverOptions = overview.guilds.map(g => {
    const counts = g.counts || {};
    const shipName = (g.ship && g.ship.name) || 'No ship';
    const guildName = g.guild_name || `Server ${g.guild_id}`;
    return `<option value="${g.guild_id}">${esc(guildName)} — ${esc(shipName)} — ${counts.members || 0} crew / ${counts.memories || 0} memories</option>`;
  }).join('');
  select.innerHTML = globalOption + serverOptions;
  selectedGuild = select.value || (overview.can_view_global ? '__global__' : ((overview.guilds[0] || {}).guild_id || ''));
  if (!selectedGuild) {
    $('content').innerHTML = card('No Access Assigned', '<p class="muted">This dashboard account does not have access to global info or any servers yet. Ask an admin to update Crew Access.</p>');
    return;
  }
  await loadSelected(selectedGuild);
  $('status').textContent = 'Ready';
}

async function loadSelected(value) {
  if (value === '__global__') return await loadGlobal();
  return await loadGuild(value);
}

async function loadGlobal() {
  currentView = 'global';
  selectedGuild = '__global__';
  $('status').textContent = 'Loading global info…';
  globalData = await api('/api/global');
  renderGlobal();
  $('status').textContent = 'Loaded global info';
}

async function loadGuild(guildId) {
  currentView = 'server';
  selectedGuild = guildId;
  $('status').textContent = 'Loading server…';
  guild = await api(`/api/guild/${guildId}`);
  renderGuild();
  $('status').textContent = `Loaded ${guild.guild_name || guildId}`;
}

function renderGlobal() {
  const counts = globalData.counts || {};
  const users = filterGlobalUsers(globalData.users || []);
  $('content').innerHTML = `
    ${card('Global Overview', `
      <div class="stats">
        ${stat('Global Users', counts.global_users || 0)}${stat('Servers', counts.servers || 0)}${stat('Messages', counts.messages || 0)}${stat('Imported', counts.history_imported || 0)}${stat('Import Channels', counts.history_import_channels || 0)}${stat('Profiles', counts.profiles || 0)}${stat('Memories', counts.memories || 0)}${stat('Jokes', counts.running_jokes || 0)}${stat('Achievements', counts.achievements || 0)}${stat('Crew Work Runs', counts.crew_work_runs || 0)}
      </div>
      <p class="muted">Global profiles are matched by Discord user_id. Server-specific relationships, permissions, economy, and gameplay stay separate.</p>
    `, 'span-12')}
    ${card('History Import Status', importStatusPanel(globalData.history_import_summary, globalData.history_imports, true), 'span-12')}
    ${card('Multi-Server Users', globalUserCards(globalData.multi_server_users || []), 'span-12')}
    ${card('Global Crew Profiles', globalUserTable(users), 'span-12')}
  `;
}

function filterGlobalUsers(users) {
  const q = $('memberSearch').value.trim().toLowerCase();
  if (!q) return users;
  return users.filter(u => JSON.stringify(u).toLowerCase().includes(q));
}

function globalUserCards(users) {
  if (!users.length) return '<p class="muted">No cross-server matches yet.</p>';
  return `<div class="profile-grid">${users.map(u => `
    <article class="profile-card" onclick="openGlobalMember('${u.user_id}')">
      <div class="profile-head">
        <div><h3>${esc(u.username || u.user_id)}</h3><span class="muted">${esc(u.user_id)}</span></div>
        <strong class="gold">${num(u.guild_count)} servers</strong>
      </div>
      ${personalityBadge(u.personality_type)}
      <div>
        <span class="pill">${num(u.message_count)} messages</span>
        <span class="pill">${num(u.memory_count)} memories</span>
        <span class="pill">${num(u.joke_count)} jokes</span>
        <span class="pill">${num(u.achievement_count)} achievements</span>
      </div>
    </article>`).join('')}</div>`;
}

function globalUserTable(users) {
  if (!users.length) return '<p class="muted">No global users found.</p>';
  return `<table><thead><tr><th>User</th><th>Global Type</th><th>Servers</th><th>Signals</th></tr></thead><tbody>${users.map(u => `
    <tr class="clickable" onclick="openGlobalMember('${u.user_id}')">
      <td><b>${esc(u.username || u.user_id)}</b><br><span class="muted">${esc(u.user_id)}</span></td>
      <td><b>${esc((u.personality_type && u.personality_type.label) || 'Unclassified')}</b><br>${esc((u.personality_type && (u.personality_type.traits || []).join(', ')) || '')}</td>
      <td>${num(u.guild_count)}<br><span class="muted">${esc((u.guild_ids || []).join(', '))}</span></td>
      <td><span class="pill">${num(u.message_count)} messages</span><span class="pill">${num(u.memory_count)} memories</span><span class="pill">${num(u.joke_count)} jokes</span><span class="pill">${num(u.achievement_count)} achievements</span><span class="pill">${num(u.work_runs)} jobs</span></td>
    </tr>`).join('')}</tbody></table>`;
}

function renderGuild() {
  const ship = guild.ship || {};
  const settings = guild.settings || {};
  const shipSettings = guild.ship_settings || {};
  const counts = guild.counts || {};
  const members = filterMembers(guild.members || []);
  const maxHull = ship.level ? 100 + ((Number(ship.level)-1) * 10) : 100;
  $('content').innerHTML = `
    ${card('Living Ship', `
      <h3>${esc(ship.name || 'No ship')}</h3>
      <div class="stats">
        ${stat('Level', ship.level || 0)}${stat('XP', ship.xp || 0)}${stat('Treasury', `${num(ship.treasury)} doubloons`)}${stat('Voyages', ship.voyages_completed || 0)}${stat('Distance', `${num(ship.distance_sailed)} nm`)}${stat('Location', ship.location || 'Unknown')}
      </div>
      <p class="muted">Hull</p><div class="bar"><i style="width:${pct(ship.hull,maxHull)}%"></i></div><p>${num(ship.hull)} / ${num(maxHull)}</p>
      <p class="muted">Sails</p><div class="bar"><i style="width:${pct(ship.sails)}%"></i></div><p>${num(ship.sails)} / 100</p>
      <p class="muted">Supplies</p><div class="bar"><i style="width:${pct(ship.supplies)}%"></i></div><p>${num(ship.supplies)} / 100</p>
      <p class="muted">Morale</p><div class="bar"><i style="width:${pct(ship.morale)}%"></i></div><p>${num(ship.morale)} / 100</p>
    `, 'span-4')}
    ${card(`Server Overview — ${esc(guild.guild_name || selectedGuild)}`, `
      <div class="stats">
        ${stat('Mood', settings.mood || 'unset')}${stat('Quiet', settings.quiet ? 'On' : 'Off')}${stat('Chronicle', settings.chronicle_enabled ? 'On' : 'Off')}${stat('Welcome', settings.welcome_enabled ? 'On' : 'Off')}${stat('Returners', settings.returning_enabled ? 'On' : 'Off')}${stat('Events', settings.event_mode ? 'On' : 'Off')}${stat('Ship World', shipSettings.enabled ? 'On' : 'Off')}${stat('Members', counts.members || 0)}${stat('Profiles', counts.profiles || 0)}${stat('Messages', counts.messages || 0)}${stat('Imported', counts.history_imported || 0)}${stat('Import Channels', counts.history_import_channels || 0)}${stat('Achievements', counts.achievements || 0)}${stat('Discoveries', counts.discoveries || 0)}${stat('History Entries', counts.ship_history || 0)}${stat('Crew Work Runs', counts.crew_work_runs || 0)}
      </div>
    `, 'span-8')}
    ${card('Bot Controls', botControls(settings, shipSettings), 'span-12')}
    ${card('History Import Status', importStatusPanel(guild.history_import_summary, guild.history_imports, false), 'span-12')}
    ${card('Crew Personality Profiles', personalityCards(members), 'span-12')}
    ${card('Crew Table', memberTable(members), 'span-12')}
    ${card('Top Doubloons', simpleRows(guild.top_doubloons, ['username','doubloons']), 'span-6')}
    ${card('Ship Contributors', simpleRows(guild.top_contributors, ['username','amount']), 'span-6')}
    ${card('Crew Work Summary', simpleRows(guild.crew_work, ['job_label','total_runs','payout_total','repair_hull_total']), 'span-6')}
    ${card('Discoveries', discoveryList(guild.discoveries), 'span-6')}
    ${card('Recent Ship History', historyList(guild.recent_history), 'span-6')}
    ${card('Recent World History', historyList(guild.recent_world_history), 'span-6')}
    ${card('Recent Voyages', voyageList(guild.voyages), 'span-6')}
    ${card('Captured Ships', capturedList(guild.captured_ships), 'span-6')}
  `;
}

function botControls(settings, shipSettings) {
  if (!$('adminBtn') || $('adminBtn').style.display === 'none') {
    return '<p class="muted">Dashboard bot controls are visible to dashboard admins.</p>';
  }
  return `
    <div class="toolbar">
      ${controlButton('Quiet Mode', 'quiet', !settings.quiet, settings.quiet)}
      ${controlButton('Event Mode', 'event_mode', !settings.event_mode, settings.event_mode)}
      ${controlButton('Welcomes', 'welcome_enabled', !settings.welcome_enabled, settings.welcome_enabled)}
      ${controlButton('Returners', 'returning_enabled', !settings.returning_enabled, settings.returning_enabled)}
      ${controlButton('Chronicles', 'chronicle_enabled', !settings.chronicle_enabled, settings.chronicle_enabled)}
      ${controlButton('Ship World', 'ship_world_enabled', !shipSettings.enabled, shipSettings.enabled)}
    </div>
    <div class="toolbar" style="margin-top:12px">
      <input id="dashMood" placeholder="Captain mood" value="${esc(settings.mood || '')}">
      <button type="button" onclick="setDashboardMood()">Set Mood</button>
    </div>
    <div class="toolbar" style="margin-top:12px">
      <input id="shipChannelId" placeholder="Ship World channel ID" value="${esc(shipSettings.channel_id || '')}">
      <button type="button" onclick="setDashboardChannel('ship','shipChannelId')">Set Ship Channel</button>
      <button type="button" onclick="clearDashboardChannel('ship','shipChannelId')">Clear Ship Channel</button>
    </div>
    <div class="toolbar" style="margin-top:12px">
      <input id="welcomeChannelId" placeholder="Welcome channel ID" value="${esc(settings.welcome_channel_id || '')}">
      <button type="button" onclick="setDashboardChannel('welcome','welcomeChannelId')">Set Welcome Channel</button>
      <button type="button" onclick="clearDashboardChannel('welcome','welcomeChannelId')">Clear Welcome Channel</button>
    </div>
    <div class="toolbar" style="margin-top:12px">
      <input id="chronicleChannelId" placeholder="Chronicle channel ID" value="${esc(settings.chronicle_channel_id || '')}">
      <button type="button" onclick="setDashboardChannel('chronicle','chronicleChannelId')">Set Chronicle Channel</button>
      <button type="button" onclick="clearDashboardChannel('chronicle','chronicleChannelId')">Clear Chronicle Channel</button>
    </div>
    <p class="muted">These buttons update the same database settings as Discord admin commands. Use Discord channel IDs for channel fields.</p>
  `;
}

function controlButton(label, control, nextValue, active) {
  return `<button type="button" onclick="setDashboardControl('${control}', ${nextValue ? 'true' : 'false'})">${active ? 'Disable' : 'Enable'} ${esc(label)}</button>`;
}

async function setDashboardControl(control, value) {
  const result = await apiJson('/api/admin/control', {guild_id: selectedGuild, control, value});
  guild = result.guild;
  renderGuild();
  $('status').textContent = 'Updated ' + control;
}

async function setDashboardChannel(target, inputId) {
  const channel_id = $(inputId).value.trim() || '0';
  const result = await apiJson('/api/admin/channel', {guild_id: selectedGuild, target, channel_id});
  guild = result.guild;
  renderGuild();
  $('status').textContent = 'Updated ' + target + ' channel';
}

async function clearDashboardChannel(target, inputId) {
  $(inputId).value = '0';
  await setDashboardChannel(target, inputId);
}

async function setDashboardMood() {
  const mood = $('dashMood').value.trim();
  const result = await apiJson('/api/admin/mood', {guild_id: selectedGuild, mood});
  guild = result.guild;
  renderGuild();
  $('status').textContent = 'Updated mood';
}

function filterMembers(members) {
  const q = $('memberSearch').value.trim().toLowerCase();
  if (!q) return members;
  return members.filter(m => JSON.stringify(m).toLowerCase().includes(q));
}

function profileBlurb(m) {
  const parts = [];
  if (m.summary) parts.push(m.summary);
  if (m.opinion) parts.push(m.opinion);
  if (m.nickname && m.nickname.toLowerCase() !== 'none') parts.push(`Nickname: ${m.nickname}`);
  if (!parts.length) parts.push('No written summary yet; open the profile to inspect memories, jokes, events, achievements, and work history.');
  return parts.join(' ');
}

function personalityBadge(type) {
  if (!type) return '';
  const traits = (type.traits || []).slice(0, 4).map(t => `<span class="pill">${esc(t)}</span>`).join('');
  const secondary = (type.secondary || []).slice(0, 2).join(', ');
  return `<div class="personality-type"><strong>${esc(type.label || 'Unclassified')}</strong><span>${num(type.confidence || 0)}% confidence${secondary ? ` • blends with ${esc(secondary)}` : ''}</span><div>${traits}</div></div>`;
}

function personalityCards(members) {
  if (!members.length) return '<p class="muted">No personality data found for this server. Choose a server with crew/profile counts from the Server dropdown above.</p>';
  return `<div class="profile-grid">${members.map(m => `
    <article class="profile-card" onclick="openMember('${m.guild_id}','${m.user_id}')">
      <div class="profile-head">
        <div><h3>${esc(m.username || m.user_id)}</h3><span class="muted">${esc(m.relationship_type || 'Crewmate')}</span></div>
        <strong class="gold">${num(m.familiarity)}/100</strong>
      </div>
      ${personalityBadge(m.personality_type)}
      <p>${esc(profileBlurb(m))}</p>
      <div>
        ${m.gender ? `<span class="pill">Gender: ${esc(m.gender)}</span>` : ''}
        ${m.pronouns ? `<span class="pill">Pronouns: ${esc(m.pronouns)}</span>` : ''}
        <span class="pill">${num(m.message_count)} local messages</span>
        <span class="pill">Seen in ${num(m.global_guild_count || 1)} server(s)</span>
        <span class="pill">${num(m.memory_count)} memories</span>
        <span class="pill">${num(m.joke_count)} jokes</span>
        <span class="pill">${num(m.achievement_count)} achievements</span>
        <span class="pill">${num(m.doubloons)} doubloons</span>
        <span class="pill">${num(m.work_runs)} jobs</span>
      </div>
    </article>`).join('')}</div>`;
}

function memberTable(members) {
  if (!members.length) return '<p class="muted">No members found for this server. Choose a server with crew/profile counts from the Server dropdown above.</p>';
  return `<table><thead><tr><th>Crew</th><th>Relationship</th><th>Profile</th><th>Doubloons</th><th>Signals</th></tr></thead><tbody>${members.map(m => `
    <tr class="clickable" onclick="openMember('${m.guild_id}','${m.user_id}')">
      <td><b>${esc(m.username || m.user_id)}</b><br><span class="muted">${esc(m.user_id)}</span></td>
      <td>${esc(m.relationship_type || '')}<br><span class="pill">Familiarity ${num(m.familiarity)}</span>${m.nickname ? `<span class="pill">${esc(m.nickname)}</span>` : ''}</td>
      <td><b>${esc((m.personality_type && m.personality_type.label) || 'Unclassified')}</b><br>${esc(m.summary || m.opinion || 'No profile summary yet.')}</td>
      <td>${num(m.doubloons)}</td>
      <td><span class="pill">${num(m.message_count)} local messages</span><span class="pill">Seen in ${num(m.global_guild_count || 1)} server(s)</span><span class="pill">${num(m.memory_count)} memories</span><span class="pill">${num(m.joke_count)} jokes</span><span class="pill">${num(m.achievement_count)} achievements</span><span class="pill">${num(m.work_runs)} jobs</span></td>
    </tr>`).join('')}</tbody></table>`;
}

function statusPill(status) {
  const s = String(status || 'unknown').toLowerCase();
  const cls = s === 'failed' ? 'red' : (s === 'running' || s === 'stopping' ? 'green' : (s === 'complete' ? 'gold' : ''));
  return `<span class="pill ${cls}">${esc(s)}</span>`;
}

function importStatusPanel(summary, imports, includeServer=false) {
  summary = summary || {};
  imports = imports || [];
  const statusParts = Object.entries(summary.by_status || {}).map(([k,v]) => `<span class="pill">${esc(k)}: ${num(v)}</span>`).join('');
  return `
    <div class="stats">
      ${stat('Channels', summary.channels || 0)}${stat('Imported', summary.imported || 0)}${stat('Scanned', summary.scanned || 0)}${stat('Running', summary.running || 0)}${stat('Paused', summary.paused || 0)}${stat('Complete', summary.complete || 0)}${stat('Failed', summary.failed || 0)}
    </div>
    <p>${statusParts || '<span class="muted">No imports recorded yet.</span>'}</p>
    ${importTable(imports, includeServer)}
  `;
}

function importTable(imports, includeServer=false) {
  if (!imports || !imports.length) return '<p class="muted">No import progress recorded yet.</p>';
  const cols = includeServer ? ['guild_id','channel_id','status','imported_count','scanned_count','updated_at'] : ['channel_id','status','imported_count','scanned_count','updated_at'];
  return `<table><thead><tr>${cols.map(c => `<th>${esc(c.replaceAll('_',' '))}</th>`).join('')}</tr></thead><tbody>${imports.slice(0, 30).map(row => `<tr>${cols.map(c => `<td>${c === 'status' ? statusPill(row[c]) : esc(row[c] ?? '')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

function simpleRows(list, keys) {
  if (!list || !list.length) return '<p class="muted">None yet.</p>';
  return `<table><thead><tr>${keys.map(k => `<th>${esc(k.replaceAll('_',' '))}</th>`).join('')}</tr></thead><tbody>${list.map(row => `<tr>${keys.map(k => `<td>${esc(row[k] ?? '')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}
function historyList(list) { return `<div class="list">${(list||[]).map(x => item(x.content, `${x.event_type || ''} ${x.created_at || ''}`)).join('') || '<p class="muted">No history yet.</p>'}</div>`; }
function discoveryList(list) { return `<div class="list">${(list||[]).map(x => item(x.location_key, `by ${x.discovered_by_name || 'Unknown'} • visits ${x.visits || 0} • ${x.discovered_at || ''}`)).join('') || '<p class="muted">No discoveries yet.</p>'}</div>`; }
function voyageList(list) { return `<div class="list">${(list||[]).map(x => item(`${x.destination} — ${x.status}`, `${x.risk} • ${x.result || ''}`)).join('') || '<p class="muted">No voyages yet.</p>'}</div>`; }
function capturedList(list) { return `<div class="list">${(list||[]).map(x => item(`${x.enemy_name} — ${x.status}`, `by ${x.captured_by_name || 'Unknown'} • ${x.reward || 0} doubloons • ${x.xp_reward || 0} XP`)).join('') || '<p class="muted">No captured ships held.</p>'}</div>`; }

async function openGlobalMember(userId) {
  const data = await api(`/api/global/member/${userId}`);
  const globalProfile = data.global_profile || {};
  const globalBase = globalProfile.base || {};
  $('memberTitle').textContent = `${(globalBase.usernames || [])[0] || userId} — Global Profile`;
  $('memberBody').innerHTML = `
    <div class="grid">
      <div class="card span-12"><h3>Cross-Server Personality Type</h3>${personalityBadge(globalProfile.personality_type)}<p class="muted">Matched by Discord user_id across ${num(globalBase.guild_count || 0)} server(s). Built from ${num(globalBase.message_count || 0)} stored messages across all servers.</p><pre>${esc(JSON.stringify(globalProfile || {}, null, 2))}</pre></div>
      <div class="card span-12"><h3>Server-Specific Profiles</h3>${simpleRows(data.local_profiles || [], ['guild_id','message_count','memory_count','achievement_count'])}</div>
      <div class="card span-6"><h3>Global Memories</h3><div class="list">${(data.memories || []).map(m => item(m.memory, `server ${m.guild_id} • confidence ${m.confidence || 0} • ${m.created_at || ''}`)).join('') || '<p class="muted">None yet.</p>'}</div></div>
      <div class="card span-6"><h3>Global Achievements</h3><div class="list">${(data.achievements || []).map(a => item(a.achievement, `server ${a.guild_id} • ${a.description || ''} • ${a.awarded_at || ''}`)).join('') || '<p class="muted">None yet.</p>'}</div></div>
      <div class="card span-6"><h3>Global Running Jokes</h3><div class="list">${(data.running_jokes || []).map(j => item(j.joke, `server ${j.guild_id} • ${j.created_at || ''}`)).join('') || '<p class="muted">None yet.</p>'}</div></div>
      <div class="card span-6"><h3>Recent Messages Across Servers</h3><div class="list">${(data.recent_messages || []).map(m => item(m.content, `server ${m.guild_id} • ${m.username || ''} • ${m.timestamp || ''}`)).join('') || '<p class="muted">None yet.</p>'}</div></div>
    </div>`;
  memberDialog.showModal();
}

async function openMember(guildId, userId) {
  const data = await api(`/api/member/${guildId}/${userId}`);
  const profile = data.profile || {};
  const rel = data.relationship || {};
  const econ = data.economy || {};
  const globalProfile = data.global_profile || {};
  const globalBase = globalProfile.base || {};
  $('memberTitle').textContent = `${rel.username || profile.username || userId}`;
  $('memberBody').innerHTML = `
    <div class="grid">
      <div class="card span-12"><h3>Local Server Personality Type</h3>${personalityBadge(data.personality_type)}<p class="muted">Built from this server’s stored message history plus local memories, jokes, relationship events, achievements, and crew activity.</p><pre>${esc(JSON.stringify(data.personality_type || {}, null, 2))}</pre></div>
      <div class="card span-12"><h3>Cross-Server Identity Match</h3>${personalityBadge(globalProfile.personality_type)}<p class="muted">Same Discord user_id seen in ${num(globalBase.guild_count || 0)} server(s). Built from ${num(globalBase.message_count || 0)} stored messages across all servers. Server-specific gameplay, economy, permissions, and relationships remain separate.</p><pre>${esc(JSON.stringify(globalProfile || {}, null, 2))}</pre></div>
      <div class="card span-6"><h3>Core Personality Profile</h3><pre>${esc(JSON.stringify({profile, relationship: rel, economy: econ, ship_contribution: data.ship_contribution}, null, 2))}</pre></div>
      <div class="card span-6"><h3>Achievements</h3><div class="list">${data.achievements.map(a => item(a.achievement, `${a.description || ''} • ${a.awarded_at || ''}`)).join('') || '<p class="muted">None yet.</p>'}</div></div>
      <div class="card span-6"><h3>Personality Memories</h3><div class="list">${data.memories.map(m => item(m.memory, `confidence ${m.confidence || 0} • ${m.created_at || ''}`)).join('') || '<p class="muted">None yet.</p>'}</div></div>
      <div class="card span-6"><h3>Running Jokes / Humor Profile</h3><div class="list">${data.running_jokes.map(j => item(j.joke, j.created_at || '')).join('') || '<p class="muted">None yet.</p>'}</div></div>
      <div class="card span-6"><h3>Relationship Events / History</h3><div class="list">${data.relationship_events.map(e => item(e.event, `importance ${e.importance || 0} • ${e.created_at || ''}`)).join('') || '<p class="muted">None yet.</p>'}</div></div>
      <div class="card span-6"><h3>Crew Work</h3>${simpleRows(data.crew_work, ['job_label','total_runs','success_count','failure_count','rare_count','payout_total','repair_hull_total'])}</div>
      <div class="card span-6"><h3>Recent Observed Messages</h3><div class="list">${data.recent_messages.map(m => item(m.content, m.timestamp || '')).join('') || '<p class="muted">None yet.</p>'}</div></div>
    </div>`;
  memberDialog.showModal();
}

let adminAccessOptions = {guilds: []};

async function openAdminUsers() {
  const data = await api('/api/admin/users');
  adminAccessOptions = data.options || {guilds: []};
  $('adminBody').innerHTML = `
    <div class="card span-12">
      <h3>Create User</h3>
      <div class="toolbar">
        <input id="newDashUser" placeholder="username">
        <input id="newDashPass" type="password" placeholder="password">
        <select id="newDashRole"><option value="user">User</option><option value="admin">Admin</option></select>
        <select id="newDashScope"><option value="selected">Selected servers</option><option value="global">Global only</option><option value="all">All access</option></select>
        <button type="button" onclick="createDashboardUserFromForm()">Create</button>
      </div>
      <div class="access-grid">${accessCheckboxes('newDashGuild', [])}</div>
      <p class="muted">Admins always see everything. Regular users can be limited to global info, selected servers, or all dashboard data.</p>
    </div>
    <div class="card span-12"><h3>Existing Users</h3>${dashboardUsersTable(data.users || [])}</div>
  `;
  adminDialog.showModal();
}

function accessSummary(user) {
  const access = user.access || {};
  if (user.role === 'admin' || access.all) return 'All dashboard data';
  const parts = [];
  if (access.global) parts.push('Global info');
  const guildIds = access.guild_ids || [];
  if (guildIds.length) parts.push(`${guildIds.length} server(s)`);
  return parts.join(' + ') || 'No access assigned';
}

function accessCheckboxes(prefix, selected) {
  const selectedSet = new Set((selected || []).map(String));
  const guilds = (adminAccessOptions.guilds || []);
  if (!guilds.length) return '<p class="muted">No servers found.</p>';
  return guilds.map(g => {
    const name = g.guild_name || `Server ${g.guild_id}`;
    return `<label><input type="checkbox" data-access-prefix="${esc(prefix)}" value="${esc(g.guild_id)}" ${selectedSet.has(String(g.guild_id)) ? 'checked' : ''}> ${esc(name)}</label>`;
  }).join('');
}

function selectedGuildAccess(prefix) {
  return Array.from(document.querySelectorAll(`input[data-access-prefix="${prefix}"]:checked`)).map(input => input.value);
}

function dashboardUsersTable(users) {
  if (!users.length) return '<p class="muted">No dashboard users configured.</p>';
  return `<table><thead><tr><th>Username</th><th>Role</th><th>Access</th><th>Edit access</th><th>Action</th></tr></thead><tbody>${users.map(u => {
    const access = u.access || {};
    const prefix = `access_${String(u.username).replace(/[^A-Za-z0-9_-]/g, '_')}`;
    return `<tr>
      <td><b>${esc(u.username)}</b><br><span class="muted">Created ${esc(u.created_at || '')}</span></td>
      <td><select id="${prefix}_role"><option value="user" ${u.role === 'user' ? 'selected' : ''}>User</option><option value="admin" ${u.role === 'admin' ? 'selected' : ''}>Admin</option></select></td>
      <td>${esc(accessSummary(u))}</td>
      <td>
        <label class="access-toggle"><input id="${prefix}_all" type="checkbox" ${access.all ? 'checked' : ''}> All access</label>
        <label class="access-toggle"><input id="${prefix}_global" type="checkbox" ${access.global ? 'checked' : ''}> Global info</label>
        <div class="access-grid">${accessCheckboxes(prefix, access.guild_ids || [])}</div>
        <button type="button" onclick="saveDashboardAccess('${esc(u.username)}','${prefix}')">Save Access</button>
      </td>
      <td><button type="button" onclick="deleteDashboardUser('${esc(u.username)}')">Delete</button></td>
    </tr>`;
  }).join('')}</tbody></table>`;
}

async function createDashboardUserFromForm() {
  const username = $('newDashUser').value;
  const password = $('newDashPass').value;
  const role = $('newDashRole').value;
  const scope = $('newDashScope').value;
  const access = {
    all: scope === 'all',
    global: scope === 'all' || scope === 'global',
    guild_ids: scope === 'selected' ? selectedGuildAccess('newDashGuild') : [],
  };
  await apiJson('/api/admin/users', {username, password, role, access});
  await openAdminUsers();
}

async function saveDashboardAccess(username, prefix) {
  const role = $(`${prefix}_role`).value;
  const access = {
    all: $(`${prefix}_all`).checked,
    global: $(`${prefix}_global`).checked,
    guild_ids: selectedGuildAccess(prefix),
  };
  await apiJson('/api/admin/users/access', {username, role, access});
  await openAdminUsers();
}

async function deleteDashboardUser(username) {
  await apiJson('/api/admin/users/delete', {username});
  await openAdminUsers();
}

$('guildSelect').addEventListener('change', e => loadSelected(e.target.value));
$('refreshBtn').addEventListener('click', () => selectedGuild ? loadSelected(selectedGuild) : loadOverview());
$('adminBtn').addEventListener('click', () => openAdminUsers().catch(err => { $('status').textContent = 'Error: ' + err.message; console.error(err); }));
$('memberSearch').addEventListener('input', () => currentView === 'global' ? renderGlobal() : (guild && renderGuild()));
loadOverview().catch(err => { $('status').textContent = 'Error: ' + err.message; console.error(err); });
</script>
</body>
</html>
"""


LOGIN_HTML = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Captain Cutlass Quarterdeck Login</title>
  <style>
    :root { color-scheme: dark; --bg:#020506; --panel:#071114; --text:#f4f7f4; --muted:#8eb6bd; --cyan:#10e7ef; --gold:#d7a23a; --red:#9d2f2f; --line:rgba(16,231,239,.42); }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; display:grid; place-items:center; padding:20px; font-family:'Trebuchet MS', Inter, ui-sans-serif, system-ui, sans-serif; color:var(--text); background:
      linear-gradient(90deg, rgba(0,0,0,.34), rgba(0,0,0,.72)),
      linear-gradient(180deg, rgba(0,0,0,.12), rgba(0,0,0,.84)),
      url('/assets/banner.png') center/cover no-repeat fixed,
      #000; }
    body::before { content:''; position:fixed; inset:0; pointer-events:none; background:radial-gradient(circle at 50% 42%, rgba(16,231,239,.14), transparent 32%), radial-gradient(ellipse at center, transparent 34%, rgba(0,0,0,.68) 100%); }
    main { width:min(470px, 100%); background:linear-gradient(180deg, rgba(8,20,24,.94), rgba(2,6,8,.98)); border:1px solid var(--line); border-radius:12px; padding:28px; box-shadow:0 24px 80px rgba(0,0,0,.68), 0 0 38px rgba(16,231,239,.18), inset 0 0 0 1px rgba(215,162,58,.12); position:relative; overflow:hidden; }
    main::before { content:''; position:absolute; inset:0; pointer-events:none; background:linear-gradient(90deg, transparent, rgba(16,231,239,.06), transparent), radial-gradient(circle at top right, rgba(16,231,239,.15), transparent 34%); }
    main > * { position:relative; }
    .login-mark { width:132px; height:132px; display:block; margin:0 auto 14px; border-radius:50%; object-fit:cover; border:2px solid var(--cyan); background:#000; box-shadow:0 0 0 4px rgba(0,0,0,.55), 0 0 34px rgba(16,231,239,.72); }
    h1 { margin:0 0 8px; font-size:34px; letter-spacing:.06em; text-transform:uppercase; color:#f6f2e8; text-align:center; text-shadow:0 2px 0 #000, 0 0 18px rgba(16,231,239,.55); }
    .login-title { display:grid; justify-items:center; line-height:.9; margin:0 0 10px; text-transform:uppercase; }
    .login-title .captain { color:#f6f2e8; font-size:30px; font-weight:900; letter-spacing:.14em; text-shadow:0 2px 0 #000, 0 0 14px rgba(255,255,255,.22); }
    .login-title .cutlass { color:var(--cyan); font-size:54px; font-weight:1000; font-style:italic; letter-spacing:.04em; transform:skewX(-9deg); text-shadow:0 3px 0 #001417, 0 0 18px rgba(16,231,239,.95), 0 0 38px rgba(16,231,239,.42); }
    .login-motto { display:flex; align-items:center; justify-content:center; gap:8px; margin:2px 0 14px; color:#f6f2e8; font:800 11px/1.2 'Courier New', monospace; letter-spacing:.1em; text-transform:uppercase; text-shadow:0 0 12px rgba(16,231,239,.35); }
    .login-motto::before, .login-motto::after { content:''; width:28px; height:2px; background:var(--cyan); box-shadow:0 0 10px rgba(16,231,239,.8); }
    p { margin:0 0 22px; color:var(--muted); line-height:1.5; text-align:center; }
    label { display:grid; gap:7px; margin:14px 0; color:var(--cyan); text-transform:uppercase; font-size:12px; letter-spacing:.08em; }
    input, button { width:100%; border:1px solid var(--line); border-radius:6px; padding:12px 13px; font:inherit; box-shadow:inset 0 1px rgba(255,255,255,.06), 0 0 16px rgba(16,231,239,.08); }
    input { background:#030708; color:var(--text); }
    button { margin-top:8px; cursor:pointer; background:linear-gradient(180deg, rgba(16,231,239,.22), rgba(0,107,120,.22)), #071114; color:#dffcff; border-color:rgba(16,231,239,.72); font-weight:800; text-transform:uppercase; letter-spacing:.06em; text-shadow:0 0 8px rgba(16,231,239,.7); }
    button:hover { border-color:var(--gold); color:#fff6d8; box-shadow:0 0 0 2px rgba(16,231,239,.18), 0 0 24px rgba(16,231,239,.24); }
    .error { margin-bottom:14px; padding:10px 12px; border:1px solid rgba(157,47,47,.65); background:rgba(157,47,47,.18); border-radius:8px; color:#ffd3c7; text-align:left; }
    .gold { color:var(--gold); }
  </style>
</head>
<body>
  <main>
    <img class="login-mark" src="/assets/cutlass.png" alt="Captain Cutlass crest">
    <div class="login-title" aria-label="Captain Cutlass">
      <span class="captain">Captain</span>
      <span class="cutlass">Cutlass</span>
    </div>
    <div class="login-motto">Pirate. Protector. Programmed to Plunder.</div>
    <p>Show yer papers to enter the quarterdeck command center for crew intel, ship telemetry, history, jobs, and achievements.</p>
    {error}
    <form method="post" action="/login">
      <label>Username <input name="username" autocomplete="username" required autofocus></label>
      <label>Password <input name="password" type="password" autocomplete="current-password" required></label>
      <button type="submit">Board the Quarterdeck</button>
    </form>
    <p style="margin-top:18px;font-size:13px;">Session access uses an <span class="gold">HttpOnly</span> ship seal. Token auth still works for API checks.</p>
  </main>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "CutlassDashboard/1.0"

    def log_message(self, fmt, *args):
        message = fmt % args
        if "token=" in message:
            message = re.sub(r"token=[^&\s]+", "token=REDACTED", message)
        print("dashboard", self.address_string(), message)

    def query_token(self):
        header = self.headers.get("Authorization", "")
        query = parse_qs(urlparse(self.path).query)
        if header.startswith("Bearer "):
            return header.removeprefix("Bearer ").strip()
        if "token" in query:
            return query["token"][0]
        return ""

    def session_username(self):
        if not dashboard_login_enabled():
            return None
        raw_cookie = self.headers.get("Cookie", "")
        jar = cookies.SimpleCookie()
        try:
            jar.load(raw_cookie)
        except cookies.CookieError:
            return None
        morsel = jar.get(DASHBOARD_COOKIE_NAME)
        if not morsel:
            return None
        return verify_session_token(morsel.value)

    def current_user(self):
        username = self.session_username()
        if not username:
            return None
        record = dashboard_user_record(username)
        if not record:
            return None
        return {"username": username, "role": record.get("role", "user"), "access": normalize_dashboard_access(record)}

    def token_authorized(self):
        if not DASHBOARD_TOKEN:
            return False
        token = self.query_token()
        return bool(token and hmac.compare_digest(token, DASHBOARD_TOKEN))

    def access_user(self):
        user = self.current_user()
        if user:
            return user
        if self.token_authorized():
            return {"username": "token", "role": "admin", "access": {"all": True, "global": True, "guild_ids": []}}
        if not DASHBOARD_TOKEN and not dashboard_login_enabled():
            return {"username": "open", "role": "admin", "access": {"all": True, "global": True, "guild_ids": []}}
        return None

    def authorized(self):
        return self.access_user() is not None

    def admin_authorized(self):
        user = self.access_user()
        return bool(user and user.get("role") == "admin")

    def send_json(self, payload, status=200):
        body = json.dumps(json_safe_ids(payload), indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, body, status=200, headers=None):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location, headers=None):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def send_login(self, error="", status=200):
        error_html = f'<div class="error">{error}</div>' if error else ""
        self.send_html(LOGIN_HTML.replace("{error}", error_html), status=status)

    def send_asset(self, path):
        asset_path = DASHBOARD_ASSETS.get(path)
        if not asset_path or not asset_path.exists():
            self.send_json({"error": "asset not found"}, 404)
            return
        data = asset_path.read_bytes()
        content_type = mimetypes.guess_type(str(asset_path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path in DASHBOARD_ASSETS:
            self.send_asset(path)
            return

        if path == "/login":
            if self.authorized():
                self.redirect("/")
            else:
                self.send_login()
            return

        if path == "/logout":
            self.redirect("/login", {"Set-Cookie": expired_dashboard_cookie_header()})
            return

        if not self.authorized():
            if path.startswith("/api/"):
                self.send_json({"error": "unauthorized"}, 401)
            else:
                self.redirect("/login")
            return

        try:
            if path == "/":
                self.send_html(INDEX_HTML)
                return
            if path == "/api/health":
                self.send_json({"ok": True, "database": DB_PATH, "login_enabled": dashboard_login_enabled()})
                return
            if path == "/api/session":
                self.send_json({"user": self.access_user(), "login_enabled": dashboard_login_enabled()})
                return
            if path == "/api/admin/users":
                if not self.admin_authorized():
                    self.send_json({"error": "admin required"}, 403)
                    return
                self.send_json({"users": dashboard_public_users(), "options": dashboard_access_options_payload()})
                return
            if path == "/api/overview":
                self.send_json(overview_payload(self.access_user()))
                return
            if path == "/api/global":
                if not require_dashboard_access(self.access_user(), global_required=True):
                    self.send_json({"error": "global access required"}, 403)
                    return
                self.send_json(global_payload())
                return
            if path.startswith("/api/global/member/"):
                if not require_dashboard_access(self.access_user(), global_required=True):
                    self.send_json({"error": "global access required"}, 403)
                    return
                user_id = safe_int(path.split("/")[-1])
                self.send_json(global_member_payload(user_id))
                return
            if path.startswith("/api/guild/"):
                guild_id = safe_int(path.split("/")[-1])
                if not require_dashboard_access(self.access_user(), guild_id=guild_id):
                    self.send_json({"error": "server access required"}, 403)
                    return
                self.send_json(guild_payload(guild_id))
                return
            if path.startswith("/api/member/"):
                parts = path.split("/")
                guild_id = safe_int(parts[-2])
                user_id = safe_int(parts[-1])
                current = self.access_user()
                if not require_dashboard_access(current, guild_id=guild_id):
                    self.send_json({"error": "server access required"}, 403)
                    return
                self.send_json(member_payload(guild_id, user_id, include_global=dashboard_user_can_global(current)))
                return
            self.send_json({"error": "not found"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)

    def read_body(self, limit=10000):
        try:
            length = min(int(self.headers.get("Content-Length", "0")), limit)
        except ValueError:
            length = 0
        return self.rfile.read(length).decode("utf-8", errors="replace")

    def read_json_body(self):
        try:
            return json.loads(self.read_body())
        except Exception:
            return {}

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/login":
            if not dashboard_login_enabled():
                self.send_login("Dashboard user login is not configured.", status=503)
                return
            fields = parse_qs(self.read_body())
            username = (fields.get("username") or [""])[0].strip()
            password = (fields.get("password") or [""])[0]
            user = verify_dashboard_login(username, password)

            if user:
                self.redirect("/", {"Set-Cookie": dashboard_cookie_header(username)})
                return

            self.send_login("Invalid dashboard username or password.", status=401)
            return

        if path == "/api/admin/users":
            if not self.admin_authorized():
                self.send_json({"error": "admin required"}, 403)
                return
            payload = self.read_json_body()
            try:
                user = create_dashboard_user(payload.get("username"), payload.get("password"), payload.get("role", "user"), payload.get("access"))
            except ValueError as exc:
                self.send_json({"error": str(exc)}, 400)
                return
            self.send_json({"user": user, "users": dashboard_public_users()}, 201)
            return

        if path == "/api/admin/control":
            if not self.admin_authorized():
                self.send_json({"error": "admin required"}, 403)
                return
            payload = self.read_json_body()
            guild_id = safe_int(payload.get("guild_id"))
            if not require_dashboard_access(self.access_user(), guild_id=guild_id):
                self.send_json({"error": "server access required"}, 403)
                return
            try:
                result = dashboard_control_payload(guild_id, payload.get("control"), payload.get("value"))
            except ValueError as exc:
                self.send_json({"error": str(exc)}, 400)
                return
            result["guild"] = guild_payload(guild_id)
            self.send_json(result)
            return

        if path == "/api/admin/channel":
            if not self.admin_authorized():
                self.send_json({"error": "admin required"}, 403)
                return
            payload = self.read_json_body()
            guild_id = safe_int(payload.get("guild_id"))
            if not require_dashboard_access(self.access_user(), guild_id=guild_id):
                self.send_json({"error": "server access required"}, 403)
                return
            target = payload.get("target")
            try:
                if target == "ship":
                    result = dashboard_set_ship_channel(guild_id, payload.get("channel_id"))
                elif target == "chronicle":
                    result = dashboard_set_chronicle_channel(guild_id, payload.get("channel_id"))
                elif target == "welcome":
                    result = dashboard_set_welcome_channel(guild_id, payload.get("channel_id"))
                else:
                    raise ValueError("Unknown channel target.")
            except ValueError as exc:
                self.send_json({"error": str(exc)}, 400)
                return
            result["guild"] = guild_payload(guild_id)
            self.send_json(result)
            return

        if path == "/api/admin/mood":
            if not self.admin_authorized():
                self.send_json({"error": "admin required"}, 403)
                return
            payload = self.read_json_body()
            guild_id = safe_int(payload.get("guild_id"))
            if not require_dashboard_access(self.access_user(), guild_id=guild_id):
                self.send_json({"error": "server access required"}, 403)
                return
            try:
                result = dashboard_set_mood(guild_id, payload.get("mood"))
            except ValueError as exc:
                self.send_json({"error": str(exc)}, 400)
                return
            result["guild"] = guild_payload(guild_id)
            self.send_json(result)
            return

        if path == "/api/admin/users/access":
            if not self.admin_authorized():
                self.send_json({"error": "admin required"}, 403)
                return
            payload = self.read_json_body()
            try:
                user = update_dashboard_user_access(str(payload.get("username", "")), payload.get("role"), payload.get("access"))
            except ValueError as exc:
                self.send_json({"error": str(exc)}, 400)
                return
            self.send_json({"user": user, "users": dashboard_public_users()})
            return

        if path == "/api/admin/users/delete":
            if not self.admin_authorized():
                self.send_json({"error": "admin required"}, 403)
                return
            payload = self.read_json_body()
            try:
                delete_dashboard_user(str(payload.get("username", "")))
            except ValueError as exc:
                self.send_json({"error": str(exc)}, 400)
                return
            self.send_json({"ok": True, "users": dashboard_public_users()})
            return

        self.send_json({"error": "not found"}, 404)


if __name__ == "__main__":
    print(f"Captain Cutlass dashboard listening on {DASHBOARD_HOST}:{DASHBOARD_PORT}")
    print(f"Database: {DB_PATH}")
    if dashboard_login_enabled():
        print(f"Dashboard user login: enabled for {len(load_dashboard_users())} user(s)")
    else:
        print("Dashboard user login: disabled")
    if DASHBOARD_TOKEN:
        print("Dashboard token auth: enabled")
    elif not dashboard_login_enabled():
        print("Dashboard auth: disabled; rely on localhost binding or firewall")
    ThreadingHTTPServer((DASHBOARD_HOST, DASHBOARD_PORT), DashboardHandler).serve_forever()
