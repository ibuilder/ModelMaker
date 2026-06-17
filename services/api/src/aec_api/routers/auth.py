"""Authentication endpoints: register / login / me. Issues signed bearer tokens that the
RBAC layer accepts as identity (see rbac.current_user). The first registered user bootstraps
as admin; after that, registering others requires an admin token."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auth
from ..db import get_db
from ..models import User
from ..rbac import current_user

router = APIRouter()


def require_admin_user(db: Session = Depends(get_db), user: str = Depends(current_user)) -> User:
    """Gate user-management endpoints on a global admin account (independent of AEC_RBAC,
    which governs per-project routes)."""
    u = db.get(User, user)
    if not u or u.role != "admin":
        raise HTTPException(403, "an admin account is required")
    return u


def _other_active_admins(db: Session, exclude: str) -> int:
    """Count active admins other than `exclude` — used to prevent locking out the last one."""
    return (db.query(User)
            .filter(User.role == "admin", User.active.isnot(False), User.username != exclude)
            .count())


def _public(u: User) -> dict:
    return {"username": u.username, "role": u.role, "active": u.active is not False,
            "created_at": u.created_at}


@router.post("/auth/register", status_code=201)
def register(username: str = Body(..., embed=True), password: str = Body(..., embed=True),
             role: str = Body("user", embed=True), authorization: str | None = Header(default=None),
             db: Session = Depends(get_db)):
    if db.query(User).count() == 0:
        role = "admin"                       # bootstrap: the first account is admin
    else:
        tok = authorization[7:] if (authorization or "").startswith("Bearer ") else ""
        sub = auth.verify_token(tok)
        admin = db.get(User, sub) if sub else None
        if not admin or admin.role != "admin":
            raise HTTPException(403, "an admin token is required to register users")
        if role not in ("admin", "user"):
            raise HTTPException(400, "role must be admin or user")
    if len(password) < 8:
        raise HTTPException(400, "password must be at least 8 characters")
    if db.get(User, username):
        raise HTTPException(409, "username already taken")
    db.add(User(username=username, password_hash=auth.hash_password(password), role=role))
    db.commit()
    return {"username": username, "role": role}


@router.post("/auth/login")
def login(response: Response, username: str = Body(..., embed=True),
          password: str = Body(..., embed=True), db: Session = Depends(get_db)):
    u = db.get(User, username)
    if not u or not auth.verify_password(password, u.password_hash):
        raise HTTPException(401, "invalid username or password")
    if u.active is False:
        raise HTTPException(403, "account is deactivated")
    token = auth.create_token(username)
    # httpOnly cookie so SSE + direct-download links (which can't set a header) authenticate
    # same-origin (via the /api proxy in prod). Fetches use the token in the body for the header.
    response.set_cookie("aec_token", token, httponly=True, samesite="lax",
                        max_age=7 * 24 * 3600, path="/")
    return {"token": token, "username": username, "role": u.role}


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie("aec_token", path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(db: Session = Depends(get_db), user: str = Depends(current_user)):
    u = db.get(User, user)
    return {"username": user, "role": (u.role if u else None), "authenticated": u is not None}


# --- self-service -------------------------------------------------------------
@router.post("/auth/password")
def change_password(current: str = Body(..., embed=True), new: str = Body(..., embed=True),
                    db: Session = Depends(get_db), user: str = Depends(current_user)):
    """Change your own password (requires the current one)."""
    u = db.get(User, user)
    if not u:
        raise HTTPException(401, "not authenticated")
    if not auth.verify_password(current, u.password_hash):
        raise HTTPException(403, "current password is incorrect")
    if len(new) < 8:
        raise HTTPException(400, "password must be at least 8 characters")
    u.password_hash = auth.hash_password(new)
    db.commit()
    return {"ok": True}


# --- admin: user management ---------------------------------------------------
class UserPatch(BaseModel):
    role: str | None = None
    active: bool | None = None


@router.get("/auth/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin_user)):
    return [_public(u) for u in db.query(User).order_by(User.created_at).all()]


@router.post("/auth/users", status_code=201)
def create_user(username: str = Body(..., embed=True), password: str = Body(..., embed=True),
                role: str = Body("user", embed=True), db: Session = Depends(get_db),
                _: User = Depends(require_admin_user)):
    """Admin-created account (the open path after bootstrap; /auth/register stays for the
    very first user)."""
    if role not in ("admin", "user"):
        raise HTTPException(400, "role must be admin or user")
    if len(password) < 8:
        raise HTTPException(400, "password must be at least 8 characters")
    if db.get(User, username):
        raise HTTPException(409, "username already taken")
    db.add(User(username=username, password_hash=auth.hash_password(password), role=role))
    db.commit()
    return _public(db.get(User, username))


@router.patch("/auth/users/{username}")
def update_user(username: str, body: UserPatch, db: Session = Depends(get_db),
                admin: User = Depends(require_admin_user)):
    """Change a user's role and/or activate/deactivate them. Won't lock out the last admin."""
    u = db.get(User, username)
    if not u:
        raise HTTPException(404, "no such user")
    demoting = body.role is not None and body.role != "admin"
    deactivating = body.active is False
    if u.role == "admin" and (demoting or deactivating) and _other_active_admins(db, username) == 0:
        raise HTTPException(400, "cannot remove the last active admin")
    if body.role is not None:
        if body.role not in ("admin", "user"):
            raise HTTPException(400, "role must be admin or user")
        u.role = body.role
    if body.active is not None:
        u.active = body.active
    db.commit()
    return _public(u)


@router.post("/auth/users/{username}/password")
def reset_password(username: str, password: str = Body(..., embed=True),
                   db: Session = Depends(get_db), _: User = Depends(require_admin_user)):
    """Admin reset of another user's password."""
    u = db.get(User, username)
    if not u:
        raise HTTPException(404, "no such user")
    if len(password) < 8:
        raise HTTPException(400, "password must be at least 8 characters")
    u.password_hash = auth.hash_password(password)
    db.commit()
    return {"ok": True}
