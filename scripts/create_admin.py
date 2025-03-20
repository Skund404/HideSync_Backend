# File: scripts/create_admin.py

import sys
import os
import logging
from pathlib import Path

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.schemas.user import UserCreate
from app.services.user_service import UserService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init() -> None:
    """
    Initialize admin user if it doesn't exist.

    Uses environment variables for email and password or defaults.
    """
    # Import settings after sys.path has been modified
    from app.core.config import settings

    admin_email = os.getenv("HIDESYNC_ADMIN_EMAIL", settings.FIRST_SUPERUSER)
    admin_password = os.getenv("HIDESYNC_ADMIN_PASSWORD", settings.FIRST_SUPERUSER_PASSWORD)
    admin_username = os.getenv("HIDESYNC_ADMIN_USERNAME", settings.FIRST_SUPERUSER_USERNAME)

    db = SessionLocal()
    try:
        user_service = UserService(db)

        # Check if admin exists
        user = user_service.get_by_email(email=admin_email)
        if not user:
            logger.info(f"Creating admin user with email: {admin_email}")

            user_in = UserCreate(
                email=admin_email,
                username=admin_username,
                password=admin_password,
                full_name=settings.FIRST_SUPERUSER_FULLNAME,
                is_superuser=True,
            )

            try:
                user = user_service.create_user(obj_in=user_in)
                logger.info(f"Admin user created successfully with ID: {user.id}")
            except Exception as e:
                logger.error(f"Failed to create admin user: {str(e)}")
        else:
            logger.info(f"Admin user already exists with email: {admin_email}")
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Creating admin user")
    init()
    logger.info("Admin user creation script completed")