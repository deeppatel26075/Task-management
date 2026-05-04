"""
routes/auth_routes.py
Authentication blueprint — login, register, logout.
"""
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from models import db
from models.user import User

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user     = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            logger.info("User login: %s", email)
            return redirect(url_for("dashboard.index"))

        logger.warning("Failed login attempt for: %s", email)
        flash("Invalid email or password", "error")

    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    import re
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # ── Name Validation ────────────────────────────────────────────────
        if not name or len(name) < 2 or len(name) > 100:
            flash("Name must be between 2 and 100 characters.", "error")
            return redirect(url_for("auth.register"))

        # ── Email Validation ───────────────────────────────────────────────
        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not email or len(email) > 120 or not re.match(email_regex, email):
            flash("Please enter a valid email address.", "error")
            return redirect(url_for("auth.register"))

        # ── Password Validation ────────────────────────────────────────────
        if not password or len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return redirect(url_for("auth.register"))

        # ── Check Duplicate User ───────────────────────────────────────────
        if User.query.filter_by(email=email).first():
            flash("This email is already registered.", "error")
            return redirect(url_for("auth.register"))

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password, method="scrypt"),
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        logger.info("New user registered: %s", email)
        return redirect(url_for("dashboard.index"))

    return render_template("register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logger.info("User logout: %s", current_user.email)
    logout_user()
    return redirect(url_for("index"))
