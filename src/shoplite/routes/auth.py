from fastapi import APIRouter, Depends, Request

from ..auth import User, create_session, current_user, verify_password
from ..errors import AppError
from ..schemas import LoginRequest

router = APIRouter(prefix="/api/auth")


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    services = request.app.state.services
    email = body.email.strip().lower()
    now = services.clock()
    failures = services.login_failures.setdefault(email, [])
    failures[:] = [ts for ts in failures if now - ts < 900]
    if len(failures) >= 5:
        retry_after = max(1, int(900 - (now - failures[0])) + 1)
        raise AppError(429, "RATE_LIMITED", "Too many login attempts", headers={"Retry-After": str(retry_after)})

    user = services.db.fetch_one("SELECT * FROM users WHERE email = ?", (email,))
    if user is None or not verify_password(body.password, user["password_hash"]):
        failures.append(now)
        raise AppError(401, "INVALID_CREDENTIALS", "Invalid email or password")

    failures.clear()
    token = create_session(request, user["id"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}


@router.post("/logout", status_code=204)
async def logout(request: Request, user: User = Depends(current_user)):
    token = request.headers["Authorization"].removeprefix("Bearer ")
    request.app.state.services.db.execute("DELETE FROM sessions WHERE token = ? AND user_id = ?", (token, user.id))
