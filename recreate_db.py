import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.database import Base, engine, init_db

print("Dropping all tables...")
Base.metadata.drop_all(bind=engine)
print("Initializing database with new schema...")
init_db()
print("Database recreated successfully.")
