from cutlass.world.crew_work import (
    format_jobs_board,
    format_work_summary,
    perform_job,
)


async def handle_work_command(
    message,
    content,
    command,
):
    """
    Handle crew work and job-board commands.

    Returns True when a work command was handled.
    Returns False when the command belongs to another subsystem.
    """

    normalized = command.strip().lower()
    lowered_content = content.strip().lower()

    if normalized not in {
        "!cutlass jobs",
        "!cutlass work",
        "!cutlass crew jobs",
        "!cutlass crew work",
    } and not normalized.startswith("!cutlass work ") and not normalized.startswith("!cutlass crew work "):
        return False

    if normalized in {
        "!cutlass jobs",
        "!cutlass crew jobs",
    }:
        await message.reply(
            await format_jobs_board(
                message.guild.id,
                message.author.id,
            ),
            mention_author=False,
        )
        return True

    if normalized in {
        "!cutlass work",
        "!cutlass crew work",
    }:
        await message.reply(
            await format_work_summary(
                message.guild.id,
                message.author.id,
            ),
            mention_author=False,
        )
        return True

    raw_job = ""

    if lowered_content.startswith("!cutlass crew work "):
        raw_job = content[len("!cutlass crew work "):].strip()
    elif lowered_content.startswith("!cutlass work "):
        raw_job = content[len("!cutlass work "):].strip()

    if not raw_job:
        await message.reply(
            "Use `!cutlass jobs` to see the board or `!cutlass work <job>` to take a shift.",
            mention_author=False,
        )
        return True

    ok, text = await perform_job(
        message.guild.id,
        message.author.id,
        message.author.display_name,
        raw_job,
    )

    await message.reply(
        text,
        mention_author=False,
    )

    return True
