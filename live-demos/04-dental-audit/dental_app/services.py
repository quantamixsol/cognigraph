"""
Booking business logic.
ASSUMPTION (undocumented): models.py validates all inputs before save.
REALITY: models.py does NO validation. Neither does services.py.
"""
import uuid
from datetime import datetime
from models import (
    get_patient, get_appointment, save_patient, save_appointment,
    appointments_db, patients_db
)

def register_patient(name: str, email: str, phone: str, dob: str) -> dict:
    # BUG: No email validation
    # BUG: No phone validation
    # BUG: dob is never parsed — "not-a-date" would be accepted
    patient_id = str(uuid.uuid4())
    patient = {
        "patient_id": patient_id,
        "name": name,
        "email": email,
        "phone": phone,
        "date_of_birth": dob,
    }
    save_patient(patient)
    return {"patient_id": patient_id, "name": name}

def book_appointment(patient_id: str, dentist: str, date: str,
                     time_slot: str, procedure: str) -> dict:
    patient = get_patient(patient_id)
    if not patient:
        return {"error": "Patient not found"}

    # BUG: No overlap check — two patients can book same dentist+date+time
    # Should check: any existing appointment with same dentist+date+time_slot

    appt_id = str(uuid.uuid4())
    appt = {
        "appointment_id": appt_id,
        "patient_id": patient_id,
        "dentist": dentist,
        "date": date,          # BUG: accepted as-is, "yesterday" would work
        "time_slot": time_slot,
        "procedure": procedure,
        "status": "scheduled",
        "notes": "",
    }
    save_appointment(appt)
    return {"appointment_id": appt_id, "status": "scheduled"}

def cancel_appointment(appointment_id: str, reason: str = "") -> dict:
    appt = get_appointment(appointment_id)
    if not appt:
        return {"error": "Appointment not found"}

    # BUG: No auth check — services.py assumes app.py verified the user
    # REALITY: app.py's cancel route has no auth requirement
    appt["status"] = "cancelled"
    appt["notes"] = reason
    save_appointment(appt)
    return {"status": "cancelled"}

def get_patient_appointments(patient_id: str) -> list:
    return [
        a for a in appointments_db.values()
        if a["patient_id"] == patient_id
    ]

def search_patients(query: str) -> list:
    # BUG: SQL injection style — if this were a real DB query:
    # f"SELECT * FROM patients WHERE name LIKE '%{query}%'"
    # For in-memory demo, we simulate the vulnerability pattern
    query_lower = query.lower()
    return [
        p for p in patients_db.values()
        if query_lower in p["name"].lower() or
           query_lower in p["email"].lower()
    ]
