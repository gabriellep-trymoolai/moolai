from __future__ import annotations
from typing import Optional, Dict, Any

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth.b2c import validate_b2c_token
from app.db.database import get_db
from app.models.user import User  # adjust import if your User model is in a different path


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    # Expect "Authorization: Bearer <token>"
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()

    try:
        claims = await validate_b2c_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    sub = claims.get("sub")
    email = (claims.get("emails") or [claims.get("email")])[0]

    # Minimal upsert of the user record
    user = db.query(User).filter(User.b2c_sub == sub).one_or_none()
    if not user:
        user = User(b2c_sub=sub, email=email, roles="[]")
        db.add(user)
        db.commit()
        db.refresh(user)
    elif email and email != user.email:
        user.email = email
        db.commit()

    return {
        "id": user.id,
        "email": user.email,
        "roles": user.roles,
        "claims": claims,
    }
