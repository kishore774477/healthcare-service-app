"""Sprint 1: US01 registration, US02 login / logout (FR001-FR006)."""
from app.models import User

from .conftest import login, logout, register


def test_home_page_loads(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Dr. Test" in res.data


def test_register_creates_patient_with_hashed_password(client, app):
    res = register(client)
    assert b"Registration successful" in res.data
    assert b"Welcome back" in res.data  # redirected to the login page
    with app.app_context():
        user = User.query.filter_by(username="alice").one()
        assert user.role == User.ROLE_PATIENT
        assert user.password_hash != "Secret123"
        assert user.check_password("Secret123")


def test_register_rejects_duplicate_email(client):
    register(client)
    res = register(client, username="alice2", email="ALICE@example.com")
    assert b"Email already exists" in res.data


def test_register_rejects_duplicate_username(client):
    register(client)
    res = register(client, email="other@example.com")
    assert b"Username already taken" in res.data


def test_register_validates_fields(client, app):
    res = register(client, password="Secret123", confirm="Different1")
    assert b"Passwords must match" in res.data
    res = register(client, email="not-an-email")
    assert b"Invalid email address" in res.data
    res = register(client, username="", email="")
    assert b"This field is required" in res.data
    with app.app_context():
        assert User.query.filter_by(role=User.ROLE_PATIENT).count() == 0


def test_login_and_logout(client):
    register(client)
    res = login(client)
    assert b"Welcome back, alice" in res.data
    assert client.get("/dashboard").status_code == 200

    res = logout(client)
    assert b"You have been logged out" in res.data
    res = client.get("/dashboard")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_login_rejects_bad_credentials(client):
    register(client)
    res = login(client, password="wrong-password")
    assert b"Invalid username or password" in res.data
    res = login(client, username="nobody")
    assert b"Invalid username or password" in res.data


def test_login_redirect_ignores_external_next(client):
    register(client)
    res = client.post("/login?next=https://evil.example.com/", data={"username": "alice", "password": "Secret123"})
    assert res.status_code == 302
    assert "evil.example.com" not in res.headers["Location"]


def test_admin_login_goes_to_admin_dashboard(client):
    res = login(client, "admin", "Admin@123")
    assert b"Admin dashboard" in res.data
