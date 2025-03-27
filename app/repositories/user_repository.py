# app/repositories/user_repository.py
"""
Repository implementation for users in HideSync.

This module provides data access for users via the repository pattern.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
import logging

from app.repositories.base_repository import BaseRepository
from app.db.models.user import User

# Set up logger properly at module level
logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User]):
    """Repository for user entities."""

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the UserRepository.

        Args:
            session: SQLAlchemy database session
            encryption_service: Optional service for field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = User

    def get_by_email(self, email: str):
        """Get a user by email using direct SQLCipher access with multiple parameter combinations"""
        import os
        import logging
        from app.db.session import EncryptionManager, db_path
        from app.core.config import settings
        from app.db.models.user import User

        logger = logging.getLogger(__name__)

        try:
            # Read key directly from file
            key_file_path = os.path.abspath(settings.KEY_FILE_PATH)
            logger.info(f"Reading encryption key directly from file: {key_file_path}")

            with open(key_file_path, "r", encoding="utf-8") as f:
                key = f.read().strip()

            logger.info(f"Key read from file, length: {len(key)}")

            # Use SQLCipher directly
            sqlcipher = EncryptionManager.get_sqlcipher_module()
            conn = sqlcipher.connect(db_path)
            cursor = conn.cursor()

            # Try multiple parameter combinations
            approaches = [
                # Approach 1: Standard SQLCipher 4
                {"name": "Standard SQLCipher 4", "params": [
                    f"PRAGMA key='{key}';",
                    "PRAGMA foreign_keys=ON;"
                ]},

                # Approach 2: SQLCipher 3 compatibility
                {"name": "SQLCipher 3 compatibility", "params": [
                    f"PRAGMA key='{key}';",
                    "PRAGMA cipher_compatibility=3;",
                    "PRAGMA foreign_keys=ON;"
                ]},

                # Approach 3: Legacy mode with different kdf_iter
                {"name": "Legacy mode with kdf_iter=64000", "params": [
                    f"PRAGMA key='{key}';",
                    "PRAGMA cipher_compatibility=3;",
                    "PRAGMA kdf_iter=64000;",
                    "PRAGMA foreign_keys=ON;"
                ]},

                # Approach 4: Try with key formatting differences
                {"name": "Hex key format", "params": [
                    f"PRAGMA key=\"x'{key}'\";",
                    "PRAGMA foreign_keys=ON;"
                ]},

                # Approach 5: From your setup_db.py script
                {"name": "Setup script params", "params": [
                    f"PRAGMA key='{key}';",
                    "PRAGMA cipher_page_size=4096;",
                    "PRAGMA kdf_iter=64000;",
                    "PRAGMA cipher_hmac_algorithm=HMAC_SHA512;",
                    "PRAGMA cipher_kdf_algorithm=PBKDF2_HMAC_SHA512;",
                    "PRAGMA foreign_keys=ON;"
                ]}
            ]

            for approach in approaches:
                try:
                    logger.info(f"Trying approach: {approach['name']}")

                    # Create a fresh connection for each approach
                    if 'cursor' in locals() and cursor:
                        cursor.close()
                    if 'conn' in locals() and conn:
                        conn.close()

                    conn = sqlcipher.connect(db_path)
                    cursor = conn.cursor()

                    # Apply SQLCipher parameters
                    for param in approach['params']:
                        cursor.execute(param)

                    # Test connection
                    cursor.execute("SELECT count(*) FROM sqlite_master;")
                    table_count = cursor.fetchone()[0]
                    logger.info(
                        f"✓ Successfully connected with approach '{approach['name']}', found {table_count} tables")

                    # Query for the user
                    query = """
                    SELECT id, email, username, hashed_password, full_name, 
                           is_active, is_superuser, last_login, change_history, 
                           created_at, updated_at
                    FROM users 
                    WHERE email = ?
                    LIMIT 1
                    """
                    cursor.execute(query, (email,))
                    result = cursor.fetchone()

                    if not result:
                        logger.debug(f"No user found with email: {email}")
                        continue

                    # Create user object
                    user = User()

                    # Map columns
                    user.id = result[0]
                    user.email = result[1]
                    user.username = result[2]
                    user.hashed_password = result[3]
                    user.full_name = result[4]
                    user.is_active = bool(result[5])
                    user.is_superuser = bool(result[6])
                    user.last_login = result[7]
                    user.change_history = result[8]
                    user.created_at = result[9]
                    user.updated_at = result[10]

                    cursor.close()
                    conn.close()
                    return user

                except Exception as e:
                    logger.error(f"✗ Approach '{approach['name']}' failed: {e}")
                    # Continue to next approach

            # If we get here, all approaches failed
            if 'cursor' in locals() and cursor:
                cursor.close()
            if 'conn' in locals() and conn:
                conn.close()

            logger.error("All SQLCipher access approaches failed")
            # Try the standard ORM approach as a last resort
            return self.session.query(self.model).filter(self.model.email == email).first()

        except Exception as e:
            logger.error(f"Error in direct SQLCipher access: {e}")
            # Fall back to standard ORM approach
            return self.session.query(self.model).filter(self.model.email == email).first()

    def get_by_username(self, username: str) -> Optional[User]:
        """
        Get a user by username.

        Args:
            username: Username to search for

        Returns:
            User if found, None otherwise
        """
        return (
            self.session.query(self.model)
            .filter(self.model.username == username)
            .first()
        )

    def list_users(self, skip: int = 0, limit: int = 100, **filters) -> List[User]:
        """
        List users with filters.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            **filters: Additional filter criteria (is_active, is_superuser, etc.)

        Returns:
            List of matching users
        """
        query = self.session.query(self.model)

        # Apply standard filters
        for key, value in filters.items():
            if hasattr(self.model, key) and key not in ["search", "email", "role_id"]:
                query = query.filter(getattr(self.model, key) == value)

        # Search filter
        if "search" in filters and filters["search"]:
            search = f"%{filters['search']}%"
            query = query.filter(
                or_(
                    self.model.full_name.ilike(search),
                    self.model.email.ilike(search),
                    self.model.username.ilike(search),
                )
            )

        # Email filter with partial match
        if "email" in filters and filters["email"]:
            query = query.filter(self.model.email.ilike(f"%{filters['email']}%"))

        # Role filter
        if "role_id" in filters and filters["role_id"]:
            # This requires the user_role association table to be imported
            from app.db.models.role import user_role

            query = query.join(user_role, user_role.c.user_id == self.model.id).filter(
                user_role.c.role_id == filters["role_id"]
            )

        # Apply pagination and ordering
        query = query.order_by(self.model.id)
        query = query.offset(skip).limit(limit)

        return query.all()