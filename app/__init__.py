"""Tender Participation Automation - the Flask web app.

Run it with:   python run.py     then open http://127.0.0.1:5000
"""
import secrets

from flask import Flask

from .services.normalizer import fmt_dash


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = secrets.token_hex(16)        # only used for flash messages
    app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024    # 200 MB per upload

    app.jinja_env.filters["dmy"] = lambda iso: fmt_dash(iso) if iso else "-"

    from .routes import bid, home, participate
    app.register_blueprint(home.bp)
    app.register_blueprint(participate.bp)
    app.register_blueprint(bid.bp)
    return app
