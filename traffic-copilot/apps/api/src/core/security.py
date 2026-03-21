"""
JWT authentication and RBAC for TrafficCopilot.

Decoding
--------
Tokens are HS256-signed JWTs created by an external identity provider or the
/auth/token endpoint (not implemented here — integration point).

Claims expected in the payload
-------------------------------
    sub      : str   — user identifier (e.g. badge number or UUID)
    role     : str   — one of VALID_ROLES
    exp      : int   — Unix epoch expiry (standard claim)
    iat      : int   — issued-at (standard claim, optional)

RBAC
----
Roles form a simple hierarchy:
    public_info_officer < officer < supervisor < admin

Use ``require_role("officer", "supervisor", "admin")`` to permit a set of roles.

Usage (in a FastAPI router)
---------------------------
    from src.core.security import require_role, get_current_user

    @router.post("/incidents/{id}/approve")
    async def approve(
        id: UUID,
        user: dict = Depends(require_role("supervisor", "admin")),
    ):
        ...
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt

from src.core.config import settings
from src.core.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ROLES: frozenset[str] = frozenset(
    {"public_info_officer", "officer", "supervisor", "admin"}
)

# The OAuth2 scheme points at the token endpoint.  ``auto_error=True`` means
# FastAPI will automatically return a 401 when the Authorization header is
# absent.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=True)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

_FORBIDDEN_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Insufficient permissions for this operation",
)


# ---------------------------------------------------------------------------
# Core decode helper
# ---------------------------------------------------------------------------


def decode_token(token: str) -> dict:
    """
    Validate and decode a JWT bearer token.

    Parameters
    ----------
    token:
        Raw JWT string (without the ``Bearer `` prefix).

    Returns
    -------
    dict
        The decoded payload claims.

    Raises
    ------
    HTTPException(401)
        If the token is missing, malformed, expired, or has an invalid
        signature.
    HTTPException(401)
        If the ``role`` claim is absent or not a recognised role.
    """
    try:
        payload: dict = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except ExpiredSignatureError:
        log.warning("jwt.expired")
        raise _CREDENTIALS_EXCEPTION
    except JWTError as exc:
        log.warning("jwt.invalid", error=str(exc))
        raise _CREDENTIALS_EXCEPTION

    role: str | None = payload.get("role")
    if role is None or role not in VALID_ROLES:
        log.warning("jwt.invalid_role", role=role)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token role '{role}' is not valid.  "
                   f"Must be one of: {sorted(VALID_ROLES)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


# ---------------------------------------------------------------------------
# FastAPI dependency — current user
# ---------------------------------------------------------------------------


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> dict:
    """
    FastAPI dependency that resolves the current authenticated user.

    Returns
    -------
    dict
        Decoded JWT payload, e.g. ``{"sub": "OFF-042", "role": "officer", ...}``

    Raises
    ------
    HTTPException(401)
        On any token validation failure.
    """
    return decode_token(token)


# ---------------------------------------------------------------------------
# RBAC dependency factory
# ---------------------------------------------------------------------------


def require_role(*roles: str):
    """
    Dependency factory that asserts the caller holds one of the given roles.

    Parameters
    ----------
    *roles:
        One or more role strings from ``VALID_ROLES``.

    Returns
    -------
    Callable
        An async FastAPI dependency that returns the decoded payload when the
        role check passes, or raises HTTP 403 otherwise.

    Example
    -------
        @router.delete("/incidents/{id}")
        async def delete_incident(
            id: UUID,
            user: dict = Depends(require_role("supervisor", "admin")),
        ):
            ...
    """
    allowed: frozenset[str] = frozenset(roles)
    unknown = allowed - VALID_ROLES
    if unknown:
        raise ValueError(
            f"require_role() received unknown role(s): {unknown}.  "
            f"Valid roles are: {sorted(VALID_ROLES)}"
        )

    async def _role_checker(
        current_user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        user_role: str = current_user.get("role", "")
        if user_role not in allowed:
            log.warning(
                "rbac.denied",
                user=current_user.get("sub"),
                user_role=user_role,
                required_roles=sorted(allowed),
            )
            raise _FORBIDDEN_EXCEPTION
        return current_user

    return _role_checker


# ---------------------------------------------------------------------------
# Convenience aliases
# ---------------------------------------------------------------------------

CurrentUser = Annotated[dict, Depends(get_current_user)]

OfficerOrAbove = Annotated[
    dict,
    Depends(require_role("officer", "supervisor", "admin")),
]

SupervisorOrAbove = Annotated[
    dict,
    Depends(require_role("supervisor", "admin")),
]

AdminOnly = Annotated[
    dict,
    Depends(require_role("admin")),
]
