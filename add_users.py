import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.database import SessionLocal, User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
db = SessionLocal()

users_to_add = [
    ("maker2", "maker"),
    ("maker3", "maker"),
    ("checker2", "checker"),
    ("checker3", "checker")
]

try:
    for username, role in users_to_add:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            hashed_pw = pwd_context.hash(username)
            new_user = User(username=username, password_hash=hashed_pw, role=role)
            db.add(new_user)
            print(f"Added {username} with role {role}")
        else:
            print(f"User {username} already exists")
    db.commit()
except Exception as e:
    print(f"Error: {e}")
    db.rollback()
finally:
    db.close()
