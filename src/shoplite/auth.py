import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass

from fastapi import Request

from .errors import AppError


@dataclass
class User:
    id: int
    email: str
    name: str


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=2**14, r=8, p=1).hex()
    return f"scrypt${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    scheme, _, rest = stored.partition("$")
    salt, _, expected = rest.partition("$")
    if scheme != "scrypt" or not salt or not expected:
        return False
    actual = hashlib.scrypt(password.encode(), salt=salt.encode(), n=2**14, r=8, p=1).hex()
    return hmac.compare_digest(actual, expected)


def create_session(request: Request, user_id: int) -> str:
    services = request.app.state.services
    token = secrets.token_hex(32)
    services.db.execute(
        "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, user_id, services.clock())
    )
    return token


TOKEN_PATTERN = re.compile(r"^Bearer ([a-f0-9]{64})$")


def current_user(request: Request) -> User:
    """FastAPI dependency: the user for the request's bearer token, or 401."""
    match = TOKEN_PATTERN.match(request.headers.get("Authorization", ""))
    if not match:
        raise AppError(401, "UNAUTHORIZED", "Authentication required")
    row = request.app.state.services.db.fetch_one(
        """SELECT users.id, users.email, users.name
             FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ?""",
        (match.group(1),),
    )
    if row is None:
        raise AppError(401, "UNAUTHORIZED", "Authentication required")
    return User(**row)
