# File: app/repositories/user_repository.py
"""
Repository implementation for users in HideSync.

This module provides data access for users via the repository pattern,
inheriting common CRUD operations from BaseRepository and adding
user-specific methods and direct SQLCipher access attempts.
"""

import logging
import os
from typing import List, Optional, Dict, Any, Tuple

import sqlalchemy.exc  # Import sqlalchemy exceptions
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings  # Import settings
from app.db.models.user import User
# Import db_path and EncryptionManager for direct access
from app.db.session import EncryptionManager, db_path
from app.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User]):
    """
    Repository for user entities, extending BaseRepository with user-specific methods
    and direct SQLCipher access capabilities.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the UserRepository.

        Args:
            session: SQLAlchemy database session
            encryption_service: Optional service for field encryption/decryption
        """
        # Initialize the BaseRepository with the User model
        super().__init__(session=session, model=User, encryption_service=encryption_service)
        # Attribute for lazy loading sqlcipher module for direct access
        self._sqlcipher_module = None
        logger.info(f"UserRepository initialized. Encryption service {'provided' if encryption_service else 'not provided'}.")

    # --- Direct SQLCipher Access Helper Methods ---

    def _get_sqlcipher_module(self):
        """Lazy load the SQLCipher module."""
        if self._sqlcipher_module is None:
            self._sqlcipher_module = EncryptionManager.get_sqlcipher_module()
        return self._sqlcipher_module

    def _try_direct_sql_connection(self, key: str) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
        """
        Attempts to connect to the SQLCipher database using various PRAGMA combinations.

        Args:
            key: The database encryption key (as read from the file).

        Returns:
            A tuple containing (connection, cursor, successful_approach_name) if successful,
            otherwise (None, None, None).
        """
        sqlcipher = self._get_sqlcipher_module()
        if not sqlcipher:
            logger.error("SQLCipher module could not be loaded for direct access.")
            return None, None, None

        # Define connection approaches (V3 and V4, Hex and Passphrase)
        approaches = [
             {"name": "SQLCipher 3 Hex key", "params": [f"PRAGMA key=\"x'{key}'\";", "PRAGMA cipher_compatibility = 3;", "PRAGMA foreign_keys=ON;"]},
             {"name": "SQLCipher 3 Passphrase", "params": [f"PRAGMA key='{key}';", "PRAGMA cipher_compatibility = 3;", "PRAGMA foreign_keys=ON;"]},
             {"name": "SQLCipher 4 Hex key", "params": [f"PRAGMA key=\"x'{key}'\";", "PRAGMA foreign_keys=ON;"]},
             {"name": "SQLCipher 4 Passphrase", "params": [f"PRAGMA key='{key}';", "PRAGMA foreign_keys=ON;"]},
        ]

        conn = None
        cursor = None

        for approach in approaches:
            try:
                logger.info(f"Trying direct connection approach: {approach['name']}")
                if cursor: cursor.close()
                if conn: conn.close()
                conn = sqlcipher.connect(db_path)
                cursor = conn.cursor()
                for param in approach["params"]:
                    logger.debug(f"Executing PRAGMA: {param.split('=')[0]}...")
                    cursor.execute(param)
                cursor.execute("SELECT count(*) FROM sqlite_master;")
                table_count = cursor.fetchone()[0]
                logger.info(f"✓ Successfully connected with approach '{approach['name']}'. Table count: {table_count}")
                return conn, cursor, approach['name']
            except Exception as e:
                logger.warning(f"✗ Approach '{approach['name']}' failed: {e}")
                if cursor: cursor.close()
                if conn: conn.close()
                conn, cursor = None, None
        logger.error("All direct SQLCipher connection approaches failed.")
        return None, None, None

    def _map_row_to_user(self, row: Tuple) -> Optional[User]:
        """Maps a raw SQL row tuple to a User object (without session attachment)."""
        if not row or len(row) < 11:
             return None
        try:
            user = User()
            user.id, user.email, user.username, user.hashed_password, user.full_name, \
            is_active, is_superuser, user.last_login, user.change_history, \
            user.created_at, user.updated_at = row[:11]
            user.is_active = bool(is_active)
            user.is_superuser = bool(is_superuser)
            # Note: This user object is NOT associated with the session
            return user
        except Exception as e:
            logger.error(f"Error mapping direct SQL row to User object: {e}", exc_info=True)
            return None

    def _direct_sql_get_by_id(self, id: int) -> Optional[User]:
        """Direct SQLCipher access for get_by_id, used ONLY as fallback for mapper errors."""
        logger.warning(f"Attempting direct SQLCipher fallback for user ID: {id}")
        conn, cursor = None, None
        try:
            key_file_path = os.path.abspath(settings.KEY_FILE_PATH)
            with open(key_file_path, "r", encoding="utf-8") as f: key = f.read().strip()
            conn, cursor, approach_name = self._try_direct_sql_connection(key)

            if conn and cursor:
                logger.info(f"Direct SQL fallback connection successful using '{approach_name}'. Querying for ID: {id}")
                query = "SELECT id, email, username, hashed_password, full_name, is_active, is_superuser, last_login, change_history, created_at, updated_at FROM users WHERE id = ? LIMIT 1"
                cursor.execute(query, (id,))
                result = cursor.fetchone()
                if result:
                    user = self._map_row_to_user(result)
                    if user:
                        logger.info(f"✓ Found user via direct SQL fallback: {user.email} (ID: {user.id})")
                        # Decrypt sensitive fields manually since this user isn't from session
                        return self._decrypt_sensitive_fields(user)
                    else:
                        logger.error("Direct SQL fallback query succeeded, but mapping row to User object failed.")
                        return None
                else:
                    logger.warning(f"User ID {id} not found via direct SQL fallback using approach '{approach_name}'.")
                    return None
            else:
                logger.error(f"Direct SQLCipher connection failed during fallback attempt for ID {id}.")
                return None
        except Exception as e:
            logger.error(f"Error during direct SQL fallback for get_by_id({id}): {e}", exc_info=True)
            return None
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # --- User-Specific Public Methods ---

    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get a user by email. Attempts direct SQLCipher access first for performance,
        then falls back to the standard ORM method.
        """
        logger.info(f"Attempting to find user by email: {email}")
        conn, cursor = None, None
        user = None
        try:
            # --- Attempt Direct SQL Access ---
            key_file_path = os.path.abspath(settings.KEY_FILE_PATH)
            logger.debug(f"Reading encryption key for direct access from: {key_file_path}")
            with open(key_file_path, "r", encoding="utf-8") as f: key = f.read().strip()
            logger.debug(f"Key read from file, length: {len(key)}")

            conn, cursor, approach_name = self._try_direct_sql_connection(key)

            if conn and cursor:
                logger.info(f"Direct SQL connection successful using '{approach_name}'. Querying for email: {email}")
                query = "SELECT id, email, username, hashed_password, full_name, is_active, is_superuser, last_login, change_history, created_at, updated_at FROM users WHERE email = ? LIMIT 1"
                cursor.execute(query, (email,))
                result = cursor.fetchone()
                if result:
                    mapped_user = self._map_row_to_user(result)
                    if mapped_user:
                        logger.info(f"✓ Found user via direct SQL: {mapped_user.email} (ID: {mapped_user.id})")
                        # Manually decrypt fields for the non-session object
                        user = self._decrypt_sensitive_fields(mapped_user)
                    else:
                        logger.warning("Direct SQL query succeeded, but mapping row to User object failed. Falling back to ORM.")
                else:
                    logger.debug(f"User with email {email} not found via direct SQL using approach '{approach_name}'.")
                    # Fall through to ORM lookup if not found via direct SQL

            else:
                logger.warning(f"Direct SQLCipher connection failed for email {email}. Falling back to ORM.")

        except Exception as e:
            logger.error(f"Unexpected error during direct SQL access attempt for email {email}: {e}", exc_info=True)
            logger.warning("Falling back to ORM due to unexpected error during direct access.")
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

        # --- Fallback or Primary ORM Lookup ---
        if user is None: # Only query ORM if direct access didn't find or failed
            logger.debug(f"Attempting ORM lookup for email: {email}")
            try:
                # Use session and model from BaseRepository
                orm_user = self.session.query(self.model).filter(self.model.email == email).first()
                if orm_user:
                    logger.info(f"✓ Found user via ORM: {orm_user.email} (ID: {orm_user.id})")
                    # Decrypt fields using the base repository method
                    user = self._decrypt_sensitive_fields(orm_user)
                else:
                    logger.info(f"User with email {email} not found via ORM either.")
            except Exception as orm_e:
                logger.error(f"ORM fallback lookup for email {email} also failed: {orm_e}", exc_info=True)
                # Return None if ORM fails too

        return user


    def get_by_id(self, id: int) -> Optional[User]:
        """
        Get a user by ID using the ORM. Falls back to direct SQL only if ORM fails
        due to specific mapper errors (e.g., during startup).
        """
        logger.debug(f"UserRepository: Getting user by ID {id} via ORM (BaseRepository)")
        try:
            # Use the standard ORM method from BaseRepository - it handles decryption
            user = super().get_by_id(id)
            if user:
                logger.debug(f"UserRepository: Found user by ID {id} via ORM.")
            else:
                logger.info(f"UserRepository: User ID {id} not found via ORM.")
            return user
        except sqlalchemy.exc.InvalidRequestError as mapper_exc:
             logger.warning(f"ORM failed for get_by_id({id}) due to mapper error: {mapper_exc}. Falling back to direct SQL.")
             # Fallback to direct SQL only if ORM fails due to mapper issues
             return self._direct_sql_get_by_id(id) # This helper method handles decryption
        except Exception as e:
            logger.error(f"Error retrieving user by ID {id} via ORM: {e}", exc_info=True)
            raise # Re-raise other unexpected ORM errors


    def get_by_username(self, username: str) -> Optional[User]:
        """Get a user by username using ORM."""
        logger.debug(f"Attempting ORM lookup for username: {username}")
        try:
            # Use session and model from BaseRepository
            user = self.session.query(self.model).filter(self.model.username == username).first()
            if user:
                logger.info(f"✓ Found user via ORM: {user.username} (ID: {user.id})")
                # Decrypt fields manually as this doesn't use a base method that auto-decrypts
                return self._decrypt_sensitive_fields(user)
            else:
                logger.info(f"User with username {username} not found via ORM.")
                return None
        except Exception as e:
            logger.error(f"Error retrieving user by username {username} via ORM: {e}", exc_info=True)
            raise # Re-raise unexpected ORM errors


    def list_users(self, skip: int = 0, limit: int = 100, **filters) -> List[User]:
        """
        List users using ORM with user-specific filtering capabilities.
        Overrides base 'list' if specific filtering/joining is needed.
        """
        logger.debug(f"Listing users with skip={skip}, limit={limit}, filters={filters}")
        try:
            # Use session and model from BaseRepository
            query = self.session.query(self.model)

            # --- Apply User-Specific Filters ---
            search_term = filters.pop("search", None)
            email_term = filters.pop("email", None)
            role_id = filters.pop("role_id", None)

            # Apply remaining generic filters (passed directly to **filters)
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)

            # Apply special search filter across multiple fields
            if search_term:
                search_pattern = f"%{search_term}%"
                logger.debug(f"Applying search filter: {search_pattern}")
                query = query.filter(
                    or_(
                        self.model.full_name.ilike(search_pattern),
                        self.model.email.ilike(search_pattern),
                        self.model.username.ilike(search_pattern)
                    )
                )

            # Apply email filter
            if email_term:
                email_pattern = f"%{email_term}%"
                logger.debug(f"Applying email filter: {email_pattern}")
                query = query.filter(self.model.email.ilike(email_pattern))

            # Apply role filter (requires join)
            if role_id:
                logger.debug(f"Applying role_id filter: {role_id}")
                # Import locally to potentially avoid circular dependency issues
                from app.db.models.associations import user_role
                query = query.join(user_role, user_role.c.user_id == self.model.id).filter(user_role.c.role_id == role_id)

            # Apply ordering, offset, and limit
            query = query.order_by(self.model.id).offset(skip).limit(limit)

            logger.debug("Executing list_users ORM query.")
            users = query.all()
            logger.info(f"Retrieved {len(users)} users via custom list_users method.")

            # Decrypt sensitive fields for each user retrieved
            return [self._decrypt_sensitive_fields(user) for user in users]

        except Exception as e:
            logger.error(f"Error listing users: {e}", exc_info=True)
            return [] # Return empty list on error


    # create, update, delete are inherited from BaseRepository
    # Override them here only if user-specific logic is needed before/after calling super()