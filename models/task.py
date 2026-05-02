"""
models/task.py
Task domain models — Task definition, daily TaskInstance, and Score records.
"""
from datetime import datetime, timezone
from models import db


class Task(db.Model):
    """
    A recurring or one-time task owned by a user.

    Priority determines base point value used by the Discipline Evaluation Engine:
      - High   → 20 pts
      - Medium → 10 pts
      - Low    →  5 pts
    """
    __tablename__ = "task"

    id                    = db.Column(db.Integer, primary_key=True)
    user_id               = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title                 = db.Column(db.String(200), nullable=False)
    description           = db.Column(db.Text, nullable=True)
    priority              = db.Column(db.String(20), nullable=False)       # High | Medium | Low
    recurrence_type       = db.Column(db.String(50), default="one-time")   # one-time | daily
    completion_percentage = db.Column(db.Integer, default=0)               # 0-100
    date_created          = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    instances = db.relationship(
        "TaskInstance", backref="task", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def point_value(self) -> int:
        """Base points awarded for full completion of this task."""
        return {"High": 20, "Medium": 10, "Low": 5}.get(self.priority, 0)

    def to_dict(self) -> dict:
        """Serialise task to JSON-safe dict (for REST API responses)."""
        return {
            "id":                    self.id,
            "title":                 self.title,
            "description":           self.description,
            "priority":              self.priority,
            "recurrence_type":       self.recurrence_type,
            "completion_percentage": self.completion_percentage,
            "point_value":           self.point_value,
            "date_created":          self.date_created.isoformat(),
        }


class TaskInstance(db.Model):
    """
    Represents a single day's occurrence of a Task.
    Status drives the scoring multiplier:
      - Full    → ×1.0  (full points)
      - Half    → ×0.5  (partial effort)
      - Missed  → ×−1.0 (discipline penalty)
      - Pending → ×0.0  (not yet actioned)
    """
    __tablename__ = "task_instance"

    id      = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False)
    date    = db.Column(db.Date, nullable=False)
    status  = db.Column(db.String(20), default="Pending")  # Pending | Full | Half | Missed

    def to_dict(self) -> dict:
        return {
            "id":       self.id,
            "task_id":  self.task_id,
            "date":     self.date.isoformat(),
            "status":   self.status,
        }


class Score(db.Model):
    """
    Persists the computed daily discipline score for a user.
    Recalculated whenever any TaskInstance changes status.
    """
    __tablename__ = "score"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    daily_score = db.Column(db.Float, default=0.0)
    date        = db.Column(db.Date, nullable=False,
                            default=lambda: datetime.now(timezone.utc).date())

    def to_dict(self) -> dict:
        return {
            "date":        self.date.isoformat(),
            "daily_score": self.daily_score,
        }
