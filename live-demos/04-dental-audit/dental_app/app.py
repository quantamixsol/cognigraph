"""
Flask dental appointment API.
"""
from flask import Flask, request, jsonify
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from services import (
    register_patient, book_appointment, cancel_appointment,
    get_patient_appointments, search_patients
)
from auth import login, register_user, require_auth
from notifications import send_confirmation, send_cancellation_notice
from utils import is_valid_time_slot, is_future_date, format_appointment
from models import get_appointment, appointments_db

app = Flask(__name__)

# ----------------------------------------------------------------
# Auth routes
# ----------------------------------------------------------------

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    result = register_user(data["username"], data["password"])
    return jsonify(result)  # BUG: returns 200 even on error {"error": "..."}

@app.route("/login", methods=["POST"])
def login_route():
    data = request.get_json()
    result = login(data["username"], data["password"])
    return jsonify(result)  # BUG: returns 200 even on failed login

# ----------------------------------------------------------------
# Patient routes
# ----------------------------------------------------------------

@app.route("/patients", methods=["POST"])
def create_patient():
    # BUG: no auth required to create a patient
    data = request.get_json()
    result = register_patient(
        name=data["name"],
        email=data["email"],
        phone=data["phone"],
        dob=data.get("date_of_birth", "")
    )
    return jsonify(result)

@app.route("/patients/search", methods=["GET"])
def search():
    # BUG: no auth required — anyone can search patient records (HIPAA violation)
    query = request.args.get("q", "")
    # BUG: no minimum query length — empty string returns ALL patients
    results = search_patients(query)
    return jsonify(results)

# ----------------------------------------------------------------
# Appointment routes
# ----------------------------------------------------------------

@app.route("/appointments", methods=["POST"])
def create_appointment():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user = require_auth(token)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()

    # BUG: time_slot validation happens here but date validation does NOT
    if not is_valid_time_slot(data.get("time_slot", "")):
        return jsonify({"error": "Invalid time slot"}), 400

    # BUG: is_future_date crashes on bad date format (TypeError from utils.py)
    # No try/except wrapping it
    if not is_future_date(data.get("date", "")):
        return jsonify({"error": "Date must be in the future"}), 400

    result = book_appointment(
        patient_id=data["patient_id"],
        dentist=data["dentist"],
        date=data["date"],
        time_slot=data["time_slot"],
        procedure=data.get("procedure", "General checkup")
    )

    if "error" not in result:
        send_confirmation(result["appointment_id"])

    return jsonify(result)

@app.route("/appointments/<appointment_id>/cancel", methods=["POST"])
def cancel(appointment_id):
    # BUG: NO AUTH CHECK — any unauthenticated user can cancel any appointment
    data = request.get_json() or {}
    reason = data.get("reason", "")
    result = cancel_appointment(appointment_id, reason)

    if "error" not in result:
        send_cancellation_notice(appointment_id, reason)

    return jsonify(result)  # BUG: returns 200 on error too

@app.route("/appointments/<appointment_id>", methods=["GET"])
def get_appointment_route(appointment_id):
    # BUG: no auth check — any unauthenticated user can view any appointment
    appt = get_appointment(appointment_id)
    if not appt:
        return jsonify({"error": "Not found"}), 404
    return jsonify(appt)

@app.route("/patients/<patient_id>/appointments", methods=["GET"])
def patient_appointments(patient_id):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user = require_auth(token)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    # BUG: no check that the requesting user is authorized for THIS patient
    # Any authenticated user can see any patient's appointments
    appointments = get_patient_appointments(patient_id)
    return jsonify(appointments)

if __name__ == "__main__":
    # Seed some test data
    from auth import register_user
    register_user("admin", "admin123", role="admin")
    register_user("receptionist", "pass123", role="receptionist")
    print("Dental Appointment System running on http://localhost:5000")
    app.run(debug=True, port=5000)
