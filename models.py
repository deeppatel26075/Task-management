from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    streak_count = db.Column(db.Integer, default=0)
    tasks = db.relationship('Task', backref='user', lazy=True)
    scores = db.relationship('Score', backref='user', lazy=True)

    @property
    def discipline_tier(self):
        """Returns the user's discipline tier based on streak count."""
        if self.streak_count >= 14:
            return 'Elite'
        elif self.streak_count >= 5:
            return 'Consistent'
        else:
            return 'Beginner'

    @property
    def tier_next_milestone(self):
        if self.streak_count < 5:
            return 5
        elif self.streak_count < 14:
            return 14
        return None

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    priority = db.Column(db.String(20), nullable=False)  # High, Medium, Low
    recurrence_type = db.Column(db.String(50), default='one-time')  # one-time, daily
    date_created = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    instances = db.relationship('TaskInstance', backref='task', lazy=True, cascade="all, delete-orphan")

    @property
    def point_value(self):
        return {'High': 20, 'Medium': 10, 'Low': 5}.get(self.priority, 0)

class TaskInstance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='Pending')  # Pending, Full, Half, Missed

class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    daily_score = db.Column(db.Float, default=0.0)
    date = db.Column(db.Date, nullable=False, default=lambda: datetime.now(timezone.utc).date())
