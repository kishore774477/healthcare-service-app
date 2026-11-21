"""Database models: patients/admins, healthcare providers and appointments."""
from datetime import datetime, timedelta

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    ROLE_PATIENT = "patient"
    ROLE_ADMIN = "admin"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_PATIENT)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    appointments = db.relationship(
        "Appointment", back_populates="patient", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        # FR002: passwords are hashed before they are stored.
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == self.ROLE_ADMIN

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username}>"


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class Provider(db.Model):
    """A doctor / healthcare provider with a weekly working schedule."""

    __tablename__ = "providers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    specialty = db.Column(db.String(100), nullable=False)
    start_hour = db.Column(db.Integer, nullable=False, default=9)
    end_hour = db.Column(db.Integer, nullable=False, default=17)
    slot_minutes = db.Column(db.Integer, nullable=False, default=30)
    # Comma separated weekday numbers, Monday = 0 ... Sunday = 6
    working_days = db.Column(db.String(20), nullable=False, default="0,1,2,3,4")
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    appointments = db.relationship("Appointment", back_populates="provider")

    @property
    def working_day_list(self) -> list[int]:
        return [int(d) for d in self.working_days.split(",") if d.strip() != ""]

    @property
    def working_days_label(self) -> str:
        return ", ".join(WEEKDAYS[d] for d in self.working_day_list) or "None"

    @property
    def hours_label(self) -> str:
        return f"{self.start_hour:02d}:00 - {self.end_hour:02d}:00"

    def works_on(self, day) -> bool:
        return day.weekday() in self.working_day_list

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Provider {self.name}>"


class Appointment(db.Model):
    __tablename__ = "appointments"

    PENDING = "Pending"
    CONFIRMED = "Confirmed"
    CANCELLED = "Cancelled"
    COMPLETED = "Completed"
    ACTIVE_STATUSES = (PENDING, CONFIRMED)

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    provider_id = db.Column(db.Integer, db.ForeignKey("providers.id"), nullable=False, index=True)
    start_at = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default=PENDING)
    reason = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    patient = db.relationship("User", back_populates="appointments")
    provider = db.relationship("Provider", back_populates="appointments")

    @property
    def end_at(self) -> datetime:
        return self.start_at + timedelta(minutes=self.provider.slot_minutes)

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES

    @property
    def is_upcoming(self) -> bool:
        return self.start_at > datetime.now()

    @property
    def can_modify(self) -> bool:
        """Patients may cancel / reschedule only active, future appointments."""
        return self.is_active and self.is_upcoming

    @property
    def display_status(self) -> str:
        if self.is_active and not self.is_upcoming:
            return "Overdue"
        return self.status

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Appointment {self.id} {self.start_at:%Y-%m-%d %H:%M} {self.status}>"
