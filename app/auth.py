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
import os
import jwt
from fastapi import Header, HTTPException

SUPABASE_URL = os.environ["SUPABASE_URL"]
ALLOWED_USER_ID = os.environ["ALLOWED_USER_ID"]
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"

_jwk_client = jwt.PyJWKClient(JWKS_URL)


async def verify_jwt(authorization: str | None = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token.")
    token = authorization[len("Bearer "):].strip()
    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(token, signing_key.key, algorithms=["ES256"], audience="authenticated")
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"Invalid token: {e}")
    sub = payload.get("sub")
    if sub != ALLOWED_USER_ID:
        raise HTTPException(401, "Token is valid but not the allowed user.")
    return sub
