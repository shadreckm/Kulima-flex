from __future__ import annotations

import os
from pathlib import Path

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from fastapi import HTTPException, Request, status


def _load_nextauth_secret() -> str | None:
    secret = os.environ.get("NEXTAUTH_SECRET")
    if secret:
        return secret

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "NEXTAUTH_SECRET":
                secret = value.strip().strip('"').strip("'")
                if secret:
                    os.environ["NEXTAUTH_SECRET"] = secret
                    return secret
    return None


JWT_SECRET = _load_nextauth_secret()
JWT_ALG = "HS256"


class AuthenticatedUser:
    def __init__(self, user_id: str):
        self.user_id = user_id


async def get_current_user(request: Request) -> AuthenticatedUser:
    """Validate Authorization: Bearer <token> and return an AuthenticatedUser.

    This is a minimal JWT validator intended for pre-beta. It assumes
    the token was issued by NextAuth using the same NEXTAUTH_SECRET and
    that the user identifier is stored in the `sub` claim.
    """

    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "message": "Unauthorized"},
        )
    token = auth.split(" ", 1)[1].strip()
    try:
        # Ensure `exp` is honoured so expired tokens are rejected with 401.
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG], options={"verify_exp": True})
    except ExpiredSignatureError:
        # Explicit path for expired tokens
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "message": "Unauthorized"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "message": "Unauthorized"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "message": "Unauthorized"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "message": "Unauthorized"},
        )
    return AuthenticatedUser(user_id=user_id)
