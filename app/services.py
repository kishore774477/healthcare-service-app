"""Business logic: slot generation, availability checks and reminders."""
from datetime import date, datetime, time, timedelta

from .extensions import db
from .models import Appointment, Provider

MAX_BOOKING_DAYS_AHEAD = 90


def now() -> datetime:
    return datetime.now()


def generate_slots(provider: Provider, day: date) -> list[datetime]:
    """All slots in the provider's working hours on ``day`` (ignores bookings)."""
    if not provider.is_active or not provider.works_on(day):
        return []
    slots = []
    current = datetime.combine(day, time(hour=provider.start_hour))
    end = datetime.combine(day, time(hour=0)) + timedelta(hours=provider.end_hour)
    step = timedelta(minutes=provider.slot_minutes)
    while current + step <= end:
        slots.append(current)
        current += step
    return slots


def booked_times(provider: Provider, day: date, exclude_appointment_id: int | None = None) -> set[datetime]:
    start = datetime.combine(day, time.min)
    end = start + timedelta(days=1)
    query = Appointment.query.filter(
        Appointment.provider_id == provider.id,
        Appointment.start_at >= start,
        Appointment.start_at < end,
        Appointment.status.in_(Appointment.ACTIVE_STATUSES),
    )
    if exclude_appointment_id is not None:
        query = query.filter(Appointment.id != exclude_appointment_id)
    return {a.start_at for a in query.all()}


def available_slots(provider: Provider, day: date, exclude_appointment_id: int | None = None) -> list[datetime]:
    """FR008 / FR019: free, future slots for a provider on a given day."""
    if not is_bookable_date(day):
        return []
    taken = booked_times(provider, day, exclude_appointment_id)
    current = now()
    return [s for s in generate_slots(provider, day) if s not in taken and s > current]


def is_bookable_date(day: date) -> bool:
    today = now().date()
    return today <= day <= today + timedelta(days=MAX_BOOKING_DAYS_AHEAD)


def is_slot_available(provider: Provider, start_at: datetime, exclude_appointment_id: int | None = None) -> bool:
    return start_at in available_slots(provider, start_at.date(), exclude_appointment_id)


def patient_has_conflict(patient_id: int, start_at: datetime, exclude_appointment_id: int | None = None) -> bool:
    """A patient cannot hold two active appointments at the same time."""
    query = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.start_at == start_at,
        Appointment.status.in_(Appointment.ACTIVE_STATUSES),
    )
    if exclude_appointment_id is not None:
        query = query.filter(Appointment.id != exclude_appointment_id)
    return db.session.query(query.exists()).scalar()


def upcoming_reminders(patient_id: int, hours: int = 24) -> list[Appointment]:
    """FR015 / FR016: active appointments starting within the next ``hours``."""
    current = now()
    return (
        Appointment.query.filter(
            Appointment.patient_id == patient_id,
            Appointment.status.in_(Appointment.ACTIVE_STATUSES),
            Appointment.start_at > current,
            Appointment.start_at <= current + timedelta(hours=hours),
        )
        .order_by(Appointment.start_at)
        .all()
    )


def split_appointments(appointments: list[Appointment]) -> tuple[list[Appointment], list[Appointment]]:
    """Return (upcoming, past). Upcoming = future and not cancelled/completed."""
    current = now()
    upcoming = sorted(
        (a for a in appointments if a.start_at > current and a.is_active), key=lambda a: a.start_at
    )
    past = sorted(
        (a for a in appointments if not (a.start_at > current and a.is_active)),
        key=lambda a: a.start_at,
        reverse=True,
    )
    return upcoming, past


def parse_slot(day: date, slot_value: str) -> datetime | None:
    try:
        slot_time = datetime.strptime(slot_value, "%H:%M").time()
    except (TypeError, ValueError):
        return None
    return datetime.combine(day, slot_time)


def provider_day_summary(provider: Provider, day: date) -> dict:
    """Utilisation numbers used by the admin schedule monitor (US09)."""
    all_slots = generate_slots(provider, day)
    taken = booked_times(provider, day)
    return {
        "provider": provider,
        "total": len(all_slots),
        "booked": len([s for s in all_slots if s in taken]),
        "slots": [{"time": s, "booked": s in taken} for s in all_slots],
    }
