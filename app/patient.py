"""Patient features: dashboard, booking (US03), manage / cancel (US04),
history (US05), reminders (US06) and rescheduling (US07)."""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from . import scheduling, services
from .decorators import patient_required
from .extensions import db
from .forms import ActionForm, BookingForm, RescheduleForm
from .models import Appointment, Provider

bp = Blueprint("patient", __name__)


def _own_appointment_or_404(appointment_id: int) -> Appointment:
    appt = db.session.get(Appointment, appointment_id)
    # 404 (not 403) so other patients' appointment IDs are not revealed.
    if appt is None or appt.patient_id != current_user.id:
        abort(404)
    return appt


@bp.route("/dashboard")
@patient_required
def dashboard():
    appointments = Appointment.query.filter_by(patient_id=current_user.id).all()
    upcoming, past = services.split_appointments(appointments)
    reminders = services.upcoming_reminders(current_user.id, current_app.config["REMINDER_WINDOW_HOURS"])
    stats = {
        "upcoming": len(upcoming),
        "completed": sum(1 for a in appointments if a.status == Appointment.COMPLETED),
        "cancelled": sum(1 for a in appointments if a.status == Appointment.CANCELLED),
        "total": len(appointments),
    }
    return render_template(
        "patient/dashboard.html", upcoming=upcoming[:5], reminders=reminders, stats=stats
    )


@bp.route("/appointments")
@patient_required
def appointments():
    appts = Appointment.query.filter_by(patient_id=current_user.id).all()
    upcoming, past = services.split_appointments(appts)
    return render_template("patient/appointments.html", upcoming=upcoming, past=past)


@bp.route("/appointments/book", methods=["GET", "POST"])
@patient_required
def book():
    providers = Provider.query.filter_by(is_active=True).order_by(Provider.name).all()
    form = BookingForm()
    form.provider_id.choices = [(0, "Select a provider")] + [
        (p.id, f"{p.name} — {p.specialty}") for p in providers
    ]

    if request.method == "GET":
        form.provider_id.data = request.args.get("provider", type=int) or 0
        form.date.data = services.now().date()

    provider = db.session.get(Provider, form.provider_id.data) if form.provider_id.data else None
    form.slot.choices = [("", "Select a time slot")] + scheduling.slot_choices(provider, form.date.data)

    if form.validate_on_submit():
        start_at, error = scheduling.validate_slot_request(
            provider, form.date.data, form.slot.data, current_user.id
        )
        if error:
            flash(error, "danger")
        else:
            appt = Appointment(
                patient_id=current_user.id,
                provider_id=provider.id,
                start_at=start_at,
                reason=(form.reason.data or "").strip() or None,
                status=Appointment.PENDING,
            )
            db.session.add(appt)
            db.session.commit()
            flash(
                f"Appointment booked with {provider.name} on {start_at:%a, %d %b %Y at %I:%M %p}. "
                "Your booking is pending confirmation from the clinic.",
                "success",
            )
            return redirect(url_for("patient.appointments"))
    elif request.method == "POST":
        flash("Please complete all required fields.", "danger")

    return render_template("patient/book.html", form=form, providers=providers, **scheduling.date_bounds())


@bp.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
@patient_required
def cancel(appointment_id: int):
    appt = _own_appointment_or_404(appointment_id)
    if not ActionForm().validate_on_submit():
        abort(400)
    if not appt.can_modify:
        flash("Only upcoming, active appointments can be cancelled.", "warning")
    else:
        appt.status = Appointment.CANCELLED
        db.session.commit()
        flash(f"Your appointment with {appt.provider.name} on {appt.start_at:%d %b %Y at %I:%M %p} was cancelled.", "success")
    return redirect(url_for("patient.appointments"))


@bp.route("/appointments/<int:appointment_id>/reschedule", methods=["GET", "POST"])
@patient_required
def reschedule(appointment_id: int):
    appt = _own_appointment_or_404(appointment_id)
    if not appt.can_modify:
        flash("Only upcoming, active appointments can be rescheduled.", "warning")
        return redirect(url_for("patient.appointments"))

    form = RescheduleForm()
    if request.method == "GET":
        form.date.data = max(appt.start_at.date(), services.now().date())
    form.slot.choices = [("", "Select a time slot")] + scheduling.slot_choices(appt.provider, form.date.data, appt.id)

    if form.validate_on_submit():
        ok, message = scheduling.reschedule(appt, form.date.data, form.slot.data)
        flash(message, "success" if ok else "danger")
        if ok:
            return redirect(url_for("patient.appointments"))
    elif request.method == "POST":
        flash("Please choose a new date and time slot.", "danger")

    return render_template(
        "reschedule.html",
        form=form,
        appointment=appt,
        back_url=url_for("patient.appointments"),
        **scheduling.date_bounds(),
    )
