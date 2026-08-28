"""
Captain Cutlass Ship World multiplayer locks.

All state-changing Ship World operations for the same guild
share one lock.

The lock is reentrant for the SAME asyncio task.

This allows high-level Ship World handlers to protect a full
operation while lower-level engines safely reuse the same
guild lock without deadlocking.

Different asyncio tasks still serialize normally.

Different guilds receive different locks and can therefore
continue playing concurrently.
"""

import asyncio
from weakref import WeakValueDictionary


class ReentrantAsyncLock:
    """
    Async lock that may be acquired multiple times by the same task.

    Other tasks must wait until the owning task fully releases it.
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._owner = None
        self._depth = 0

    async def acquire(self):
        task = asyncio.current_task()

        if task is None:
            raise RuntimeError(
                "ReentrantAsyncLock requires an active asyncio task."
            )

        if self._owner is task:
            self._depth += 1
            return True

        await self._lock.acquire()

        self._owner = task
        self._depth = 1

        return True

    def release(self):
        task = asyncio.current_task()

        if self._owner is not task:
            raise RuntimeError(
                "ReentrantAsyncLock released by a task that does not own it."
            )

        self._depth -= 1

        if self._depth == 0:
            self._owner = None
            self._lock.release()

    def locked(self):
        return self._lock.locked()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        tb
    ):
        self.release()
        return False


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
        lock = ReentrantAsyncLock()

        _guild_locks[
            guild_id
        ] = lock

    return lock
