"""Default data so the app is usable on first run: an admin, a demo patient and providers."""
import os

from .extensions import db
from .models import Provider, User

DEFAULT_PROVIDERS = [
    # name, specialty, start, end, slot minutes, working days
    ("Dr. Ananya Rao", "General Physician", 9, 17, 30, "0,1,2,3,4,5"),
    ("Dr. Vikram Menon", "Cardiologist", 10, 16, 30, "0,2,4"),
    ("Dr. Priya Sharma", "Dermatologist", 11, 18, 20, "1,3,5"),
    ("Dr. Arjun Iyer", "Pediatrician", 9, 13, 15, "0,1,2,3,4"),
    ("Dr. Meera Krishnan", "Orthopedic Surgeon", 14, 19, 30, "0,1,3,4"),
]


def seed_defaults() -> None:
    """Idempotent: only inserts rows that are missing."""
    admin_username = os.environ.get("HSA_ADMIN_USERNAME", "admin")
    if not User.query.filter_by(username=admin_username).first():
        admin = User(
            username=admin_username,
            email=os.environ.get("HSA_ADMIN_EMAIL", "admin@hsa.local"),
            role=User.ROLE_ADMIN,
        )
        admin.set_password(os.environ.get("HSA_ADMIN_PASSWORD", "Admin@123"))
        db.session.add(admin)

    if not User.query.filter_by(username="demo").first():
        demo = User(username="demo", email="demo@hsa.local", role=User.ROLE_PATIENT)
        demo.set_password("Demo@1234")
        db.session.add(demo)

    if Provider.query.count() == 0:
        for name, specialty, start, end, minutes, days in DEFAULT_PROVIDERS:
            db.session.add(
                Provider(
                    name=name,
                    specialty=specialty,
                    start_hour=start,
                    end_hour=end,
                    slot_minutes=minutes,
                    working_days=days,
                )
            )
    db.session.commit()
