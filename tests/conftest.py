import pytest
from werkzeug.security import generate_password_hash
from app import create_app
from models import db
from models.user import User

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "JWT_SECRET_KEY": "test-jwt-secret",
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
        user = User(
            name="Test User",
            email="test@example.com",
            password_hash=generate_password_hash("password123", method="scrypt"),
            role="user"
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return user_id

@pytest.fixture
def admin_user(app):
    """Creates an admin user and returns it."""
    with app.app_context():
        user = User(
            name="Admin User",
            email="admin@example.com",
            password_hash=generate_password_hash("admin123", method="scrypt"),
            role="admin"
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return user_id
