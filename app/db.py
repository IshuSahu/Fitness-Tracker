"""Single asyncpg connection pool. Trusted server-side connection -- not
subject to RLS the way PostgREST calls from the browser were; auth.py's
verify_jwt dependency is the enforcement layer now."""
from __future__ import annotations
import os
from decimal import Decimal
from typing import Optional
import asyncpg

DATABASE_URL = os.environ["DATABASE_URL"]


def num(value: Optional[float], places: int = 2) -> Optional[Decimal]:
    """Round a float for storage in a numeric column.

    asyncpg hands a Python float to postgres at its exact binary value, so a
    weight of 85.4 lands as 85.400000000000005684341886080801486968994140625
    and every report that prints it is unreadable. Going through a Decimal
    built from the rounded string stores what the user actually typed."""
    if value is None:
        return None
    return Decimal(f"{round(float(value), places):.{places}f}")

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
