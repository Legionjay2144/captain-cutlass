import re

from cutlass import police_chief as pc


def _usage():
    return """POLICE CHIEF TRACKER
!c pc player <name> — show a Police Chief player
!c pc top — top power roster
!c pc power <name> <power> — set player power
!c pc rank <name> <rank> — set alliance rank
!c pc status <name> <ally|neutral|enemy|watchlist|inactive|unknown>
!c pc note <name> | <note> — set notes
!c pc link <name> @DiscordUser — attach Discord profile
!c pc unlink <name> — remove Discord link
!c pc import alliance/profile — attach screenshots for dashboard review"""


def _db():
    return pc.connect()


def _split_name_value(text):
    parts = text.strip().rsplit(" ", 1)
    if len(parts) != 2:
        raise ValueError("Include a player name and value.")
    return parts[0].strip(), parts[1].strip()


def _split_note(text):
    if "|" not in text:
        raise ValueError("Use `!c pc note <player name> | <note>`.")
    name, note = text.split("|", 1)
    return name.strip(), note.strip()


async def handle_police_chief_command(message, content, command):
    if not (command == "!cutlass pc" or command.startswith("!cutlass pc ") or command == "!cutlass policechief" or command.startswith("!cutlass policechief ")):
        return False

    guild_id = message.guild.id if message.guild else 0
    raw = content.strip()
    lowered = command
    if lowered.startswith("!cutlass policechief"):
        args = raw[len("!cutlass policechief"):].strip()
    else:
        args = raw[len("!cutlass pc"):].strip()

    if not args or args.lower() in {"help", "commands"}:
        await message.reply(_usage(), mention_author=False)
        return True

    sub, _, rest = args.partition(" ")
    sub = sub.lower().strip()
    rest = rest.strip()

    try:
        with _db() as conn:
            if sub in {"player", "show", "whois"}:
                if not rest:
                    raise ValueError("Use `!c pc player <name>`.")
                detail = pc.get_player_detail(conn, guild_id, rest)
                await message.reply(pc.format_player(detail), mention_author=False)
                return True

            if sub == "top":
                players = pc.list_players(conn, guild_id=guild_id, limit=10)
                if not players:
                    await message.reply("No Police Chief players tracked yet.", mention_author=False)
                    return True
                lines = ["POLICE CHIEF POWER TOP 10"]
                for idx, row in enumerate(players, 1):
                    power = int(row.get("power") or 0)
                    rank = f" • {row.get('alliance_rank')}" if row.get("alliance_rank") else ""
                    lines.append(f"{idx}. {row.get('player_name')} — {power:,}{rank}")
                await message.reply("\n".join(lines), mention_author=False)
                return True

            if sub == "power":
                name, power = _split_name_value(rest)
                player, created = pc.upsert_player(conn, guild_id, name, power=power, source="discord", actor=message.author)
                await message.reply(f"Police Chief power {'created' if created else 'updated'}: {player['player_name']} — {int(player['power'] or 0):,}", mention_author=False)
                return True

            if sub == "rank":
                name, rank = _split_name_value(rest)
                player, created = pc.upsert_player(conn, guild_id, name, alliance_rank=rank, source="discord", actor=message.author)
                await message.reply(f"Police Chief rank {'created' if created else 'updated'}: {player['player_name']} — {player['alliance_rank']}", mention_author=False)
                return True

            if sub == "status":
                name, status = _split_name_value(rest)
                player, created = pc.upsert_player(conn, guild_id, name, status=status, source="discord", actor=message.author)
                await message.reply(f"Police Chief status {'created' if created else 'updated'}: {player['player_name']} — {player['status']}", mention_author=False)
                return True

            if sub == "note":
                name, note = _split_note(rest)
                player, created = pc.upsert_player(conn, guild_id, name, notes=note, source="discord", actor=message.author)
                await message.reply(f"Police Chief notes {'created' if created else 'updated'} for {player['player_name']}.", mention_author=False)
                return True

            if sub == "link":
                if not message.mentions:
                    raise ValueError("Mention the Discord user to link, like `!c pc link PlayerName @user`.")
                member = message.mentions[0]
                name = re.sub(r"<@!?\d+>", "", rest).strip()
                if not name:
                    raise ValueError("Use `!c pc link <player name> @DiscordUser`.")
                detail = pc.link_discord(conn, guild_id, name, member.id, member.display_name, actor=message.author)
                await message.reply(f"Linked {detail['player_name']} to Discord profile {member.display_name}.", mention_author=False)
                return True

            if sub == "unlink":
                if not rest:
                    raise ValueError("Use `!c pc unlink <player name>`.")
                detail = pc.unlink_discord(conn, guild_id, rest, actor=message.author)
                await message.reply(f"Unlinked Discord profile from {detail['player_name']}.", mention_author=False)
                return True

            if sub == "import":
                import_type = rest.split(" ", 1)[0].lower() if rest else ""
                if import_type not in pc.IMPORT_TYPES:
                    raise ValueError("Use `!c pc import alliance` or `!c pc import profile` with screenshots attached.")
                if not message.attachments:
                    raise ValueError("Attach one or more Police Chief screenshots.")
                count = 0
                for attachment in message.attachments:
                    filename = attachment.filename or "discord-upload"
                    pc.add_import(
                        conn,
                        guild_id,
                        import_type,
                        filename=filename,
                        stored_path=attachment.url,
                        content_type=getattr(attachment, "content_type", "") or "discord-attachment",
                        uploader=message.author,
                        notes="Discord attachment saved for dashboard review.",
                    )
                    count += 1
                await message.reply(f"Saved {count} Police Chief {import_type} screenshot(s) for dashboard review.", mention_author=False)
                return True

        await message.reply(_usage(), mention_author=False)
        return True

    except ValueError as exc:
        await message.reply(str(exc), mention_author=False)
        return True
    except Exception as exc:
        print("Police Chief command error:", repr(exc))
        await message.reply("Police Chief tracker hit a reef while handling that.", mention_author=False)
        return True
