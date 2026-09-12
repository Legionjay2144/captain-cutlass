import asyncio
import re

import discord

_ACTIVE_IMPORTS = {}
_STOP_REQUESTS = set()


def _key(guild_id, channel_id):
    return (int(guild_id), int(channel_id))


def _parse_limit(content):
    lowered = content.lower()
    if re.search(r"\ball\b", lowered):
        return None
    cleaned = re.sub(r"<#[0-9]+>", "", lowered)
    numbers = re.findall(r"\b\d{1,7}\b", cleaned)
    if not numbers:
        return 1000
    value = int(numbers[-1])
    return max(1, min(value, 5000))


def _resolve_channel(message):
    if message.channel_mentions:
        return message.channel_mentions[0]
    return message.channel


def _format_progress_row(row, channel_lookup=None):
    channel_id = int(row.get("channel_id") or 0)
    channel = channel_lookup(channel_id) if channel_lookup else None
    channel_name = channel.mention if channel else str(channel_id)
    return (
        channel_name
        + " — "
        + str(row.get("status") or "unknown")
        + " | imported "
        + str(row.get("imported_count") or 0)
        + " / scanned "
        + str(row.get("scanned_count") or 0)
        + " | last message "
        + str(row.get("last_message_id") or "none")
    )


async def _import_channel_history(
    status_channel,
    target_channel,
    *,
    limit,
    save_message,
    ensure_user_profile,
    ensure_relationship,
    touch_member_seen,
    get_import_progress,
    upsert_import_progress,
):
    key = _key(target_channel.guild.id, target_channel.id)
    imported = 0
    scanned = 0
    last_seen_id = None

    try:
        progress = await get_import_progress(target_channel.guild.id, target_channel.id)
        before = None
        if progress and progress.get("last_message_id"):
            before = discord.Object(id=int(progress["last_message_id"]))

        await upsert_import_progress(
            target_channel.guild.id,
            target_channel.id,
            status="running",
        )

        while True:
            if key in _STOP_REQUESTS:
                await upsert_import_progress(
                    target_channel.guild.id,
                    target_channel.id,
                    status="stopped",
                )
                await status_channel.send(
                    "History import stopped for " + target_channel.mention + ". Imported " + str(imported) + " new messages this run."
                )
                return

            remaining = None if limit is None else limit - scanned
            if remaining is not None and remaining <= 0:
                await upsert_import_progress(
                    target_channel.guild.id,
                    target_channel.id,
                    status="paused",
                )
                await status_channel.send(
                    "History import paused for " + target_channel.mention + ". Limit reached. Imported " + str(imported) + " new messages this run. Run the command again to continue."
                )
                return

            batch_limit = 100 if remaining is None else min(100, remaining)
            batch = []
            async for historic_message in target_channel.history(
                limit=batch_limit,
                before=before,
                oldest_first=False,
            ):
                batch.append(historic_message)

            if not batch:
                await upsert_import_progress(
                    target_channel.guild.id,
                    target_channel.id,
                    status="complete",
                )
                await status_channel.send(
                    "History import complete for " + target_channel.mention + ". Imported " + str(imported) + " new messages this run."
                )
                return

            batch_imported = 0
            batch_scanned = 0
            for historic_message in batch:
                last_seen_id = historic_message.id
                batch_scanned += 1
                scanned += 1

                if historic_message.author.bot:
                    continue

                content = (historic_message.content or "").strip()
                if not content:
                    continue

                await asyncio.gather(
                    ensure_user_profile(
                        target_channel.guild.id,
                        historic_message.author.id,
                        historic_message.author.display_name,
                    ),
                    ensure_relationship(
                        target_channel.guild.id,
                        historic_message.author.id,
                        historic_message.author.display_name,
                    ),
                    touch_member_seen(
                        target_channel.guild.id,
                        historic_message.author.id,
                        historic_message.author.display_name,
                    ),
                )

                inserted_id = await save_message(
                    target_channel.guild.id,
                    target_channel.id,
                    historic_message.author.id,
                    historic_message.author.display_name,
                    content,
                    discord_message_id=historic_message.id,
                    timestamp=historic_message.created_at.isoformat(),
                    imported=True,
                )
                if inserted_id:
                    imported += 1
                    batch_imported += 1

            before = discord.Object(id=int(last_seen_id)) if last_seen_id else before
            await upsert_import_progress(
                target_channel.guild.id,
                target_channel.id,
                status="running",
                last_message_id=last_seen_id,
                imported_delta=batch_imported,
                scanned_delta=batch_scanned,
            )

            await asyncio.sleep(0.25)

    except discord.Forbidden:
        await upsert_import_progress(
            target_channel.guild.id,
            target_channel.id,
            status="failed",
        )
        await status_channel.send("I cannot read message history in " + target_channel.mention + ". Check my channel permissions.")
    except Exception as error:
        await upsert_import_progress(
            target_channel.guild.id,
            target_channel.id,
            status="failed",
        )
        await status_channel.send("History import failed for " + target_channel.mention + ": " + repr(error)[:500])
    finally:
        _ACTIVE_IMPORTS.pop(key, None)
        _STOP_REQUESTS.discard(key)


async def handle_history_import_command(
    message,
    content,
    command,
    *,
    is_admin,
    save_message,
    ensure_user_profile,
    ensure_relationship,
    touch_member_seen,
    get_import_progress,
    upsert_import_progress,
    list_import_progress,
):
    if not command.startswith("!cutlass history import"):
        return False

    if not is_admin(message):
        await message.reply("Only the Admiralty may import channel history.", mention_author=False)
        return True

    target_channel = _resolve_channel(message)
    key = _key(message.guild.id, target_channel.id)

    if command.startswith("!cutlass history import status"):
        rows = await list_import_progress(message.guild.id)
        if not rows:
            await message.reply("No history imports recorded for this server.", mention_author=False)
            return True
        lines = ["**HISTORY IMPORT STATUS**"]
        for row in rows[:10]:
            lines.append(_format_progress_row(row, message.guild.get_channel))
        await message.reply("\n".join(lines)[:1900], mention_author=False)
        return True

    if command.startswith("!cutlass history import stop"):
        if key in _ACTIVE_IMPORTS:
            _STOP_REQUESTS.add(key)
            await upsert_import_progress(message.guild.id, target_channel.id, status="stopping")
            await message.reply("Stopping history import for " + target_channel.mention + " after the current batch.", mention_author=False)
        else:
            await upsert_import_progress(message.guild.id, target_channel.id, status="stopped")
            await message.reply("No active history import was running for " + target_channel.mention + ".", mention_author=False)
        return True

    if key in _ACTIVE_IMPORTS:
        await message.reply("A history import is already running for " + target_channel.mention + ". Use `!c history import status`.", mention_author=False)
        return True

    limit = _parse_limit(content)
    task = asyncio.create_task(
        _import_channel_history(
            message.channel,
            target_channel,
            limit=limit,
            save_message=save_message,
            ensure_user_profile=ensure_user_profile,
            ensure_relationship=ensure_relationship,
            touch_member_seen=touch_member_seen,
            get_import_progress=get_import_progress,
            upsert_import_progress=upsert_import_progress,
        )
    )
    _ACTIVE_IMPORTS[key] = task

    limit_text = "all available history" if limit is None else str(limit) + " messages max"
    await message.reply(
        "Started history import for " + target_channel.mention + " (" + limit_text + "). Use `!c history import status` to check progress or `!c history import stop #channel` to stop.",
        mention_author=False,
    )
    return True
