"""Authentication endpoints: register / login / me. Issues signed bearer tokens that the
RBAC layer accepts as identity (see rbac.current_user). The first registered user bootstraps
as admin; after that, registering others requires an admin token."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .. import auth
from ..db import get_db
from ..models import User
from ..rbac import current_user

router = APIRouter()


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
def login(username: str = Body(..., embed=True), password: str = Body(..., embed=True),
          db: Session = Depends(get_db)):
    u = db.get(User, username)
    if not u or not auth.verify_password(password, u.password_hash):
        raise HTTPException(401, "invalid username or password")
    return {"token": auth.create_token(username), "username": username, "role": u.role}


@router.get("/auth/me")
def me(db: Session = Depends(get_db), user: str = Depends(current_user)):
    u = db.get(User, user)
    return {"username": user, "role": (u.role if u else None), "authenticated": u is not None}
