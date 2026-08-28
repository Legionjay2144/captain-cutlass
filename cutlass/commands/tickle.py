import re

from cutlass.personality.tickle import (
    build_tickle_reaction,
    register_tickle_streak,
)


async def perform_tickle(
    message,
    *,
    get_tickle_count,
    increment_tickle_count,
    get_relationship,
    is_creator,
):
    guild_id = message.guild.id
    user_id = message.author.id

    accepted, streak = register_tickle_streak(
        guild_id,
        user_id,
    )

    if not accepted:
        await message.reply(
            "Easy there, ye rapid-fire menace! Give an old pirate a second!",
            mention_author=False,
        )
        return True

    lifetime_count = await increment_tickle_count(
        guild_id,
        user_id,
    )

    relationship = await get_relationship(
        guild_id,
        user_id,
    )

    familiarity = 0

    if relationship:
        familiarity = int(
            relationship["familiarity"] or 0
        )

    reaction = build_tickle_reaction(
        streak=streak,
        lifetime_count=lifetime_count,
        familiarity=familiarity,
        creator=is_creator(user_id),
    )

    await message.reply(
        reaction["text"][:1900],
        mention_author=False,
    )

    return True


async def handle_tickle_command(
    message,
    command,
    *,
    get_tickle_count,
    increment_tickle_count,
    get_relationship,
    is_creator,
):
    if command not in {
        "!cutlass tickle",
        "!cutlass tickle cutlass",
        "!cutlass tickle captain",
    }:
        return False

    return await perform_tickle(
        message,
        get_tickle_count=get_tickle_count,
        increment_tickle_count=increment_tickle_count,
        get_relationship=get_relationship,
        is_creator=is_creator,
    )


def is_natural_tickle_message(
    content
):
    """
    Detect clear conversational actions directed at Captain Cutlass.

    Deliberately conservative so normal discussion ABOUT tickling
    does not accidentally trigger the interaction system.
    """

    text = str(content or "").strip().lower()

    if not text:
        return False

    # Discord / roleplay formatting.
    text = text.replace("*", " ")
    text = re.sub(r"\s+", " ", text).strip()

    patterns = [
        r"^(?:i\s+)?tickle\s+(?:captain\s+)?cutlass[.!]*$",
        r"^(?:i\s+)?tickle\s+(?:the\s+)?captain[.!]*$",
        r"^tickles\s+(?:captain\s+)?cutlass[.!]*$",
        r"^tickles\s+(?:the\s+)?captain[.!]*$",
        r"^gives?\s+(?:captain\s+)?cutlass\s+(?:a\s+)?tickle[.!]*$",
        r"^gives?\s+(?:the\s+)?captain\s+(?:a\s+)?tickle[.!]*$",
        r"^pokes?\s+(?:captain\s+)?cutlass\s+and\s+tickles?\s+(?:him|them)[.!]*$",
    ]

    return any(
        re.fullmatch(
            pattern,
            text,
            flags=re.IGNORECASE
        )
        for pattern in patterns
    )
