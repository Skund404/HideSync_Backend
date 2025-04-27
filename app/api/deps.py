# app/api/deps.py
"""
FastAPI dependencies for HideSync.

Provides dependency functions for database sessions, user authentication/authorization,
and service injection for API routes.
"""

import logging
from datetime import datetime, timezone  # Use timezone aware datetime
from typing import Generator, Optional, Any, Dict, List, Union

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError, BaseModel
from sqlalchemy.orm import Session
from app.services.settings_service import SettingsService

# --- App Imports ---
# Core components
from app.core import security
from app.core.config import settings
from app.core.exceptions import (
    EntityNotFoundException,
)

# Database session provider
from app.db.session import SessionLocal, get_db

# Models
from app.db.models.user import User

# Schemas
from app.schemas.token import TokenPayload

# --- Services ---
from app.services.user_service import UserService
from app.services.inventory_service import InventoryService
from app.services.product_service import ProductService
from app.services.pattern_service import PatternService
from app.services.material_service import MaterialService
from app.services.enum_service import EnumService # <-- Import EnumService

# Import other services if they are dependencies for the main ones
# from app.services.tool_service import ToolService
# ... etc

# --- Repositories needed for direct instantiation within service getters ---
from app.repositories.user_repository import UserRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.inventory_transaction_repository import InventoryTransactionRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.pattern_repository import PatternRepository, ProjectTemplateRepository
from app.repositories.material_repository import MaterialRepository
# No specific repos needed for EnumService currently, as it uses raw session or ORM directly

# ... other imports ...

logger = logging.getLogger(__name__)

# --- Authentication ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")

# --- Database Session Dependency ---
# get_db is imported from app.db.session

# --- User Authentication & Authorization Dependencies ---

def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """Get current authenticated user from JWT token."""
    # ... (implementation remains the same) ...
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        token_data = TokenPayload.model_validate(payload)
        if token_data.exp is None or datetime.fromtimestamp(
            token_data.exp, tz=timezone.utc
        ) < datetime.now(timezone.utc):
            logger.warning(f"Token expired for sub: {token_data.sub}")
            raise credentials_exception
        if token_data.sub is None:
            logger.error("Token payload missing 'sub' (user id).")
            raise credentials_exception
    except (JWTError, ValidationError) as e:
        logger.error(f"Token validation failed: {e}", exc_info=False)
        raise credentials_exception from e

    try:
        user_repo = UserRepository(session=db)
        user_service = UserService(session=db, repository=user_repo)
        user_id = int(token_data.sub)
        user = user_service.get_by_id(user_id)
        if user is None:
            logger.warning(f"User with ID {user_id} from token not found in DB.")
            raise credentials_exception
        return user
    except ValueError:
        logger.error(f"Invalid user ID format in token 'sub': {token_data.sub}")
        raise credentials_exception
    except EntityNotFoundException:
        logger.warning(f"User with ID {token_data.sub} from token not found (service layer).")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Error fetching user during authentication: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authentication.",
        )


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Gets current user and verifies they are active."""
    # ... (implementation remains the same) ...
    if not current_user.is_active:
        logger.warning(
            f"Authentication attempt by inactive user: {current_user.email} (ID: {current_user.id})"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return current_user

def get_current_active_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Gets current active user and verifies superuser status."""
    # ... (implementation remains the same) ...
    if not current_user.is_superuser:
        logger.warning(
            f"Superuser access denied for user: {current_user.email} (ID: {current_user.id})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have sufficient privileges",
        )
    logger.info(
        f"Superuser access granted for user: {current_user.email} (ID: {current_user.id})"
    )
    return current_user

def get_settings_service(db: Session = Depends(get_db)) -> SettingsService:
    """Provides an instance of SettingsService."""
    return SettingsService(db)

# --- Permissions Checker Dependency (Example) ---
class PermissionsChecker:
    """Dependency class to check if user has required permissions."""
    # ... (implementation remains the same) ...
    def __init__(self, required_permissions: List[str]):
        self.required_permissions = set(required_permissions)

    def __call__(self, current_user: User = Depends(get_current_active_user)):
        user_permissions = set(role.name for role in getattr(current_user, "roles", []))
        logger.debug(f"Checking permissions for user {current_user.id}. Required: {self.required_permissions}. User has: {user_permissions}")
        if not self.required_permissions.issubset(user_permissions):
            missing_perms = self.required_permissions - user_permissions
            logger.warning(f"Permission denied for user {current_user.id}. Missing: {missing_perms}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        logger.debug(f"Permission granted for user {current_user.id}.")


# --- Service Dependency Injectors ---

# --- ADD Injector for EnumService ---
def get_enum_service(db: Session = Depends(get_db)) -> EnumService:
    """Provides an instance of EnumService."""
    logger.debug("Providing EnumService instance.")
    # EnumService currently only needs the db session
    return EnumService(db=db)
# --- END Injector for EnumService ---

# Injector for PatternService
def get_pattern_service(db: Session = Depends(get_db)) -> PatternService:
    """Provides an instance of PatternService."""
    logger.debug("Providing PatternService instance.")
    pattern_repo = PatternRepository(session=db)
    template_repo = ProjectTemplateRepository(session=db)
    return PatternService(
        session=db,
        repository=pattern_repo,
        template_repository=template_repo,
    )

# Injector for MaterialService
def get_material_service(db: Session = Depends(get_db)) -> MaterialService:
    """Provides an instance of MaterialService."""
    logger.debug("Providing MaterialService instance.")
    material_repo = MaterialRepository(session=db)
    return MaterialService(
        session=db,
        repository=material_repo,
    )

# Injector for InventoryService
def get_inventory_service(db: Session = Depends(get_db)) -> InventoryService:
    """Injector providing InventoryService with session."""
    logger.debug("Providing InventoryService instance (deps).")
    inv_repo = InventoryRepository(session=db)
    inv_tx_repo = InventoryTransactionRepository(session=db)
    return InventoryService(
        session=db,
        repository=inv_repo,
        transaction_repository=inv_tx_repo,
    )

# Injector for ProductService
def get_product_service(
    db: Session = Depends(get_db),
    inventory_service: InventoryService = Depends(get_inventory_service),
    pattern_service: PatternService = Depends(get_pattern_service),
    material_service: MaterialService = Depends(get_material_service),
) -> ProductService:
    """Injector providing ProductService with necessary dependencies."""
    logger.debug("Providing ProductService instance (deps).")
    product_repo = ProductRepository(session=db)
    return ProductService(
        session=db,
        repository=product_repo,
        inventory_service=inventory_service,
        pattern_service=pattern_service,
        material_service=material_service,
    )

# --- (Add other service injectors as needed following the pattern) ---

# Example for UserService (if needed directly by endpoints)
# def get_user_service(db: Session = Depends(get_db)) -> UserService:
#     logger.debug("Providing UserService instance.")
#     user_repo = UserRepository(session=db)
#     # Pass other dependencies like key_service if UserService requires them
#     return UserService(session=db, repository=user_repo)