import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

DB_PATH = os.getenv("DATABASE_PATH", "/app/data/captain.db")
UPLOAD_DIR = Path(os.getenv("POLICE_CHIEF_UPLOAD_DIR", "/app/data/police_chief_uploads"))

STATUS_VALUES = {"unknown", "ally", "neutral", "enemy", "watchlist", "inactive"}
IMPORT_TYPES = {"alliance", "profile"}


def now_ts() -> int:
    return int(time.time())


def clean_name(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:120]


def clean_rank(value: Any) -> str:
    return str(value or "").strip()[:40]


def clean_status(value: Any) -> str:
    value = str(value or "unknown").strip().lower()
    return value if value in STATUS_VALUES else "unknown"


def parse_power(value: Any) -> Optional[int]:
    if value is None or str(value).strip() == "":
        return None
    digits = re.sub(r"[^0-9]", "", str(value))
    if not digits:
        raise ValueError("Power must contain digits.")
    return int(digits)


def connect(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def ensure_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS police_chief_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL DEFAULT 0,
            player_name TEXT NOT NULL,
            player_key TEXT NOT NULL,
            game_player_id TEXT DEFAULT '',
            alliance_name TEXT DEFAULT '',
            alliance_rank TEXT DEFAULT '',
            power INTEGER,
            status TEXT DEFAULT 'unknown',
            notes TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            source TEXT DEFAULT 'manual',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            updated_by_id INTEGER DEFAULT 0,
            updated_by_name TEXT DEFAULT '',
            UNIQUE(guild_id, player_key)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS police_chief_discord_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL DEFAULT 0,
            discord_user_id INTEGER NOT NULL,
            discord_username TEXT DEFAULT '',
            confidence TEXT DEFAULT 'manual',
            linked_by_id INTEGER DEFAULT 0,
            linked_by_name TEXT DEFAULT '',
            linked_at INTEGER NOT NULL,
            UNIQUE(player_id, guild_id),
            FOREIGN KEY(player_id) REFERENCES police_chief_players(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS police_chief_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL DEFAULT 0,
            field TEXT NOT NULL,
            old_value TEXT DEFAULT '',
            new_value TEXT DEFAULT '',
            source TEXT DEFAULT 'manual',
            changed_by_id INTEGER DEFAULT 0,
            changed_by_name TEXT DEFAULT '',
            changed_at INTEGER NOT NULL,
            FOREIGN KEY(player_id) REFERENCES police_chief_players(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS police_chief_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL DEFAULT 0,
            import_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            original_filename TEXT DEFAULT '',
            stored_path TEXT DEFAULT '',
            content_type TEXT DEFAULT '',
            uploaded_by_id INTEGER DEFAULT 0,
            uploaded_by_name TEXT DEFAULT '',
            uploaded_at INTEGER NOT NULL,
            notes TEXT DEFAULT '',
            raw_text TEXT DEFAULT '',
            extracted_json TEXT DEFAULT ''
        )
        """
    )
    conn.commit()


def rowdict(row):
    return dict(row) if row is not None else None


def player_key(name: str) -> str:
    return clean_name(name).casefold()


def actor_info(actor=None, actor_id=None, actor_name=None):
    if actor is not None:
        return int(getattr(actor, "id", 0) or 0), str(getattr(actor, "display_name", None) or getattr(actor, "name", "") or "")[:120]
    return int(actor_id or 0), str(actor_name or "")[:120]


def get_player(conn, guild_id: int, name: str):
    return rowdict(conn.execute(
        "SELECT * FROM police_chief_players WHERE guild_id=? AND player_key=?",
        (int(guild_id or 0), player_key(name)),
    ).fetchone())


def get_player_by_id(conn, player_id: int):
    return rowdict(conn.execute("SELECT * FROM police_chief_players WHERE id=?", (int(player_id),)).fetchone())


def history_insert(conn, player_id, guild_id, field, old, new, source, actor_id, actor_name):
    if str(old or "") == str(new or ""):
        return
    conn.execute(
        """
        INSERT INTO police_chief_history
        (player_id, guild_id, field, old_value, new_value, source, changed_by_id, changed_by_name, changed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (player_id, int(guild_id or 0), field, str(old or ""), str(new or ""), source, actor_id, actor_name, now_ts()),
    )


def upsert_player(conn, guild_id: int, name: str, *, power=None, alliance_rank=None, alliance_name=None,
                  status=None, notes=None, tags=None, game_player_id=None, source="manual", actor=None,
                  actor_id=None, actor_name=None):
    guild_id = int(guild_id or 0)
    name = clean_name(name)
    if len(name) < 2:
        raise ValueError("Player name must be at least 2 characters.")
    actor_id, actor_name = actor_info(actor, actor_id, actor_name)
    existing = get_player(conn, guild_id, name)
    ts = now_ts()
    power_value = parse_power(power) if power is not None else None
    status_value = clean_status(status) if status is not None else None
    updates = {
        "player_name": name,
        "game_player_id": str(game_player_id or "")[:80] if game_player_id is not None else None,
        "alliance_name": str(alliance_name or "")[:120] if alliance_name is not None else None,
        "alliance_rank": clean_rank(alliance_rank) if alliance_rank is not None else None,
        "power": power_value if power is not None else None,
        "status": status_value,
        "notes": str(notes or "")[:2000] if notes is not None else None,
        "tags": str(tags or "")[:500] if tags is not None else None,
    }
    if existing:
        fields = []
        params = []
        for key, value in updates.items():
            if value is None:
                continue
            history_insert(conn, existing["id"], guild_id, key, existing.get(key), value, source, actor_id, actor_name)
            fields.append(f"{key}=?")
            params.append(value)
        fields.extend(["source=?", "updated_at=?", "updated_by_id=?", "updated_by_name=?"])
        params.extend([source, ts, actor_id, actor_name, existing["id"]])
        conn.execute(f"UPDATE police_chief_players SET {', '.join(fields)} WHERE id=?", params)
        conn.commit()
        return get_player_by_id(conn, existing["id"]), False
    conn.execute(
        """
        INSERT INTO police_chief_players
        (guild_id, player_name, player_key, game_player_id, alliance_name, alliance_rank, power, status, notes, tags, source, created_at, updated_at, updated_by_id, updated_by_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            guild_id, name, player_key(name), updates["game_player_id"] or "", updates["alliance_name"] or "",
            updates["alliance_rank"] or "", power_value, status_value or "unknown", updates["notes"] or "",
            updates["tags"] or "", source, ts, ts, actor_id, actor_name,
        ),
    )
    player_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    for key, value in updates.items():
        if value not in (None, ""):
            history_insert(conn, player_id, guild_id, key, "", value, source, actor_id, actor_name)
    conn.commit()
    return get_player_by_id(conn, player_id), True


def link_discord(conn, guild_id, player_name_value, discord_user_id, discord_username="", actor=None, actor_id=None, actor_name=None):
    player, _ = upsert_player(conn, guild_id, player_name_value, source="manual-link", actor=actor, actor_id=actor_id, actor_name=actor_name)
    actor_id, actor_name = actor_info(actor, actor_id, actor_name)
    conn.execute(
        """
        INSERT INTO police_chief_discord_links
        (player_id, guild_id, discord_user_id, discord_username, confidence, linked_by_id, linked_by_name, linked_at)
        VALUES (?, ?, ?, ?, 'manual', ?, ?, ?)
        ON CONFLICT(player_id, guild_id) DO UPDATE SET
            discord_user_id=excluded.discord_user_id,
            discord_username=excluded.discord_username,
            confidence='manual',
            linked_by_id=excluded.linked_by_id,
            linked_by_name=excluded.linked_by_name,
            linked_at=excluded.linked_at
        """,
        (player["id"], int(guild_id or 0), int(discord_user_id), str(discord_username or "")[:120], actor_id, actor_name, now_ts()),
    )
    history_insert(conn, player["id"], guild_id, "discord_link", "", f"{discord_username or discord_user_id}", "manual", actor_id, actor_name)
    conn.commit()
    return get_player_detail(conn, guild_id, player["player_name"])


def unlink_discord(conn, guild_id, player_name_value, actor=None, actor_id=None, actor_name=None):
    player = get_player(conn, guild_id, player_name_value)
    if not player:
        raise ValueError("Police Chief player not found.")
    actor_id, actor_name = actor_info(actor, actor_id, actor_name)
    old = conn.execute("SELECT discord_username, discord_user_id FROM police_chief_discord_links WHERE player_id=? AND guild_id=?", (player["id"], int(guild_id or 0))).fetchone()
    conn.execute("DELETE FROM police_chief_discord_links WHERE player_id=? AND guild_id=?", (player["id"], int(guild_id or 0)))
    if old:
        history_insert(conn, player["id"], guild_id, "discord_unlink", f"{old['discord_username'] or old['discord_user_id']}", "", "manual", actor_id, actor_name)
    conn.commit()
    return get_player_detail(conn, guild_id, player["player_name"])


def list_players(conn, guild_id=0, query="", limit=500):
    guild_id = int(guild_id or 0)
    params = [guild_id]
    where = "p.guild_id=?"
    if query:
        where += " AND (p.player_name LIKE ? OR p.alliance_rank LIKE ? OR p.status LIKE ? OR p.notes LIKE ? OR p.tags LIKE ?)"
        q = f"%{query}%"
        params.extend([q, q, q, q, q])
    params.append(int(limit))
    return [dict(row) for row in conn.execute(
        f"""
        SELECT p.*, l.discord_user_id, l.discord_username, l.confidence AS discord_confidence
        FROM police_chief_players p
        LEFT JOIN police_chief_discord_links l ON l.player_id=p.id AND l.guild_id=p.guild_id
        WHERE {where}
        ORDER BY COALESCE(p.power, 0) DESC, p.player_name COLLATE NOCASE
        LIMIT ?
        """,
        params,
    ).fetchall()]


def get_player_detail(conn, guild_id, name):
    base = get_player(conn, guild_id, name)
    if not base:
        return None
    link = rowdict(conn.execute("SELECT * FROM police_chief_discord_links WHERE player_id=? AND guild_id=?", (base["id"], int(guild_id or 0))).fetchone())
    hist = [dict(r) for r in conn.execute("SELECT * FROM police_chief_history WHERE player_id=? ORDER BY changed_at DESC, id DESC LIMIT 50", (base["id"],)).fetchall()]
    base["discord_link"] = link
    base["history"] = hist
    return base


def delete_player(conn, guild_id, name):
    player = get_player(conn, guild_id, name)
    if not player:
        raise ValueError("Police Chief player not found.")
    conn.execute("DELETE FROM police_chief_discord_links WHERE player_id=?", (player["id"],))
    conn.execute("DELETE FROM police_chief_history WHERE player_id=?", (player["id"],))
    conn.execute("DELETE FROM police_chief_players WHERE id=?", (player["id"],))
    conn.commit()


def add_import(conn, guild_id, import_type, filename="", stored_path="", content_type="", uploader=None, uploader_id=None, uploader_name=None, notes=""):
    import_type = str(import_type or "").strip().lower()
    if import_type not in IMPORT_TYPES:
        raise ValueError("Import type must be alliance or profile.")
    uploader_id, uploader_name = actor_info(uploader, uploader_id, uploader_name)
    conn.execute(
        """
        INSERT INTO police_chief_imports
        (guild_id, import_type, status, original_filename, stored_path, content_type, uploaded_by_id, uploaded_by_name, uploaded_at, notes)
        VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?)
        """,
        (int(guild_id or 0), import_type, str(filename or "")[:240], str(stored_path or "")[:500], str(content_type or "")[:120], uploader_id, uploader_name, now_ts(), str(notes or "")[:2000]),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_imports(conn, guild_id=0, limit=100):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM police_chief_imports WHERE guild_id=? ORDER BY uploaded_at DESC, id DESC LIMIT ?",
        (int(guild_id or 0), int(limit)),
    ).fetchall()]


def update_import_status(conn, import_id, status, notes=None):
    status = str(status or "pending").strip().lower()
    if status not in {"pending", "confirmed", "rejected", "needs_review", "processed"}:
        raise ValueError("Invalid import status.")
    if notes is None:
        conn.execute("UPDATE police_chief_imports SET status=? WHERE id=?", (status, int(import_id)))
    else:
        conn.execute("UPDATE police_chief_imports SET status=?, notes=? WHERE id=?", (status, str(notes or "")[:2000], int(import_id)))
    conn.commit()


def save_upload_file(file_bytes: bytes, filename: str) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", filename or "upload.png")[:120]
    path = UPLOAD_DIR / f"{now_ts()}_{safe}"
    path.write_bytes(file_bytes)
    return str(path)


def roster_payload(conn, guild_id=0):
    ensure_schema(conn)
    players = list_players(conn, guild_id=guild_id, limit=1000)
    imports = list_imports(conn, guild_id=guild_id, limit=100)
    total_power = sum(int(p.get("power") or 0) for p in players)
    linked = sum(1 for p in players if p.get("discord_user_id"))
    return {
        "guild_id": int(guild_id or 0),
        "players": players,
        "imports": imports,
        "counts": {
            "players": len(players),
            "linked": linked,
            "unlinked": len(players) - linked,
            "total_power": total_power,
            "pending_imports": sum(1 for row in imports if row.get("status") == "pending"),
        },
        "statuses": sorted(STATUS_VALUES),
    }


def format_player(player: Dict[str, Any]) -> str:
    if not player:
        return "Police Chief player not found."
    lines = ["POLICE CHIEF PLAYER", f"Player: {player.get('player_name')}"]
    if player.get("power") is not None:
        lines.append(f"Power: {int(player.get('power')):,}")
    if player.get("alliance_rank"):
        lines.append(f"Alliance Rank: {player.get('alliance_rank')}")
    if player.get("alliance_name"):
        lines.append(f"Alliance: {player.get('alliance_name')}")
    lines.append(f"Status: {player.get('status') or 'unknown'}")
    link = player.get("discord_link") or {}
    if link.get("discord_user_id"):
        lines.append(f"Discord: {link.get('discord_username') or link.get('discord_user_id')}")
    if player.get("notes"):
        lines.append(f"Notes: {player.get('notes')[:300]}")
    return "\n".join(lines)
