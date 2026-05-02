"""
services/scoring_service.py
Discipline Evaluation Engine — the core algorithm of Project PA.

This service encapsulates all score computation and streak management logic,
keeping it completely decoupled from HTTP request handling.

Scoring Algorithm:
    daily_score = Σ (priority_points × status_multiplier)

    Priority points : High=20, Medium=10, Low=5
    Status multipliers:
        Full    → +1.0  (rewarded)
        Half    → +0.5  (partial credit)
        Missed  → −1.0  (discipline penalty)
        Pending →  0.0  (neutral)

Streak Rules:
    - Streak increments only when ALL High-priority tasks are 'Full' for today.
    - Any High task not 'Full' resets streak to 0.
    - Days with no High tasks are streak-neutral (no change).
"""
import logging
from datetime import datetime, timezone, timedelta

from models import db
from models.task import Task, TaskInstance, Score

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PRIORITY_POINTS: dict[str, int]    = {"High": 20, "Medium": 10, "Low": 5}
STATUS_MULTIPLIER: dict[str, float] = {"Full": 1.0, "Half": 0.5, "Missed": -1.0, "Pending": 0.0}


def generate_instances_for_date(user_id: int, target_date) -> None:
    """
    Ensure TaskInstance rows exist for every applicable task on `target_date`.

    A task is applicable if:
      - recurrence_type == 'daily'  → always applicable after creation date
      - recurrence_type == 'one-time' → only on its creation date
    """
    tasks = Task.query.filter(Task.user_id == user_id).all()
    created = False

    for task in tasks:
        task_date = task.date_created.date()
        if task_date > target_date:
            continue

        applicable = (
            task.recurrence_type == "daily"
            or (task.recurrence_type == "one-time" and task_date == target_date)
        )

        if applicable:
            exists = TaskInstance.query.filter_by(
                task_id=task.id, date=target_date
            ).first()
            if not exists:
                db.session.add(TaskInstance(task_id=task.id, date=target_date))
                created = True

    if created:
        db.session.commit()
        logger.debug("Generated task instances for user=%s date=%s", user_id, target_date)


def calculate_score_and_streak(user_id: int, target_date) -> float:
    """
    Recalculate the daily score for `target_date` and update the Score record.

    Also updates the user's streak_count if target_date is today.

    Returns:
        float: The computed daily_score.
    """
    from models.user import User  # local import to avoid circular at module level

    instances = TaskInstance.query.join(Task).filter(
        Task.user_id == user_id,
        TaskInstance.date == target_date,
    ).all()

    daily_total   = 0.0
    all_high_done = True
    has_high      = False
    has_any       = len(instances) > 0

    for inst in instances:
        pts        = PRIORITY_POINTS.get(inst.task.priority, 0)
        multiplier = STATUS_MULTIPLIER.get(inst.status, 0.0)
        daily_total += pts * multiplier

        if inst.task.priority == "High":
            has_high = True
            if inst.status != "Full":
                all_high_done = False

    # Persist / update Score record
    score_record = Score.query.filter_by(user_id=user_id, date=target_date).first()
    if not score_record:
        score_record = Score(user_id=user_id, date=target_date, daily_score=daily_total)
        db.session.add(score_record)
    else:
        score_record.daily_score = daily_total

    db.session.commit()

    # Deterministic Streak Calculation
    # A streak is the number of consecutive past days (ending today or yesterday) 
    # where ALL High-priority tasks for that day were 'Full'.
    user = db.session.get(User, user_id)
    today = datetime.now(timezone.utc).date()
    
    # Get all task instances up to today, ordered by date descending
    all_past_instances = TaskInstance.query.join(Task).filter(
        Task.user_id == user_id,
        TaskInstance.date <= today
    ).order_by(TaskInstance.date.desc()).all()

    # Group by date, keeping only High priority tasks
    days_map = {}
    for inst in all_past_instances:
        if inst.task.priority == "High":
            if inst.date not in days_map:
                days_map[inst.date] = []
            days_map[inst.date].append(inst)

    new_streak = 0
    check_date = today
    
    while True:
        if check_date in days_map:
            day_insts = days_map[check_date]
            all_full = all(i.status == "Full" for i in day_insts)
            
            if all_full:
                new_streak += 1
            else:
                # If today's high-priority tasks are not full yet, it doesn't break the streak
                # (they might finish them later today). But if it's a past day, it breaks the streak.
                # If they explicitly marked it "Missed" today, it breaks the streak.
                if check_date != today or any(i.status == "Missed" for i in day_insts):
                    break
        elif check_date < today:
            # If there are no High priority tasks for a past day, it's a neutral day (streak continues)
            pass
            
        # Move to previous day
        check_date -= timedelta(days=1)
        
        # Stop checking if we've gone back further than the earliest task recorded
        if not all_past_instances or check_date < all_past_instances[-1].date:
            break

    if user.streak_count != new_streak:
        logger.info("Streak updated for user=%s: %s → %s", user_id, user.streak_count, new_streak)
        user.streak_count = new_streak
        db.session.commit()

    logger.debug(
        "Score calculated: user=%s date=%s score=%.1f", user_id, target_date, daily_total
    )
    return daily_total
