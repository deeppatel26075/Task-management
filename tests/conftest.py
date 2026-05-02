import pytest
from app import create_app
from models import db
from models.user import User

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # Use an in-memory SQLite database for testing
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
    })

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()

@pytest.fixture
def test_user(app):
    """Creates a test user and returns it."""
    with app.app_context():
        user = User(name="Test User", email="test@example.com", password_hash="hashed")
        db.session.add(user)
        db.session.commit()
        # Detach so tests can query it freshly, or we just return the ID
        user_id = user.id
    return user_id
