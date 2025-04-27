# scripts/register_material_settings.py

import sys
import os
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session

from app.db.session import engine, SessionLocal
from app.services.settings_service import SettingsService
from app.settings.material_settings import get_material_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def register_settings():
    """Register material settings into the database."""
    # Create a database session
    db = SessionLocal()

    try:
        logger.info("Initializing settings service...")
        settings_service = SettingsService(db)

        logger.info("Getting material settings...")
        settings_definitions = get_material_settings()

        logger.info(f"Found {len(settings_definitions)} material settings to register")

        # Register settings
        result = settings_service.register_settings(settings_definitions)

        logger.info(f"Successfully registered {len(result)} material settings")

    except Exception as e:
        logger.error(f"Error registering material settings: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Starting material settings registration...")
    register_settings()
    logger.info("Material settings registration complete")