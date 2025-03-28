# app/services/user_service.py
"""
User service for HideSync.

This module provides functionality for user management,
authentication, and authorization.
"""

from typing import Optional, List, Dict, Any, Type
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import secrets
import logging # Added for logging

from jose import jwt, JWTError
from pydantic import EmailStr, ValidationError # Assuming EmailStr might be used

from app import schemas # Import top-level schemas
from app.services.base_service import BaseService
from app.db.models.user import User
from app.db.models.password_reset import PasswordResetToken
from app.repositories.user_repository import UserRepository
from app.repositories.password_reset_repository import PasswordResetRepository
from app.core.exceptions import (
    EntityNotFoundException,
    AuthenticationException,
    BusinessRuleException,
    DuplicateEntityException, # Assuming this might be needed for create
)
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    ALGORITHM, # Import ALGORITHM
)
from app.core.config import settings

# Setup logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO) # Configure basic logging for visibility


class UserService(BaseService[User]):
    """
    Service layer for managing Users.
    Handles business logic related to users, authentication, password resets etc.
    """

    # Explicitly declare the repository type for clarity and type checking
    repository: UserRepository

    def __init__(
            self,
            session: Session,
            repository: Optional[UserRepository] = None, # Type hint repository
            password_reset_repository: Optional[PasswordResetRepository] = None, # Type hint
            security_context=None, # Add type hint if available e.g. SecurityContext
            event_bus=None, # Add type hint if available e.g. EventBus
            cache_service=None, # Add type hint if available e.g. CacheService
            email_service=None, # Add type hint if available e.g. EmailService
    ):
        """Initialize the UserService with dependencies."""
        # Determine the repository class to pass to the parent
        # BaseService likely expects the class, not an instance, to initialize its own repo
        repo_class: Type[UserRepository] = UserRepository

        # Call parent class init. BaseService should initialize self.repository
        super().__init__(
            session=session,
            repository_class=repo_class, # Pass the class
            security_context=security_context,
            event_bus=event_bus,
            cache_service=cache_service,
        )

        # If a specific repository instance was provided externally,
        # override the one potentially created by BaseService.
        # This depends on how BaseService is implemented. If BaseService
        # already uses the passed instance, this isn't needed.
        if repository is not None:
             self.repository = repository
             logger.debug("UserService initialized with provided UserRepository instance.")
        else:
             logger.debug(f"UserService initialized, using repository type: {type(self.repository)}")


        # Ensure self.repository is an instance of UserRepository after super().__init__
        # This check is important if BaseService logic is complex.
        if not isinstance(self.repository, UserRepository):
             logger.error(f"UserService repository is not an instance of UserRepository: {type(self.repository)}")
             # If BaseService failed to set it correctly, fallback or raise error
             # self.repository = UserRepository(session) # Fallback
             raise TypeError("UserService requires a UserRepository instance.")

        # Initialize other specific repositories and services
        self.password_reset_repository = (
                password_reset_repository or PasswordResetRepository(session)
        )
        self.email_service = email_service
        logger.info("UserService initialized.")
    # --- End of __init__ ---

    # --- Basic CRUD Methods (assuming BaseService might provide some) ---

    def create_user(self, user_in: schemas.UserCreate) -> User:
        """
        Creates a new user, hashing the password.

        Args:
            user_in: User creation schema containing user details and plain password.

        Returns:
            The created User object.

        Raises:
            DuplicateEntityException: If a user with the same email already exists.
            BusinessRuleException: If password requirements are not met.
        """
        logger.info(f"Attempting to create user with email: {user_in.email}")
        # Check if user already exists
        existing_user = self.get_by_email(user_in.email)
        if existing_user:
            logger.warning(f"Attempted to create duplicate user: {user_in.email}")
            raise DuplicateEntityException(
                "User with this email already exists",
                details={"email": user_in.email}
            )

        # Validate password strength (example)
        if len(user_in.password) < settings.MIN_PASSWORD_LENGTH:
             raise BusinessRuleException(f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters long")

        # Hash the password
        hashed_password = get_password_hash(user_in.password)

        # Prepare user data for repository (excluding plain password)
        user_data = user_in.model_dump(exclude={"password", "role", "phone"})
        user_data["hashed_password"] = hashed_password
        user_data["is_active"] = True # Default to active, adjust as needed

        # Use the repository to create the user in the database
        # Assuming BaseService.create or repository.create handles the DB interaction
        try:
            # If BaseService has create:
            # created_user = super().create(obj_in=user_data) # Pass dict if BaseService expects it

            # If calling repository directly:
            created_user = self.repository.create(data=user_data)# Pass dict or model? Check repo

            logger.info(f"Successfully created user {created_user.email} (ID: {created_user.id})")
            # Optionally publish an event
            # if self.event_bus:
            #     self.event_bus.publish("user_created", user_id=created_user.id)
            return created_user
        except Exception as e:
            logger.error(f"Error creating user {user_in.email}: {e}", exc_info=True)
            # Re-raise or handle as appropriate
            raise RuntimeError(f"Could not create user {user_in.email}") from e

    def update_user(self, user_id: int, user_in: schemas.UserUpdate) -> Optional[User]:
        """
        Updates an existing user. Handles password update separately if included.

        Args:
            user_id: The ID of the user to update.
            user_in: User update schema containing fields to update.

        Returns:
            The updated User object or None if not found.

        Raises:
            EntityNotFoundException: If the user does not exist.
            BusinessRuleException: If password requirements are not met (if password is updated).
        """
        logger.info(f"Attempting to update user ID: {user_id}")
        # Use BaseService's update or repository's update
        # Need to handle password hashing if password is part of UserUpdate
        update_data = user_in.model_dump(exclude_unset=True) # Get only provided fields

        # Handle password update specifically
        new_password = update_data.pop("password", None)
        if new_password:
             logger.info(f"Updating password for user ID: {user_id}")
             if len(new_password) < settings.MIN_PASSWORD_LENGTH:
                 raise BusinessRuleException(f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters long")
             update_data["hashed_password"] = get_password_hash(new_password)

        try:
            # If BaseService has update:
            # updated_user = super().update(db_obj_id=user_id, obj_in=update_data)

            # If calling repository directly:
            updated_user = self.repository.update(db_obj_id=user_id, obj_in=update_data)

            if updated_user:
                logger.info(f"Successfully updated user ID: {user_id}")
                # Optionally publish event
                # if self.event_bus:
                #     self.event_bus.publish("user_updated", user_id=user_id, changes=list(update_data.keys()))
            else:
                 # This case implies the update method returned None or 0, maybe user not found
                 logger.warning(f"User ID: {user_id} not found during update attempt.")
                 # BaseService/Repository should ideally raise NotFound, but handle if it returns None
                 raise EntityNotFoundException("User", user_id)

            return updated_user
        except EntityNotFoundException:
             # Re-raise if caught from repository/base
             raise
        except Exception as e:
            logger.error(f"Error updating user ID {user_id}: {e}", exc_info=True)
            raise RuntimeError(f"Could not update user {user_id}") from e

    def get_user(self, user_id: int) -> Optional[User]:
        """Gets a single user by ID."""
        logger.debug(f"Getting user by ID: {user_id}")
        # Use BaseService or repository method
        # return super().get(db_obj_id=user_id)
        return self.repository.get_by_id(user_id) # Assuming repo has get_by_id

    def get_all_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Gets a list of users."""
        logger.debug(f"Getting all users with skip={skip}, limit={limit}")
        # Use BaseService or repository method
        # return super().get_multi(skip=skip, limit=limit)
        return self.repository.get_all(skip=skip, limit=limit) # Assuming repo has get_all

    def delete_user(self, user_id: int) -> Optional[User]:
        """
        Deletes a user by ID.

        Args:
            user_id: The ID of the user to delete.

        Returns:
            The deleted User object or None if not found.

        Raises:
            EntityNotFoundException: If the user does not exist.
        """
        logger.info(f"Attempting to delete user ID: {user_id}")
        try:
            # Use BaseService or repository method
            # deleted_user = super().remove(db_obj_id=user_id)

            # If calling repository directly:
            deleted_user = self.repository.delete(db_obj_id=user_id)

            if deleted_user:
                logger.info(f"Successfully deleted user ID: {user_id}")
                # Optionally publish event
                # if self.event_bus:
                #     self.event_bus.publish("user_deleted", user_id=user_id)
            else:
                 # This case implies the delete method returned None or 0, maybe user not found
                 logger.warning(f"User ID: {user_id} not found during delete attempt.")
                 raise EntityNotFoundException("User", user_id)

            return deleted_user
        except EntityNotFoundException:
             raise # Re-raise if caught from repository/base
        except Exception as e:
            logger.error(f"Error deleting user ID {user_id}: {e}", exc_info=True)
            raise RuntimeError(f"Could not delete user {user_id}") from e

    # --- Authentication & Password Management Methods ---

    def get_by_email(self, email: str) -> Optional[User]:
        """
        Retrieves a user by their email address.

        Args:
            email: The email address of the user to retrieve.

        Returns:
            The User object if found, otherwise None.
        """
        logger.debug(f"Attempting to retrieve user by email: {email}")
        # Ensure self.repository is correctly initialized and has the method
        if not hasattr(self, 'repository') or not hasattr(self.repository, 'get_by_email'):
             logger.error("UserRepository or get_by_email method not available in UserService.")
             raise RuntimeError("UserService is not configured correctly with UserRepository.")

        try:
            user = self.repository.get_by_email(email=email)
            if not user:
                logger.debug(f"User with email {email} not found in service layer.")
            else:
                logger.debug(f"User found with email {email}: ID {user.id}")
            return user
        except Exception as e:
            logger.error(f"Error retrieving user by email {email}: {e}", exc_info=True)
            return None # Or raise e

    def request_password_reset(self, email: str) -> bool:
        """
        Request a password reset for a user. Generates a token and sends email.

        Args:
            email: User email address

        Returns:
            True if request was processed (for security, always true unless internal error).
        """
        # Find the user by email using the service method
        user = self.get_by_email(email)

        # Don't reveal if user exists or not for security
        if not user:
            logger.info(f"Password reset requested for non-existent or unfound email: {email}")
            return True # Still return True for security

        logger.info(f"Processing password reset request for user: {user.id}")
        try:
            with self.transaction():
                # Invalidate any existing tokens for this user
                self.password_reset_repository.invalidate_all_for_user(user.id)

                # Create a new reset token
                token = self.password_reset_repository.create_for_user(user.id)

                # Send email with reset link
                if self.email_service and hasattr(self.email_service, 'send_password_reset_email'):
                    reset_url = (
                        f"{settings.FRONTEND_URL}/reset-password?token={token.token}"
                    )
                    try:
                        # Assuming email service method signature
                        self.email_service.send_password_reset_email(
                            recipient_email=user.email,
                            user_name=user.full_name or user.email, # Use name or fallback
                            reset_url=reset_url
                        )
                        logger.info(f"Password reset email initiated for {user.email}")
                    except Exception as e_email:
                        logger.error(f"Failed to send password reset email to {user.email}: {e_email}", exc_info=True)
                        # Consider how to handle email failures (e.g., background retry queue)
                elif not self.email_service:
                    logger.warning("Email service not configured. Cannot send password reset email.")
                else:
                     logger.warning("Email service is configured but missing 'send_password_reset_email' method.")


                return True
        except Exception as e_trans:
             logger.error(f"Error during password reset transaction for user {user.id}: {e_trans}", exc_info=True)
             return False # Indicate failure if transaction fails

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate a user with email and password.

        Args:
            email: User email address
            password: Plain text password

        Returns:
            User object if authentication successful, None otherwise.
        """
        logger.debug(f"Authenticating user with email: {email}")
        user = self.get_by_email(email) # Use the service method

        if not user:
            logger.info(f"Authentication failed: No user found with email: {email}")
            return None

        logger.debug(f"User found for authentication: ID={user.id}, email={user.email}")

        if not user.is_active:
            logger.warning(f"Authentication failed: User {user.email} is inactive")
            # Consider raising AuthenticationException("Inactive user")
            return None

        try:
            password_valid = verify_password(password, user.hashed_password)
            logger.debug(f"Password verification result for user {user.id}: {password_valid}")
        except Exception as e_verify:
             logger.error(f"Error verifying password for user {user.id}: {e_verify}", exc_info=True)
             return None # Treat verification error as failure

        if not password_valid:
            logger.warning(f"Authentication failed: Invalid password attempt for user {user.email}")
            return None

        # Update last login timestamp
        try:
            with self.transaction():
                user.last_login = datetime.utcnow()
            logger.info(f"Authentication successful for user {user.email} (ID={user.id})")
        except Exception as e_update:
            logger.error(f"Failed to update last_login for user {user.id}: {e_update}", exc_info=True)
            # Authentication succeeded, but log the update failure.

        return user

    def validate_reset_token(self, token_str: str) -> Optional[User]:
        """
        Validate a password reset token string.

        Args:
            token_str: The password reset token string.

        Returns:
            The associated User object if the token is valid and exists, otherwise None.
        """
        logger.debug(f"Validating password reset token: {token_str[:10]}...")
        try:
            token = self.password_reset_repository.get_by_token(token_str)

            if not token or not token.is_valid:
                logger.warning(f"Invalid or expired password reset token used: {token_str[:10]}...")
                return None

            # Get user using the service method get_by_id for consistency
            user = self.get_by_id(token.user_id)
            if not user:
                 logger.error(f"User {token.user_id} not found for valid reset token {token.id}")
                 return None

            logger.debug(f"Password reset token validated successfully for user {user.id}")
            return user
        except Exception as e:
             logger.error(f"Error validating reset token {token_str[:10]}...: {e}", exc_info=True)
             return None

    def reset_password(self, token_str: str, new_password: str) -> User:
        """
        Reset a user's password using a valid token.

        Args:
            token_str: Password reset token string.
            new_password: New plain text password.

        Returns:
            The updated User object.

        Raises:
            AuthenticationException: If token is invalid or expired.
            BusinessRuleException: If password doesn't meet requirements or is same as old.
            EntityNotFoundException: If user associated with token not found.
            RuntimeError: If database update fails or unexpected error occurs.
        """
        logger.info(f"Attempting password reset with token: {token_str[:10]}...")
        try:
            with self.transaction():
                # Validate token and get user in one go
                user = self.validate_reset_token(token_str)
                if not user:
                     # Logging done in validate_reset_token
                     raise AuthenticationException("Invalid or expired password reset token")

                # Get the token object again to mark as used (or modify validate_reset_token to return it too)
                token = self.password_reset_repository.get_by_token(token_str)
                if not token: # Should not happen if user was found, but safety check
                     raise AuthenticationException("Reset token disappeared unexpectedly.")


                # Validate password strength
                if len(new_password) < settings.MIN_PASSWORD_LENGTH:
                    raise BusinessRuleException(
                        f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters long"
                    )

                # Check if new password is same as old
                if verify_password(new_password, user.hashed_password):
                    raise BusinessRuleException("New password cannot be the same as the old password.")

                # Update password
                hashed_password = get_password_hash(new_password)
                updated_count = self.repository.update(user.id, {"hashed_password": hashed_password})
                if updated_count == 0:
                     logger.error(f"Failed to update password for user {user.id} during reset (update count 0).")
                     raise RuntimeError(f"Failed to update password for user {user.id}")

                # Mark token as used
                self.password_reset_repository.mark_used(token.id)
                logger.info(f"Password successfully reset for user {user.id}")

                # Refresh user object to reflect changes before returning
                self.session.refresh(user)
                return user
        except (AuthenticationException, BusinessRuleException, EntityNotFoundException) as e_known:
             logger.warning(f"Known error during password reset for token {token_str[:10]}...: {e_known}")
             raise e_known
        except Exception as e_unknown:
             logger.error(f"Unexpected error during password reset for token {token_str[:10]}...: {e_unknown}", exc_info=True)
             raise RuntimeError("An unexpected error occurred during password reset.") from e_unknown

    def change_password(
        self, user_id: int, current_password: str, new_password: str
    ) -> bool:
        """
        Change a user's password when they know the current one.

        Args:
            user_id: User ID.
            current_password: Current plain text password.
            new_password: New plain text password.

        Returns:
            True if password was changed successfully.

        Raises:
            EntityNotFoundException: If user not found.
            AuthenticationException: If current password is incorrect.
            BusinessRuleException: If new password doesn't meet requirements or is same as current.
            RuntimeError: If database update fails or unexpected error occurs.
        """
        logger.info(f"Attempting password change for user {user_id}")
        try:
            with self.transaction():
                # Get user using service method
                user = self.get_by_id(user_id)
                if not user:
                    raise EntityNotFoundException("User", user_id)

                # Verify current password
                if not verify_password(current_password, user.hashed_password):
                    logger.warning(f"Incorrect current password provided for user {user_id}")
                    raise AuthenticationException("Incorrect current password")

                # Validate new password
                if len(new_password) < settings.MIN_PASSWORD_LENGTH:
                    raise BusinessRuleException(
                        f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters long"
                    )

                if current_password == new_password:
                    raise BusinessRuleException(
                        "New password must be different from current password"
                    )

                # Update password
                hashed_password = get_password_hash(new_password)
                updated_count = self.repository.update(user_id, {"hashed_password": hashed_password})
                if updated_count == 0:
                     logger.error(f"Failed to change password for user {user_id} (update count 0).")
                     raise RuntimeError(f"Failed to change password for user {user_id}")

                logger.info(f"Password successfully changed for user {user_id}")
                return True
        except (EntityNotFoundException, AuthenticationException, BusinessRuleException) as e_known:
             logger.warning(f"Known error during password change for user {user_id}: {e_known}")
             raise e_known
        except Exception as e_unknown:
             logger.error(f"Unexpected error during password change for user {user_id}: {e_unknown}", exc_info=True)
             raise RuntimeError("An unexpected error occurred during password change.") from e_unknown


    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an access token using a valid refresh token.

        Args:
            refresh_token: The refresh token string.

        Returns:
            A dictionary containing the new access token, refresh token, type, and expiry.

        Raises:
            AuthenticationException: If the refresh token is invalid, expired, or user is inactive.
        """
        logger.debug("Attempting token refresh")
        try:
            payload = jwt.decode(
                refresh_token, settings.SECRET_KEY, algorithms=[ALGORITHM]
            )
            user_id_str = payload.get("sub")
            if user_id_str is None:
                 raise jwt.JWTError("Refresh token missing 'sub' claim.")
            try:
                user_id = int(user_id_str)
            except (ValueError, TypeError):
                 raise jwt.JWTError("Refresh token 'sub' claim is not a valid ID.")

            # Optionally check token type if you add 'type': 'refresh' during creation
            # token_type = payload.get("type")
            # if token_type != "refresh":
            #    raise jwt.JWTError("Invalid token type provided for refresh.")

            token_data = schemas.TokenPayload(sub=user_id)
        except (jwt.JWTError, ValidationError) as e:
            logger.warning(f"Invalid refresh token provided: {e}")
            raise AuthenticationException("Invalid refresh token")

        # Get user using service method
        user = self.get_by_id(token_data.sub)
        if not user or not user.is_active:
            logger.warning(f"Refresh token used for inactive or non-existent user: {token_data.sub}")
            raise AuthenticationException("Invalid refresh token") # Keep generic for security

        # Create new tokens
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS) # Consider if refresh token should also be rotated

        access_token = create_access_token(subject=user.id, expires_delta=access_token_expires)
        # Optionally rotate refresh token (more secure)
        new_refresh_token = create_refresh_token(subject=user.id, expires_delta=refresh_token_expires)

        logger.info(f"Token refreshed for user {user.id}")
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token, # Return new one if rotated
            "token_type": "bearer",
            "expires_in": int(access_token_expires.total_seconds()), # Return seconds
        }

    # Method used by validate_reset_token and change_password
    def get_by_id(self, user_id: Any) -> Optional[User]:
        """
        Get a user by ID, handling potential type errors.

        Args:
            user_id: User ID (can be string or int).

        Returns:
            User object or None if not found or ID is invalid.
        """
        try:
            user_id_int = int(user_id)
        except (ValueError, TypeError):
            logger.warning(f"Invalid user ID format provided to get_by_id: '{user_id}'")
            return None

        logger.debug(f"Looking up user with ID: {user_id_int}")
        try:
            user = self.repository.get_by_id(user_id_int)
            if user:
                logger.debug(f"Found user: {user.id} - {user.email}")
            else:
                logger.debug(f"No user found with ID: {user_id_int}")
            return user
        except Exception as e:
             logger.error(f"Error retrieving user by ID {user_id_int}: {e}", exc_info=True)
             return None

    # Add other UserService specific methods here, e.g.:
    # def assign_role_to_user(self, user_id: int, role_name: str) -> User: ...
    # def get_user_permissions(self, user_id: int) -> List[str]: ...

