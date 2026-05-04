"""
routes/admin_routes.py
Admin blueprint — role-based access for system administrators.

All routes require the logged-in user to have role == "admin".
Regular users receive a 403 Forbidden response.

Endpoints:
    GET  /admin/users              → list all users with their stats
    GET  /admin/users/<id>         → view a specific user's details
    POST /admin/users/<id>/role    → change a user's role
    GET  /admin/assign             → page to assign tasks to users
    POST /admin/assign             → create + assign a task to a specific user
"""
import logging
from functools import wraps
from datetime import datetime, timezone, timedelta

from flask import (
    Blueprint, render_template, redirect, url_for,
    request, jsonify, flash, abort
)
from flask_login import login_required, current_user

from models import db
from models.user import User
from models.task import Task, Score

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------------------------------------------------------
# Admin guard decorator
# ---------------------------------------------------------------------------
def admin_required(f):
    """Decorator: only allows users with role='admin' to access the route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# /admin/users — list all users
# ---------------------------------------------------------------------------
@admin_bp.route("/users")
@login_required
@admin_required
def users():
    """Admin panel — overview of all registered users with their key metrics."""
    today    = datetime.now(timezone.utc).date()
    start_30 = today - timedelta(days=29)

    all_users = User.query.order_by(User.id).all()
    user_stats = []

    for u in all_users:
        task_count = Task.query.filter_by(user_id=u.id).count()

        scores_30 = Score.query.filter(
            Score.user_id == u.id,
            Score.date >= start_30,
            Score.date <= today,
        ).all()

        vals      = [s.daily_score for s in scores_30]
        avg_score = round(sum(vals) / len(vals), 1) if vals else 0.0

        user_stats.append({
            "user":       u,
            "task_count": task_count,
            "avg_score":  avg_score,
        })

    return render_template("admin_users.html", user_stats=user_stats, today=today)


# ---------------------------------------------------------------------------
# /admin/users/<id>/role — change role
# ---------------------------------------------------------------------------
@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def change_role(user_id: int):
    """Promote or demote a user's role (admin ↔ user)."""
    if user_id == current_user.id:
        flash("You cannot change your own role.", "error")
        return redirect(url_for("admin.users"))

    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("admin.users"))

    new_role = request.form.get("role", "user")
    if new_role not in ("admin", "user"):
        flash("Invalid role.", "error")
        return redirect(url_for("admin.users"))

    old_role = user.role
    user.role = new_role
    db.session.commit()

    logger.info(
        "Admin %s changed user %s role: %s → %s",
        current_user.id, user_id, old_role, new_role
    )
    flash(f"Role for {user.name} updated to '{new_role}'.", "success")
    return redirect(url_for("admin.users"))


# ---------------------------------------------------------------------------
# /admin/assign — assign task to a user
# ---------------------------------------------------------------------------
@admin_bp.route("/assign", methods=["GET", "POST"])
@login_required
@admin_required
def assign_task():
    """Admin can create a task and assign it to any registered user."""
    all_users = User.query.order_by(User.name).all()

    if request.method == "POST":
        title       = request.form.get("title", "").strip()
        priority    = request.form.get("priority", "")
        recurrence  = request.form.get("recurrence", "one-time")
        category    = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        assignee_id = request.form.get("assign_to", type=int)

        if not title or len(title) > 200:
            flash("Task title must be between 1 and 200 characters.", "error")
            return render_template("admin_assign.html", users=all_users)

        if priority not in ("High", "Medium", "Low"):
            flash("Please select a valid priority.", "error")
            return render_template("admin_assign.html", users=all_users)

        if recurrence not in ("one-time", "daily"):
            flash("Please select a valid recurrence type.", "error")
            return render_template("admin_assign.html", users=all_users)

        if category and len(category) > 50:
            flash("Category must not exceed 50 characters.", "error")
            return render_template("admin_assign.html", users=all_users)

        if description and len(description) > 1000:
            flash("Description must not exceed 1000 characters.", "error")
            return render_template("admin_assign.html", users=all_users)

        if not assignee_id:
            flash("You must select a user to assign this task to.", "error")
            return render_template("admin_assign.html", users=all_users)

        assignee = db.session.get(User, assignee_id)
        if not assignee:
            flash("Selected user not found.", "error")
            return render_template("admin_assign.html", users=all_users)

        task = Task(
            title=title,
            priority=priority,
            recurrence_type=recurrence,
            category=category or None,
            description=description,
            user_id=assignee_id,        # task belongs to the assignee
            assigned_to=current_user.id,  # set who assigned it
        )
        db.session.add(task)
        db.session.commit()

        logger.info(
            "Admin %s assigned task '%s' [%s] to user %s",
            current_user.id, title, priority, assignee_id
        )
        flash(f"Task '{title}' assigned to {assignee.name}.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin_assign.html", users=all_users)


# ---------------------------------------------------------------------------
# /admin/api/stats — quick JSON endpoint for admin dashboard data
# ---------------------------------------------------------------------------
@admin_bp.route("/api/stats")
@login_required
@admin_required
def admin_stats_api():
    """Return aggregate system stats as JSON (for admin dashboard widgets)."""
    total_users = User.query.count()
    total_tasks = Task.query.count()
    admin_count = User.query.filter_by(role="admin").count()

    today    = datetime.now(timezone.utc).date()
    start_7  = today - timedelta(days=6)
    active_7 = (
        db.session.query(db.func.count(db.func.distinct(Score.user_id)))
        .filter(Score.date >= start_7, Score.date <= today, Score.daily_score > 0)
        .scalar()
    ) or 0

    return jsonify({
        "success": True,
        "data": {
            "total_users":       total_users,
            "total_tasks":       total_tasks,
            "admin_count":       admin_count,
            "active_users_7d":   active_7,
        },
    })
