from __future__ import annotations
import time
from typing import Dict, Any
import httpx, jwt
from jwt import PyJWKClient
from cachetools import TTLCache

TENANT = "moolaib2c.onmicrosoft.com"
POLICY = "B2C_1_susi"
API_CLIENT_ID = "0263d89f-754d-4861-a401-8a44a0611618"  

OPENID_CONFIG = f"https://{TENANT}.b2clogin.com/{TENANT}/{POLICY}/v2.0/.well-known/openid-configuration"
_cfg = TTLCache(maxsize=1, ttl=3600)
_jwks = TTLCache(maxsize=1, ttl=3600)


async def _openid() -> Dict[str, Any]:
    if "v" in _cfg: return _cfg["v"]
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(OPENID_CONFIG)
        r.raise_for_status()
        _cfg["v"] = r.json()
        return _cfg["v"]

async def _jwks() -> PyJWKClient:
    if "v" in _jwks: return _jwks["v"]
    jwks_uri = (await _openid())["jwks_uri"]
    _jwks["v"] = PyJWKClient(jwks_uri)
    return _jwks["v"]

async def validate_b2c_token(token: str) -> Dict[str, Any]:
    cfg = await _openid()
    key = (await _jwks()).get_signing_key_from_jwt(token).key
    claims = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=API_CLIENT_ID,     
        issuer=cfg["issuer"],       
        options={"require": ["exp", "iat"]},
    )
    # Enforce policy claim (tfp or acr)
    tfp = claims.get("tfp") or claims.get("acr")
    if not tfp or POLICY.lower() not in tfp.lower():
        raise jwt.InvalidTokenError("Policy (tfp/acr) mismatch")

    now = int(time.time())
    if claims.get("nbf") and now < int(claims["nbf"]):
        raise jwt.InvalidTokenError("Token not yet valid")
    if now > int(claims["exp"]):
        raise jwt.ExpiredSignatureError("Token expired")

    return claims


