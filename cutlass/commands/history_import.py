import asyncio
import re

import discord

_ACTIVE_IMPORTS = {}
_STOP_REQUESTS = set()
_ACTIVE_SERVER_IMPORTS = {}
_SERVER_STOP_REQUESTS = set()


def _server_key(guild_id):
    return int(guild_id)


def _is_server_import_command(command):
    return (
        command.startswith("!cutlass history import server")
        or command.startswith("!cutlass history import all server")
        or command.startswith("!cutlass history import whole server")
    )


def _is_server_stop_command(command):
    return (
        command.startswith("!cutlass history import stop server")
        or command.startswith("!cutlass history import server stop")
    )


def _readable_history_channels(guild):
    bot_member = guild.me
    channels = []
    for channel in getattr(guild, "text_channels", []):
        perms = channel.permissions_for(bot_member) if bot_member else None
        if perms and perms.view_channel and perms.read_message_history:
            channels.append(channel)
    return sorted(channels, key=lambda channel: (getattr(channel, "position", 0), channel.id))


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


def _format_server_summary(results, processed_channels, skipped_channels, *, stopped):
    total_imported = sum(int(item.get("imported") or 0) for item in results if item)
    total_scanned = sum(int(item.get("scanned") or 0) for item in results if item)
    title = "**SERVER HISTORY IMPORT STOPPED**" if stopped else "**SERVER HISTORY IMPORT COMPLETE**"
    lines = [
        title,
        "Channels processed: " + str(processed_channels),
        "Channels skipped: " + str(skipped_channels),
        "Messages imported: " + str(total_imported),
        "Messages scanned: " + str(total_scanned),
        "",
    ]
    sorted_results = sorted(
        [item for item in results if item],
        key=lambda item: int(item.get("imported") or 0),
        reverse=True,
    )
    for item in sorted_results[:20]:
        lines.append(
            "• "
            + str(item.get("mention") or item.get("channel_name") or item.get("channel_id"))
            + " — "
            + str(item.get("status") or "unknown")
            + " | imported "
            + str(item.get("imported") or 0)
            + " / scanned "
            + str(item.get("scanned") or 0)
        )
    if len(sorted_results) > 20:
        lines.append("• ...and " + str(len(sorted_results) - 20) + " more channel(s).")
    return "\n".join(lines)[:1900]


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
    announce=True,
):
    key = _key(target_channel.guild.id, target_channel.id)
    imported = 0
    scanned = 0
    last_seen_id = None
    final_message = ""

    def result(status, message=""):
        return {
            "channel_id": target_channel.id,
            "channel_name": getattr(target_channel, "name", str(target_channel.id)),
            "mention": target_channel.mention,
            "status": status,
            "imported": imported,
            "scanned": scanned,
            "last_message_id": last_seen_id,
            "message": message,
        }

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
                final_message = "History import stopped for " + target_channel.mention + ". Imported " + str(imported) + " new messages this run."
                if announce:
                    await status_channel.send(final_message)
                return result("stopped", final_message)

            remaining = None if limit is None else limit - scanned
            if remaining is not None and remaining <= 0:
                await upsert_import_progress(
                    target_channel.guild.id,
                    target_channel.id,
                    status="paused",
                )
                final_message = "History import paused for " + target_channel.mention + ". Limit reached. Imported " + str(imported) + " new messages this run. Run the command again to continue."
                if announce:
                    await status_channel.send(final_message)
                return result("paused", final_message)

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
                final_message = "History import complete for " + target_channel.mention + ". Imported " + str(imported) + " new messages this run."
                if announce:
                    await status_channel.send(final_message)
                return result("complete", final_message)

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
        final_message = "I cannot read message history in " + target_channel.mention + ". Check my channel permissions."
        if announce:
            await status_channel.send(final_message)
        return result("failed", final_message)
    except Exception as error:
        await upsert_import_progress(
            target_channel.guild.id,
            target_channel.id,
            status="failed",
        )
        final_message = "History import failed for " + target_channel.mention + ": " + repr(error)[:500]
        if announce:
            await status_channel.send(final_message)
        return result("failed", final_message)
    finally:
        _ACTIVE_IMPORTS.pop(key, None)
        _STOP_REQUESTS.discard(key)


async def _import_server_history(
    status_channel,
    guild,
    *,
    limit,
    save_message,
    ensure_user_profile,
    ensure_relationship,
    touch_member_seen,
    get_import_progress,
    upsert_import_progress,
):
    server_key = _server_key(guild.id)
    channels = _readable_history_channels(guild)
    imported_channels = 0
    skipped_channels = 0
    results = []

    try:
        if not channels:
            await status_channel.send("I cannot find any readable text channels with message-history permission in this server.")
            return

        for target_channel in channels:
            if server_key in _SERVER_STOP_REQUESTS:
                await status_channel.send(_format_server_summary(results, imported_channels, skipped_channels, stopped=True))
                return

            key = _key(guild.id, target_channel.id)
            if key in _ACTIVE_IMPORTS:
                skipped_channels += 1
                continue

            task = asyncio.create_task(
                _import_channel_history(
                    status_channel,
                    target_channel,
                    limit=limit,
                    save_message=save_message,
                    ensure_user_profile=ensure_user_profile,
                    ensure_relationship=ensure_relationship,
                    touch_member_seen=touch_member_seen,
                    get_import_progress=get_import_progress,
                    upsert_import_progress=upsert_import_progress,
                    announce=False,
                )
            )
            _ACTIVE_IMPORTS[key] = task
            imported_channels += 1
            channel_result = await task
            results.append(channel_result)
            await asyncio.sleep(0.5)

        await status_channel.send(_format_server_summary(results, imported_channels, skipped_channels, stopped=False))
    finally:
        _ACTIVE_SERVER_IMPORTS.pop(server_key, None)
        _SERVER_STOP_REQUESTS.discard(server_key)


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

    if command.startswith("!cutlass history import status"):
        server_key = _server_key(message.guild.id)
        server_note = ""
        if server_key in _ACTIVE_SERVER_IMPORTS:
            server_note = "\nServer-wide import: running"

        rows = await list_import_progress(message.guild.id)
        if not rows and not server_note:
            await message.reply("No history imports recorded for this server.", mention_author=False)
            return True
        lines = ["**HISTORY IMPORT STATUS**" + server_note]
        for row in rows[:15]:
            lines.append(_format_progress_row(row, message.guild.get_channel))
        await message.reply("\n".join(lines)[:1900], mention_author=False)
        return True

    if _is_server_stop_command(command):
        server_key = _server_key(message.guild.id)
        if server_key in _ACTIVE_SERVER_IMPORTS:
            _SERVER_STOP_REQUESTS.add(server_key)
            for active_guild_id, active_channel_id in list(_ACTIVE_IMPORTS):
                if active_guild_id == message.guild.id:
                    _STOP_REQUESTS.add((active_guild_id, active_channel_id))
                    await upsert_import_progress(message.guild.id, active_channel_id, status="stopping")
            await message.reply("Stopping server-wide history import after current channel/batch.", mention_author=False)
        else:
            await message.reply("No server-wide history import is currently running.", mention_author=False)
        return True

    if _is_server_import_command(command):
        server_key = _server_key(message.guild.id)
        if server_key in _ACTIVE_SERVER_IMPORTS:
            await message.reply("A server-wide history import is already running. Use `!c history import status`.", mention_author=False)
            return True
        limit = _parse_limit(content)
        channels = _readable_history_channels(message.guild)
        task = asyncio.create_task(
            _import_server_history(
                message.channel,
                message.guild,
                limit=limit,
                save_message=save_message,
                ensure_user_profile=ensure_user_profile,
                ensure_relationship=ensure_relationship,
                touch_member_seen=touch_member_seen,
                get_import_progress=get_import_progress,
                upsert_import_progress=upsert_import_progress,
            )
        )
        _ACTIVE_SERVER_IMPORTS[server_key] = task
        limit_text = "all available history per channel" if limit is None else str(limit) + " messages max per channel"
        await message.reply(
            "Started server-wide history import across " + str(len(channels)) + " readable channel(s) (" + limit_text + "). Use `!c history import status` or `!c history import stop server`.",
            mention_author=False,
        )
        return True

    target_channel = _resolve_channel(message)
    key = _key(message.guild.id, target_channel.id)

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
