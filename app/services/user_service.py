# File: app/services/user_service.py

from typing import Optional, List, Any, Dict, Union
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder

from app.db.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password
from app.services.base_service import BaseService
from app.core.exceptions import EntityNotFoundException, BusinessRuleException


class UserService(BaseService[User]):
    """
    Service for managing user-related operations.

    Handles authentication, user creation, updates, and permissions.
    """

    def __init__(self, db: Session):
        """Initialize user service with database session."""
        super().__init__(db)
        self.model = User

    def get_by_email(self, email: str) -> Optional[User]:
        """Retrieve a user by email address."""
        return self.db.query(User).filter(User.email == email).first()

    def get_by_username(self, username: str) -> Optional[User]:
        """Retrieve a user by username."""
        return self.db.query(User).filter(User.username == username).first()

    def get_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Retrieve a list of users with pagination."""
        return self.db.query(User).offset(skip).limit(limit).all()

    def create_user(self, obj_in: UserCreate) -> User:
        """
        Create a new user.

        Args:
            obj_in: User data for creation

        Raises:
            BusinessRuleException: If email or username already exists

        Returns:
            User: Created user instance
        """
        # Check if email already exists
        existing_email = self.get_by_email(obj_in.email)
        if existing_email:
            raise BusinessRuleException("The user with this email already exists")

        # Check if username already exists
        existing_username = self.get_by_username(obj_in.username)
        if existing_username:
            raise BusinessRuleException("The user with this username already exists")

        # Create user with hashed password
        db_obj = User(
            email=obj_in.email,
            username=obj_in.username,
            hashed_password=get_password_hash(obj_in.password),
            full_name=obj_in.full_name,
            is_superuser=obj_in.is_superuser,
            is_active=True,
        )

        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update_user(
        self, user_id: int, obj_in: Union[UserUpdate, Dict[str, Any]]
    ) -> User:
        """
        Update a user's information.

        Args:
            user_id: ID of the user to update
            obj_in: Update data, either as UserUpdate schema or dict

        Raises:
            EntityNotFoundException: If user doesn't exist

        Returns:
            User: Updated user instance
        """
        db_obj = self.get(user_id)
        if not db_obj:
            raise EntityNotFoundException("User not found")

        # Convert to dict if it's a Pydantic model
        update_data = (
            obj_in if isinstance(obj_in, dict) else obj_in.dict(exclude_unset=True)
        )

        # Handle password update - hash the new password
        if "password" in update_data and update_data["password"]:
            hashed_password = get_password_hash(update_data["password"])
            del update_data["password"]
            update_data["hashed_password"] = hashed_password

        # Update user data
        for field in update_data:
            if hasattr(db_obj, field):
                setattr(db_obj, field, update_data[field])

        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete_user(self, user_id: int) -> User:
        """
        Delete a user.

        Args:
            user_id: ID of the user to delete

        Raises:
            EntityNotFoundException: If user doesn't exist

        Returns:
            User: The deleted user
        """
        user = self.get(user_id)
        if not user:
            raise EntityNotFoundException("User not found")

        self.db.delete(user)
        self.db.commit()
        return user

    def authenticate(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate a user with email and password.

        Args:
            email: User's email
            password: User's password

        Returns:
            User if authentication is successful, None otherwise
        """
        user = self.get_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None

        # Update last login timestamp
        user.last_login = datetime.now()
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        return user

    def is_active(self, user: User) -> bool:
        """Check if user is active."""
        return user.is_active

    def is_superuser(self, user: User) -> bool:
        """Check if user has superuser privileges."""
        return user.is_superuser

    def to_dict(self, user: User) -> Dict:
        """Convert user model to dictionary without sensitive data."""
        user_data = jsonable_encoder(user)

        # Remove sensitive fields
        if "hashed_password" in user_data:
            del user_data["hashed_password"]

        return user_data
