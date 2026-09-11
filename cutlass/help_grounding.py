from cutlass.help.natural import (
    find_contextual_command_help,
    find_natural_command_help,
    is_contextual_help_followup,
)
from memory import get_recent_messages


async def resolve_authoritative_command_help(
    message,
    *,
    bot_user_display_name=None,
    bot_user_name=None,
):
    """
    Resolve natural gameplay command help directly from the
    authoritative Crew-safe command catalog.
    """

    natural_help = find_natural_command_help(message.content)
    if natural_help is not None:
        return natural_help

    if not is_contextual_help_followup(message.content):
        return None

    recent_for_help = await get_recent_messages(
        message.guild.id,
        message.channel.id,
        8,
    )

    recent_help_text = [
        str(row[1])
        for row in reversed(recent_for_help)
        if str(row[0]) not in {
            str(bot_user_display_name),
            str(bot_user_name),
        }
    ]

    return find_contextual_command_help(
        message.content,
        recent_help_text,
    )


def format_authoritative_command_reply(command, description):
    """
    Deterministic Priority 6A response.
    """

    return (
        "Aye, matey. For that, use **`"
        + command
        + "`** — "
        + description
        + "."
    )
