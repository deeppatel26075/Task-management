from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.user import User        # noqa: E402,F401
from models.task import Task, TaskInstance, Score  # noqa: E402,F401
