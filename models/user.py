"""
models/user.py
User domain model — authentication, discipline tier, streak logic, roles.
"""
from flask_login import UserMixin
from models import db


class User(db.Model, UserMixin):
    """Represents an authenticated user of Project PA."""
    __tablename__ = "user"

    id                  = db.Column(db.Integer, primary_key=True)
    name                = db.Column(db.String(100), nullable=False)
    email               = db.Column(db.String(120), unique=True, nullable=False)
    password_hash       = db.Column(db.String(255), nullable=False)
    streak_count        = db.Column(db.Integer, default=0)

    # Role-based access: "user" (default) | "admin"
    role                = db.Column(db.String(20), nullable=False, default="user")

    # Profile fields
    bio                 = db.Column(db.Text, nullable=True)
    avatar_url          = db.Column(db.String(300), nullable=True)

    # Notification preferences
    email_notifications = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    tasks  = db.relationship("Task",  backref="user", lazy=True,
                             foreign_keys="Task.user_id")
    scores = db.relationship("Score", backref="user", lazy=True)

    # ------------------------------------------------------------------
    # Role helpers
    # ------------------------------------------------------------------

    @property
    def is_admin(self) -> bool:
        """True if the user has admin privileges."""
        return self.role == "admin"

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

    def to_dict(self) -> dict:
        """Serialise user to JSON-safe dict (for REST API responses)."""
        return {
            "id":                  self.id,
            "name":                self.name,
            "email":               self.email,
            "role":                self.role,
            "streak_count":        self.streak_count,
            "discipline_tier":     self.discipline_tier,
            "tier_next_milestone": self.tier_next_milestone,
            "email_notifications": self.email_notifications,
            "bio":                 self.bio,
        }
