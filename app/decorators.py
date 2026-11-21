"""Role-based access helpers (FR011: prevent unauthorized access)."""
from functools import wraps

from flask import abort, redirect, url_for
from flask_login import current_user, login_required


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def patient_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        return view(*args, **kwargs)

    return wrapped
