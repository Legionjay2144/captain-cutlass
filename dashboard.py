import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DB_PATH = os.getenv("DATABASE_PATH", "/app/data/captain.db")
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8787"))
DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN", "").strip()

TEXT_LIMIT = 500
LIST_LIMIT = 200


def db_connect():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    uri = "file:" + DB_PATH + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
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


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


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
    ):
        if table_exists(conn, table):
            for row in conn.execute(f"SELECT DISTINCT guild_id FROM {table}"):
                ids.add(row[0])
    return sorted(ids)


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
        "captured_ships": count("captured_ships"),
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
            COALESCE(cw.repair_hull_total, 0) AS repair_hull_total
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
                COALESCE(cw.repair_hull_total, 0) AS repair_hull_total
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


def guild_summary(conn, guild_id):
    settings = one(conn, "SELECT * FROM guild_settings WHERE guild_id=?", (guild_id,)) if table_exists(conn, "guild_settings") else None
    ship = one(conn, "SELECT * FROM ships WHERE guild_id=?", (guild_id,)) if table_exists(conn, "ships") else None
    return {
        "guild_id": guild_id,
        "settings": settings,
        "ship": ship,
        "counts": dashboard_counts(conn, guild_id),
    }


def overview_payload():
    with db_connect() as conn:
        return {
            "database": DB_PATH,
            "guilds": [guild_summary(conn, guild_id) for guild_id in guild_ids(conn)],
        }


def guild_payload(guild_id):
    with db_connect() as conn:
        payload = guild_summary(conn, guild_id)
        payload.update(
            {
                "members": member_rows(conn, guild_id),
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


def member_payload(guild_id, user_id):
    with db_connect() as conn:
        profile = one(conn, "SELECT * FROM user_profiles WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "user_profiles") else None
        relationship = one(conn, "SELECT * FROM relationships WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "relationships") else None
        economy = one(conn, "SELECT * FROM economy WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "economy") else None
        contribution = one(conn, "SELECT * FROM ship_contributions WHERE guild_id=? AND user_id=?", (guild_id, user_id)) if table_exists(conn, "ship_contributions") else None
        return {
            "guild_id": guild_id,
            "user_id": user_id,
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
        }


INDEX_HTML = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Captain Cutlass Dashboard</title>
  <style>
    :root { color-scheme: dark; --bg:#08111f; --panel:#111c2e; --panel2:#172640; --text:#e8f0ff; --muted:#9fb0c9; --gold:#f6c453; --red:#ff6b6b; --green:#5ee0a0; --blue:#7db7ff; --line:#263a5d; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; background: radial-gradient(circle at top left, #142647, var(--bg) 50%); color:var(--text); }
    header { padding:28px clamp(16px,4vw,48px); border-bottom:1px solid var(--line); background:rgba(8,17,31,.72); position:sticky; top:0; backdrop-filter: blur(12px); z-index:3; }
    h1 { margin:0; font-size: clamp(26px, 4vw, 44px); letter-spacing:-.03em; }
    h2 { margin:0 0 14px; font-size:20px; }
    h3 { margin:0 0 8px; font-size:16px; color:var(--gold); }
    .sub { color:var(--muted); margin-top:6px; }
    main { padding:24px clamp(16px,4vw,48px) 60px; display:grid; gap:20px; }
    .toolbar { display:flex; gap:12px; flex-wrap:wrap; align-items:center; }
    select, input, button { background:var(--panel); color:var(--text); border:1px solid var(--line); border-radius:12px; padding:10px 12px; font:inherit; }
    button { cursor:pointer; background:#1b3358; }
    button:hover { border-color:var(--gold); }
    .grid { display:grid; grid-template-columns: repeat(12, 1fr); gap:16px; }
    .card { background:linear-gradient(180deg, rgba(23,38,64,.96), rgba(14,25,43,.96)); border:1px solid var(--line); border-radius:18px; padding:18px; box-shadow:0 12px 40px rgba(0,0,0,.25); }
    .span-12 { grid-column: span 12; } .span-8 { grid-column: span 8; } .span-6 { grid-column: span 6; } .span-4 { grid-column: span 4; } .span-3 { grid-column: span 3; }
    .stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:10px; }
    .stat { background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.07); border-radius:14px; padding:12px; }
    .stat b { display:block; font-size:24px; color:var(--gold); }
    .stat span { color:var(--muted); font-size:13px; }
    table { width:100%; border-collapse:collapse; }
    th,td { padding:10px 8px; border-bottom:1px solid rgba(255,255,255,.08); text-align:left; vertical-align:top; }
    th { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }
    tr.clickable { cursor:pointer; }
    tr.clickable:hover { background:rgba(246,196,83,.08); }
    .pill { display:inline-block; border:1px solid var(--line); background:rgba(255,255,255,.05); border-radius:999px; padding:3px 8px; color:var(--muted); font-size:12px; margin:2px; }
    .bar { height:10px; background:#243855; border-radius:999px; overflow:hidden; }
    .bar > i { display:block; height:100%; background:linear-gradient(90deg,var(--green),var(--gold)); }
    .muted { color:var(--muted); } .gold { color:var(--gold); } .green { color:var(--green); } .red { color:var(--red); }
    .list { display:grid; gap:8px; max-height:440px; overflow:auto; padding-right:4px; }
    .item { padding:10px 12px; background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.07); border-radius:12px; }
    .item small { color:var(--muted); display:block; margin-top:4px; }
    dialog { width:min(980px, calc(100vw - 28px)); border:1px solid var(--line); border-radius:18px; background:#0e192b; color:var(--text); padding:0; }
    dialog::backdrop { background:rgba(0,0,0,.6); backdrop-filter: blur(4px); }
    .modal-head { display:flex; justify-content:space-between; gap:12px; align-items:center; padding:18px; border-bottom:1px solid var(--line); }
    .modal-body { padding:18px; max-height:75vh; overflow:auto; }
    pre { white-space:pre-wrap; background:rgba(0,0,0,.18); border:1px solid var(--line); padding:12px; border-radius:12px; color:#dbe8ff; }
    @media (max-width: 900px) { .span-8,.span-6,.span-4,.span-3 { grid-column:span 12; } }
  </style>
</head>
<body>
<header>
  <h1>Captain Cutlass Dashboard</h1>
  <div class="sub">Read-only view of crew personality profiles, Living Ship stats, world history, jobs, and achievements.</div>
</header>
<main>
  <section class="toolbar card">
    <label>Server <select id="guildSelect"></select></label>
    <input id="memberSearch" placeholder="Filter crew by name, relationship, summary…" size="42">
    <button id="refreshBtn">Refresh</button>
    <span id="status" class="muted"></span>
  </section>
  <section id="content" class="grid"></section>
</main>
<dialog id="memberDialog"><div class="modal-head"><h2 id="memberTitle"></h2><button onclick="memberDialog.close()">Close</button></div><div id="memberBody" class="modal-body"></div></dialog>
<script>
const $ = id => document.getElementById(id);
let overview = null;
let guild = null;
let selectedGuild = null;

function esc(value) { return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
function num(value) { return Number(value || 0).toLocaleString(); }
function pct(value, max=100) { const n = Math.max(0, Math.min(100, Number(value || 0) / max * 100)); return n.toFixed(0); }
async function api(path) { const res = await fetch(path); if (!res.ok) throw new Error(await res.text()); return await res.json(); }
function card(title, body, cls='span-12') { return `<div class="card ${cls}"><h2>${esc(title)}</h2>${body}</div>`; }
function stat(label, value) { return `<div class="stat"><b>${esc(value)}</b><span>${esc(label)}</span></div>`; }
function item(text, meta='') { return `<div class="item">${esc(text)}${meta ? `<small>${esc(meta)}</small>` : ''}</div>`; }

async function loadOverview() {
  $('status').textContent = 'Loading…';
  overview = await api('/api/overview');
  const select = $('guildSelect');
  select.innerHTML = overview.guilds.map(g => `<option value="${g.guild_id}">${g.guild_id} — ${(g.ship && esc(g.ship.name)) || 'No ship'}</option>`).join('');
  selectedGuild = select.value || (overview.guilds[0] && overview.guilds[0].guild_id);
  if (selectedGuild) await loadGuild(selectedGuild);
  $('status').textContent = 'Ready';
}

async function loadGuild(guildId) {
  selectedGuild = guildId;
  $('status').textContent = 'Loading server…';
  guild = await api(`/api/guild/${guildId}`);
  renderGuild();
  $('status').textContent = `Loaded ${guildId}`;
}

function renderGuild() {
  const ship = guild.ship || {};
  const settings = guild.settings || {};
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
    ${card('Server Overview', `
      <div class="stats">
        ${stat('Mood', settings.mood || 'unset')}${stat('Quiet', settings.quiet ? 'On' : 'Off')}${stat('Chronicle', settings.chronicle_enabled ? 'On' : 'Off')}${stat('Members', counts.members || 0)}${stat('Profiles', counts.profiles || 0)}${stat('Achievements', counts.achievements || 0)}${stat('Discoveries', counts.discoveries || 0)}${stat('History Entries', counts.ship_history || 0)}${stat('Crew Work Runs', counts.crew_work_runs || 0)}
      </div>
    `, 'span-8')}
    ${card('Crew Personality Profiles', memberTable(members), 'span-12')}
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

function filterMembers(members) {
  const q = $('memberSearch').value.trim().toLowerCase();
  if (!q) return members;
  return members.filter(m => JSON.stringify(m).toLowerCase().includes(q));
}

function memberTable(members) {
  if (!members.length) return '<p class="muted">No members found.</p>';
  return `<table><thead><tr><th>Crew</th><th>Relationship</th><th>Profile</th><th>Doubloons</th><th>Signals</th></tr></thead><tbody>${members.map(m => `
    <tr class="clickable" onclick="openMember('${m.guild_id}','${m.user_id}')">
      <td><b>${esc(m.username || m.user_id)}</b><br><span class="muted">${esc(m.user_id)}</span></td>
      <td>${esc(m.relationship_type || '')}<br><span class="pill">Familiarity ${num(m.familiarity)}</span>${m.nickname ? `<span class="pill">${esc(m.nickname)}</span>` : ''}</td>
      <td>${esc(m.summary || m.opinion || 'No profile summary yet.')}</td>
      <td>${num(m.doubloons)}</td>
      <td><span class="pill">${num(m.memory_count)} memories</span><span class="pill">${num(m.joke_count)} jokes</span><span class="pill">${num(m.achievement_count)} achievements</span><span class="pill">${num(m.work_runs)} jobs</span></td>
    </tr>`).join('')}</tbody></table>`;
}

function simpleRows(list, keys) {
  if (!list || !list.length) return '<p class="muted">None yet.</p>';
  return `<table><thead><tr>${keys.map(k => `<th>${esc(k.replaceAll('_',' '))}</th>`).join('')}</tr></thead><tbody>${list.map(row => `<tr>${keys.map(k => `<td>${esc(row[k] ?? '')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}
function historyList(list) { return `<div class="list">${(list||[]).map(x => item(x.content, `${x.event_type || ''} ${x.created_at || ''}`)).join('') || '<p class="muted">No history yet.</p>'}</div>`; }
function discoveryList(list) { return `<div class="list">${(list||[]).map(x => item(x.location_key, `by ${x.discovered_by_name || 'Unknown'} • visits ${x.visits || 0} • ${x.discovered_at || ''}`)).join('') || '<p class="muted">No discoveries yet.</p>'}</div>`; }
function voyageList(list) { return `<div class="list">${(list||[]).map(x => item(`${x.destination} — ${x.status}`, `${x.risk} • ${x.result || ''}`)).join('') || '<p class="muted">No voyages yet.</p>'}</div>`; }
function capturedList(list) { return `<div class="list">${(list||[]).map(x => item(`${x.enemy_name} — ${x.status}`, `by ${x.captured_by_name || 'Unknown'} • ${x.reward || 0} doubloons • ${x.xp_reward || 0} XP`)).join('') || '<p class="muted">No captured ships held.</p>'}</div>`; }

async function openMember(guildId, userId) {
  const data = await api(`/api/member/${guildId}/${userId}`);
  const profile = data.profile || {};
  const rel = data.relationship || {};
  const econ = data.economy || {};
  $('memberTitle').textContent = `${rel.username || profile.username || userId}`;
  $('memberBody').innerHTML = `
    <div class="grid">
      <div class="card span-6"><h3>Profile</h3><pre>${esc(JSON.stringify({profile, relationship: rel, economy: econ, ship_contribution: data.ship_contribution}, null, 2))}</pre></div>
      <div class="card span-6"><h3>Achievements</h3><div class="list">${data.achievements.map(a => item(a.achievement, `${a.description || ''} • ${a.awarded_at || ''}`)).join('') || '<p class="muted">None yet.</p>'}</div></div>
      <div class="card span-6"><h3>Memories</h3><div class="list">${data.memories.map(m => item(m.memory, `confidence ${m.confidence || 0} • ${m.created_at || ''}`)).join('') || '<p class="muted">None yet.</p>'}</div></div>
      <div class="card span-6"><h3>Running Jokes</h3><div class="list">${data.running_jokes.map(j => item(j.joke, j.created_at || '')).join('') || '<p class="muted">None yet.</p>'}</div></div>
      <div class="card span-6"><h3>Relationship Events</h3><div class="list">${data.relationship_events.map(e => item(e.event, `importance ${e.importance || 0} • ${e.created_at || ''}`)).join('') || '<p class="muted">None yet.</p>'}</div></div>
      <div class="card span-6"><h3>Crew Work</h3>${simpleRows(data.crew_work, ['job_label','total_runs','success_count','failure_count','rare_count','payout_total','repair_hull_total'])}</div>
    </div>`;
  memberDialog.showModal();
}

$('guildSelect').addEventListener('change', e => loadGuild(e.target.value));
$('refreshBtn').addEventListener('click', () => selectedGuild ? loadGuild(selectedGuild) : loadOverview());
$('memberSearch').addEventListener('input', () => guild && renderGuild());
loadOverview().catch(err => { $('status').textContent = 'Error: ' + err.message; console.error(err); });
</script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "CutlassDashboard/1.0"

    def log_message(self, fmt, *args):
        print("dashboard", self.address_string(), fmt % args)

    def authorized(self):
        if not DASHBOARD_TOKEN:
            return True
        header = self.headers.get("Authorization", "")
        query = parse_qs(urlparse(self.path).query)
        token = ""
        if header.startswith("Bearer "):
            token = header.removeprefix("Bearer ").strip()
        elif "token" in query:
            token = query["token"][0]
        return token == DASHBOARD_TOKEN

    def send_json(self, payload, status=200):
        body = json.dumps(payload, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, body, status=200):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.authorized():
            self.send_json({"error": "unauthorized"}, 401)
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        try:
            if path == "/":
                self.send_html(INDEX_HTML)
                return
            if path == "/api/health":
                self.send_json({"ok": True, "database": DB_PATH})
                return
            if path == "/api/overview":
                self.send_json(overview_payload())
                return
            if path.startswith("/api/guild/"):
                guild_id = safe_int(path.split("/")[-1])
                self.send_json(guild_payload(guild_id))
                return
            if path.startswith("/api/member/"):
                parts = path.split("/")
                guild_id = safe_int(parts[-2])
                user_id = safe_int(parts[-1])
                self.send_json(member_payload(guild_id, user_id))
                return
            self.send_json({"error": "not found"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)


if __name__ == "__main__":
    print(f"Captain Cutlass dashboard listening on {DASHBOARD_HOST}:{DASHBOARD_PORT}")
    print(f"Database: {DB_PATH}")
    if DASHBOARD_TOKEN:
        print("Dashboard token auth: enabled")
    else:
        print("Dashboard token auth: disabled; rely on localhost binding or firewall")
    ThreadingHTTPServer((DASHBOARD_HOST, DASHBOARD_PORT), DashboardHandler).serve_forever()
