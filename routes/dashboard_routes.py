"""
routes/dashboard_routes.py
Dashboard blueprint — all page routes (dashboard, analytics, manage) and
Chart.js data endpoints.
"""
import logging
from datetime import datetime, timezone, timedelta

from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user

from models import db
from models.task import Task, TaskInstance, Score
from services.scoring_service import generate_instances_for_date, calculate_score_and_streak

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__)


# ---------------------------------------------------------------------------
# Helper — parse date from query string
# ---------------------------------------------------------------------------
def _parse_date(date_str: str | None):
    if date_str:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass
    return datetime.now(timezone.utc).date()


# ---------------------------------------------------------------------------
# Dashboard (main page)
# ---------------------------------------------------------------------------
@dashboard_bp.route("/dashboard")
@login_required
def index():
    target_date = _parse_date(request.args.get("date"))

    generate_instances_for_date(current_user.id, target_date)
    calculate_score_and_streak(current_user.id, target_date)

    score_record = Score.query.filter_by(
        user_id=current_user.id, date=target_date
    ).first()
    daily_score = score_record.daily_score if score_record else 0.0

    instances = (
        TaskInstance.query.join(Task)
        .filter(Task.user_id == current_user.id, TaskInstance.date == target_date)
        .order_by(Task.priority)
        .all()
    )

    total          = len(instances)
    done           = sum(1 for i in instances if i.status == "Full")
    completion_pct = round((done / total * 100) if total > 0 else 0)

    max_possible = sum(
        {"High": 20, "Medium": 10, "Low": 5}.get(i.task.priority, 0)
        for i in instances
    )
    score_pct = min(
        100, max(0, round((daily_score / max_possible * 100) if max_possible > 0 else 0))
    )

    prev_date = (target_date - timedelta(days=1)).strftime("%Y-%m-%d")
    next_date = (target_date + timedelta(days=1)).strftime("%Y-%m-%d")

    return render_template(
        "dashboard.html",
        daily_score=daily_score,
        score_pct=score_pct,
        streak=current_user.streak_count,
        instances=instances,
        current_date=target_date.strftime("%Y-%m-%d"),
        prev_date=prev_date,
        next_date=next_date,
        total_tasks=total,
        done_tasks=done,
        completion_pct=completion_pct,
        discipline_tier=current_user.discipline_tier,
        tier_next=current_user.tier_next_milestone,
    )


# ---------------------------------------------------------------------------
# Add / Update / Delete task instances
# ---------------------------------------------------------------------------
@dashboard_bp.route("/add_task", methods=["POST"])
@login_required
def add_task():
    title       = request.form.get("title", "").strip()
    priority    = request.form.get("priority")
    recurrence  = request.form.get("recurrence", "one-time")
    current_date = request.form.get("current_date")

    if title and priority in ("High", "Medium", "Low"):
        task = Task(
            title=title,
            priority=priority,
            recurrence_type=recurrence,
            user_id=current_user.id,
        )
        try:
            task.date_created = datetime.strptime(current_date, "%Y-%m-%d")
        except Exception:
            pass
        db.session.add(task)
        db.session.commit()
        logger.info("Task added: '%s' [%s] by user=%s", title, priority, current_user.id)

    if current_date:
        return redirect(url_for("dashboard.index", date=current_date))
    return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/update_task_instance/<int:instance_id>/<status>")
@login_required
def update_task_instance(instance_id: int, status: str):
    if status not in ("Full", "Half", "Missed", "Pending"):
        return redirect(url_for("dashboard.index"))

    instance = db.session.get(TaskInstance, instance_id)
    if not instance or instance.task.user_id != current_user.id:
        return redirect(url_for("dashboard.index"))

    instance.status = status
    db.session.commit()
    calculate_score_and_streak(current_user.id, instance.date)
    logger.info(
        "Instance %s marked '%s' by user=%s", instance_id, status, current_user.id
    )
    return redirect(url_for("dashboard.index", date=instance.date.strftime("%Y-%m-%d")))


@dashboard_bp.route("/delete_task/<int:task_id>")
@login_required
def delete_task(task_id: int):
    current_date = request.args.get("current_date")
    task = db.session.get(Task, task_id)

    if task and task.user_id == current_user.id:
        db.session.delete(task)
        db.session.commit()
        logger.info("Task %s deleted by user=%s", task_id, current_user.id)

    if current_date:
        try:
            target_date = datetime.strptime(current_date, "%Y-%m-%d").date()
            calculate_score_and_streak(current_user.id, target_date)
        except Exception:
            pass
        return redirect(url_for("dashboard.index", date=current_date))
    return redirect(url_for("dashboard.manage"))


# ---------------------------------------------------------------------------
# Manage tasks page
# ---------------------------------------------------------------------------
@dashboard_bp.route("/manage")
@login_required
def manage():
    tasks = (
        Task.query.filter_by(user_id=current_user.id)
        .order_by(Task.date_created.desc())
        .all()
    )
    return render_template("manage.html", tasks=tasks)


# ---------------------------------------------------------------------------
# Analytics page
# ---------------------------------------------------------------------------
@dashboard_bp.route("/analytics")
@login_required
def analytics():
    today    = datetime.now(timezone.utc).date()
    start_30 = today - timedelta(days=29)

    scores_30  = Score.query.filter(
        Score.user_id == current_user.id,
        Score.date >= start_30,
        Score.date <= today,
    ).order_by(Score.date).all()

    score_map = {s.date: s.daily_score for s in scores_30}

    # Activity heatmap data
    heatmap, cur = [], start_30
    while cur <= today:
        val   = score_map.get(cur, 0.0)
        level = 0
        if val > 0:  level = 1
        if val > 10: level = 2
        if val > 20: level = 3
        if val > 35: level = 4
        if val > 50: level = 5
        heatmap.append({"date": cur.strftime("%Y-%m-%d"), "score": val, "level": level})
        cur += timedelta(days=1)

    scores_vals = [s.daily_score for s in scores_30]
    avg_score   = round(sum(scores_vals) / len(scores_vals), 1) if scores_vals else 0
    best_score  = max(scores_vals) if scores_vals else 0
    best_day    = next(
        (s.date.strftime("%b %d") for s in scores_30 if s.daily_score == best_score),
        "N/A",
    ) if scores_vals else "N/A"
    active_days = sum(1 for v in scores_vals if v > 0)

    all_inst  = TaskInstance.query.join(Task).filter(
        Task.user_id == current_user.id,
        TaskInstance.date >= start_30,
    ).all()

    def _count(priority, status=None):
        return sum(
            1 for i in all_inst
            if i.task.priority == priority and (status is None or i.status == status)
        )

    def pct(done, total):
        return round(done / total * 100) if total > 0 else 0

    high_done, high_total = _count("High", "Full"), _count("High")
    med_done,  med_total  = _count("Medium", "Full"), _count("Medium")
    low_done,  low_total  = _count("Low", "Full"), _count("Low")

    return render_template(
        "analytics.html",
        heatmap=heatmap,
        avg_score=avg_score,
        best_score=round(best_score, 1),
        best_day=best_day,
        active_days=active_days,
        streak=current_user.streak_count,
        discipline_tier=current_user.discipline_tier,
        tier_next=current_user.tier_next_milestone,
        high_pct=pct(high_done, high_total), high_done=high_done, high_total=high_total,
        med_pct=pct(med_done, med_total),   med_done=med_done,   med_total=med_total,
        low_pct=pct(low_done, low_total),   low_done=low_done,   low_total=low_total,
        total_tasks_tracked=len(all_inst),
    )


# ---------------------------------------------------------------------------
# Chart.js JSON data endpoints
# ---------------------------------------------------------------------------
@dashboard_bp.route("/progress_data")
@login_required
def progress_data():
    days       = int(request.args.get("days", 7))
    end_date   = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)

    scores    = Score.query.filter(
        Score.user_id == current_user.id,
        Score.date >= start_date,
        Score.date <= end_date,
    ).order_by(Score.date).all()

    score_map       = {s.date: s.daily_score for s in scores}
    labels, data    = [], []
    cur             = start_date
    while cur <= end_date:
        labels.append(cur.strftime("%m/%d"))
        data.append(score_map.get(cur, 0.0))
        cur += timedelta(days=1)

    return jsonify({"labels": labels, "data": data})


@dashboard_bp.route("/analytics_data")
@login_required
def analytics_data():
    days       = int(request.args.get("days", 30))
    end_date   = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)

    scores = Score.query.filter(
        Score.user_id == current_user.id,
        Score.date >= start_date,
        Score.date <= end_date,
    ).order_by(Score.date).all()

    score_map    = {s.date: s.daily_score for s in scores}
    labels, data = [], []
    cur          = start_date
    while cur <= end_date:
        labels.append(cur.strftime("%m/%d"))
        data.append(score_map.get(cur, 0.0))
        cur += timedelta(days=1)

    avg = round(sum(data) / len(data), 1) if data else 0
    return jsonify({"labels": labels, "data": data, "avg": avg})
