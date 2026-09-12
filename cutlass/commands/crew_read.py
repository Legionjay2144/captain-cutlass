import re

from cutlass.personality_read import (
    crew_read_label,
    infer_personality_type,
    summarize_evidence,
)
from memory import get_db


def _clean_discord_text(content, bot_user_id=None):
    text = str(content or "")
    if bot_user_id is not None:
        text = re.sub(rf"<@!?{bot_user_id}>", "", text)
    return text.strip()


def _extract_target_text(content):
    text = str(content or "").strip()
    for prefix in (
        "!cutlass crew read",
        "!cutlass profile read",
        "!cutlass read crew",
    ):
        if text.lower().startswith(prefix):
            return text[len(prefix):].strip()
    return ""


async def _resolve_target(message, content):
    if message.mentions:
        for member in message.mentions:
            if not member.bot:
                return member

    target_text = _extract_target_text(content)
    target_text = target_text.strip().strip("@").strip()
    if not target_text:
        return message.author

    if target_text.isdigit():
        member = message.guild.get_member(int(target_text))
        if member:
            return member

    target_lower = target_text.lower()
    exact = []
    partial = []
    for member in message.guild.members:
        if member.bot:
            continue
        names = {member.display_name.lower(), member.name.lower()}
        if target_lower in names:
            exact.append(member)
        elif any(target_lower in name for name in names):
            partial.append(member)

    if len(exact) == 1:
        return exact[0]
    if len(partial) == 1:
        return partial[0]
    return None


async def _fetch_text_rows(db, sql, params):
    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()
    return [row[0] for row in rows if row and row[0]]


async def build_global_crew_profile(user_id):
    db = await get_db()

    cursor = await db.execute(
        """
        SELECT DISTINCT guild_id
        FROM (
            SELECT guild_id, user_id FROM messages
            UNION SELECT guild_id, user_id FROM relationships
            UNION SELECT guild_id, user_id FROM user_profiles
            UNION SELECT guild_id, user_id FROM user_memories
            UNION SELECT guild_id, user_id FROM running_jokes
            UNION SELECT guild_id, user_id FROM achievements
        )
        WHERE user_id=?
        ORDER BY guild_id
        """,
        (user_id,),
    )
    guild_rows = await cursor.fetchall()
    guild_ids = [int(row[0]) for row in guild_rows if row and row[0] is not None]

    cursor = await db.execute(
        """
        SELECT username
        FROM (
            SELECT username, MAX(timestamp) AS seen_at FROM messages WHERE user_id=? GROUP BY username
            UNION ALL
            SELECT username, MAX(updated_at) AS seen_at FROM user_profiles WHERE user_id=? GROUP BY username
            UNION ALL
            SELECT username, MAX(updated_at) AS seen_at FROM relationships WHERE user_id=? GROUP BY username
        )
        WHERE username IS NOT NULL AND username != ''
        GROUP BY username
        ORDER BY MAX(seen_at) DESC
        LIMIT 5
        """,
        (user_id, user_id, user_id),
    )
    username_rows = await cursor.fetchall()
    usernames = [row[0] for row in username_rows if row and row[0]]

    signal_parts = []
    text_queries = (
        ("SELECT relationship_type || ' ' || COALESCE(nickname, '') || ' ' || COALESCE(opinion, '') FROM relationships WHERE user_id=? ORDER BY updated_at ASC", (user_id,)),
        ("SELECT summary FROM user_profiles WHERE user_id=? AND summary IS NOT NULL AND summary != '' ORDER BY updated_at ASC", (user_id,)),
        ("SELECT memory FROM user_memories WHERE user_id=? ORDER BY guild_id ASC, confidence DESC, id ASC", (user_id,)),
        ("SELECT joke FROM running_jokes WHERE user_id=? ORDER BY guild_id ASC, id ASC", (user_id,)),
        ("SELECT event FROM relationship_events WHERE user_id=? ORDER BY guild_id ASC, importance DESC, id ASC", (user_id,)),
        ("SELECT assessment || ' ' || sentiment || ' ' || COALESCE(tags, '') FROM message_assessments WHERE user_id=? ORDER BY guild_id ASC, assessed_at ASC", (user_id,)),
        ("SELECT achievement || CASE WHEN description IS NOT NULL AND description != '' THEN ': ' || description ELSE '' END FROM achievements WHERE user_id=? ORDER BY guild_id ASC, id ASC", (user_id,)),
        ("SELECT content FROM messages WHERE user_id=? AND content IS NOT NULL AND content != '' ORDER BY id ASC", (user_id,)),
    )

    for sql, params in text_queries:
        try:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
        except Exception:
            rows = []
        signal_parts.extend(str(row[0]) for row in rows if row and row[0])

    async def count(sql):
        try:
            cursor = await db.execute(sql, (user_id,))
            row = await cursor.fetchone()
        except Exception:
            return 0
        return int(row[0] or 0) if row else 0

    base = {
        "user_id": user_id,
        "guild_count": len(guild_ids),
        "guild_ids": guild_ids,
        "usernames": usernames,
        "message_count": await count("SELECT COUNT(*) FROM messages WHERE user_id=?"),
        "memory_count": await count("SELECT COUNT(*) FROM user_memories WHERE user_id=?"),
        "joke_count": await count("SELECT COUNT(*) FROM running_jokes WHERE user_id=?"),
        "achievement_count": await count("SELECT COUNT(*) FROM achievements WHERE user_id=?"),
        "assessed_messages": await count("SELECT COUNT(*) FROM message_assessments WHERE user_id=?"),
        "work_runs": await count("SELECT COALESCE(SUM(total_runs), 0) FROM crew_work_stats WHERE user_id=?"),
        "ship_contributed": await count("SELECT COALESCE(SUM(amount), 0) FROM ship_contributions WHERE user_id=?"),
    }
    base["messages_analyzed"] = base["message_count"]

    signal_text = "\n".join(signal_parts)
    return {
        "base": base,
        "personality_type": infer_personality_type(signal_text, base),
        "crew_read": crew_read_label(signal_text, base),
    }


async def build_member_crew_read(guild_id, user_id):
    db = await get_db()

    cursor = await db.execute(
        """
        SELECT r.username, r.relationship_type, r.familiarity, r.nickname, r.opinion,
               p.summary, p.gender, p.pronouns,
               COALESCE(e.doubloons, 0) AS doubloons,
               COALESCE(sc.amount, 0) AS ship_contributed
        FROM relationships r
        LEFT JOIN user_profiles p ON p.guild_id=r.guild_id AND p.user_id=r.user_id
        LEFT JOIN economy e ON e.guild_id=r.guild_id AND e.user_id=r.user_id
        LEFT JOIN ship_contributions sc ON sc.guild_id=r.guild_id AND sc.user_id=r.user_id
        WHERE r.guild_id=? AND r.user_id=?
        LIMIT 1
        """,
        (guild_id, user_id),
    )
    row = await cursor.fetchone()

    if row is None:
        cursor = await db.execute(
            """
            SELECT p.username, '' AS relationship_type, 0 AS familiarity, '' AS nickname, '' AS opinion,
                   p.summary, p.gender, p.pronouns,
                   COALESCE(e.doubloons, 0) AS doubloons,
                   COALESCE(sc.amount, 0) AS ship_contributed
            FROM user_profiles p
            LEFT JOIN economy e ON e.guild_id=p.guild_id AND e.user_id=p.user_id
            LEFT JOIN ship_contributions sc ON sc.guild_id=p.guild_id AND sc.user_id=p.user_id
            WHERE p.guild_id=? AND p.user_id=?
            LIMIT 1
            """,
            (guild_id, user_id),
        )
        row = await cursor.fetchone()

    base = dict(row) if row else {
        "username": str(user_id),
        "relationship_type": "Unknown",
        "familiarity": 0,
        "nickname": "",
        "opinion": "",
        "summary": "",
        "gender": None,
        "pronouns": None,
        "doubloons": 0,
        "ship_contributed": 0,
    }

    memories = await _fetch_text_rows(
        db,
        "SELECT memory FROM user_memories WHERE guild_id=? AND user_id=? ORDER BY confidence DESC, id DESC LIMIT 10",
        (guild_id, user_id),
    )
    jokes = await _fetch_text_rows(
        db,
        "SELECT joke FROM running_jokes WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 8",
        (guild_id, user_id),
    )
    events = await _fetch_text_rows(
        db,
        "SELECT event FROM relationship_events WHERE guild_id=? AND user_id=? ORDER BY importance DESC, id DESC LIMIT 8",
        (guild_id, user_id),
    )
    assessments = []
    try:
        cursor = await db.execute(
            """
            SELECT sentiment, assessment, tags, excerpt
            FROM message_assessments
            WHERE guild_id=? AND user_id=?
            ORDER BY assessed_at DESC, message_id DESC
            LIMIT 40
            """,
            (guild_id, user_id),
        )
        assessment_rows = await cursor.fetchall()
        assessments = [
            {
                "sentiment": row[0] or "neutral",
                "assessment": row[1] or "",
                "tags": row[2] or "",
                "excerpt": row[3] or "",
            }
            for row in assessment_rows
        ]
    except Exception:
        assessments = []
    achievements = await _fetch_text_rows(
        db,
        "SELECT achievement || CASE WHEN description IS NOT NULL AND description != '' THEN ': ' || description ELSE '' END FROM achievements WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 10",
        (guild_id, user_id),
    )
    cursor = await db.execute(
        "SELECT COUNT(*) FROM messages WHERE guild_id=? AND user_id=?",
        (guild_id, user_id),
    )
    message_count_row = await cursor.fetchone()
    total_message_count = int(message_count_row[0] or 0)
    messages = await _fetch_text_rows(
        db,
        "SELECT content FROM messages WHERE guild_id=? AND user_id=? AND content IS NOT NULL AND content != '' ORDER BY id ASC",
        (guild_id, user_id),
    )

    cursor = await db.execute(
        """
        SELECT COALESCE(SUM(total_runs), 0), COALESCE(SUM(payout_total), 0),
               COALESCE(SUM(repair_hull_total), 0), COALESCE(SUM(rare_count), 0)
        FROM crew_work_stats
        WHERE guild_id=? AND user_id=?
        """,
        (guild_id, user_id),
    )
    work_row = await cursor.fetchone()
    base["work_runs"] = int(work_row[0] or 0)
    base["work_payout"] = int(work_row[1] or 0)
    base["repair_hull_total"] = int(work_row[2] or 0)
    base["rare_count"] = int(work_row[3] or 0)
    base["memory_count"] = len(memories)
    base["joke_count"] = len(jokes)
    base["achievement_count"] = len(achievements)
    base["message_count"] = total_message_count
    base["messages_analyzed"] = len(messages)
    base["assessed_messages"] = len(assessments)
    base["positive_messages"] = len([item for item in assessments if item["sentiment"] == "positive"])
    base["mixed_messages"] = len([item for item in assessments if item["sentiment"] == "mixed"])
    base["concern_messages"] = len([item for item in assessments if item["sentiment"] == "concern"])
    base["neutral_messages"] = len([item for item in assessments if item["sentiment"] == "neutral"])

    signal_parts = []
    for key in ("relationship_type", "nickname", "opinion", "summary"):
        if base.get(key):
            signal_parts.append(str(base[key]))
    signal_parts.extend(memories)
    signal_parts.extend(jokes)
    signal_parts.extend(events)
    signal_parts.extend(
        item["assessment"] + " " + item["sentiment"] + " " + item["tags"]
        for item in assessments
    )
    signal_parts.extend(achievements)
    signal_parts.extend(messages)
    signal_text = "\n".join(signal_parts)

    personality_type = infer_personality_type(signal_text, base)
    read_label = crew_read_label(signal_text, base)

    global_profile = await build_global_crew_profile(user_id)

    return {
        "base": base,
        "personality_type": personality_type,
        "crew_read": read_label,
        "global_profile": global_profile,
        "memories": memories,
        "jokes": jokes,
        "events": events,
        "assessments": assessments,
        "achievements": achievements,
        "messages": messages,
    }


def format_member_crew_read(target, data):
    base = data["base"]
    personality = data["personality_type"]
    positive = summarize_evidence(
        list(data["achievements"])
        + list(data["events"])
        + list(data["memories"]),
        3,
    )
    assessed_positive = [
        item.get("excerpt") or item.get("assessment")
        for item in data.get("assessments", [])
        if item.get("sentiment") == "positive"
    ][:3]
    concern = [
        item.get("excerpt") or item.get("assessment")
        for item in data.get("assessments", [])
        if item.get("sentiment") == "concern"
    ][:3]

    lines = [
        "**CREW READ — " + target.display_name + "**",
        "Observed label: **" + data["crew_read"] + "**",
        "Personality type: **" + personality["label"] + "** (" + str(personality["confidence"]) + "% confidence)",
        "Traits: " + ", ".join(personality["traits"]),
        "Relationship: " + str(base.get("relationship_type") or "Unknown") + " | Familiarity: " + str(base.get("familiarity") or 0) + "/100",
        "Signals: " + str(personality["signal_count"]) + " local signals, " + str(base.get("messages_analyzed", 0)) + " lifetime messages analyzed in this server (" + str(base.get("message_count", 0)) + " stored), " + str(base.get("assessed_messages", 0)) + " imported messages assessed, " + str(base.get("memory_count", 0)) + " memories, " + str(base.get("joke_count", 0)) + " jokes, " + str(base.get("achievement_count", 0)) + " achievements, " + str(base.get("work_runs", 0)) + " work runs.",
    ]

    global_profile = data.get("global_profile") or {}
    global_base = global_profile.get("base") or {}
    global_personality = global_profile.get("personality_type") or {}
    if global_personality.get("label"):
        lines.extend([
            "",
            "Cross-server profile: **" + str(global_personality.get("label")) + "** (" + str(global_personality.get("confidence", 0)) + "% confidence)",
            "Seen in " + str(global_base.get("guild_count", 0)) + " server(s); analyzed " + str(global_base.get("message_count", 0)) + " stored messages, " + str(global_base.get("memory_count", 0)) + " memories, " + str(global_base.get("joke_count", 0)) + " jokes, " + str(global_base.get("achievement_count", 0)) + " achievements.",
        ])

    if personality["secondary"]:
        lines.append("Blended with: " + ", ".join(personality["secondary"][:3]))
    if personality["evidence"]:
        lines.append("Evidence keywords: " + ", ".join(personality["evidence"]))
    if base.get("opinion"):
        lines.append("Captain's note: " + str(base["opinion"])[:260])

    lines.append("")
    lines.append("Positive / useful signals:")
    positive_items = assessed_positive + positive
    if positive_items:
        lines.extend("• " + item for item in positive_items[:3])
    else:
        lines.append("• Not enough positive signal recorded yet.")

    lines.append("Concern signals:")
    if concern:
        lines.extend("• " + item for item in concern)
    else:
        lines.append("• No strong concern pattern found in stored observations.")

    lines.append("")
    lines.append("This is an observed chat/activity read, not a moral verdict or private-trait diagnosis.")

    return "\n".join(lines)[:1900]


async def handle_crew_read_command(message, content, command, *, is_admin):
    if not (
        command.startswith("!cutlass crew read")
        or command.startswith("!cutlass profile read")
        or command.startswith("!cutlass read crew")
    ):
        return False

    if not is_admin(message):
        await message.reply(
            "Only the Admiralty may request crew reads.",
            mention_author=False,
        )
        return True

    target = await _resolve_target(message, content)
    if target is None:
        await message.reply(
            "I couldn't identify that crewmate. Use `!c crew read @user`.",
            mention_author=False,
        )
        return True

    data = await build_member_crew_read(message.guild.id, target.id)
    await message.reply(
        format_member_crew_read(target, data),
        mention_author=False,
    )
    return True
