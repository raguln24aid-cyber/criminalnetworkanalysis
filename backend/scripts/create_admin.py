"""
Creates or resets the one ADMIN account, interactively.

No credentials are ever hardcoded in source - this prompts for a username and
a hidden (non-echoed) password at run time. Run it once from backend/:

    ./venv311/Scripts/python.exe scripts/create_admin.py

If the username already exists, its password and role are updated in place
(useful for resetting a lost admin password) rather than failing.
"""
import getpass
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, Base, engine
from app.models.domain import User
from app.security.auth import get_password_hash

MIN_PASSWORD_LENGTH = 10


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        username = input("Admin username: ").strip()
        if not username or not re.match(r"^[A-Za-z0-9_.-]{3,50}$", username):
            print("Username must be 3-50 characters: letters, digits, _ . -")
            sys.exit(1)

        password = getpass.getpass("Admin password (min 10 chars, input hidden): ")
        if len(password) < MIN_PASSWORD_LENGTH:
            print(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
            sys.exit(1)
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords did not match.")
            sys.exit(1)

        user = db.query(User).filter(User.username == username).first()
        if user:
            user.hashed_password = get_password_hash(password)
            user.role = "ADMIN"
            user.is_active = True
            user.failed_login_attempts = 0
            user.locked_until = None
            db.commit()
            print(f"Updated existing user '{username}' to ADMIN with the new password.")
        else:
            user = User(
                username=username,
                hashed_password=get_password_hash(password),
                role="ADMIN",
                is_active=True,
            )
            db.add(user)
            db.commit()
            print(f"Created ADMIN user '{username}'.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
