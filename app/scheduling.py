"""View helpers shared by the patient and admin booking / rescheduling screens."""
from datetime import date, timedelta

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from . import services
from .extensions import db
from .models import Appointment, Provider


def slot_choices(provider: Provider | None, day: date | None, exclude_id: int | None = None) -> list[tuple[str, str]]:
    if provider is None or day is None:
        return []
    return [(s.strftime("%H:%M"), s.strftime("%I:%M %p")) for s in services.available_slots(provider, day, exclude_id)]


def date_bounds() -> dict:
    today = services.now().date()
    return {"min_date": today.isoformat(), "max_date": (today + timedelta(days=services.MAX_BOOKING_DAYS_AHEAD)).isoformat()}


def validate_slot_request(provider: Provider | None, day: date, slot_value: str, patient_id: int, exclude_id: int | None = None):
    """Return (start_at, error_message). Exactly one of them is None."""
    if provider is None or not provider.is_active:
        return None, "Please choose an available healthcare provider."
    if not services.is_bookable_date(day):
        return None, f"Please choose a date between today and {services.MAX_BOOKING_DAYS_AHEAD} days from now."
    start_at = services.parse_slot(day, slot_value)
    if start_at is None:
        return None, "Please choose a valid time slot."
    if not services.is_slot_available(provider, start_at, exclude_id):
        return None, "Sorry, that slot is no longer available. Please pick another one."
    if services.patient_has_conflict(patient_id, start_at, exclude_id):
        return None, "The patient already has another appointment at that time."
    return start_at, None


def reschedule(appointment: Appointment, day: date, slot_value: str):
    """FR018-FR020: move an appointment to a new available slot."""
    start_at, error = validate_slot_request(
        appointment.provider, day, slot_value, appointment.patient_id, exclude_id=appointment.id
    )
    if error:
        return False, error
    appointment.start_at = start_at
    db.session.commit()
    return True, f"Appointment rescheduled to {start_at:%a, %d %b %Y at %I:%M %p}."


# --- JSON endpoint used by the booking / rescheduling pages -----------------
api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/providers/<int:provider_id>/slots")
@login_required
def provider_slots(provider_id: int):
    provider = db.get_or_404(Provider, provider_id)
    try:
        day = date.fromisoformat(request.args.get("date", ""))
    except ValueError:
        return jsonify({"error": "Invalid date", "slots": []}), 400

    exclude_id = request.args.get("exclude", type=int)
    if exclude_id is not None:
        appt = db.session.get(Appointment, exclude_id)
        # Only allow excluding an appointment the caller may manage.
        if appt is None or (appt.patient_id != current_user.id and not current_user.is_admin):
            exclude_id = None

    reason = None
    if not provider.is_active:
        reason = f"{provider.name} is not accepting appointments right now."
    elif not services.is_bookable_date(day):
        reason = "Please pick a date from today onwards (up to 90 days ahead)."
    elif not provider.works_on(day):
        reason = f"{provider.name} works on {provider.working_days_label}."

    slots = [{"value": v, "label": l} for v, l in slot_choices(provider, day, exclude_id)]
    if not slots and reason is None:
        reason = "All slots on this day are booked. Please try another date."
    return jsonify({"slots": slots, "message": reason})
