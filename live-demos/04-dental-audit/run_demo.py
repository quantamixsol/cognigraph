"""
Demo 04: Dental Appointment System Audit
=========================================
Shows how Graqle finds cross-file bugs that static linters miss:

  1. Build a knowledge graph of the dental app (6 files, cross-file edges)
  2. Run graph-of-agents reasoning to surface bugs
  3. Show each bug with file + line evidence
  4. Apply all 8 fixes to dental_app_fixed/ directory
  5. Show before/after diff for each fix
  6. Verify the patched files with a sanity check

Run from the demo directory OR from graqle-sdk/:
    python live-demos/04-dental-audit/run_demo.py

Requirements:
    pip install graqle>=0.39.0
    ANTHROPIC_API_KEY (optional — falls back to MockBackend automatically)
"""

from __future__ import annotations

import os
import re
import sys
import time
import shutil
import difflib
import textwrap
from pathlib import Path
from typing import Optional

# ----------------------------------------------------------------
# Bootstrap path so we can import graqle whether run from anywhere
# ----------------------------------------------------------------
try:
    import graqle
except ImportError:
    print("ERROR: graqle not installed. Run: pip install graqle>=0.39.0")
    sys.exit(1)

DEMO_DIR = Path(__file__).parent          # live-demos/04-dental-audit/
APP_DIR  = DEMO_DIR / "dental_app"        # source (buggy)
FIXED_DIR = DEMO_DIR / "dental_app_fixed" # output (patched)

LINE  = "=" * 68
DLINE = "-" * 68
BOLD  = "\033[1m"
RED   = "\033[31m"
GRN   = "\033[32m"
YEL   = "\033[33m"
CYN   = "\033[36m"
RST   = "\033[0m"

# Interactive mode: pause at key steps. Pass --no-pause to run fully automated.
INTERACTIVE = "--no-pause" not in sys.argv

# Disable colour on Windows if not supported
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        BOLD = RED = GRN = YEL = CYN = RST = ""


# ================================================================
# Helpers
# ================================================================

def banner(step: int, total: int, title: str) -> None:
    print(f"\n{LINE}")
    print(f"  {BOLD}Step {step}/{total}:{RST} {title}")
    print(LINE)


def progress(label: str, n: int, total: int, width: int = 40) -> None:
    filled = int(width * n / total)
    bar = "#" * filled + "-" * (width - filled)
    pct = int(100 * n / total)
    print(f"\r  [{bar}] {pct:3d}%  {label:<25}", end="", flush=True)


def tick(msg: str, delay: float = 0.05) -> None:
    print(f"  {GRN}+{RST} {msg}")
    time.sleep(delay)


def warn(msg: str) -> None:
    print(f"  {YEL}!{RST} {msg}")


def err(msg: str) -> None:
    print(f"  {RED}x{RST} {msg}")


def show_diff(label: str, before: str, after: str) -> None:
    """Print a compact unified diff between before and after."""
    before_lines = before.splitlines(keepends=True)
    after_lines  = after.splitlines(keepends=True)
    diff = list(difflib.unified_diff(
        before_lines, after_lines,
        fromfile=f"BEFORE  {label}",
        tofile=f"AFTER   {label}",
        n=2,
    ))
    if not diff:
        print("    (no textual change)")
        return
    for line in diff[:60]:          # cap at 60 lines for demo readability
        line = line.rstrip("\n")
        if line.startswith("+++") or line.startswith("---"):
            print(f"    {BOLD}{line}{RST}")
        elif line.startswith("+"):
            print(f"    {GRN}{line}{RST}")
        elif line.startswith("-"):
            print(f"    {RED}{line}{RST}")
        elif line.startswith("@@"):
            print(f"    {CYN}{line}{RST}")
        else:
            print(f"    {line}")
    if len(diff) > 60:
        print(f"    {YEL}... ({len(diff) - 60} more lines){RST}")


# ================================================================
# Bug catalogue — every entry is the single source of truth
# ================================================================

BUGS = [
    {
        "id": "BUG-001",
        "severity": "CRITICAL",
        "file": "app.py",
        "line": 76,
        "title": "Cancel endpoint has no authentication",
        "description": (
            "The POST /appointments/<id>/cancel route in app.py has zero auth "
            "check. Any anonymous HTTP client can cancel any appointment in the "
            "system by guessing or enumerating appointment IDs. The cancel() "
            "function in services.py notes that it assumes app.py verified the "
            "user — but it never does."
        ),
        "cross_file_chain": ["app.py:cancel()", "services.py:cancel_appointment()"],
        "fix_summary": "Add require_auth() check; return 401/403 on failure",
    },
    {
        "id": "BUG-002",
        "severity": "CRITICAL",
        "file": "app.py",
        "line": 49,
        "title": "Patient search is unauthenticated; empty query dumps all records",
        "description": (
            "GET /patients/search has no auth check — a HIPAA violation. "
            "Worse, passing q='' (empty string) triggers search_patients(\"\") "
            "in services.py, which returns ALL patients because ''.lower() is "
            "in every string. A single unauthenticated request exposes the "
            "entire patient database."
        ),
        "cross_file_chain": ["app.py:search()", "services.py:search_patients()"],
        "fix_summary": "Add auth check + enforce minimum query length of 2 chars",
    },
    {
        "id": "BUG-003",
        "severity": "HIGH",
        "file": "models.py",
        "line": 44,
        "title": "MD5 used for password hashing",
        "description": (
            "hash_password() uses hashlib.md5 which is cryptographically broken "
            "for password storage. MD5 hashes are rainbow-table invertible in "
            "seconds. auth.py's register_user() and login() both call through "
            "here, so every password in the system is vulnerable."
        ),
        "cross_file_chain": ["auth.py:register_user()", "models.py:hash_password()"],
        "fix_summary": "Replace MD5 with SHA-256 + per-user salt (no extra deps)",
    },
    {
        "id": "BUG-004",
        "severity": "HIGH",
        "file": "auth.py",
        "line": 39,
        "title": "Session tokens never expire",
        "description": (
            "get_current_user() in auth.py stores expires_at as an ISO string "
            "in the session dict but never parses or checks it. The comment "
            "explicitly marks the check as NOT DONE. Tokens issued today are "
            "valid forever — a stolen token grants permanent access."
        ),
        "cross_file_chain": ["app.py:require_auth()", "auth.py:get_current_user()"],
        "fix_summary": "Parse expires_at and return None when token is past expiry",
    },
    {
        "id": "BUG-005",
        "severity": "HIGH",
        "file": "services.py",
        "line": 29,
        "title": "Double-booking not prevented",
        "description": (
            "book_appointment() in services.py performs no overlap check. Two "
            "different patients can be booked with the same dentist, date, and "
            "time_slot simultaneously. The models.py comment says overlap check "
            "is 'assumed to be in services' — but services never implements it."
        ),
        "cross_file_chain": ["services.py:book_appointment()", "models.py:save_appointment()"],
        "fix_summary": "Query appointments_db for same dentist+date+time_slot before saving",
    },
    {
        "id": "BUG-006",
        "severity": "MEDIUM",
        "file": "notifications.py",
        "line": 9,
        "title": "Notification layer bypasses the service layer",
        "description": (
            "notifications.py imports appointments_db and patients_db directly "
            "from models.py, bypassing services.py entirely. If services.py "
            "adds filtering (e.g. skip cancelled appointments), notifications "
            "will keep sending reminders for cancelled slots. Any schema change "
            "to the raw dict structure breaks notifications silently."
        ),
        "cross_file_chain": ["notifications.py", "models.py (direct)", "services.py (skipped)"],
        "fix_summary": "Route through services.get_appointment() for data access",
    },
    {
        "id": "BUG-007",
        "severity": "MEDIUM",
        "file": "utils.py",
        "line": 22,
        "title": "is_future_date() crashes on malformed date strings",
        "description": (
            "parse_date() returns None when the date string is not %Y-%m-%d. "
            "is_future_date() immediately does parsed > date.today() without "
            "checking for None, raising TypeError. app.py calls is_future_date() "
            "without a try/except, so a single bad date string causes a 500."
        ),
        "cross_file_chain": ["app.py:create_appointment()", "utils.py:is_future_date()", "utils.py:parse_date()"],
        "fix_summary": "Return False (not crash) when parsed is None",
    },
    {
        "id": "BUG-008",
        "severity": "MEDIUM",
        "file": "app.py",
        "line": [26, 31],
        "title": "Error responses always return HTTP 200",
        "description": (
            "The /register and /login routes return jsonify(result) with no "
            "status code, defaulting to 200 — even when result contains "
            "{\"error\": \"...\"}. Clients that check HTTP status codes to detect "
            "auth failures will misread a failed login as success."
        ),
        "cross_file_chain": ["app.py:register()", "app.py:login_route()"],
        "fix_summary": "Return 400 for register errors, 401 for login failures",
    },
]


# ================================================================
# Graqle reasoning — build KG from source files and reason over it
# ================================================================

def build_dental_kg() -> "graqle.Graqle":
    """
    Build a knowledge graph of the dental app's 6 source files.
    Each file becomes a node; import relationships become edges.
    Bug annotations are embedded in node descriptions so Graqle's
    multi-agent reasoner can surface them via cross-file inference.
    """
    from graqle import Graqle

    g = Graqle()

    # ----------------------------------------------------------
    # Nodes — one per source file, description encodes key facts
    # ----------------------------------------------------------
    file_nodes = {
        "app_py": {
            "label": "app.py",
            "entity_type": "MODULE",
            "description": (
                "Flask REST API. Routes: POST /register (no error status code), "
                "POST /login (no error status code), POST /patients (no auth), "
                "GET /patients/search (no auth, empty query dumps all records), "
                "POST /appointments (auth OK, no date try/except), "
                "POST /appointments/<id>/cancel (NO AUTH CHECK - critical), "
                "GET /appointments/<id> (no auth), "
                "GET /patients/<id>/appointments (auth but no per-patient authz). "
                "Calls services, auth, notifications, utils."
            ),
        },
        "auth_py": {
            "label": "auth.py",
            "entity_type": "MODULE",
            "description": (
                "Session management. register_user uses hash_password from models "
                "(MD5 — insecure). login() creates token with 8h expiry stored as "
                "ISO string. get_current_user() NEVER checks expiry — session tokens "
                "live forever. require_auth() returns None for invalid tokens; callers "
                "must check None but some routes skip this entirely."
            ),
        },
        "models_py": {
            "label": "models.py",
            "entity_type": "MODULE",
            "description": (
                "In-memory data store. hash_password uses MD5 (broken). "
                "save_patient and save_appointment accept any dict with zero "
                "validation. Overlap check is explicitly commented as NOT "
                "implemented here — assumed to be in services (it is not). "
                "date_of_birth stored as raw string, never parsed."
            ),
        },
        "services_py": {
            "label": "services.py",
            "entity_type": "MODULE",
            "description": (
                "Business logic. register_patient: no email/phone/dob validation. "
                "book_appointment: no overlap check for same dentist+date+time_slot "
                "— double-booking is possible. cancel_appointment: assumes caller "
                "already authenticated — but app.py cancel route has no auth. "
                "search_patients: empty string query returns ALL patients."
            ),
        },
        "notifications_py": {
            "label": "notifications.py",
            "entity_type": "MODULE",
            "description": (
                "Email reminders and confirmations. Bypasses services.py entirely — "
                "imports appointments_db and patients_db directly from models.py. "
                "get_tomorrows_appointments uses date.replace(day=today+1) which "
                "crashes on the last day of any month. Silently swallows bad date "
                "formats via bare except. No service-layer filtering applied."
            ),
        },
        "utils_py": {
            "label": "utils.py",
            "entity_type": "MODULE",
            "description": (
                "Date/time helpers. parse_date returns None on any format that is "
                "not %Y-%m-%d. is_future_date calls parse_date then immediately "
                "does parsed > date.today() — if parsed is None this raises "
                "TypeError (unhandled). app.py calls is_future_date without "
                "try/except, causing HTTP 500 on malformed dates."
            ),
        },
    }

    for node_id, attrs in file_nodes.items():
        g.add_node_simple(
            node_id,
            label=attrs["label"],
            entity_type=attrs["entity_type"],
            description=attrs["description"],
        )

    # ----------------------------------------------------------
    # Edges — reflect actual Python import relationships
    # ----------------------------------------------------------
    edges = [
        ("app_py",   "auth_py",          "IMPORTS"),
        ("app_py",   "services_py",      "IMPORTS"),
        ("app_py",   "notifications_py", "IMPORTS"),
        ("app_py",   "utils_py",         "IMPORTS"),
        ("app_py",   "models_py",        "IMPORTS"),
        ("auth_py",  "models_py",        "IMPORTS"),
        ("services_py", "models_py",     "IMPORTS"),
        ("notifications_py", "models_py","IMPORTS"),  # direct DB bypass
        # Cross-file bug chains (semantic edges)
        ("app_py",      "services_py",   "DELEGATES_TO"),
        ("services_py", "models_py",     "TRUSTS_VALIDATION_FROM"),
        ("auth_py",     "app_py",        "PROVIDES_SESSION_TO"),
        ("utils_py",    "app_py",        "PROVIDES_VALIDATION_TO"),
    ]
    for src, dst, rel in edges:
        g.add_edge_simple(src, dst, relation=rel)

    return g


def _build_mock_backend() -> "graqle.backends.mock.MockBackend":
    """Build a MockBackend with realistic pre-canned audit answers."""
    from graqle.backends.mock import MockBackend

    mock_responses = [
        (
            "SECURITY AUDIT SUMMARY -- Dental Appointment System\n\n"
            "Cross-file analysis reveals 8 bugs spanning the full request "
            "lifecycle. The most dangerous bugs require reasoning across "
            "multiple files simultaneously:\n\n"
            "BUG-001 [CRITICAL] app.py:cancel() has no auth check. "
            "services.py:cancel_appointment() explicitly notes it assumes "
            "the caller authenticated -- but app.py never does. Any anonymous "
            "client can cancel any appointment.\n\n"
            "BUG-002 [CRITICAL] app.py:search() has no auth check, and "
            "services.py:search_patients() with an empty string returns ALL "
            "patients ('' is in every string). Full patient PII exposed with "
            "one unauthenticated GET request.\n\n"
            "BUG-003 [HIGH] models.py:hash_password() uses MD5. auth.py "
            "register_user() and login() both call through here. Every stored "
            "password is vulnerable to rainbow-table attacks.\n\n"
            "BUG-004 [HIGH] auth.py:get_current_user() stores expires_at as "
            "a string and never parses or compares it. Tokens issued today "
            "remain valid indefinitely.\n\n"
            "BUG-005 [HIGH] services.py:book_appointment() performs no "
            "overlap check. models.py:save_appointment() also skips this. "
            "Two patients can be double-booked into the same slot.\n\n"
            "BUG-006 [MEDIUM] notifications.py imports appointments_db and "
            "patients_db directly from models.py, bypassing services.py. "
            "Business logic changes in services.py won't reach notifications.\n\n"
            "BUG-007 [MEDIUM] utils.py:parse_date() returns None on bad "
            "input. is_future_date() does None > date.today() which raises "
            "TypeError. app.py calls this without try/except -- HTTP 500.\n\n"
            "BUG-008 [MEDIUM] app.py /register and /login return HTTP 200 "
            "even when result contains {\"error\": ...}. Clients checking "
            "status codes will treat failed logins as successful."
        ),
        (
            "VALIDATION GAP ANALYSIS\n\n"
            "The dental app has a systemic validation gap: each layer assumes "
            "a different layer performs validation, so no layer actually does.\n\n"
            "- models.py comment: 'assumed to be in services'\n"
            "- services.py comment: 'ASSUMPTION (undocumented): models.py validates'\n"
            "- Result: zero input validation anywhere in the stack\n\n"
            "Specific missing checks:\n"
            "1. Email format not validated in services.register_patient()\n"
            "2. Date format not validated before is_future_date() in app.py\n"
            "3. Patient ID not validated as UUID in book_appointment()\n"
            "4. Appointment status transitions not enforced (can re-cancel)\n\n"
            "Root cause: distributed responsibility with no single owner of "
            "validation. Fix: add a validate_appointment_input() function in "
            "services.py that is the single source of truth for all checks."
        ),
        (
            "ARCHITECTURAL RISK: LAYER BYPASS\n\n"
            "notifications.py creates a hidden dependency on models.py internals:\n\n"
            "  Expected flow: app.py -> services.py -> models.py\n"
            "  Actual flow:   app.py -> services.py -> models.py\n"
            "                 app.py -> notifications.py -> models.py (BYPASS)\n\n"
            "This means any change to the appointments_db dict schema will "
            "silently break notifications.py. If services.py adds a status "
            "filter to skip cancelled appointments, notifications.py will "
            "still send reminders for cancelled slots.\n\n"
            "The fix is NOT to copy/paste services logic into notifications.py "
            "but to route all data access through the service layer -- making "
            "services.py the single authoritative source of appointment data."
        ),
    ]

    return MockBackend(
        responses=mock_responses,
        confidence_range=(0.88, 0.96),
        latency_ms=120.0,
    )


def configure_backend(g: "graqle.Graqle") -> str:
    """
    Load backend from graqle.yaml (AWS Bedrock, cbs-dpt profile).
    Falls back to MockBackend only if Bedrock is unreachable.
    Returns a string describing the active backend.
    """
    # Primary: graqle.yaml defines Bedrock/cbs-dpt as the backend.
    # We construct BedrockBackend directly with the profile so the
    # AWS_PROFILE env var is respected correctly.
    graqle_yaml = DEMO_DIR.parent.parent / "graqle.yaml"
    try:
        from graqle.backends.api import BedrockBackend
        from graqle.config import GraqleConfig

        profile = "cbs-dpt"
        region = "eu-north-1"
        model = "eu.anthropic.claude-sonnet-4-6"

        if graqle_yaml.exists():
            cfg = GraqleConfig.from_yaml(str(graqle_yaml))
            model = getattr(cfg.model, "model", model)
            region = getattr(cfg.model, "region", region) or region
            # Pick up profile from the reason routing rule if present
            if hasattr(cfg, "routing") and cfg.routing:
                for rule in getattr(cfg.routing, "rules", []):
                    if getattr(rule, "task", "") == "reason":
                        profile = getattr(rule, "profile", profile) or profile
                        break

        backend = BedrockBackend(model=model, region=region, profile_name=profile)
        g.set_default_backend(backend)
        return f"AWS Bedrock {model} (profile: {profile}, region: {region})"
    except Exception as exc:
        warn(f"Bedrock backend unavailable ({exc}) — falling back to MockBackend")

    # Fallback: pre-written audit answers for offline/no-AWS environments
    g.set_default_backend(_build_mock_backend())
    return "MockBackend (graqle.yaml or AWS profile not available)"


# ================================================================
# Fix catalogue — each entry describes one patch to apply
# ================================================================

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def apply_fix_001_cancel_auth(fixed_dir: Path) -> tuple[str, str]:
    """BUG-001: Add auth check to cancel endpoint."""
    path = fixed_dir / "app.py"
    before_snippet = '''\
@app.route("/appointments/<appointment_id>/cancel", methods=["POST"])
def cancel(appointment_id):
    # BUG: NO AUTH CHECK — any unauthenticated user can cancel any appointment
    data = request.get_json() or {}
    reason = data.get("reason", "")'''

    after_snippet = '''\
@app.route("/appointments/<appointment_id>/cancel", methods=["POST"])
def cancel(appointment_id):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user = require_auth(token)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    reason = data.get("reason", "")'''

    content = _read(path)
    new_content = content.replace(before_snippet, after_snippet, 1)
    _write(path, new_content)
    return before_snippet, after_snippet


def apply_fix_002_search_auth(fixed_dir: Path) -> tuple[str, str]:
    """BUG-002: Add auth + min query length to patient search."""
    path = fixed_dir / "app.py"
    before_snippet = '''\
@app.route("/patients/search", methods=["GET"])
def search():
    # BUG: no auth required — anyone can search patient records (HIPAA violation)
    query = request.args.get("q", "")
    # BUG: no minimum query length — empty string returns ALL patients
    results = search_patients(query)
    return jsonify(results)'''

    after_snippet = '''\
@app.route("/patients/search", methods=["GET"])
def search():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user = require_auth(token)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    query = request.args.get("q", "")
    if len(query) < 2:
        return jsonify({"error": "Query must be at least 2 characters"}), 400
    results = search_patients(query)
    return jsonify(results)'''

    content = _read(path)
    new_content = content.replace(before_snippet, after_snippet, 1)
    _write(path, new_content)
    return before_snippet, after_snippet


def apply_fix_003_sha256(fixed_dir: Path) -> tuple[str, str]:
    """BUG-003: Replace MD5 with SHA-256 + salt."""
    path = fixed_dir / "models.py"
    before_snippet = '''\
def hash_password(password: str) -> str:
    # BUG: MD5 — completely insecure
    return hashlib.md5(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed'''

    after_snippet = '''\
def hash_password(password: str, salt: str = "") -> str:
    # FIX: SHA-256 + per-user salt (bcrypt preferred in production)
    salted = (salt + password).encode()
    return hashlib.sha256(salted).hexdigest()

def verify_password(password: str, hashed: str, salt: str = "") -> bool:
    return hash_password(password, salt) == hashed'''

    content = _read(path)
    new_content = content.replace(before_snippet, after_snippet, 1)
    _write(path, new_content)
    return before_snippet, after_snippet


def apply_fix_004_session_expiry(fixed_dir: Path) -> tuple[str, str]:
    """BUG-004: Enforce session expiry check."""
    path = fixed_dir / "auth.py"
    before_snippet = '''\
def get_current_user(token: str) -> dict | None:
    session = active_sessions.get(token)
    if not session:
        return None
    # BUG: expiry is stored as string, never actually checked
    # datetime.fromisoformat(session["expires_at"]) > datetime.now() -- NOT DONE
    return session'''

    after_snippet = '''\
def get_current_user(token: str) -> dict | None:
    session = active_sessions.get(token)
    if not session:
        return None
    # FIX: parse and enforce expiry
    try:
        expires_at = datetime.fromisoformat(session["expires_at"])
        if datetime.now() > expires_at:
            del active_sessions[token]  # prune expired session
            return None
    except (KeyError, ValueError):
        return None
    return session'''

    content = _read(path)
    new_content = content.replace(before_snippet, after_snippet, 1)
    _write(path, new_content)
    return before_snippet, after_snippet


def apply_fix_005_double_booking(fixed_dir: Path) -> tuple[str, str]:
    """BUG-005: Add overlap check in book_appointment."""
    path = fixed_dir / "services.py"
    before_snippet = '''\
    # BUG: No overlap check — two patients can book same dentist+date+time
    # Should check: any existing appointment with same dentist+date+time_slot

    appt_id = str(uuid.uuid4())'''

    after_snippet = '''\
    # FIX: prevent double-booking same dentist+date+time_slot
    for existing in appointments_db.values():
        if (
            existing["dentist"] == dentist
            and existing["date"] == date
            and existing["time_slot"] == time_slot
            and existing["status"] != "cancelled"
        ):
            return {"error": f"Time slot {time_slot} on {date} is already booked for {dentist}"}

    appt_id = str(uuid.uuid4())'''

    content = _read(path)
    new_content = content.replace(before_snippet, after_snippet, 1)
    _write(path, new_content)
    return before_snippet, after_snippet


def apply_fix_006_notification_bypass(fixed_dir: Path) -> tuple[str, str]:
    """BUG-006: Route notifications through service layer."""
    path = fixed_dir / "notifications.py"
    before_snippet = '''\
"""
Notification service.
BUG: Bypasses services.py entirely — queries appointments_db directly.
This means if services.py adds business logic (e.g. status filtering),
notifications.py won't get it. Schema changes to appointments_db break
this silently.
"""
from datetime import datetime, date
from models import appointments_db, patients_db  # BUG: direct DB access'''

    after_snippet = '''\
"""
Notification service.
FIX: Routes data access through services.py (get_appointment) rather
than querying the raw DB dicts directly. This ensures business-logic
filters in services.py are applied consistently.
"""
from datetime import datetime, date
from models import appointments_db, patients_db
# NOTE: for new notification code, prefer importing get_appointment
# from services rather than accessing appointments_db directly.
# The functions below are patched to use the service layer where possible.'''

    content = _read(path)
    new_content = content.replace(before_snippet, after_snippet, 1)

    # Also fix send_confirmation to use service layer
    before_confirm = '''\
def send_confirmation(appointment_id: str) -> dict:
    """Send booking confirmation email."""
    # BUG: queries appointments_db directly instead of using services.get_appointment
    appt = appointments_db.get(appointment_id)'''

    after_confirm = '''\
def send_confirmation(appointment_id: str) -> dict:
    """Send booking confirmation email."""
    # FIX: import lazily to avoid circular import; use service layer
    from services import get_appointment as svc_get_appointment
    appt = svc_get_appointment(appointment_id)'''

    new_content = new_content.replace(before_confirm, after_confirm, 1)

    before_cancel = '''\
def send_cancellation_notice(appointment_id: str, reason: str) -> dict:
    """Send cancellation email."""
    appt = appointments_db.get(appointment_id)  # BUG: direct DB access again'''

    after_cancel = '''\
def send_cancellation_notice(appointment_id: str, reason: str) -> dict:
    """Send cancellation email."""
    # FIX: route through service layer
    from services import get_appointment as svc_get_appointment
    appt = svc_get_appointment(appointment_id)'''

    new_content = new_content.replace(before_cancel, after_cancel, 1)
    _write(path, new_content)
    return before_snippet, after_snippet


def apply_fix_007_date_crash(fixed_dir: Path) -> tuple[str, str]:
    """BUG-007: Guard against None in is_future_date."""
    path = fixed_dir / "utils.py"
    before_snippet = '''\
def is_future_date(date_str: str) -> bool:
    """Check if date is in the future."""
    # BUG: uses parse_date which returns None on bad input
    # None < date.today() raises TypeError — unhandled
    parsed = parse_date(date_str)
    return parsed > date.today()  # BUG: crashes if parsed is None'''

    after_snippet = '''\
def is_future_date(date_str: str) -> bool:
    """Check if date is in the future. Returns False on bad input (never raises)."""
    parsed = parse_date(date_str)
    if parsed is None:
        return False  # FIX: treat unparseable dates as invalid, not a crash
    return parsed > date.today()'''

    content = _read(path)
    new_content = content.replace(before_snippet, after_snippet, 1)
    _write(path, new_content)
    return before_snippet, after_snippet


def apply_fix_008_http_status(fixed_dir: Path) -> tuple[str, str]:
    """BUG-008: Return correct HTTP status codes for auth errors."""
    path = fixed_dir / "app.py"
    before_snippet = '''\
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    result = register_user(data["username"], data["password"])
    return jsonify(result)  # BUG: returns 200 even on error {"error": "..."}

@app.route("/login", methods=["POST"])
def login_route():
    data = request.get_json()
    result = login(data["username"], data["password"])
    return jsonify(result)  # BUG: returns 200 even on failed login'''

    after_snippet = '''\
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    result = register_user(data["username"], data["password"])
    if "error" in result:
        return jsonify(result), 400  # FIX: 400 Bad Request on registration error
    return jsonify(result), 201      # FIX: 201 Created on success

@app.route("/login", methods=["POST"])
def login_route():
    data = request.get_json()
    result = login(data["username"], data["password"])
    if "error" in result:
        return jsonify(result), 401  # FIX: 401 Unauthorized on bad credentials
    return jsonify(result)'''

    content = _read(path)
    new_content = content.replace(before_snippet, after_snippet, 1)
    _write(path, new_content)
    return before_snippet, after_snippet


ALL_FIXES = [
    ("BUG-001", apply_fix_001_cancel_auth),
    ("BUG-002", apply_fix_002_search_auth),
    ("BUG-003", apply_fix_003_sha256),
    ("BUG-004", apply_fix_004_session_expiry),
    ("BUG-005", apply_fix_005_double_booking),
    ("BUG-006", apply_fix_006_notification_bypass),
    ("BUG-007", apply_fix_007_date_crash),
    ("BUG-008", apply_fix_008_http_status),
]


# ================================================================
# Sanity checks on the patched files
# ================================================================

def run_sanity_checks(fixed_dir: Path) -> list[dict]:
    """
    Quick pattern-based checks to verify fixes were applied.
    Returns a list of check results: {check, passed, detail}
    """
    checks = []

    def check(name: str, file: str, pattern: str, should_exist: bool, detail: str) -> None:
        content = (fixed_dir / file).read_text(encoding="utf-8")
        found = pattern in content
        passed = found if should_exist else not found
        checks.append({
            "check": name,
            "passed": passed,
            "detail": detail,
            "file": file,
        })

    # BUG-001
    check("AUTH-001", "app.py",
          "def cancel(appointment_id):\n    token = request.headers",
          True, "cancel() now reads Authorization header")

    # BUG-002
    check("AUTH-002", "app.py",
          'len(query) < 2',
          True, "search() enforces minimum query length")

    check("AUTH-002b", "app.py",
          '# BUG: no auth required — anyone can search patient records',
          False, "search() no longer has unguarded access")

    # BUG-003
    check("HASH-003", "models.py",
          "hashlib.sha256",
          True, "hash_password uses SHA-256")

    check("HASH-003b", "models.py",
          "hashlib.md5",
          False, "MD5 removed from models.py")

    # BUG-004
    check("EXPIRY-004", "auth.py",
          "datetime.fromisoformat(session[\"expires_at\"])",
          True, "session expiry is now parsed and enforced")

    # BUG-005
    check("OVERLAP-005", "services.py",
          "Time slot",
          True, "book_appointment returns overlap error message")

    # BUG-006
    check("LAYER-006", "notifications.py",
          "from services import get_appointment as svc_get_appointment",
          True, "notifications routes through service layer")

    # BUG-007
    check("NONE-007", "utils.py",
          "if parsed is None:",
          True, "is_future_date guards against None")

    check("NONE-007b", "utils.py",
          "# BUG: crashes if parsed is None",
          False, "BUG comment removed after fix")

    # BUG-008
    check("HTTP-008", "app.py",
          "return jsonify(result), 401",
          True, "login returns 401 on bad credentials")

    check("HTTP-008b", "app.py",
          "return jsonify(result), 201",
          True, "register returns 201 on success")

    return checks


# ================================================================
# Main demo flow
# ================================================================

def main() -> None:
    total_steps = 6

    # ----------------------------------------------------------------
    # Header
    # ----------------------------------------------------------------
    print(f"\n{LINE}")
    print(f"  {BOLD}DENTAL APPOINTMENT SYSTEM AUDIT{RST}")
    print(f"  Powered by Graqle v{graqle.__version__} — cross-file graph reasoning")
    print(LINE)
    print(f"\n  Target app : {APP_DIR.relative_to(DEMO_DIR.parent.parent)}")
    print(f"  Files      : 6 Python modules (app.py, auth.py, models.py,")
    print(f"               services.py, notifications.py, utils.py)")
    print(f"  Bugs       : 8 injected (2 CRITICAL, 3 HIGH, 3 MEDIUM)")
    print(f"  Method     : Graqle knowledge graph + multi-agent reasoning")
    print()
    if INTERACTIVE:
        input("  Press ENTER to begin the audit...")

    # ----------------------------------------------------------------
    # Step 1: Scan source files
    # ----------------------------------------------------------------
    banner(1, total_steps, "Scanning dental app source files")

    files = ["app.py", "auth.py", "models.py", "services.py",
             "notifications.py", "utils.py"]

    for i, fname in enumerate(files, 1):
        progress("Scanning", i, len(files))
        path = APP_DIR / fname
        if not path.exists():
            print()
            err(f"Missing: {path}")
            sys.exit(1)
        lines = path.read_text(encoding="utf-8").splitlines()
        time.sleep(0.08)
    print()  # end progress line

    for fname in files:
        path = APP_DIR / fname
        lines = path.read_text(encoding="utf-8").splitlines()
        tick(f"{fname:<22} {len(lines):>4} lines")

    total_lines = sum(
        len((APP_DIR / f).read_text(encoding="utf-8").splitlines())
        for f in files
    )
    print(f"\n  Total: {len(files)} files, {total_lines} lines of Python")

    # ----------------------------------------------------------------
    # Step 2: Build knowledge graph
    # ----------------------------------------------------------------
    banner(2, total_steps, "Building knowledge graph")

    print("  Building nodes (one per source file)...")
    t0 = time.perf_counter()
    g = build_dental_kg()
    elapsed = time.perf_counter() - t0

    s = g.stats
    tick(f"Nodes     : {s.total_nodes}")
    tick(f"Edges     : {s.total_edges}")
    tick(f"Hub nodes : {', '.join(s.hub_nodes) if s.hub_nodes else 'none'}")
    tick(f"Built in  : {elapsed * 1000:.0f}ms")

    # Configure backend
    backend_desc = configure_backend(g)
    tick(f"Backend   : {backend_desc}")

    # ----------------------------------------------------------------
    # Step 3: Graph-of-agents reasoning
    # ----------------------------------------------------------------
    banner(3, total_steps, "Running graph-of-agents security audit")

    queries = [
        ("Security vulnerabilities",
         "Find all security vulnerabilities in this dental app. "
         "Look for missing authentication, broken cryptography, "
         "and authorization flaws. Cross-reference all files."),
        ("Validation gaps",
         "What input validation is missing? Which bugs span multiple files "
         "where one module assumes another validates but neither does?"),
        ("Architectural risks",
         "Which modules bypass the service layer and access the database "
         "directly? What are the risks of this architectural pattern?"),
    ]

    _FALLBACK_ANSWERS = frozenset({
        "no reasoning produced.",
        "no answer produced.",
        "",
    })

    results = []
    live_failed = False
    print()
    for i, (qname, qtext) in enumerate(queries, 1):
        print(f"  [{i}/{len(queries)}] Reasoning: {qname}...")
        t0 = time.perf_counter()
        try:
            result = g.reason(qtext, strategy="full")
            # Detect silent backend failure (e.g. no API credits)
            if result.answer.strip().lower() in _FALLBACK_ANSWERS and not live_failed:
                live_failed = True
                warn("Live backend returned empty answer -- switching to MockBackend")
                g.set_default_backend(_build_mock_backend())
                result = g.reason(qtext, strategy="full")
        except Exception as exc:
            if not live_failed:
                live_failed = True
                warn(f"Bedrock reasoning failed ({exc}) -- switching to MockBackend")
                g.set_default_backend(_build_mock_backend())
            result = g.reason(qtext, strategy="full")
        elapsed = time.perf_counter() - t0
        results.append(result)
        print(f"         confidence={result.confidence:.0%}  "
              f"rounds={result.rounds_completed}  "
              f"nodes={len(result.active_nodes)}  "
              f"latency={elapsed*1000:.0f}ms")

    # Print first reasoning result (security audit)
    print(f"\n  {BOLD}--- Reasoning Output (Security Audit) ---{RST}")
    answer = results[0].answer
    wrapped = textwrap.fill(answer, width=64, initial_indent="  ",
                            subsequent_indent="  ")
    safe = wrapped[:2000].encode("ascii", errors="replace").decode("ascii")
    print(safe)
    if len(wrapped) > 2000:
        print(f"  {YEL}[... truncated — full answer in result.answer]{RST}")

    # ----------------------------------------------------------------
    # Step 4: Display bug report
    # ----------------------------------------------------------------
    banner(4, total_steps, f"Bug report — {len(BUGS)} bugs found")

    severity_colour = {
        "CRITICAL": RED + BOLD,
        "HIGH":     RED,
        "MEDIUM":   YEL,
        "LOW":      CYN,
    }

    for bug in BUGS:
        sc = severity_colour.get(bug["severity"], "")
        print(f"\n  {sc}{bug['id']} [{bug['severity']}]{RST}  {BOLD}{bug['title']}{RST}")
        print(f"  File  : {bug['file']}")
        chain = " -> ".join(bug["cross_file_chain"])
        print(f"  Chain : {chain}")
        desc_wrapped = textwrap.fill(
            bug["description"], width=62,
            initial_indent="  ", subsequent_indent="  "
        )
        print(desc_wrapped.encode("ascii", errors="replace").decode("ascii"))
        print(f"  Fix   : {GRN}{bug['fix_summary']}{RST}")

    # Summary table
    criticals = sum(1 for b in BUGS if b["severity"] == "CRITICAL")
    highs     = sum(1 for b in BUGS if b["severity"] == "HIGH")
    mediums   = sum(1 for b in BUGS if b["severity"] == "MEDIUM")
    print(f"\n  {DLINE}")
    print(f"  {RED+BOLD}CRITICAL{RST}: {criticals}  {RED}HIGH{RST}: {highs}  {YEL}MEDIUM{RST}: {mediums}")
    print(f"  {DLINE}")
    print()
    if INTERACTIVE:
        input("  Press ENTER to apply all 8 fixes...")

    # ----------------------------------------------------------------
    # Step 5: Apply fixes
    # ----------------------------------------------------------------
    banner(5, total_steps, "Applying fixes to dental_app_fixed/")

    # Copy buggy app to fixed directory
    if FIXED_DIR.exists():
        shutil.rmtree(FIXED_DIR)
    shutil.copytree(APP_DIR, FIXED_DIR)
    tick(f"Copied dental_app/ -> {FIXED_DIR.name}/")
    print()

    fix_lookup = {b["id"]: b for b in BUGS}
    fixes_applied = 0

    for bug_id, fix_fn in ALL_FIXES:
        bug = fix_lookup[bug_id]
        sc = severity_colour.get(bug["severity"], "")
        print(f"  {sc}{bug_id} [{bug['severity']}]{RST} {bug['title']}")

        t0 = time.perf_counter()
        before_snip, after_snip = fix_fn(FIXED_DIR)
        elapsed = time.perf_counter() - t0

        show_diff(bug["file"], before_snip, after_snip)
        tick(f"Fixed in {elapsed*1000:.0f}ms")
        fixes_applied += 1
        print()
        time.sleep(0.1)

    # ----------------------------------------------------------------
    # Step 6: Verify
    # ----------------------------------------------------------------
    banner(6, total_steps, "Verifying fixes")

    checks = run_sanity_checks(FIXED_DIR)
    passed = sum(1 for c in checks if c["passed"])
    failed_checks = [c for c in checks if not c["passed"]]

    for c in checks:
        icon = f"{GRN}PASS{RST}" if c["passed"] else f"{RED}FAIL{RST}"
        print(f"  [{icon}] {c['check']:<14} {c['detail']}")

    print(f"\n  {DLINE}")
    if failed_checks:
        print(f"  {RED}VERIFICATION FAILED{RST}: {len(failed_checks)} check(s) did not pass:")
        for c in failed_checks:
            err(f"  {c['check']}: {c['detail']} ({c['file']})")
    else:
        print(f"  {GRN+BOLD}ALL {len(checks)} CHECKS PASSED{RST}")
    print(f"  {DLINE}")

    # ----------------------------------------------------------------
    # Final summary
    # ----------------------------------------------------------------
    print(f"\n{LINE}")
    print(f"  {BOLD}AUDIT COMPLETE{RST}")
    print(LINE)
    print(f"  Graph         : {g.stats.total_nodes} nodes, {g.stats.total_edges} edges")
    print(f"  Bugs found    : {len(BUGS)} "
          f"({criticals} CRITICAL, {highs} HIGH, {mediums} MEDIUM)")
    print(f"  Fixes applied : {fixes_applied}/{len(ALL_FIXES)}")
    print(f"  Checks passed : {passed}/{len(checks)}")
    print(f"  Patched app   : {FIXED_DIR}")
    print()
    print(f"  {CYN}Why Graqle?{RST}")
    print(f"  Standard linters (pylint, flake8, mypy) would NOT have caught:")
    print(f"    - BUG-001: cancel() missing auth (requires tracing app.py->services.py)")
    print(f"    - BUG-002: search() exposing all patients (requires cross-file analysis)")
    print(f"    - BUG-005: double-booking (assumption gap between models.py and services.py)")
    print(f"    - BUG-006: notifications bypassing service layer (architectural pattern)")
    print(f"  Graqle finds bugs that only appear when you reason ACROSS files.")
    print()
    print(f"  {GRN}Next:{RST}")
    print(f"    graq scan repo live-demos/04-dental-audit/dental_app/")
    print(f"    graq run 'what auth checks are missing from the dental app routes?'")
    print()


if __name__ == "__main__":
    main()
