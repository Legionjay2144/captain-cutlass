"""
Captain Cutlass Ship World multiplayer locks.

All state-changing Ship World operations for the same guild
share one lock.

This prevents simultaneous players from modifying the same
ship, encounter, treasury, upgrade, repair, or voyage state
at the same time.

Different guilds receive different locks and can therefore
continue playing concurrently.
"""

import asyncio
from weakref import WeakValueDictionary


_guild_locks = WeakValueDictionary()


def get_guild_lock(guild_id):
    """
    Return the shared Ship World lock for a guild.
    """

    guild_id = int(guild_id)

    lock = _guild_locks.get(
        guild_id
    )

    if lock is None:
        lock = asyncio.Lock()

        _guild_locks[
            guild_id
        ] = lock

    return lock
