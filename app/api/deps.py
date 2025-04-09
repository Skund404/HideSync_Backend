# File: app/api/deps.py
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

# --- App Imports ---
# Core components
from app.core import security
from app.core.config import settings
from app.core.exceptions import (
    EntityNotFoundException,
)  # Import if needed by services directly

# Database session provider
from app.db.session import SessionLocal, get_db

# Models
from app.db.models.user import User

# Schemas
from app.schemas.token import TokenPayload

# Services
from app.services.user_service import UserService
from app.services.inventory_service import InventoryService
from app.services.product_service import ProductService
from app.services.pattern_service import PatternService
from app.services.material_service import MaterialService

# Import other services if they are dependencies for the main ones
# from app.services.tool_service import ToolService
# from app.services.supplier_service import SupplierService
# from app.services.storage_service import StorageService
# from app.services.component_service import ComponentService
# from app.services.file_storage_service import FileStorageService


# Repositories needed for direct instantiation within service getters
from app.repositories.user_repository import UserRepository  # For UserService
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.inventory_transaction_repository import (
    InventoryTransactionRepository,
)
from app.repositories.product_repository import ProductRepository
from app.repositories.pattern_repository import (
    PatternRepository,
    ProjectTemplateRepository,
)  # PatternService needs both
from app.repositories.material_repository import MaterialRepository

# Import other repositories if needed by services instantiated here
# from app.repositories.component_repository import ComponentRepository


logger = logging.getLogger(__name__)

# --- Authentication ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")

# --- Database Session Dependency ---
# get_db is imported from app.db.session

# --- User Authentication & Authorization Dependencies ---


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """
    Get current authenticated user from JWT token.

    Raises:
        HTTPException 401: If token is invalid, expired, or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        token_data = TokenPayload.model_validate(payload)  # Pydantic v2 validation

        # Use timezone aware comparison
        if token_data.exp is None or datetime.fromtimestamp(
            token_data.exp, tz=timezone.utc
        ) < datetime.now(timezone.utc):
            logger.warning(f"Token expired for sub: {token_data.sub}")
            raise credentials_exception

        if token_data.sub is None:
            logger.error("Token payload missing 'sub' (user id).")
            raise credentials_exception

    except (JWTError, ValidationError) as e:
        logger.error(
            f"Token validation failed: {e}", exc_info=False
        )  # Reduce noise in logs unless debugging tokens
        raise credentials_exception from e

    try:
        # Use UserRepository directly or instantiate UserService
        # Using UserService is generally cleaner
        user_repo = UserRepository(
            session=db
        )  # Or get from a factory/registry if available
        user_service = UserService(session=db, repository=user_repo)
        user_id = int(token_data.sub)  # Ensure subject is treated as int ID
        user = user_service.get_by_id(user_id)  # Use service method
        if user is None:
            logger.warning(f"User with ID {user_id} from token not found in DB.")
            raise credentials_exception
        return user
    except ValueError:
        logger.error(f"Invalid user ID format in token 'sub': {token_data.sub}")
        raise credentials_exception
    except EntityNotFoundException:  # Catch if service raises this
        logger.warning(
            f"User with ID {token_data.sub} from token not found (service layer)."
        )
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
    if not current_user.is_active:
        logger.warning(
            f"Authentication attempt by inactive user: {current_user.email} (ID: {current_user.id})"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return current_user


def get_current_active_superuser(
    current_user: User = Depends(get_current_active_user),  # Chain dependency
) -> User:
    """Gets current active user and verifies superuser status."""
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


# --- Permissions Checker Dependency (Example) ---
class PermissionsChecker:
    """Dependency class to check if user has required permissions."""

    def __init__(self, required_permissions: List[str]):
        self.required_permissions = set(required_permissions)

    def __call__(self, current_user: User = Depends(get_current_active_user)):
        # Ensure roles are loaded or handle potential lazy loading if necessary
        # This assumes roles are eagerly loaded or accessible via the user object
        user_permissions = set(role.name for role in getattr(current_user, "roles", []))
        logger.debug(
            f"Checking permissions for user {current_user.id}. Required: {self.required_permissions}. User has: {user_permissions}"
        )
        if not self.required_permissions.issubset(user_permissions):
            missing_perms = self.required_permissions - user_permissions
            logger.warning(
                f"Permission denied for user {current_user.id}. Missing: {missing_perms}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        logger.debug(f"Permission granted for user {current_user.id}.")


# --- Service Dependency Injectors ---


# Injector for PatternService
def get_pattern_service(db: Session = Depends(get_db)) -> PatternService:
    """Provides an instance of PatternService."""
    logger.debug("Providing PatternService instance.")
    pattern_repo = PatternRepository(session=db)
    template_repo = ProjectTemplateRepository(
        session=db
    )  # PatternService needs this too
    # component_repo = ComponentRepository(session=db) # Example: Instantiate if needed
    # file_storage_service_instance = get_file_storage_service() # Example: Get if needed
    return PatternService(
        session=db,
        repository=pattern_repo,
        template_repository=template_repo,
        # component_repository=component_repo, # Pass dependencies
        # component_service=get_component_service(db=db), # Or inject service if needed
        # file_storage_service=file_storage_service_instance
    )


# Injector for MaterialService
def get_material_service(db: Session = Depends(get_db)) -> MaterialService:
    """Provides an instance of MaterialService."""
    logger.debug("Providing MaterialService instance.")
    material_repo = MaterialRepository(session=db)
    # key_service_instance = get_key_service() # Example if encryption is used
    return MaterialService(
        session=db,
        repository=material_repo,
        # key_service=key_service_instance
    )


# Injector for InventoryService
def get_inventory_service(db: Session = Depends(get_db)) -> InventoryService:
    """Injector providing InventoryService with session.
    Instantiates its own repos. Does not directly inject ProductService here.
    """
    logger.debug("Providing InventoryService instance (deps).")
    inv_repo = InventoryRepository(session=db)
    inv_tx_repo = InventoryTransactionRepository(session=db)
    # Instantiate other direct dependencies if needed by InventoryService.__init__
    # e.g., material_service=get_material_service(db=db)
    return InventoryService(
        session=db,
        repository=inv_repo,
        transaction_repository=inv_tx_repo,
        # material_service = get_material_service(db=db), # Example
        # tool_service = get_tool_service(db=db) # Example
        # Pass security_context/event_bus/cache if needed by init
    )


# Injector for ProductService (Updated to inject dependencies)
def get_product_service(
    db: Session = Depends(get_db),
    # --- GET DEPENDENT SERVICES VIA THEIR INJECTORS ---
    inventory_service: InventoryService = Depends(get_inventory_service),
    pattern_service: PatternService = Depends(get_pattern_service),
    material_service: MaterialService = Depends(get_material_service),
    # --- END GETTING DEPENDENT SERVICES ---
) -> ProductService:
    """Injector providing ProductService with necessary dependencies."""
    logger.debug("Providing ProductService instance (deps).")
    product_repo = ProductRepository(session=db)

    # --- PASS FETCHED SERVICES TO ProductService CONSTRUCTOR ---
    return ProductService(
        session=db,
        repository=product_repo,
        inventory_service=inventory_service,  # Pass fetched InventoryService
        pattern_service=pattern_service,  # Pass fetched PatternService
        material_service=material_service,  # Pass fetched MaterialService
        # Pass other core services like event_bus, security_context if needed by ProductService.__init__
    )


# Add injectors for other services (UserService, ToolService, etc.) if needed by endpoints
# Example:
# def get_user_service(db: Session = Depends(get_db)) -> UserService:
#     logger.debug("Providing UserService instance.")
#     user_repo = UserRepository(session=db)
#     return UserService(session=db, repository=user_repo)

# Add injectors for services needed by PatternService, MaterialService, InventoryService constructors
# Example:
# def get_component_service(db: Session = Depends(get_db)) -> ComponentService: ...
# def get_file_storage_service() -> FileStorageService: ... # Might not need db session
