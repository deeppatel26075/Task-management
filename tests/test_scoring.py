from datetime import datetime, timezone, timedelta
from models import db
from models.task import Task, TaskInstance
from models.user import User
from services.scoring_service import calculate_score_and_streak

def test_calculate_score_basic(app, test_user):
    """Test that scoring correctly weights priority and multipliers."""
    with app.app_context():
        today = datetime.now(timezone.utc).date()
        
        # Create tasks
        task_high = Task(title="High Task", priority="High", user_id=test_user)
        task_med = Task(title="Medium Task", priority="Medium", user_id=test_user)
        task_low = Task(title="Low Task", priority="Low", user_id=test_user)
        db.session.add_all([task_high, task_med, task_low])
        db.session.commit()

        # Create instances
        inst1 = TaskInstance(task_id=task_high.id, date=today, status="Full")    # 20 * 1.0 = 20
        inst2 = TaskInstance(task_id=task_med.id, date=today, status="Half")     # 10 * 0.5 = 5
        inst3 = TaskInstance(task_id=task_low.id, date=today, status="Missed")   # 5 * -1.0 = -5
        db.session.add_all([inst1, inst2, inst3])
        db.session.commit()

        # Run scoring engine
        score = calculate_score_and_streak(test_user, today)
        
        # 20 + 5 - 5 = 20
        assert score == 20.0

def test_streak_calculation(app, test_user):
    """Test that streaks are calculated based on historical High-priority tasks."""
    with app.app_context():
        today = datetime.now(timezone.utc).date()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        # Create high priority task
        task_high = Task(title="Daily Hard Thing", priority="High", user_id=test_user)
        db.session.add(task_high)
        db.session.commit()

        # Two days ago: Full
        db.session.add(TaskInstance(task_id=task_high.id, date=two_days_ago, status="Full"))
        # Yesterday: Full
        db.session.add(TaskInstance(task_id=task_high.id, date=yesterday, status="Full"))
        
        db.session.commit()

        # Calculate score/streak for yesterday (simulating a past run)
        calculate_score_and_streak(test_user, yesterday)
        
        # Verify streak is 2
        user = db.session.get(User, test_user)
        assert user.streak_count == 2
