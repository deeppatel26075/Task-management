import logging
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone, timedelta
from flask import Flask
from models import db
from models.user import User
from services.scoring_service import generate_instances_for_date, calculate_score_and_streak

logger = logging.getLogger(__name__)

def nightly_discipline_job(app: Flask):
    """
    Background job that runs at midnight.
    It finalizes yesterday's scores and generates today's task instances.
    """
    with app.app_context():
        logger.info("Running nightly discipline job...")
        today = datetime.now(timezone.utc).date()
        yesterday = today - timedelta(days=1)
        
        users = User.query.all()
        for user in users:
            try:
                # 1. Finalize yesterday's score and streak
                calculate_score_and_streak(user.id, yesterday)
                
                # 2. Generate instances for today so the user wakes up to a fresh board
                generate_instances_for_date(user.id, today)
                
            except Exception as e:
                logger.error("Error processing background job for user %s: %s", user.id, e)
                
        db.session.commit()
        logger.info("Nightly discipline job completed for %s users.", len(users))

def init_scheduler(app: Flask):
    """Initialize and start the background scheduler."""
    scheduler = BackgroundScheduler()
    
    # Run at 00:01 AM every day
    scheduler.add_job(
        func=nightly_discipline_job,
        trigger="cron",
        hour=0,
        minute=1,
        args=[app],
        id="nightly_discipline_job",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("APScheduler started: nightly_discipline_job scheduled.")
    return scheduler
