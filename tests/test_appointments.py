"""Sprint 1 & 2: booking (US03), manage / cancel (US04), dashboard (US05),
reminders (US06) and rescheduling (US07)."""
from datetime import datetime, time, timedelta

from app.models import Appointment

from .conftest import create_patient, future_day, login, make_appointment, next_weekend_day, provider_id, register


def book(client, pid, day, slot, reason=""):
    return client.post(
        "/appointments/book",
        data={"provider_id": pid, "date": day.isoformat(), "slot": slot, "reason": reason},
        follow_redirects=True,
    )


def get_appt(app, appt_id):
    from app.extensions import db

    with app.app_context():
        appt = db.session.get(Appointment, appt_id)
        db.session.expunge(appt)
        return appt


def test_pages_require_login(client):
    for url in ["/dashboard", "/appointments", "/appointments/book", "/api/providers/1/slots?date=2030-01-01"]:
        res = client.get(url)
        assert res.status_code == 302 and "/login" in res.headers["Location"], url


def test_slots_api_lists_available_slots(patient, app):
    pid = provider_id(app)
    res = patient.get(f"/api/providers/{pid}/slots?date={future_day().isoformat()}")
    data = res.get_json()
    assert res.status_code == 200
    assert len(data["slots"]) == 24  # 08:00-20:00 in 30 minute slots
    assert data["slots"][0] == {"value": "08:00", "label": "08:00 AM"}


def test_slots_api_explains_non_working_day(patient, app):
    pid = provider_id(app, "Dr. Weekday")
    data = patient.get(f"/api/providers/{pid}/slots?date={next_weekend_day().isoformat()}").get_json()
    assert data["slots"] == []
    assert "works on" in data["message"]


def test_book_appointment(patient, app):
    pid = provider_id(app)
    day = future_day()
    res = book(patient, pid, day, "10:30", "Headache")
    assert b"Appointment booked with Dr. Test" in res.data
    with app.app_context():
        appt = Appointment.query.one()
        assert appt.start_at == datetime.combine(day, time(10, 30))
        assert appt.status == Appointment.PENDING
        assert appt.reason == "Headache"

    # The booked slot is no longer offered.
    data = patient.get(f"/api/providers/{pid}/slots?date={day.isoformat()}").get_json()
    assert "10:30" not in [s["value"] for s in data["slots"]]


def test_cannot_double_book_a_slot(patient, client, app):
    pid = provider_id(app)
    day = future_day()
    book(patient, pid, day, "11:00")
    patient.post("/logout")
    register(client, "bob", "bob@example.com")
    login(client, "bob")
    res = book(client, pid, day, "11:00")
    assert b"no longer available" in res.data
    with app.app_context():
        assert Appointment.query.count() == 1


def test_cannot_book_past_or_invalid_slots(patient, app):
    pid = provider_id(app)
    yesterday = datetime.now().date() - timedelta(days=1)
    assert b"Please choose a date between today" in book(patient, pid, yesterday, "10:00").data
    assert b"no longer available" in book(patient, pid, future_day(), "07:00").data  # outside hours
    assert b"no longer available" in book(patient, pid, future_day(), "10:15").data  # not on slot grid
    weekday_pid = provider_id(app, "Dr. Weekday")
    assert b"no longer available" in book(patient, weekday_pid, next_weekend_day(), "09:00").data
    with app.app_context():
        assert Appointment.query.count() == 0


def test_patient_cannot_hold_two_appointments_at_same_time(patient, app):
    day = future_day()
    book(patient, provider_id(app), day, "09:00")
    res = book(patient, provider_id(app, "Dr. Weekday"), day, "09:00")
    if day.weekday() < 5:
        assert b"already has another appointment" in res.data
    with app.app_context():
        assert Appointment.query.count() == 1


def test_appointments_page_splits_upcoming_and_history(patient, app):
    make_appointment(app, start_at=datetime.combine(future_day(), time(9, 0)))
    make_appointment(app, start_at=datetime.now() - timedelta(days=5), status=Appointment.COMPLETED)
    res = patient.get("/appointments")
    html = res.data.decode()
    assert "Upcoming <span class=\"badge text-bg-primary\">1</span>" in html
    assert "History <span class=\"badge text-bg-secondary\">1</span>" in html
    assert "Completed" in html


def test_cancel_appointment(patient, app):
    appt_id = make_appointment(app)
    res = patient.post(f"/appointments/{appt_id}/cancel", follow_redirects=True)
    assert b"was cancelled" in res.data
    assert get_appt(app, appt_id).status == Appointment.CANCELLED
    # Cancelled slot is free again.
    appt = get_appt(app, appt_id)
    data = patient.get(f"/api/providers/{appt.provider_id}/slots?date={appt.start_at.date()}").get_json()
    assert appt.start_at.strftime("%H:%M") in [s["value"] for s in data["slots"]]


def test_cannot_cancel_or_reschedule_someone_elses_appointment(client, app):
    register(client, "bob", "bob@example.com")
    register(client)
    appt_id = make_appointment(app, username="bob")
    login(client)
    assert client.post(f"/appointments/{appt_id}/cancel").status_code == 404
    assert client.get(f"/appointments/{appt_id}/reschedule").status_code == 404
    assert get_appt(app, appt_id).status == Appointment.PENDING


def test_cannot_cancel_past_appointment(patient, app):
    appt_id = make_appointment(app, start_at=datetime.now() - timedelta(hours=2))
    res = patient.post(f"/appointments/{appt_id}/cancel", follow_redirects=True)
    assert b"Only upcoming, active appointments" in res.data
    assert get_appt(app, appt_id).status == Appointment.PENDING


def test_reschedule_appointment(patient, app):
    appt_id = make_appointment(app)
    new_day = future_day(5)
    res = patient.post(
        f"/appointments/{appt_id}/reschedule",
        data={"date": new_day.isoformat(), "slot": "15:00"},
        follow_redirects=True,
    )
    assert b"Appointment rescheduled" in res.data
    assert get_appt(app, appt_id).start_at == datetime.combine(new_day, time(15, 0))


def test_reschedule_to_taken_slot_is_rejected(patient, app):
    create_patient(app, "bob", "bob@example.com")
    taken = datetime.combine(future_day(4), time(12, 0))
    make_appointment(app, username="bob", start_at=taken)
    appt_id = make_appointment(app)
    res = patient.post(
        f"/appointments/{appt_id}/reschedule",
        data={"date": taken.date().isoformat(), "slot": "12:00"},
        follow_redirects=True,
    )
    assert b"no longer available" in res.data
    assert get_appt(app, appt_id).start_at != taken


def test_reschedule_page_offers_current_slot(patient, app):
    appt_id = make_appointment(app)
    appt = get_appt(app, appt_id)
    data = patient.get(
        f"/api/providers/{appt.provider_id}/slots?date={appt.start_at.date()}&exclude={appt_id}"
    ).get_json()
    assert appt.start_at.strftime("%H:%M") in [s["value"] for s in data["slots"]]


def test_reminder_shown_for_appointment_within_24_hours(patient, app):
    make_appointment(app, start_at=datetime.now() + timedelta(hours=3))
    make_appointment(app, start_at=datetime.now() + timedelta(days=3))
    html = patient.get("/dashboard").data.decode()
    assert "Reminders: appointments in the next 24 hours" in html
    assert html.count("reminder-item") == 1


def test_no_reminder_for_cancelled_or_distant_appointments(patient, app):
    make_appointment(app, start_at=datetime.now() + timedelta(hours=3), status=Appointment.CANCELLED)
    make_appointment(app, start_at=datetime.now() + timedelta(days=2))
    html = patient.get("/dashboard").data.decode()
    assert "Reminders:" not in html
