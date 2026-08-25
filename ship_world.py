import os
import random
from datetime import datetime, timezone, timedelta

import aiosqlite

DB_PATH = os.getenv("DATABASE_PATH", "/app/data/captain.db")

DESTINATIONS = {
    1: {"name": "Blacktooth Cove", "risk": "Low", "hours": 2, "supplies": 10, "reward": (100, 180), "xp": 100, "miles": 85},
    2: {"name": "Skullfin Island", "risk": "Medium", "hours": 6, "supplies": 25, "reward": (250, 450), "xp": 225, "miles": 240},
    3: {"name": "Devil's Maw", "risk": "Extreme", "hours": 12, "supplies": 40, "reward": (700, 1200), "xp": 500, "miles": 510},
}

UPGRADES = {
    "reinforced hull": {"label": "Reinforced Hull", "cost": 1000, "max_level": 3},
    "improved sails": {"label": "Improved Sails", "cost": 750, "max_level": 3},
    "expanded hold": {"label": "Expanded Hold", "cost": 800, "max_level": 3},
    "improved galley": {"label": "Improved Galley", "cost": 600, "max_level": 3},
    "crows nest": {"label": "Crow's Nest", "cost": 900, "max_level": 3},
}


def _now():
    return datetime.now(timezone.utc)


def _ts(dt=None):
    return (dt or _now()).strftime("%Y-%m-%d %H:%M:%S")


async def _db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def initialize_ship_world():
    db = await _db()
    try:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS ship_settings (
            guild_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            channel_id INTEGER DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS ships (
            guild_id INTEGER PRIMARY KEY,
            name TEXT DEFAULT 'The Rusty Kraken',
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            hull INTEGER DEFAULT 100,
            sails INTEGER DEFAULT 100,
            supplies INTEGER DEFAULT 100,
            morale INTEGER DEFAULT 100,
            treasury INTEGER DEFAULT 0,
            location TEXT DEFAULT 'Port Cutlass',
            voyages_completed INTEGER DEFAULT 0,
            distance_sailed INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS ship_upgrades (
            guild_id INTEGER NOT NULL,
            upgrade_key TEXT NOT NULL,
            level INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, upgrade_key)
        );
        CREATE TABLE IF NOT EXISTS ship_voyages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            destination TEXT NOT NULL,
            risk TEXT NOT NULL,
            supplies_cost INTEGER NOT NULL,
            reward_min INTEGER NOT NULL,
            reward_max INTEGER NOT NULL,
            xp_reward INTEGER NOT NULL,
            distance INTEGER NOT NULL,
            started_at DATETIME NOT NULL,
            completes_at DATETIME NOT NULL,
            status TEXT DEFAULT 'active',
            result TEXT DEFAULT '',
            completed_at DATETIME
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ship_active_voyage
        ON ship_voyages(guild_id) WHERE status = 'active';
        CREATE TABLE IF NOT EXISTS ship_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            event_type TEXT DEFAULT 'event',
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS ship_contributions (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT DEFAULT '',
            amount INTEGER DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, user_id)
        );
        """)
        await db.commit()
    finally:
        await db.close()


async def ensure_ship(guild_id):
    db = await _db()
    try:
        await db.execute("INSERT OR IGNORE INTO ship_settings (guild_id) VALUES (?)", (guild_id,))
        await db.execute("INSERT OR IGNORE INTO ships (guild_id) VALUES (?)", (guild_id,))
        await db.commit()
    finally:
        await db.close()


async def get_ship_settings(guild_id):
    await ensure_ship(guild_id)
    db = await _db()
    try:
        row = await (await db.execute("SELECT enabled, channel_id FROM ship_settings WHERE guild_id = ?", (guild_id,))).fetchone()
        return {"enabled": bool(row["enabled"]), "channel_id": int(row["channel_id"] or 0)}
    finally:
        await db.close()


async def set_ship_setting(guild_id, field, value):
    if field not in {"enabled", "channel_id"}:
        raise ValueError("Invalid ship setting")
    await ensure_ship(guild_id)
    db = await _db()
    try:
        await db.execute(f"UPDATE ship_settings SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE guild_id = ?", (value, guild_id))
        await db.commit()
    finally:
        await db.close()


async def get_ship(guild_id):
    await ensure_ship(guild_id)
    db = await _db()
    try:
        row = await (await db.execute("SELECT * FROM ships WHERE guild_id = ?", (guild_id,))).fetchone()
        return dict(row)
    finally:
        await db.close()


async def get_upgrade_levels(guild_id):
    db = await _db()
    try:
        rows = await (await db.execute("SELECT upgrade_key, level FROM ship_upgrades WHERE guild_id = ?", (guild_id,))).fetchall()
        return {r["upgrade_key"]: int(r["level"]) for r in rows}
    finally:
        await db.close()


def ship_caps(upgrades):
    return {
        "hull": 100 + 20 * upgrades.get("reinforced hull", 0),
        "supplies": 100 + 25 * upgrades.get("expanded hold", 0),
    }


def xp_needed(level):
    return 500 * max(1, level)


async def add_history(guild_id, content, event_type="event"):
    db = await _db()
    try:
        await db.execute("INSERT INTO ship_history (guild_id, event_type, content) VALUES (?, ?, ?)", (guild_id, event_type, content))
        await db.commit()
    finally:
        await db.close()


async def get_history(guild_id, limit=12):
    db = await _db()
    try:
        rows = await (await db.execute("SELECT content, created_at FROM ship_history WHERE guild_id = ? ORDER BY id DESC LIMIT ?", (guild_id, limit))).fetchall()
        return [(r["content"], r["created_at"]) for r in rows]
    finally:
        await db.close()


async def rename_ship(guild_id, name):
    name = " ".join(name.split()).strip()[:60]
    if len(name) < 2:
        raise ValueError("Ship name is too short.")
    await ensure_ship(guild_id)
    db = await _db()
    try:
        await db.execute("UPDATE ships SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE guild_id = ?", (name, guild_id))
        await db.commit()
    finally:
        await db.close()
    await add_history(guild_id, f"The ship was renamed **{name}**.", "rename")
    return name


async def donate(guild_id, user_id, username, amount, get_balance, change_balance):
    amount = int(amount)
    if amount < 1:
        return False, "Donation must be at least 1 doubloon."
    balance = await get_balance(guild_id, user_id)
    if balance < amount:
        return False, f"Ye only have **{balance} doubloons**."
    await change_balance(guild_id, user_id, -amount)
    db = await _db()
    try:
        await db.execute("UPDATE ships SET treasury = treasury + ?, updated_at = CURRENT_TIMESTAMP WHERE guild_id = ?", (amount, guild_id))
        await db.execute("""INSERT INTO ship_contributions (guild_id, user_id, username, amount) VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET username=excluded.username, amount=amount+excluded.amount, updated_at=CURRENT_TIMESTAMP""",
            (guild_id, user_id, username, amount))
        await db.commit()
    finally:
        await db.close()
    await add_history(guild_id, f"**{username}** donated **{amount} doubloons** to the ship treasury.", "donation")
    return True, f"**{username}** donated **{amount} doubloons** to the ship treasury."


async def top_contributors(guild_id, limit=5):
    db = await _db()
    try:
        rows = await (await db.execute("SELECT username, amount FROM ship_contributions WHERE guild_id = ? ORDER BY amount DESC LIMIT ?", (guild_id, limit))).fetchall()
        return [(r["username"], int(r["amount"])) for r in rows]
    finally:
        await db.close()


async def repair_ship(guild_id):
    ship = await get_ship(guild_id)
    upgrades = await get_upgrade_levels(guild_id)
    max_hull = ship_caps(upgrades)["hull"]
    if ship["hull"] >= max_hull and ship["sails"] >= 100:
        return False, "The ship is already in fighting shape."
    cost = 100
    if ship["treasury"] < cost:
        return False, f"Repairs cost **{cost} doubloons** from the ship treasury."
    db = await _db()
    try:
        await db.execute("UPDATE ships SET treasury=treasury-?, hull=MIN(?, hull+15), sails=MIN(100, sails+15), updated_at=CURRENT_TIMESTAMP WHERE guild_id=?", (cost, max_hull, guild_id))
        await db.commit()
    finally:
        await db.close()
    await add_history(guild_id, "The crew completed ship repairs: **Hull +15, Sails +15**.", "repair")
    return True, "Repairs complete. **Hull +15, Sails +15**. Treasury **-100 doubloons**."


async def buy_upgrade(guild_id, raw_key):
    key = raw_key.lower().strip().replace("crow's", "crows")
    if key not in UPGRADES:
        return False, "Unknown upgrade. Use `!cutlass ship upgrades`."
    ship = await get_ship(guild_id)
    levels = await get_upgrade_levels(guild_id)
    current = levels.get(key, 0)
    info = UPGRADES[key]
    if current >= info["max_level"]:
        return False, f"**{info['label']}** is already max level."
    cost = info["cost"] * (current + 1)
    if ship["treasury"] < cost:
        return False, f"That upgrade costs **{cost} doubloons** from the ship treasury."
    new_level = current + 1
    db = await _db()
    try:
        await db.execute("UPDATE ships SET treasury=treasury-?, updated_at=CURRENT_TIMESTAMP WHERE guild_id=?", (cost, guild_id))
        await db.execute("""INSERT INTO ship_upgrades (guild_id, upgrade_key, level) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, upgrade_key) DO UPDATE SET level=excluded.level""", (guild_id, key, new_level))
        if key == "reinforced hull":
            await db.execute("UPDATE ships SET hull=hull+20 WHERE guild_id=?", (guild_id,))
        elif key == "expanded hold":
            await db.execute("UPDATE ships SET supplies=supplies+25 WHERE guild_id=?", (guild_id,))
        await db.commit()
    finally:
        await db.close()
    text = f"**{info['label']} {new_level}** installed for **{cost} doubloons**."
    await add_history(guild_id, text, "upgrade")
    return True, text


async def get_active_voyage(guild_id):
    db = await _db()
    try:
        row = await (await db.execute("SELECT * FROM ship_voyages WHERE guild_id=? AND status='active' ORDER BY id DESC LIMIT 1", (guild_id,))).fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def start_voyage(guild_id, destination_number):
    await ensure_ship(guild_id)
    if await get_active_voyage(guild_id):
        return False, "The ship is already on a voyage."
    info = DESTINATIONS.get(int(destination_number))
    if not info:
        return False, "Choose destination **1, 2, or 3**."
    ship = await get_ship(guild_id)
    if ship["supplies"] < info["supplies"]:
        return False, f"Not enough supplies. This voyage needs **{info['supplies']}**."
    levels = await get_upgrade_levels(guild_id)
    speed = 1.0 - 0.05 * levels.get("improved sails", 0)
    duration = timedelta(hours=info["hours"] * max(0.75, speed))
    started = _now()
    completes = started + duration
    db = await _db()
    try:
        await db.execute("UPDATE ships SET supplies=supplies-?, updated_at=CURRENT_TIMESTAMP WHERE guild_id=?", (info["supplies"], guild_id))
        await db.execute("""INSERT INTO ship_voyages
            (guild_id,destination,risk,supplies_cost,reward_min,reward_max,xp_reward,distance,started_at,completes_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (guild_id, info["name"], info["risk"], info["supplies"], info["reward"][0], info["reward"][1], info["xp"], info["miles"], _ts(started), _ts(completes)))
        await db.commit()
    finally:
        await db.close()
    await add_history(guild_id, f"Voyage begun for **{info['name']}** ({info['risk']} risk).", "voyage_start")
    return True, {**info, "completes_at": _ts(completes)}


async def resolve_due_voyages():
    db = await _db()
    try:
        rows = await (await db.execute("SELECT * FROM ship_voyages WHERE status='active' AND datetime(completes_at) <= datetime('now') ORDER BY id")).fetchall()
    finally:
        await db.close()
    results = []
    for row in rows:
        result = await resolve_voyage(int(row["id"]))
        if result:
            results.append(result)
    return results


async def resolve_voyage(voyage_id):
    db = await _db()
    try:
        row = await (await db.execute("SELECT * FROM ship_voyages WHERE id=? AND status='active'", (voyage_id,))).fetchone()
        if not row:
            return None
        guild_id = int(row["guild_id"])
        levels_rows = await (await db.execute("SELECT upgrade_key, level FROM ship_upgrades WHERE guild_id=?", (guild_id,))).fetchall()
        levels = {r["upgrade_key"]: int(r["level"]) for r in levels_rows}
        reward = random.randint(int(row["reward_min"]), int(row["reward_max"]))
        lookout_bonus = levels.get("crows nest", 0) * 0.05
        galley = levels.get("improved galley", 0)
        roll = random.random()
        risk = row["risk"]
        damage_chance = {"Low": .15, "Medium": .35, "Extreme": .60}.get(risk, .25)
        damage_chance = max(.05, damage_chance - lookout_bonus)
        hull_damage = sails_damage = morale_change = 0
        event = "Calm seas carried the crew safely to port."
        if roll < damage_chance:
            base = {"Low": (3, 8), "Medium": (6, 15), "Extreme": (12, 28)}.get(risk, (5, 12))
            hull_damage = random.randint(*base)
            sails_damage = random.randint(max(1, base[0]-2), max(2, base[1]-3))
            morale_change = -max(1, random.randint(2, 8) - galley * 2)
            event = "Rough seas battered the ship before landfall."
        elif random.random() < .25 + lookout_bonus:
            bonus = random.randint(25, 100)
            reward += bonus
            event = f"The lookout spotted floating cargo worth **{bonus} extra doubloons**."
        ship = await (await db.execute("SELECT level,xp FROM ships WHERE guild_id=?", (guild_id,))).fetchone()
        level, xp = int(ship["level"]), int(ship["xp"]) + int(row["xp_reward"])
        levels_gained = 0
        while xp >= xp_needed(level):
            xp -= xp_needed(level)
            level += 1
            levels_gained += 1
        await db.execute("""UPDATE ships SET treasury=treasury+?, hull=MAX(0,hull-?), sails=MAX(0,sails-?),
            morale=MAX(0,MIN(100,morale+?)), xp=?, level=?, location=?, voyages_completed=voyages_completed+1,
            distance_sailed=distance_sailed+?, updated_at=CURRENT_TIMESTAMP WHERE guild_id=?""",
            (reward, hull_damage, sails_damage, morale_change, xp, level, row["destination"], int(row["distance"]), guild_id))
        result_text = f"Arrived at **{row['destination']}**. Treasury **+{reward}**. XP **+{row['xp_reward']}**. {event}"
        if hull_damage or sails_damage:
            result_text += f" Hull **-{hull_damage}**, Sails **-{sails_damage}**."
        if levels_gained:
            result_text += f" Ship reached **Level {level}**!"
        await db.execute("UPDATE ship_voyages SET status='completed', result=?, completed_at=CURRENT_TIMESTAMP WHERE id=?", (result_text, voyage_id))
        await db.execute("INSERT INTO ship_history (guild_id,event_type,content) VALUES (?,?,?)", (guild_id, "voyage_complete", result_text))
        await db.commit()
        return {"guild_id": guild_id, "destination": row["destination"], "text": result_text}
    finally:
        await db.close()




def discord_timestamp(timestamp_text):
    try:
        dt = datetime.strptime(
            timestamp_text,
            "%Y-%m-%d %H:%M:%S"
        )

        dt = dt.replace(
            tzinfo=timezone.utc
        )

        unix = int(
            dt.timestamp()
        )

        return (
            f"<t:{unix}:f> "
            f"(<t:{unix}:R>)"
        )

    except Exception:
        return timestamp_text + " UTC"


async def format_ship_status(guild_id):
    ship = await get_ship(guild_id)
    levels = await get_upgrade_levels(guild_id)
    caps = ship_caps(levels)
    voyage = await get_active_voyage(guild_id)
    status = "At Sea" if voyage else "Anchored"
    lines = [
        f"**{ship['name']}**",
        f"Level: **{ship['level']}** | XP: **{ship['xp']}/{xp_needed(ship['level'])}**",
        f"Status: **{status}**",
        f"Location: **En route to {voyage['destination']}**" if voyage else f"Location: **{ship['location']}**",
        "",
        f"Hull: **{ship['hull']}/{caps['hull']}**",
        f"Sails: **{ship['sails']}/100**",
        f"Supplies: **{ship['supplies']}/{caps['supplies']}**",
        f"Morale: **{ship['morale']}/100**",
        f"Treasury: **{ship['treasury']} doubloons**",
        "",
        f"Voyages Completed: **{ship['voyages_completed']}**",
        f"Distance Sailed: **{ship['distance_sailed']} nautical miles**",
    ]
    if voyage:
        lines += [
            "",
            f"Current Voyage: **{voyage['destination']}**",
            f"Expected Completion: **{discord_timestamp(voyage['completes_at'])}**"
        ]
    return "\n".join(lines)


def format_destinations():
    lines = ["**AVAILABLE VOYAGES**"]
    for number, d in DESTINATIONS.items():
        lines += ["", f"**{number}. {d['name']}**", f"Risk: {d['risk']} | Duration: {d['hours']}h | Supplies: {d['supplies']}", f"Reward: {d['reward'][0]}-{d['reward'][1]} doubloons | XP: {d['xp']}"]
    return "\n".join(lines)


async def format_upgrades(guild_id):
    levels = await get_upgrade_levels(guild_id)
    lines = ["**SHIP UPGRADES**"]
    for key, info in UPGRADES.items():
        level = levels.get(key, 0)
        if level >= info["max_level"]:
            cost = "MAX"
        else:
            cost = f"{info['cost'] * (level + 1)} doubloons"
        lines.append(f"- **{info['label']}** {level}/{info['max_level']} - {cost}")
    lines += ["", "Use `!cutlass ship upgrade <name>`." ]
    return "\n".join(lines)


# =========================================================
# Living Ship Combat API
# =========================================================

async def damage_ship(guild_id, amount):
    """
    Apply real combat damage to the Living Ship.

    Hull can never fall below zero.
    Returns the updated ship.
    """

    await ensure_ship(guild_id)

    amount = max(0, int(amount))

    db = await _db()

    try:
        await db.execute(
            """
            UPDATE ships
            SET hull = MAX(0, hull - ?),
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (amount, guild_id)
        )

        await db.commit()

    finally:
        await db.close()

    return await get_ship(guild_id)


async def reward_ship(
    guild_id,
    doubloons=0,
    xp_reward=0
):
    """
    Award the Living Ship treasury and XP.

    Handles multiple level-ups automatically.
    Returns reward and updated ship information.
    """

    await ensure_ship(guild_id)

    doubloons = max(0, int(doubloons))
    xp_reward = max(0, int(xp_reward))

    db = await _db()

    try:
        row = await (
            await db.execute(
                """
                SELECT level, xp
                FROM ships
                WHERE guild_id = ?
                """,
                (guild_id,)
            )
        ).fetchone()

        level = int(row["level"])
        xp = int(row["xp"]) + xp_reward

        levels_gained = 0

        while xp >= xp_needed(level):
            xp -= xp_needed(level)
            level += 1
            levels_gained += 1

        await db.execute(
            """
            UPDATE ships
            SET treasury = treasury + ?,
                xp = ?,
                level = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (
                doubloons,
                xp,
                level,
                guild_id
            )
        )

        await db.commit()

    finally:
        await db.close()

    ship = await get_ship(guild_id)

    return {
        "doubloons": doubloons,
        "xp": xp_reward,
        "levels_gained": levels_gained,
        "level": level,
        "ship": ship,
    }


async def combat_ship_status(guild_id):
    """
    Return combat-relevant Living Ship information.
    """

    ship = await get_ship(guild_id)
    upgrades = await get_upgrade_levels(guild_id)
    caps = ship_caps(upgrades)

    return {
        "name": ship["name"],
        "hull": int(ship["hull"]),
        "max_hull": int(caps["hull"]),
        "sails": int(ship["sails"]),
        "morale": int(ship["morale"]),
        "treasury": int(ship["treasury"]),
        "level": int(ship["level"]),
        "xp": int(ship["xp"]),
        "xp_needed": xp_needed(
            int(ship["level"])
        ),
        "disabled": int(ship["hull"]) <= 0,
    }


async def add_ship_treasury(
    guild_id,
    amount
):
    await ensure_ship(guild_id)

    amount = max(0, int(amount))

    db = await _db()

    try:
        await db.execute(
            """
            UPDATE ships
            SET treasury = treasury + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (amount, guild_id)
        )

        await db.commit()

    finally:
        await db.close()

    return await get_ship(guild_id)


async def add_ship_supplies(
    guild_id,
    amount
):
    await ensure_ship(guild_id)

    amount = max(0, int(amount))

    upgrades = await get_upgrade_levels(
        guild_id
    )

    max_supplies = ship_caps(
        upgrades
    )["supplies"]

    db = await _db()

    try:
        await db.execute(
            """
            UPDATE ships
            SET supplies = MIN(?, supplies + ?),
                updated_at = CURRENT_TIMESTAMP
            WHERE guild_id = ?
            """,
            (
                max_supplies,
                amount,
                guild_id
            )
        )

        await db.commit()

    finally:
        await db.close()

    return await get_ship(guild_id)
