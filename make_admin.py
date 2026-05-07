from app import app
from models import db
from models.user import User
import sys

def make_admin(email=None):
    with app.app_context():
        if email:
            user = User.query.filter_by(email=email).first()
        else:
            # If no email provided, just make the first user an admin
            user = User.query.first()
            
        if user:
            user.role = "admin"
            db.session.commit()
            print(f"Success! {user.email} is now an admin.")
            print("You can now access the admin panel at: http://127.0.0.1:5000/admin/users")
        else:
            print("No users found in the database. Please register an account first on the website.")

if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else None
    make_admin(email)
