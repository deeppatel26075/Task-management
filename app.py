"""
app.py
Application factory for Project PA — Intelligent Discipline & Productivity System.

Usage:
    python app.py           → development server
    gunicorn app:app        → production (Render / Docker)
    flask run               → Flask CLI dev server

Environment variables (see .env.example):
    SECRET_KEY          — Flask session secret
    JWT_SECRET_KEY      — JWT signing key (keep separate from Flask secret)
    DATABASE_URL        — SQLAlchemy DB URI (default: SQLite)
    MAIL_USERNAME       — Gmail address for notifications
    MAIL_PASSWORD       — Gmail App Password
"""
import os
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, current_user
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from models import db
from models.user import User

# ---------------------------------------------------------------------------
# Extensions (initialised without app — bound in create_app)
# ---------------------------------------------------------------------------
mail    = Mail()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per hour"])


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
def _configure_logging(app: Flask) -> None:
    """
    Set up structured application logging.
      - Console handler: INFO and above (always enabled)
      - File handler: WARNING and above, rotating at 2 MB (production)
    """
    log_level = logging.DEBUG if app.debug else logging.INFO
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(fmt)

    try:
        os.makedirs("logs", exist_ok=True)
        file_handler = RotatingFileHandler(
            "logs/app.log", maxBytes=2 * 1024 * 1024, backupCount=5
        )
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(fmt)
        app.logger.addHandler(file_handler)
    except OSError:
        pass  # Read-only context (Docker layer, etc.)

    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)

    if not app.debug:
        logging.getLogger("werkzeug").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
def create_app(config: dict | None = None) -> Flask:
    """
    Create and configure a Flask application instance.

    Design pattern: Application Factory
      - Enables testing with different configs
      - Supports multiple instances in the same process
      - Cleanly separates config from application logic
    """
    app = Flask(__name__)

    # ── Configuration ──────────────────────────────────────────────────────
    app.config.update(
        # Flask core
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod"),

        # Database
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL", "sqlite:///project_pa.db"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},

        # JWT (Flask-JWT-Extended)
        JWT_SECRET_KEY=os.environ.get(
            "JWT_SECRET_KEY", "jwt-secret-key-change-in-prod"
        ),
        JWT_ACCESS_TOKEN_EXPIRES=900,        # 15 minutes
        JWT_REFRESH_TOKEN_EXPIRES=2592000,   # 30 days

        # Email (Flask-Mail via Gmail SMTP)
        MAIL_SERVER="smtp.gmail.com",
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USERNAME=os.environ.get("MAIL_USERNAME", "deeppatel26075@gmail.com"),
        MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD", ""),
        MAIL_DEFAULT_SENDER=(
            "Project PA",
            os.environ.get("MAIL_USERNAME", "deeppatel26075@gmail.com"),
        ),

        # Rate limiting
        RATELIMIT_STORAGE_URL="memory://",
    )
    if config:
        app.config.update(config)

    # ── Extensions ─────────────────────────────────────────────────────────
    db.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)
    JWTManager(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "error"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import request, jsonify
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return redirect(url_for(login_manager.login_view))

    # ── Blueprints ─────────────────────────────────────────────────────────
    from routes.auth_routes      import auth_bp
    from routes.dashboard_routes import dashboard_bp
    from routes.api_routes       import api_bp
    from routes.jwt_routes       import jwt_bp
    from routes.admin_routes     import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(jwt_bp)
    app.register_blueprint(admin_bp)

    # ── Root route ─────────────────────────────────────────────────────────
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard.index"))
        return render_template("index.html")

    # ── Error handlers ─────────────────────────────────────────────────────
    @app.errorhandler(403)
    def forbidden(e):
        from flask import request, jsonify
        app.logger.warning("403 Forbidden: %s", request.path)
        if request.path.startswith("/api/") or request.path.startswith("/admin/api/"):
            return jsonify({"success": False, "error": "Forbidden — admin access required"}), 403
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        app.logger.warning("404: %s", e)
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error("500: %s", e, exc_info=True)
        db.session.rollback()
        return render_template("500.html"), 500

    # ── Logging ────────────────────────────────────────────────────────────
    _configure_logging(app)
    app.logger.info("Project PA started — debug=%s", app.debug)

    # ── Background Jobs ────────────────────────────────────────────────────
    if not app.config.get("TESTING"):
        if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            from services.scheduler import init_scheduler
            init_scheduler(app)

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        app.logger.info("Database tables verified/created.")
    app.run(debug=True, port=5000)
