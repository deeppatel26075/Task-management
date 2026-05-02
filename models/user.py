"""
models/user.py
User domain model — authentication, discipline tier, streak logic.
"""
from flask_login import UserMixin
from models import db


class User(db.Model, UserMixin):
    """Represents an authenticated user of Project PA."""
    __tablename__ = "user"

    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(100), nullable=False)
    email          = db.Column(db.String(120), unique=True, nullable=False)
    password_hash  = db.Column(db.String(255), nullable=False)
    streak_count   = db.Column(db.Integer, default=0)

    # Relationships
    tasks  = db.relationship("Task",  backref="user", lazy=True)
    scores = db.relationship("Score", backref="user", lazy=True)

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def discipline_tier(self) -> str:
        """
        Maps streak_count to a named discipline tier.

        Tiers:
          - Beginner   : streak < 5
          - Consistent : 5 <= streak < 14
          - Elite      : streak >= 14
        """
        if self.streak_count >= 14:
            return "Elite"
        elif self.streak_count >= 5:
            return "Consistent"
        return "Beginner"

    @property
    def tier_next_milestone(self):
        """Returns the streak count needed for the next tier, or None if already Elite."""
        if self.streak_count < 5:
            return 5
        elif self.streak_count < 14:
            return 14
        return None
