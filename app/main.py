"""Public pages."""
from flask import Blueprint, render_template

from .models import Provider

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    providers = Provider.query.filter_by(is_active=True).order_by(Provider.name).all()
    return render_template("home.html", providers=providers)
