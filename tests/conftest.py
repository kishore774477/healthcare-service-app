from datetime import date, datetime, time, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import Appointment, Provider, User


@pytest.fixture()
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
            "SEED_DEMO_DATA": False,
        }
    )
    with app.app_context():
        admin = User(username="admin", email="admin@test.local", role=User.ROLE_ADMIN)
        admin.set_password("Admin@123")
        # Works every day 08:00-20:00 so tests don't depend on the weekday.
        provider = Provider(
            name="Dr. Test", specialty="General", start_hour=8, end_hour=20,
            slot_minutes=30, working_days="0,1,2,3,4,5,6",
        )
        weekday_only = Provider(
            name="Dr. Weekday", specialty="Cardiology", start_hour=9, end_hour=12,
            slot_minutes=60, working_days="0,1,2,3,4",
        )
        db.session.add_all([admin, provider, weekday_only])
        db.session.commit()
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def future_day(days: int = 3) -> date:
    return date.today() + timedelta(days=days)


def next_weekend_day() -> date:
    d = date.today() + timedelta(days=1)
    while d.weekday() < 5:
        d += timedelta(days=1)
    return d


def register(client, username="alice", email="alice@example.com", password="Secret123", confirm=None):
    return client.post(
        "/register",
        data={"username": username, "email": email, "password": password, "confirm_password": confirm or password},
        follow_redirects=True,
    )


def login(client, username="alice", password="Secret123"):
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=True)


def logout(client):
    return client.post("/logout", follow_redirects=True)


@pytest.fixture()
def patient(client):
    register(client)
    login(client)
    return client


def create_patient(app, username, email, password="Secret123"):
    with app.app_context():
        user = User(username=username, email=email, role=User.ROLE_PATIENT)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()


def make_appointment(app, username="alice", start_at=None, status=Appointment.PENDING, provider_name="Dr. Test"):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        provider = Provider.query.filter_by(name=provider_name).first()
        appt = Appointment(
            patient_id=user.id,
            provider_id=provider.id,
            start_at=start_at or datetime.combine(future_day(), time(10, 0)),
            status=status,
        )
        db.session.add(appt)
        db.session.commit()
        return appt.id


def provider_id(app, name="Dr. Test"):
    with app.app_context():
        return Provider.query.filter_by(name=name).first().id
