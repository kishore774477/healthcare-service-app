"""Healthcare Service Application (HSA) - Flask application factory."""
import os
from datetime import datetime

import click
from flask import Flask, render_template
from flask_login import current_user

from .extensions import csrf, db, login_manager


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL", "sqlite:///" + os.path.join(app.instance_path, "hsa.db")
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_HTTPONLY=True,
        REMINDER_WINDOW_HOURS=24,
        SEED_DEMO_DATA=True,
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "warning"

    from . import models  # noqa: F401  (register models with SQLAlchemy)
    from .admin import bp as admin_bp
    from .auth import bp as auth_bp
    from .main import bp as main_bp
    from .patient import bp as patient_bp
    from .scheduling import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(admin_bp)

    _register_template_helpers(app)
    _register_error_handlers(app)
    _register_cli(app)

    with app.app_context():
        db.create_all()
        if app.config["SEED_DEMO_DATA"]:
            from .seed import seed_defaults

            seed_defaults()

    return app


def _register_template_helpers(app: Flask) -> None:
    from .forms import ActionForm
    from .services import upcoming_reminders

    @app.context_processor
    def inject_globals():
        reminder_count = 0
        if current_user.is_authenticated and not current_user.is_admin:
            reminder_count = len(
                upcoming_reminders(current_user.id, app.config["REMINDER_WINDOW_HOURS"])
            )
        return {
            "action_form": ActionForm(),
            "reminder_count": reminder_count,
            "current_year": datetime.now().year,
        }

    @app.template_filter("dt")
    def format_datetime(value, fmt="%a, %d %b %Y · %I:%M %p"):
        return value.strftime(fmt) if value else ""

    @app.template_filter("tm")
    def format_time(value):
        return value.strftime("%I:%M %p") if value else ""


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/error.html", code=403, message="You don't have permission to view this page."), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/error.html", code=404, message="The page you were looking for doesn't exist."), 404


def _register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    @click.option("--reset", is_flag=True, help="Drop all tables before creating them.")
    def init_db(reset: bool):
        """Create the database tables and seed default data."""
        from .seed import seed_defaults

        if reset:
            db.drop_all()
        db.create_all()
        seed_defaults()
        click.echo("Database ready.")
