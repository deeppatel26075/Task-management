"""
routes/api_routes.py
REST API Blueprint — /api/v1/

Provides a full JSON API for external clients, mobile apps, or integrations.
All endpoints are protected by Flask-Login session authentication.

Endpoints:
    GET    /api/v1/tasks            List all tasks for current user
    POST   /api/v1/tasks            Create a new task
    GET    /api/v1/tasks/<id>       Get a single task by ID
    PUT    /api/v1/tasks/<id>       Update a task
    DELETE /api/v1/tasks/<id>       Delete a task and all its history

    GET    /api/v1/scores           Get score history (last N days)
    GET    /api/v1/stats            Get aggregated user stats summary
"""
import logging
from datetime import datetime, timezone, timedelta

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from models import db
from models.task import Task, TaskInstance, Score
from services.scoring_service import generate_instances_for_date, calculate_score_and_streak

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _error(message: str, code: int = 400):
    return jsonify({"success": False, "error": message}), code


def _ok(data, code: int = 200):
    return jsonify({"success": True, "data": data}), code


def _get_task_or_404(task_id: int):
    """Return task if it belongs to current user, else None."""
    task = db.session.get(Task, task_id)
    if not task or task.user_id != current_user.id:
        return None
    return task


# ---------------------------------------------------------------------------
# /api/v1/tasks
# ---------------------------------------------------------------------------
@api_bp.route("/tasks", methods=["GET"])
@login_required
def list_tasks():
    """
    GET /api/v1/tasks
    Query params:
        priority  (optional) filter by High|Medium|Low
        recurrence (optional) filter by daily|one-time
    """
    query = Task.query.filter_by(user_id=current_user.id)

    if priority := request.args.get("priority"):
        query = query.filter_by(priority=priority)
    if recurrence := request.args.get("recurrence"):
        query = query.filter_by(recurrence_type=recurrence)

    tasks = query.order_by(Task.date_created.desc()).all()
    return _ok([t.to_dict() for t in tasks])


@api_bp.route("/tasks/<int:task_id>", methods=["GET"])
@login_required
def get_task(task_id: int):
    """GET /api/v1/tasks/<id>"""
    task = _get_task_or_404(task_id)
    if not task:
        return _error("Task not found", 404)
    return _ok(task.to_dict())


@api_bp.route("/tasks", methods=["POST"])
@login_required
def create_task():
    """
    POST /api/v1/tasks
    Body (JSON):
        title         (required) string
        priority      (required) High|Medium|Low
        recurrence    (optional) daily|one-time  [default: one-time]
        description   (optional) string
    """
    body = request.get_json(silent=True) or {}

    title      = (body.get("title") or "").strip()
    priority   = body.get("priority", "")
    recurrence = body.get("recurrence", "one-time")
    description = body.get("description", "")

    if not title:
        return _error("'title' is required")
    if priority not in ("High", "Medium", "Low"):
        return _error("'priority' must be High, Medium, or Low")
    if recurrence not in ("daily", "one-time"):
        return _error("'recurrence' must be 'daily' or 'one-time'")

    task = Task(
        title=title,
        priority=priority,
        recurrence_type=recurrence,
        description=description,
        user_id=current_user.id,
    )
    db.session.add(task)
    db.session.commit()
    logger.info("API: task created id=%s by user=%s", task.id, current_user.id)
    return _ok(task.to_dict(), 201)


@api_bp.route("/tasks/<int:task_id>", methods=["PUT"])
@login_required
def update_task(task_id: int):
    """
    PUT /api/v1/tasks/<id>
    Body (JSON): any subset of {title, priority, recurrence, description}
    """
    task = _get_task_or_404(task_id)
    if not task:
        return _error("Task not found", 404)

    body = request.get_json(silent=True) or {}

    if "title" in body and body["title"].strip():
        task.title = body["title"].strip()
    if "description" in body:
        task.description = body["description"]
    if "priority" in body:
        if body["priority"] not in ("High", "Medium", "Low"):
            return _error("'priority' must be High, Medium, or Low")
        task.priority = body["priority"]
    if "recurrence" in body:
        if body["recurrence"] not in ("daily", "one-time"):
            return _error("'recurrence' must be 'daily' or 'one-time'")
        task.recurrence_type = body["recurrence"]

    db.session.commit()
    logger.info("API: task updated id=%s by user=%s", task_id, current_user.id)
    return _ok(task.to_dict())


@api_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task(task_id: int):
    """DELETE /api/v1/tasks/<id> — removes task and all its history."""
    task = _get_task_or_404(task_id)
    if not task:
        return _error("Task not found", 404)

    db.session.delete(task)
    db.session.commit()
    logger.info("API: task deleted id=%s by user=%s", task_id, current_user.id)
    return _ok({"deleted_id": task_id})


# ---------------------------------------------------------------------------
# /api/v1/scores
# ---------------------------------------------------------------------------
@api_bp.route("/scores", methods=["GET"])
@login_required
def get_scores():
    """
    GET /api/v1/scores
    Query params:
        days  (optional, default=7) number of days to look back
    """
    days       = min(int(request.args.get("days", 7)), 365)
    end_date   = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)

    scores = Score.query.filter(
        Score.user_id == current_user.id,
        Score.date >= start_date,
        Score.date <= end_date,
    ).order_by(Score.date).all()

    return _ok([s.to_dict() for s in scores])


# ---------------------------------------------------------------------------
# /api/v1/stats
# ---------------------------------------------------------------------------
@api_bp.route("/stats", methods=["GET"])
@login_required
def get_stats():
    """
    GET /api/v1/stats
    Returns a summary of the user's discipline metrics.
    """
    today      = datetime.now(timezone.utc).date()
    start_30   = today - timedelta(days=29)

    # Generate today's instances so score is up to date
    generate_instances_for_date(current_user.id, today)
    calculate_score_and_streak(current_user.id, today)

    scores_30 = Score.query.filter(
        Score.user_id == current_user.id,
        Score.date >= start_30,
        Score.date <= today,
    ).all()

    vals        = [s.daily_score for s in scores_30]
    avg_score   = round(sum(vals) / len(vals), 1) if vals else 0
    best_score  = max(vals) if vals else 0
    active_days = sum(1 for v in vals if v > 0)

    today_score = Score.query.filter_by(
        user_id=current_user.id, date=today
    ).first()

    total_tasks = Task.query.filter_by(user_id=current_user.id).count()

    return _ok({
        "user": {
            "name":             current_user.name,
            "streak":           current_user.streak_count,
            "discipline_tier":  current_user.discipline_tier,
            "tier_next":        current_user.tier_next_milestone,
        },
        "today": {
            "score":      today_score.daily_score if today_score else 0,
            "date":       today.isoformat(),
        },
        "last_30_days": {
            "avg_score":   avg_score,
            "best_score":  best_score,
            "active_days": active_days,
        },
        "total_tasks_defined": total_tasks,
    })
