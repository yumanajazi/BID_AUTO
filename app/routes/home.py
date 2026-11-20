from flask import Blueprint, render_template

from ..services.converter import available_engines
from ..services.storage import recent_tenders

bp = Blueprint("home", __name__)


@bp.route("/")
def index():
    return render_template("home.html", tenders=recent_tenders(), engines=available_engines())
