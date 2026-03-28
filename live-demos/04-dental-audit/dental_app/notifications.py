"""
Notification service.
BUG: Bypasses services.py entirely — queries appointments_db directly.
This means if services.py adds business logic (e.g. status filtering),
notifications.py won't get it. Schema changes to appointments_db break
this silently.
"""
from datetime import datetime, date
from models import appointments_db, patients_db  # BUG: direct DB access

def get_tomorrows_appointments() -> list:
    """Get all appointments for tomorrow — used for reminder emails."""
    # BUG: naive datetime comparison, no timezone handling
    tomorrow = date.today().replace(day=date.today().day + 1)  # BUG: will crash on month-end

    results = []
    for appt in appointments_db.values():
        try:
            appt_date = datetime.strptime(appt["date"], "%Y-%m-%d").date()
            if appt_date == tomorrow:
                patient = patients_db.get(appt["patient_id"], {})
                results.append({
                    "appointment": appt,
                    "patient_name": patient.get("name", "Unknown"),
                    "patient_email": patient.get("email", ""),
                })
        except (ValueError, KeyError):
            # BUG: silently swallows bad date formats
            pass

    return results

def send_confirmation(appointment_id: str) -> dict:
    """Send booking confirmation email."""
    # BUG: queries appointments_db directly instead of using services.get_appointment
    appt = appointments_db.get(appointment_id)
    if not appt:
        return {"error": "Appointment not found"}

    patient = patients_db.get(appt["patient_id"], {})
    # Simulate sending email
    print(f"[EMAIL] Confirmation to {patient.get('email', 'unknown')}: "
          f"Appointment {appointment_id} on {appt['date']} at {appt['time_slot']}")
    return {"sent": True, "to": patient.get("email", "")}

def send_cancellation_notice(appointment_id: str, reason: str) -> dict:
    """Send cancellation email."""
    appt = appointments_db.get(appointment_id)  # BUG: direct DB access again
    if not appt:
        return {"error": "not found"}
    patient = patients_db.get(appt["patient_id"], {})
    print(f"[EMAIL] Cancellation to {patient.get('email', 'unknown')}: "
          f"Appointment {appointment_id} cancelled. Reason: {reason}")
    return {"sent": True}
