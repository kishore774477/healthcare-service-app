"""US01 / US02: patient registration, login and logout."""
from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from .extensions import db
from .forms import ActionForm, LoginForm, RegistrationForm
from .models import User

bp = Blueprint("auth", __name__)


def _home_for(user) -> str:
    return url_for("admin.dashboard") if user.is_admin else url_for("patient.dashboard")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(_home_for(current_user))

    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        email = form.email.data.strip().lower()
        ok = True
        if User.query.filter(func.lower(User.username) == username.lower()).first():
            form.username.errors.append("Username already taken.")
            ok = False
        if User.query.filter_by(email=email).first():
            form.email.errors.append("Email already exists.")
            ok = False
        if ok:
            user = User(username=username, email=email, role=User.ROLE_PATIENT)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("auth.login"))
        flash("Registration failed. Please fix the errors below.", "danger")
    elif request.method == "POST":
        flash("Registration failed. Please fix the errors below.", "danger")
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_home_for(current_user))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter(func.lower(User.username) == form.username.data.strip().lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash(f"Welcome back, {user.username}!", "success")
            next_url = request.args.get("next")
            # Only follow relative redirects to avoid open-redirect attacks.
            if next_url and not urlsplit(next_url).netloc and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(_home_for(user))
        flash("Invalid username or password.", "danger")
    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    if ActionForm().validate_on_submit():
        logout_user()
        flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))
