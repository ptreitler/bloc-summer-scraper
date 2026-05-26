"""web/auth.py — Session-based authentication helpers"""
from __future__ import annotations

import os
import secrets
from functools import wraps

from flask import abort, redirect, request, session, url_for


def _users() -> dict[str, dict]:
    return {
        os.environ.get("ADMIN_USERNAME", "admin"): {
            "password": os.environ.get("ADMIN_PASSWORD", ""),
            "is_admin": True,
        },
        os.environ.get("GUEST_USERNAME", "guest"): {
            "password": os.environ.get("GUEST_PASSWORD", ""),
            "is_admin": False,
        },
    }


def check_credentials(username: str, password: str) -> tuple[bool, bool]:
    """Return (valid, is_admin).  Uses secrets.compare_digest to resist timing attacks."""
    users = _users()
    user = users.get(username)
    if user is None or not user["password"]:
        return False, False
    ok = secrets.compare_digest(
        user["password"].encode("utf-8"), password.encode("utf-8")
    )
    return ok, (user["is_admin"] if ok else False)


def require_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("index.login", next=request.full_path))
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("index.login", next=request.full_path))
        if not session.get("is_admin"):
            abort(403)
        return f(*args, **kwargs)
    return decorated
