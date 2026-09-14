from __future__ import annotations

import os

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from fastapi import HTTPException, Request, status


def _load_nextauth_secret() -> str:
    secret = os.environ.get("NEXTAUTH_SECRET")
    if secret:
        return secret
    raise RuntimeError("NEXTAUTH_SECRET must be configured before the backend starts")


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
