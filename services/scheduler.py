"""
services/scheduler.py
Background job scheduler for Project PA.

Jobs:
  - nightly_discipline_job  → runs at 00:01 AM daily
      1. Finalizes yesterday's score + streak for all users
      2. Generates today's task instances
      3. Sends email notifications (streak at risk, broken, personal best)
"""
import logging
from datetime import datetime, timezone, timedelta

from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

from models import db
from models.user import User
from models.task import Task, TaskInstance, Score
from services.scoring_service import generate_instances_for_date, calculate_score_and_streak

logger = logging.getLogger(__name__)


def nightly_discipline_job(app: Flask) -> None:
    """
    Background job that runs at midnight.
    Finalizes yesterday's scores, generates today's task instances,
    and dispatches email notifications.
    """
    with app.app_context():
        logger.info("Running nightly discipline job...")
        today     = datetime.now(timezone.utc).date()
        yesterday = today - timedelta(days=1)

        users = User.query.all()
        for user in users:
            try:
                # 1. Finalize yesterday's score and streak
                calculate_score_and_streak(user.id, yesterday)

                # 2. Generate instances for today so user wakes up to a fresh board
                generate_instances_for_date(user.id, today)

                # 3. Email notifications (only if opted in)
                if user.email_notifications:
                    _send_notifications(app, user, today, yesterday)

            except Exception as exc:
                logger.error(
                    "Error in nightly job for user %s: %s", user.id, exc, exc_info=True
                )

        logger.info("Nightly discipline job completed for %d users.", len(users))


def _send_notifications(app: Flask, user: User, today, yesterday) -> None:
    """Dispatch email notifications based on the user's discipline state."""
    from services.email_service import (
        send_streak_at_risk,
        send_streak_broken,
        send_personal_best,
    )

    # Check if streak was just broken (yesterday had High tasks that weren't Full)
    yesterday_insts = (
        TaskInstance.query.join(Task)
        .filter(
            Task.user_id == user.id,
            TaskInstance.date == yesterday,
            Task.priority == "High",
        )
        .all()
    )
    prev_streak = user.streak_count  # Already updated by calculate_score_and_streak

    if yesterday_insts:
        all_full = all(i.status == "Full" for i in yesterday_insts)
        if not all_full and prev_streak == 0:
            # Streak was just broken — figure out what it was before
            # We look at the lost streak as approximated by consecutive days prior to yesterday
            send_streak_broken(user.email, user.name, lost_streak=0)

    # Check today's progress: are there unfinished High tasks?
    today_high_insts = (
        TaskInstance.query.join(Task)
        .filter(
            Task.user_id == user.id,
            TaskInstance.date == today,
            Task.priority == "High",
        )
        .all()
    )
    unfinished = [i for i in today_high_insts if i.status not in ("Full",)]
    if unfinished and user.streak_count > 0:
        send_streak_at_risk(
            user.email, user.name, user.streak_count, len(unfinished)
        )

    # Check personal best: today's score vs historical best
    today_score_record = Score.query.filter_by(user_id=user.id, date=today).first()
    if today_score_record and today_score_record.daily_score > 0:
        previous_best = (
            db.session.query(db.func.max(Score.daily_score))
            .filter(Score.user_id == user.id, Score.date < today)
            .scalar()
        ) or 0
        if today_score_record.daily_score > previous_best:
            send_personal_best(
                user.email, user.name,
                today_score_record.daily_score, previous_best
            )


def init_scheduler(app: Flask) -> BackgroundScheduler:
    """Initialize and start the APScheduler background scheduler."""
    scheduler = BackgroundScheduler()

    scheduler.add_job(
        func=nightly_discipline_job,
        trigger="cron",
        hour=0,
        minute=1,
        args=[app],
        id="nightly_discipline_job",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("APScheduler started: nightly_discipline_job scheduled at 00:01.")
    return scheduler
