"""web/__init__.py — Flask application factory"""
from __future__ import annotations

import os


def create_app():
    from flask import Flask
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-changeme")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # Use secure cookies only when running on Render (HTTPS)
    if os.environ.get("RENDER"):
        app.config["SESSION_COOKIE_SECURE"] = True

    from .routes.index import bp as index_bp
    from .routes.reports import bp as reports_bp
    from .routes.admin import bp as admin_bp

    app.register_blueprint(index_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)

    return app
