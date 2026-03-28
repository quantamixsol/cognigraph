"""
Date and time utilities.
"""
from datetime import datetime, date, timedelta

VALID_TIME_SLOTS = [
    "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
    "13:00", "13:30", "14:00", "14:30", "15:00", "15:30",
    "16:00", "16:30"
]

def parse_date(date_str: str) -> date | None:
    """Parse date string. Returns None on failure."""
    # BUG: only handles one format — "2026-03-28" works, "28/03/2026" silently fails
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None  # BUG: returns None silently, caller rarely checks

def is_valid_time_slot(time_slot: str) -> bool:
    return time_slot in VALID_TIME_SLOTS

def is_future_date(date_str: str) -> bool:
    """Check if date is in the future."""
    # BUG: uses parse_date which returns None on bad input
    # None < date.today() raises TypeError — unhandled
    parsed = parse_date(date_str)
    return parsed > date.today()  # BUG: crashes if parsed is None

def get_available_slots(dentist: str, date_str: str, booked: list[str]) -> list[str]:
    """Return available time slots for a dentist on a given date."""
    return [s for s in VALID_TIME_SLOTS if s not in booked]

def format_appointment(appt: dict) -> str:
    """Format appointment for display."""
    return (
        f"ID: {appt.get('appointment_id', '?')[:8]}... | "
        f"Patient: {appt.get('patient_id', '?')[:8]}... | "
        f"Date: {appt.get('date', '?')} {appt.get('time_slot', '?')} | "
        f"Dentist: {appt.get('dentist', '?')} | "
        f"Status: {appt.get('status', '?')}"
    )
