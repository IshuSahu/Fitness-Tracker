"""Verifies the Supabase-issued JWT the frontend sends after
supabase.auth.signInWithPassword(). This -- not RLS -- is the enforcement
layer: the backend connects to Postgres directly, so a valid-but-wrong-user
token must be rejected here before any query runs.

This project uses Supabase's newer JWT Signing Keys (asymmetric, ES256),
confirmed by decoding a real issued token -- not the legacy HS256 shared
secret the original spec assumed. Verification therefore uses Supabase's
public JWKS endpoint (no secret involved; it's public-key crypto) rather
than SUPABASE_JWT_SECRET."""
from __future__ import annotations
import asyncio
import os
import jwt
from fastapi import Header, HTTPException

SUPABASE_URL = os.environ["SUPABASE_URL"]
ALLOWED_USER_ID = os.environ["ALLOWED_USER_ID"]
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"

# Supabase rotates signing keys rarely, so a long cache costs nothing and keeps
# the (blocking, network-bound) JWKS fetch off the hot path. lifespan=86400
# still picks up a rotation within a day.
_jwk_client = jwt.PyJWKClient(JWKS_URL, cache_keys=True, lifespan=86400)


async def verify_jwt(authorization: str | None = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token.")
    token = authorization[len("Bearer "):].strip()
    try:
        # get_signing_key_from_jwt does a synchronous urllib fetch on a cache
        # miss; on the event loop that stalls every other in-flight request.
        signing_key = await asyncio.to_thread(_jwk_client.get_signing_key_from_jwt, token)
        payload = jwt.decode(token, signing_key.key, algorithms=["ES256"], audience="authenticated")
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"Invalid token: {e}")
    sub = payload.get("sub")
    if sub != ALLOWED_USER_ID:
        raise HTTPException(401, "Token is valid but not the allowed user.")
    return sub
