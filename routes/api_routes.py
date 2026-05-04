"""
routes/api_routes.py
REST API Blueprint — /api/v1/

Provides a production-grade JSON API for external clients, mobile apps, and integrations.
Auth: Accepts EITHER Flask-Login session (browser) OR JWT Bearer token (external clients).

Endpoints:
    GET    /api/v1/health            System health check (no auth required)
    GET    /api/v1/tasks             List tasks (paginated, filterable)
    POST   /api/v1/tasks             Create a new task
    GET    /api/v1/tasks/<id>        Get a single task by ID
    PUT    /api/v1/tasks/<id>        Update a task
    DELETE /api/v1/tasks/<id>        Delete a task and all its history
    PATCH  /api/v1/tasks/<id>/status Update a task instance status
    GET    /api/v1/scores            Score history (last N days)
    GET    /api/v1/stats             Aggregated user stats summary
"""
import logging
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import Blueprint, jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from flask_login import current_user

from models import db
from models.task import Task, TaskInstance, Score
from services.scoring_service import generate_instances_for_date, calculate_score_and_streak

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

# ---------------------------------------------------------------------------
# Rate limiter (initialized in app.py, accessed via extension)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _error(message: str, code: int = 400):
    return jsonify({"success": False, "error": message, "api_version": "1.0"}), code


def _ok(data, code: int = 200, meta: dict | None = None):
    resp = {"success": True, "data": data, "api_version": "1.0"}
    if meta:
        resp["meta"] = meta
    return jsonify(resp), code


def _get_current_user_id() -> int | None:
    """
    Resolve the current user's ID from EITHER:
      1. A valid JWT Bearer token (Authorization header), or
      2. An active Flask-Login session (browser cookie)
    Returns None if neither is present.
    """
    # Try JWT first
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if identity:
            return int(identity)
    except Exception:
        pass

    # Fall back to session
    if current_user and current_user.is_authenticated:
        return current_user.id

    return None


def dual_auth_required(f):
    """
    Decorator: requires authentication via JWT token OR active session.
    Returns 401 if neither is valid.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = _get_current_user_id()
        if user_id is None:
            return _error("Unauthorized. Provide a Bearer token or log in.", 401)
        return f(*args, **kwargs)
    return decorated


def _get_task_or_404(task_id: int, user_id: int):
    """Return task if it belongs to the given user, else None."""
    task = db.session.get(Task, task_id)
    if not task or task.user_id != user_id:
        return None
    return task


# ---------------------------------------------------------------------------
# GET /api/v1/health  (no auth required)
# ---------------------------------------------------------------------------
@api_bp.route("/health", methods=["GET"])
def health_check():
    """
    System health check — no auth required.
    Verifies: API is up, DB is reachable.

    Returns:
        200 {"status": "ok", "db": "ok"}
        503 {"status": "degraded", "db": "error"}
    """
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({
            "status":      "ok",
            "db":          "ok",
            "api_version": "1.0",
            "timestamp":   datetime.now(timezone.utc).isoformat(),
        }), 200
    except Exception as exc:
        logger.error("Health check DB error: %s", exc)
        return jsonify({
            "status":      "degraded",
            "db":          "error",
            "api_version": "1.0",
        }), 503


# ---------------------------------------------------------------------------
# GET/POST /api/v1/tasks
# ---------------------------------------------------------------------------
@api_bp.route("/tasks", methods=["GET"])
@dual_auth_required
def list_tasks():
    """
    GET /api/v1/tasks
    Query params:
        priority    (optional) High|Medium|Low
        recurrence  (optional) daily|one-time
        category    (optional) string
        page        (optional, default=1)
        per_page    (optional, default=20, max=100)
    """
    user_id = _get_current_user_id()
    query   = Task.query.filter_by(user_id=user_id)

    # Filters
    if priority := request.args.get("priority"):
        query = query.filter_by(priority=priority)
    if recurrence := request.args.get("recurrence"):
        query = query.filter_by(recurrence_type=recurrence)
    if category := request.args.get("category"):
        query = query.filter_by(category=category)

    query = query.order_by(Task.date_created.desc())

    # Pagination
    page     = max(1, request.args.get("page", 1, type=int))
    per_page = min(100, max(1, request.args.get("per_page", 20, type=int)))
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return _ok(
        [t.to_dict() for t in paginated.items],
        meta={
            "page":        paginated.page,
            "per_page":    per_page,
            "total":       paginated.total,
            "total_pages": paginated.pages,
            "has_next":    paginated.has_next,
            "has_prev":    paginated.has_prev,
        },
    )


@api_bp.route("/tasks/<int:task_id>", methods=["GET"])
@dual_auth_required
def get_task(task_id: int):
    """GET /api/v1/tasks/<id>"""
    user_id = _get_current_user_id()
    task    = _get_task_or_404(task_id, user_id)
    if not task:
        return _error("Task not found", 404)
    return _ok(task.to_dict())


@api_bp.route("/tasks", methods=["POST"])
@dual_auth_required
def create_task():
    """
    POST /api/v1/tasks
    Body (JSON):
        title         (required) string
        priority      (required) High|Medium|Low
        recurrence    (optional) daily|one-time  [default: one-time]
        description   (optional) string
        category      (optional) string
    """
    user_id = _get_current_user_id()
    body    = request.get_json(silent=True) or {}

    title       = (body.get("title") or "").strip()
    priority    = body.get("priority", "")
    recurrence  = body.get("recurrence", "one-time")
    description = (body.get("description") or "").strip()
    category    = (body.get("category") or "").strip() or None

    if not title or len(title) > 200:
        return _error("'title' is required and must be up to 200 characters")
    if priority not in ("High", "Medium", "Low"):
        return _error("'priority' must be High, Medium, or Low")
    if recurrence not in ("daily", "one-time"):
        return _error("'recurrence' must be 'daily' or 'one-time'")
    if category and len(category) > 50:
        return _error("'category' must not exceed 50 characters")
    if description and len(description) > 1000:
        return _error("'description' must not exceed 1000 characters")

    task = Task(
        title=title,
        priority=priority,
        recurrence_type=recurrence,
        description=description,
        category=category,
        user_id=user_id,
    )
    db.session.add(task)
    db.session.commit()
    logger.info("API: task created id=%s by user=%s", task.id, user_id)
    return _ok(task.to_dict(), 201)


@api_bp.route("/tasks/<int:task_id>", methods=["PUT"])
@dual_auth_required
def update_task(task_id: int):
    """
    PUT /api/v1/tasks/<id>
    Body (JSON): any subset of {title, priority, recurrence, description, category}
    """
    user_id = _get_current_user_id()
    task    = _get_task_or_404(task_id, user_id)
    if not task:
        return _error("Task not found", 404)

    body = request.get_json(silent=True) or {}

    if "title" in body and body["title"].strip():
        task.title = body["title"].strip()
    if "description" in body:
        task.description = body["description"]
    if "category" in body:
        task.category = body["category"] or None
    if "priority" in body:
        if body["priority"] not in ("High", "Medium", "Low"):
            return _error("'priority' must be High, Medium, or Low")
        task.priority = body["priority"]
    if "recurrence" in body:
        if body["recurrence"] not in ("daily", "one-time"):
            return _error("'recurrence' must be 'daily' or 'one-time'")
        task.recurrence_type = body["recurrence"]

    db.session.commit()
    logger.info("API: task updated id=%s by user=%s", task_id, user_id)
    return _ok(task.to_dict())


@api_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
@dual_auth_required
def delete_task(task_id: int):
    """DELETE /api/v1/tasks/<id> — removes task and all its history."""
    user_id = _get_current_user_id()
    task    = _get_task_or_404(task_id, user_id)
    if not task:
        return _error("Task not found", 404)

    db.session.delete(task)
    db.session.commit()
    logger.info("API: task deleted id=%s by user=%s", task_id, user_id)
    return _ok({"deleted_id": task_id})


# ---------------------------------------------------------------------------
# PATCH /api/v1/tasks/<id>/status  — update a task instance status
# ---------------------------------------------------------------------------
@api_bp.route("/tasks/<int:task_id>/status", methods=["PATCH"])
@dual_auth_required
def update_task_status(task_id: int):
    """
    PATCH /api/v1/tasks/<id>/status
    Body (JSON):
        status  (required) Pending|Full|Half|Missed
        date    (optional) YYYY-MM-DD  [default: today]
    """
    user_id = _get_current_user_id()
    task    = _get_task_or_404(task_id, user_id)
    if not task:
        return _error("Task not found", 404)

    body   = request.get_json(silent=True) or {}
    status = body.get("status", "")
    if status not in ("Pending", "Full", "Half", "Missed"):
        return _error("'status' must be Pending, Full, Half, or Missed")

    date_str = body.get("date")
    try:
        target_date = (
            datetime.strptime(date_str, "%Y-%m-%d").date()
            if date_str
            else datetime.now(timezone.utc).date()
        )
    except ValueError:
        return _error("'date' must be in YYYY-MM-DD format")

    # Ensure instance exists
    generate_instances_for_date(user_id, target_date)

    instance = TaskInstance.query.filter_by(task_id=task_id, date=target_date).first()
    if not instance:
        return _error("No task instance found for that date", 404)

    instance.status = status
    db.session.commit()
    calculate_score_and_streak(user_id, target_date)

    logger.info("API: task %s status → %s on %s by user=%s", task_id, status, target_date, user_id)
    return _ok(instance.to_dict())


# ---------------------------------------------------------------------------
# GET /api/v1/scores
# ---------------------------------------------------------------------------
@api_bp.route("/scores", methods=["GET"])
@dual_auth_required
def get_scores():
    """
    GET /api/v1/scores
    Query params:
        days  (optional, default=7, max=365) number of days to look back
    """
    user_id    = _get_current_user_id()
    days       = min(int(request.args.get("days", 7)), 365)
    end_date   = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)

    scores = Score.query.filter(
        Score.user_id == user_id,
        Score.date >= start_date,
        Score.date <= end_date,
    ).order_by(Score.date).all()

    return _ok([s.to_dict() for s in scores])


# ---------------------------------------------------------------------------
# GET /api/v1/stats
# ---------------------------------------------------------------------------
@api_bp.route("/stats", methods=["GET"])
@dual_auth_required
def get_stats():
    """
    GET /api/v1/stats
    Returns a summary of the user's discipline metrics.
    """
    from models.user import User

    user_id  = _get_current_user_id()
    today    = datetime.now(timezone.utc).date()
    start_30 = today - timedelta(days=29)

    # Ensure today's data is up to date
    generate_instances_for_date(user_id, today)
    calculate_score_and_streak(user_id, today)

    scores_30 = Score.query.filter(
        Score.user_id == user_id,
        Score.date >= start_30,
        Score.date <= today,
    ).all()

    vals        = [s.daily_score for s in scores_30]
    avg_score   = round(sum(vals) / len(vals), 1) if vals else 0
    best_score  = max(vals) if vals else 0
    active_days = sum(1 for v in vals if v > 0)

    today_score = Score.query.filter_by(user_id=user_id, date=today).first()
    total_tasks = Task.query.filter_by(user_id=user_id).count()
    user        = db.session.get(User, user_id)

    return _ok({
        "user": {
            "id":              user.id,
            "name":            user.name,
            "role":            user.role,
            "streak":          user.streak_count,
            "discipline_tier": user.discipline_tier,
            "tier_next":       user.tier_next_milestone,
        },
        "today": {
            "score": today_score.daily_score if today_score else 0,
            "date":  today.isoformat(),
        },
        "last_30_days": {
            "avg_score":   avg_score,
            "best_score":  best_score,
            "active_days": active_days,
        },
        "total_tasks_defined": total_tasks,
    })
