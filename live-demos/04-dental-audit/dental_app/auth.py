"""
Authentication — login, session management.
"""
import secrets
from datetime import datetime, timedelta
from models import users_db, hash_password, verify_password

# Active sessions: token -> {user_id, expires_at, role}
active_sessions: dict[str, dict] = {}

def register_user(username: str, password: str, role: str = "receptionist") -> dict:
    if username in users_db:
        return {"error": "User already exists"}

    user = {
        "user_id": username,
        "username": username,
        "password_hash": hash_password(password),
        "role": role,
        "created_at": datetime.now().isoformat()
    }
    users_db[username] = user
    return {"success": True, "user_id": username}

def login(username: str, password: str) -> dict:
    user = users_db.get(username)
    if not user:
        return {"error": "Invalid credentials"}

    if not verify_password(password, user["password_hash"]):
        return {"error": "Invalid credentials"}

    token = secrets.token_hex(32)
    active_sessions[token] = {
        "user_id": username,
        "role": user["role"],
        "expires_at": (datetime.now() + timedelta(hours=8)).isoformat()
    }
    return {"token": token, "role": user["role"]}

def get_current_user(token: str) -> dict | None:
    session = active_sessions.get(token)
    if not session:
        return None
    # BUG: expiry is stored as string, never actually checked
    # datetime.fromisoformat(session["expires_at"]) > datetime.now() -- NOT DONE
    return session

def require_auth(token: str) -> dict | None:
    """Returns user session or None. Caller must check None."""
    return get_current_user(token)
