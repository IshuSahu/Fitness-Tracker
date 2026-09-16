"""Single asyncpg connection pool. Trusted server-side connection -- not
subject to RLS the way PostgREST calls from the browser were; auth.py's
verify_jwt dependency is the enforcement layer now."""
from __future__ import annotations
import os
import asyncpg

DATABASE_URL = os.environ["DATABASE_URL"]

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
