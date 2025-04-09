# File: app/repositories/user_repository.py
"""
Repository implementation for users in HideSync.

This module provides data access for users via the repository pattern.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
import logging
import os # Import os
import sqlalchemy.exc # Import sqlalchemy exceptions

from app.repositories.base_repository import BaseRepository
from app.db.models.user import User
from app.db.session import EncryptionManager, db_path # Import db_path
from app.core.config import settings # Import settings

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

    def get_by_email(self, email: str) -> Optional[User]:
        """Get a user by email using direct SQLCipher access with multiple parameter combinations"""
        # --- This method remains largely the same as provided, using direct access ---
        logger.info(f"Attempting direct SQLCipher lookup for email: {email}")
        try:
            key_file_path = os.path.abspath(settings.KEY_FILE_PATH)
            logger.info(f"Reading encryption key directly from file: {key_file_path}")
            with open(key_file_path, "r", encoding="utf-8") as f: key = f.read().strip()
            logger.info(f"Key read from file, length: {len(key)}")

            sqlcipher = EncryptionManager.get_sqlcipher_module()
            conn = None
            cursor = None

            # Use the Hex key format approach first as it worked before
            approaches = [
                {"name": "Hex key format", "params": [f"PRAGMA key=\"x'{key}'\";", "PRAGMA foreign_keys=ON;"]},
                {"name": "Standard SQLCipher 4", "params": [f"PRAGMA key='{key}';", "PRAGMA foreign_keys=ON;"]},
                # Add other approaches back if needed for testing
            ]

            for approach in approaches:
                try:
                    logger.info(f"Trying approach: {approach['name']}")
                    if cursor: cursor.close()
                    if conn: conn.close()
                    conn = sqlcipher.connect(db_path)
                    cursor = conn.cursor()
                    for param in approach["params"]: cursor.execute(param)
                    cursor.execute("SELECT count(*) FROM sqlite_master;")
                    table_count = cursor.fetchone()[0]
                    logger.info(f"✓ Connected with approach '{approach['name']}', tables: {table_count}")

                    query = "SELECT id, email, username, hashed_password, full_name, is_active, is_superuser, last_login, change_history, created_at, updated_at FROM users WHERE email = ? LIMIT 1"
                    cursor.execute(query, (email,))
                    result = cursor.fetchone()

                    if result:
                        # Manually create and map User object - THIS CAN FAIL if mappers aren't configured
                        try:
                            user = User() # This instantiation might trigger mapper configuration
                            user.id = result[0]; user.email = result[1]; user.username = result[2]; user.hashed_password = result[3]; user.full_name = result[4]; user.is_active = bool(result[5]); user.is_superuser = bool(result[6]); user.last_login = result[7]; user.change_history = result[8]; user.created_at = result[9]; user.updated_at = result[10]
                            logger.info(f"Found user via direct SQL: {user.email}")
                            return user
                        except sqlalchemy.exc.InvalidRequestError as mapper_exc:
                             # Log the specific mapper error if object creation fails
                             logger.error(f"Mapper error creating User object after direct SQL query: {mapper_exc}", exc_info=True)
                             # Fallback to ORM might be needed here, or re-raise specific exception
                             break # Break approach loop if object mapping fails, try ORM below
                        finally:
                             if cursor: cursor.close()
                             if conn: conn.close()
                    else:
                        logger.debug(f"No user found with email {email} using approach '{approach['name']}'")

                except Exception as e:
                    logger.warning(f"✗ Approach '{approach['name']}' failed: {e}")
                    if cursor: cursor.close()
                    if conn: conn.close()
                    conn, cursor = None, None # Reset for next loop

            # If direct access failed or mapper failed, try ORM
            logger.warning(f"Direct SQLCipher access failed for email {email}, falling back to ORM.")
            return self.session.query(self.model).filter(self.model.email == email).first()

        except Exception as e:
            logger.error(f"General error in get_by_email: {e}", exc_info=True)
            # Final fallback to ORM
            try:
                 return self.session.query(self.model).filter(self.model.email == email).first()
            except Exception as orm_e:
                 logger.error(f"ORM fallback in get_by_email also failed: {orm_e}", exc_info=True)
                 return None
        finally:
             # Ensure connection/cursor are closed if they exist from the last attempt
             if 'cursor' in locals() and cursor: cursor.close()
             if 'conn' in locals() and conn: conn.close()


    def get_by_id(self, id: int) -> Optional[User]:
        """
        Get a user by ID. Prefers ORM, falls back to direct SQL if needed (e.g., during startup).
        """
        logger.debug(f"UserRepository: Getting user by ID {id}")
        try:
            # --- FIX: Use correct superclass method name ---
            user = super().get_by_id(id)
            if user:
                logger.debug(f"UserRepository: Found user by ID {id} via ORM.")
                # Decryption handled by BaseRepository if configured
                return user
            else:
                logger.debug(f"UserRepository: User ID {id} not found via ORM.")
                return None
        except sqlalchemy.exc.InvalidRequestError as mapper_exc:
             # This might happen during startup before mappers are fully configured
             logger.warning(f"ORM failed for get_by_id({id}) due to mapper error: {mapper_exc}. Falling back to direct SQL.")
             # Fallback to direct SQL only if ORM fails due to mapper issues
             return self._direct_sql_get_by_id(id)
        except Exception as e:
            logger.error(f"Error retrieving user by ID {id} via ORM: {e}", exc_info=True)
            # Optionally try direct SQL as a last resort for other errors? Less ideal.
            # return self._direct_sql_get_by_id(id)
            raise # Re-raise other ORM errors


    def _direct_sql_get_by_id(self, id: int) -> Optional[User]:
        """Direct SQLCipher access for get_by_id, used as fallback."""
        logger.warning(f"Attempting direct SQLCipher fallback for user ID: {id}")
        try:
            key_file_path = os.path.abspath(settings.KEY_FILE_PATH)
            with open(key_file_path, "r", encoding="utf-8") as f: key = f.read().strip()

            sqlcipher = EncryptionManager.get_sqlcipher_module()
            conn = sqlcipher.connect(db_path)
            cursor = conn.cursor()

            # Use the Hex key format approach
            cursor.execute(f"PRAGMA key=\"x'{key}'\";")
            cursor.execute("PRAGMA foreign_keys=ON;")

            query = "SELECT id, email, username, hashed_password, full_name, is_active, is_superuser, last_login, change_history, created_at, updated_at FROM users WHERE id = ? LIMIT 1"
            cursor.execute(query, (id,))
            result = cursor.fetchone()

            if result:
                try:
                    # Manually create user object - might still fail if dependent mappers error
                    user = User()
                    user.id = result[0]; user.email = result[1]; user.username = result[2]; user.hashed_password = result[3]; user.full_name = result[4]; user.is_active = bool(result[5]); user.is_superuser = bool(result[6]); user.last_login = result[7]; user.change_history = result[8]; user.created_at = result[9]; user.updated_at = result[10]
                    logger.info(f"Found user via direct SQL fallback: {user.email}")
                    return user
                except sqlalchemy.exc.InvalidRequestError as mapper_exc:
                     logger.error(f"Mapper error creating User object during direct SQL fallback: {mapper_exc}", exc_info=True)
                     return None # Cannot proceed if object creation fails
            else:
                logger.warning(f"User ID {id} not found via direct SQL fallback.")
                return None

        except Exception as e:
            logger.error(f"Error in direct SQLCipher fallback for get_by_id({id}): {e}", exc_info=True)
            return None
        finally:
            if 'cursor' in locals() and cursor: cursor.close()
            if 'conn' in locals() and conn: conn.close()

    # ... (get_by_username, list_users remain the same) ...
    def get_by_username(self, username: str) -> Optional[User]:
        return (self.session.query(self.model).filter(self.model.username == username).first())

    def list_users(self, skip: int = 0, limit: int = 100, **filters) -> List[User]:
        query = self.session.query(self.model)
        for key, value in filters.items():
            if hasattr(self.model, key) and key not in ["search", "email", "role_id"]:
                query = query.filter(getattr(self.model, key) == value)
        if "search" in filters and filters["search"]:
            search = f"%{filters['search']}%"
            query = query.filter(or_(self.model.full_name.ilike(search), self.model.email.ilike(search), self.model.username.ilike(search)))
        if "email" in filters and filters["email"]:
            query = query.filter(self.model.email.ilike(f"%{filters['email']}%"))
        if "role_id" in filters and filters["role_id"]:
            from app.db.models.associations import user_role # Import locally if needed
            query = query.join(user_role, user_role.c.user_id == self.model.id).filter(user_role.c.role_id == filters["role_id"])
        query = query.order_by(self.model.id).offset(skip).limit(limit)
        return query.all()