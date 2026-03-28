"""
Patient and Appointment data models.
In-memory storage — no real DB needed for demo.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import hashlib

# In-memory storage
patients_db: dict[str, dict] = {}
appointments_db: dict[str, dict] = {}
users_db: dict[str, dict] = {}

@dataclass
class Patient:
    patient_id: str
    name: str
    email: str
    phone: str
    date_of_birth: str  # BUG: stored as string, never validated

@dataclass
class Appointment:
    appointment_id: str
    patient_id: str
    dentist: str
    date: str          # BUG: stored as string, no timezone info
    time_slot: str     # BUG: "09:00" — never checked for overlap
    procedure: str
    status: str = "scheduled"   # scheduled/cancelled/completed
    notes: str = ""

def get_patient(patient_id: str) -> Optional[dict]:
    return patients_db.get(patient_id)

def get_appointment(appointment_id: str) -> Optional[dict]:
    return appointments_db.get(appointment_id)

def save_patient(patient: dict) -> None:
    # BUG: no validation — any dict accepted
    patients_db[patient["patient_id"]] = patient

def save_appointment(appt: dict) -> None:
    # BUG: no validation — no overlap check here (assumed to be in services)
    appointments_db[appt["appointment_id"]] = appt

def hash_password(password: str) -> str:
    # BUG: MD5 — completely insecure
    return hashlib.md5(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed
