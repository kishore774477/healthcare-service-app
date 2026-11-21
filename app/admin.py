"""Admin module: manage appointments (US08) and monitor schedules / provider availability (US09)."""
from datetime import date, datetime, time, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from . import scheduling, services
from .decorators import admin_required
from .extensions import db
from .forms import ActionForm, ProviderForm, RescheduleForm
from .models import Appointment, Provider, User

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _parse_date(value: str | None, default: date | None = None) -> date | None:
    try:
        return date.fromisoformat(value) if value else default
    except ValueError:
        return default


@bp.route("/")
@admin_required
def dashboard():
    today = services.now().date()
    start = datetime.combine(today, time.min)
    end = start + timedelta(days=1)
    todays = (
        Appointment.query.filter(Appointment.start_at >= start, Appointment.start_at < end)
        .order_by(Appointment.start_at)
        .all()
    )
    pending = (
        Appointment.query.filter(
            Appointment.status == Appointment.PENDING, Appointment.start_at > services.now()
        )
        .order_by(Appointment.start_at)
        .limit(10)
        .all()
    )
    stats = {
        "patients": User.query.filter_by(role=User.ROLE_PATIENT).count(),
        "providers": Provider.query.filter_by(is_active=True).count(),
        "today": len([a for a in todays if a.status != Appointment.CANCELLED]),
        "pending": Appointment.query.filter(
            Appointment.status == Appointment.PENDING, Appointment.start_at > services.now()
        ).count(),
    }
    return render_template("admin/dashboard.html", todays=todays, pending=pending, stats=stats)


@bp.route("/appointments")
@admin_required
def appointments():
    status = request.args.get("status", "")
    provider_id = request.args.get("provider", type=int)
    day = _parse_date(request.args.get("date"))

    query = Appointment.query
    if status == "Overdue":
        query = query.filter(
            Appointment.status.in_(Appointment.ACTIVE_STATUSES), Appointment.start_at <= services.now()
        )
    elif status:
        query = query.filter(Appointment.status == status)
    if provider_id:
        query = query.filter(Appointment.provider_id == provider_id)
    if day:
        start = datetime.combine(day, time.min)
        query = query.filter(Appointment.start_at >= start, Appointment.start_at < start + timedelta(days=1))

    appts = query.order_by(Appointment.start_at.desc()).all()
    providers = Provider.query.order_by(Provider.name).all()
    return render_template(
        "admin/appointments.html",
        appointments=appts,
        providers=providers,
        statuses=[Appointment.PENDING, Appointment.CONFIRMED, Appointment.COMPLETED, Appointment.CANCELLED, "Overdue"],
        filters={"status": status, "provider": provider_id, "date": day.isoformat() if day else ""},
    )


ACTIONS = {
    "approve": (Appointment.CONFIRMED, "Appointment confirmed."),
    "cancel": (Appointment.CANCELLED, "Appointment cancelled."),
    "complete": (Appointment.COMPLETED, "Appointment marked as completed."),
}


@bp.route("/appointments/<int:appointment_id>/<action>", methods=["POST"])
@admin_required
def appointment_action(appointment_id: int, action: str):
    if action not in ACTIONS:
        abort(404)
    if not ActionForm().validate_on_submit():
        abort(400)
    appt = db.get_or_404(Appointment, appointment_id)
    new_status, message = ACTIONS[action]

    if action == "approve" and appt.status != Appointment.PENDING:
        flash("Only pending appointments can be approved.", "warning")
    elif action == "cancel" and not appt.is_active:
        flash("This appointment is already closed.", "warning")
    elif action == "complete" and (not appt.is_active or appt.start_at > services.now()):
        flash("Only active appointments whose time has passed can be completed.", "warning")
    else:
        appt.status = new_status
        db.session.commit()
        flash(f"{message} ({appt.patient.username} with {appt.provider.name}, {appt.start_at:%d %b %Y %I:%M %p})", "success")
    return redirect(request.referrer or url_for("admin.appointments"))


@bp.route("/appointments/<int:appointment_id>/reschedule", methods=["GET", "POST"])
@admin_required
def reschedule(appointment_id: int):
    appt = db.get_or_404(Appointment, appointment_id)
    if not appt.is_active:
        flash("Cancelled or completed appointments cannot be rescheduled.", "warning")
        return redirect(url_for("admin.appointments"))

    form = RescheduleForm()
    today = services.now().date()
    if request.method == "GET":
        form.date.data = max(appt.start_at.date(), today)
    form.slot.choices = [("", "Select a time slot")] + scheduling.slot_choices(appt.provider, form.date.data, appt.id)

    if form.validate_on_submit():
        ok, message = scheduling.reschedule(appt, form.date.data, form.slot.data)
        flash(message, "success" if ok else "danger")
        if ok:
            return redirect(url_for("admin.appointments"))
    elif request.method == "POST":
        flash("Please choose a new date and time slot.", "danger")

    return render_template(
        "reschedule.html",
        form=form,
        appointment=appt,
        back_url=url_for("admin.appointments"),
        **scheduling.date_bounds(),
    )


@bp.route("/schedule")
@admin_required
def schedule():
    day = _parse_date(request.args.get("date"), services.now().date())
    providers = Provider.query.order_by(Provider.name).all()
    summaries = [services.provider_day_summary(p, day) for p in providers]
    booked = {
        (a.provider_id, a.start_at): a
        for a in Appointment.query.filter(
            Appointment.start_at >= datetime.combine(day, time.min),
            Appointment.start_at < datetime.combine(day, time.min) + timedelta(days=1),
            Appointment.status.in_(Appointment.ACTIVE_STATUSES),
        ).all()
    }
    return render_template(
        "admin/schedule.html",
        day=day,
        prev_day=day - timedelta(days=1),
        next_day=day + timedelta(days=1),
        summaries=summaries,
        booked=booked,
    )


@bp.route("/providers")
@admin_required
def providers():
    all_providers = Provider.query.order_by(Provider.name).all()
    today = services.now().date()
    upcoming_counts = {
        p.id: Appointment.query.filter(
            Appointment.provider_id == p.id,
            Appointment.start_at > services.now(),
            Appointment.status.in_(Appointment.ACTIVE_STATUSES),
        ).count()
        for p in all_providers
    }
    free_today = {p.id: len(services.available_slots(p, today)) for p in all_providers}
    return render_template(
        "admin/providers.html", providers=all_providers, upcoming_counts=upcoming_counts, free_today=free_today
    )


def _save_provider(form: ProviderForm, provider: Provider) -> None:
    provider.name = form.name.data.strip()
    provider.specialty = form.specialty.data.strip()
    provider.start_hour = form.start_hour.data
    provider.end_hour = form.end_hour.data
    provider.slot_minutes = form.slot_minutes.data
    provider.working_days = ",".join(str(d) for d in sorted(form.working_days.data))
    provider.is_active = form.is_active.data


@bp.route("/providers/new", methods=["GET", "POST"])
@admin_required
def new_provider():
    form = ProviderForm()
    if form.validate_on_submit():
        provider = Provider()
        _save_provider(form, provider)
        db.session.add(provider)
        db.session.commit()
        flash(f"{provider.name} added.", "success")
        return redirect(url_for("admin.providers"))
    return render_template("admin/provider_form.html", form=form, title="Add provider")


@bp.route("/providers/<int:provider_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_provider(provider_id: int):
    provider = db.get_or_404(Provider, provider_id)
    form = ProviderForm(obj=provider)
    if request.method == "GET":
        form.working_days.data = provider.working_day_list
    if form.validate_on_submit():
        _save_provider(form, provider)
        db.session.commit()
        flash(f"{provider.name} updated. Existing appointments are unchanged.", "success")
        return redirect(url_for("admin.providers"))
    return render_template("admin/provider_form.html", form=form, title=f"Edit {provider.name}")


@bp.route("/providers/<int:provider_id>/toggle", methods=["POST"])
@admin_required
def toggle_provider(provider_id: int):
    if not ActionForm().validate_on_submit():
        abort(400)
    provider = db.get_or_404(Provider, provider_id)
    provider.is_active = not provider.is_active
    db.session.commit()
    state = "is now accepting appointments" if provider.is_active else "is no longer accepting new appointments"
    flash(f"{provider.name} {state}.", "info")
    return redirect(url_for("admin.providers"))
