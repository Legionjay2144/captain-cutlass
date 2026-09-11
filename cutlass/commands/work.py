from cutlass.world.crew_work import (
    format_jobs_board,
    format_work_summary,
    perform_job,
)


def _discord_chunks(text, limit=1900):
    chunks = []
    current = []
    current_length = 0

    for line in str(text or "").splitlines():
        line_length = len(line) + 1

        if current and current_length + line_length > limit:
            chunks.append("\n".join(current))
            current = []
            current_length = 0

        if len(line) >= limit:
            if current:
                chunks.append("\n".join(current))
                current = []
                current_length = 0
            chunks.extend(
                line[index:index + limit]
                for index in range(0, len(line), limit)
            )
            continue

        current.append(line)
        current_length += line_length

    if current:
        chunks.append("\n".join(current))

    return chunks or [""]


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
        jobs_text = await format_jobs_board(
            message.guild.id,
            message.author.id,
        )
        chunks = _discord_chunks(jobs_text)
        await message.reply(chunks[0], mention_author=False)
        for chunk in chunks[1:]:
            await message.channel.send(chunk)
        return True

    if normalized in {
        "!cutlass work",
        "!cutlass crew work",
    }:
        summary_text = await format_work_summary(
            message.guild.id,
            message.author.id,
        )
        await message.reply(summary_text[:1900], mention_author=False)
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
