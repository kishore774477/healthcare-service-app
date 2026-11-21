"""Sprint 3: admin appointment management (US08) and schedule monitoring (US09)."""
from datetime import datetime, timedelta

from app.extensions import db
from app.models import Appointment, Provider

from .conftest import future_day, login, logout, make_appointment, provider_id, register


def status_of(app, appt_id):
    with app.app_context():
        return db.session.get(Appointment, appt_id).status


def admin_client(client):
    login(client, "admin", "Admin@123")
    return client


def test_patient_cannot_access_admin(patient):
    for url in ["/admin/", "/admin/appointments", "/admin/schedule", "/admin/providers"]:
        assert patient.get(url).status_code == 403, url


def test_admin_pages_render(client, app):
    register(client)
    make_appointment(app)
    admin_client(client)
    for url in ["/admin/", "/admin/appointments", "/admin/schedule", "/admin/providers",
                f"/admin/schedule?date={future_day().isoformat()}", "/admin/appointments?status=Pending"]:
        res = client.get(url)
        assert res.status_code == 200, url
    assert b"alice" in client.get("/admin/appointments").data


def test_admin_approve_cancel_complete(client, app):
    register(client)
    a1 = make_appointment(app)
    a2 = make_appointment(app, start_at=datetime.combine(future_day(4), datetime.min.time().replace(hour=9)))
    past = make_appointment(app, start_at=datetime.now() - timedelta(hours=1), status=Appointment.CONFIRMED)
    admin_client(client)

    assert b"Appointment confirmed" in client.post(f"/admin/appointments/{a1}/approve", follow_redirects=True).data
    assert status_of(app, a1) == Appointment.CONFIRMED

    client.post(f"/admin/appointments/{a2}/cancel")
    assert status_of(app, a2) == Appointment.CANCELLED

    # Future appointments can't be completed; past ones can.
    client.post(f"/admin/appointments/{a1}/complete")
    assert status_of(app, a1) == Appointment.CONFIRMED
    client.post(f"/admin/appointments/{past}/complete")
    assert status_of(app, past) == Appointment.COMPLETED

    assert client.post(f"/admin/appointments/{a1}/delete").status_code == 404


def test_admin_reschedule(client, app):
    register(client)
    appt_id = make_appointment(app)
    admin_client(client)
    new_day = future_day(6)
    res = client.post(
        f"/admin/appointments/{appt_id}/reschedule",
        data={"date": new_day.isoformat(), "slot": "16:30"},
        follow_redirects=True,
    )
    assert b"Appointment rescheduled" in res.data
    with app.app_context():
        assert db.session.get(Appointment, appt_id).start_at.date() == new_day


def test_admin_filter_by_status(client, app):
    register(client)
    make_appointment(app, status=Appointment.CANCELLED)
    admin_client(client)
    html = client.get("/admin/appointments?status=Confirmed").data.decode()
    assert "No appointments match" in html


def test_admin_add_edit_and_toggle_provider(client, app):
    admin_client(client)
    res = client.post(
        "/admin/providers/new",
        data={"name": "Dr. New", "specialty": "ENT", "start_hour": 10, "end_hour": 14,
              "slot_minutes": 60, "working_days": ["0", "6"], "is_active": "y"},
        follow_redirects=True,
    )
    assert b"Dr. New added" in res.data
    with app.app_context():
        p = Provider.query.filter_by(name="Dr. New").one()
        assert p.working_days == "0,6" and p.slot_minutes == 60
        pid = p.id

    # Invalid hours are rejected.
    res = client.post(
        f"/admin/providers/{pid}/edit",
        data={"name": "Dr. New", "specialty": "ENT", "start_hour": 14, "end_hour": 10,
              "slot_minutes": 60, "working_days": ["0"]},
    )
    assert b"End hour must be after the start hour" in res.data

    client.post(f"/admin/providers/{pid}/toggle")
    with app.app_context():
        assert db.session.get(Provider, pid).is_active is False


def test_inactive_provider_has_no_slots(client, app):
    pid = provider_id(app)
    admin_client(client)
    client.post(f"/admin/providers/{pid}/toggle")
    logout(client)
    register(client)
    login(client)
    data = client.get(f"/api/providers/{pid}/slots?date={future_day().isoformat()}").get_json()
    assert data["slots"] == []
    assert "not accepting" in data["message"]
