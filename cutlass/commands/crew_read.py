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

    signal_parts = []
    for key in ("relationship_type", "nickname", "opinion", "summary"):
        if base.get(key):
            signal_parts.append(str(base[key]))
    signal_parts.extend(memories)
    signal_parts.extend(jokes)
    signal_parts.extend(events)
    signal_parts.extend(achievements)
    signal_parts.extend(messages)
    signal_text = "\n".join(signal_parts)

    personality_type = infer_personality_type(signal_text, base)
    read_label = crew_read_label(signal_text, base)

    return {
        "base": base,
        "personality_type": personality_type,
        "crew_read": read_label,
        "memories": memories,
        "jokes": jokes,
        "events": events,
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
    concern = [
        text for text in summarize_evidence(
            list(data["events"]) + list(data["memories"]),
            8,
        )
        if any(term in text.lower() for term in ("drama", "mutiny", "threat", "kicked", "crushed", "trouble", "argument"))
    ][:3]

    lines = [
        "**CREW READ — " + target.display_name + "**",
        "Observed label: **" + data["crew_read"] + "**",
        "Personality type: **" + personality["label"] + "** (" + str(personality["confidence"]) + "% confidence)",
        "Traits: " + ", ".join(personality["traits"]),
        "Relationship: " + str(base.get("relationship_type") or "Unknown") + " | Familiarity: " + str(base.get("familiarity") or 0) + "/100",
        "Signals: " + str(personality["signal_count"]) + " total signals, " + str(base.get("messages_analyzed", 0)) + " lifetime messages analyzed (" + str(base.get("message_count", 0)) + " stored), " + str(base.get("memory_count", 0)) + " memories, " + str(base.get("joke_count", 0)) + " jokes, " + str(base.get("achievement_count", 0)) + " achievements, " + str(base.get("work_runs", 0)) + " work runs.",
    ]

    if personality["secondary"]:
        lines.append("Blended with: " + ", ".join(personality["secondary"][:3]))
    if personality["evidence"]:
        lines.append("Evidence keywords: " + ", ".join(personality["evidence"]))
    if base.get("opinion"):
        lines.append("Captain's note: " + str(base["opinion"])[:260])

    lines.append("")
    lines.append("Positive / useful signals:")
    if positive:
        lines.extend("• " + item for item in positive)
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
