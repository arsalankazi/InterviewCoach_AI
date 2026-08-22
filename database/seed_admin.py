import os
import sys
from pathlib import Path

# Add project root to sys.path if run directly
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app
from database.schema import init_db
from models.admin import Admin


def seed_admin(name="Super Admin", email="admin@interviewcoach.ai", password=None):
    """
    Seed an initial administrator account if one does not already exist.
    """
    app = create_app('development')
    with app.app_context():
        init_db()

        admin_email = os.environ.get('INITIAL_ADMIN_EMAIL', email).strip().lower()
        admin_pass = os.environ.get('INITIAL_ADMIN_PASSWORD', password or 'Admin@123456')
        admin_name = os.environ.get('INITIAL_ADMIN_NAME', name).strip()

        existing_admin = Admin.get_by_email(admin_email)
        if existing_admin:
            print(f"[INFO] Admin account already exists: {admin_email} (ID: {existing_admin.id})")
            return existing_admin

        new_admin = Admin.create(name=admin_name, email=admin_email, password=admin_pass)
        print(f"[SUCCESS] Admin account created successfully!")
        print(f"  Name:  {new_admin.name}")
        print(f"  Email: {new_admin.email}")
        print(f"  ID:    {new_admin.id}")
        return new_admin


if __name__ == '__main__':
    seed_admin()
