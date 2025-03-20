# File: app/db/init_db.py
"""
Database initialization script.

This script initializes the database, creates tables, and sets up
initial data like the admin user.
"""

import logging
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.services.user_service import UserService
from app.schemas.user import UserCreate
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init(db: Session) -> None:
    """
    Initialize database with tables and initial data.

    Args:
        db: SQLAlchemy database session
    """
    # Create tables
    init_db()

    # Create initial admin user if needed
    user_service = UserService(db)
    admin_email = settings.FIRST_SUPERUSER

    # Check if admin exists
    admin = user_service.get_by_email(email=admin_email)
    if not admin:
        logger.info(f"Creating initial admin user: {admin_email}")

        admin_in = UserCreate(
            email=admin_email,
            username=settings.FIRST_SUPERUSER_USERNAME,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            full_name=settings.FIRST_SUPERUSER_FULLNAME,
            is_superuser=True,
        )

        try:
            user = user_service.create_user(obj_in=admin_in)
            logger.info(f"Admin user created with ID: {user.id}")
        except Exception as e:
            logger.error(f"Error creating admin user: {str(e)}")
    else:
        logger.info(f"Admin user already exists: {admin_email}")


def main() -> None:
    """Run database initialization."""
    logger.info("Creating initial data")
    db = SessionLocal()
    try:
        init(db)
    finally:
        db.close()
    logger.info("Initial data created")


if __name__ == "__main__":
    main()