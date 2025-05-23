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
from app.services.enum_service import EnumService
from app.services.property_definition_service import PropertyDefinitionService
from app.services.material_type_service import MaterialTypeService
from app.services.dynamic_material_service import DynamicMaterialService

# --- Repositories needed for direct instantiation within service getters ---
from app.repositories.user_repository import UserRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.inventory_transaction_repository import InventoryTransactionRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.pattern_repository import PatternRepository, ProjectTemplateRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.property_definition_repository import PropertyDefinitionRepository
from app.repositories.material_type_repository import MaterialTypeRepository
from app.repositories.dynamic_material_repository import DynamicMaterialRepository
from app.services.workflow_service import WorkflowService
from app.services.workflow_execution_service import WorkflowExecutionService
from app.services.workflow_navigation_service import WorkflowNavigationService
from app.services.workflow_import_export_service import WorkflowImportExportService

logger = logging.getLogger(__name__)

# --- Authentication ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")


# --- Database Session Dependency ---
# get_db is imported from app.db.session

# --- Security Context ---
def get_security_context(current_user: Optional[User] = Depends(get_current_active_user)):
    """
    Provides a security context for services that need user information.

    Creates a simple object with the current_user property that can be passed to services.
    """
    context = type('SecurityContext', (), {
        'current_user': current_user
    })
    logger.debug(f"Created security context with user ID: {getattr(current_user, 'id', None)}")
    return context


# --- User Authentication & Authorization Dependencies ---

def get_current_user(
        db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """Get current authenticated user from JWT token."""
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


# --- Permissions Checker Dependency ---
class PermissionsChecker:
    """Dependency class to check if user has required permissions."""

    def __init__(self, required_permissions: List[str]):
        self.required_permissions = set(required_permissions)

    def __call__(self, current_user: User = Depends(get_current_active_user)):
        user_permissions = set(role.name for role in getattr(current_user, "roles", []))
        logger.debug(
            f"Checking permissions for user {current_user.id}. Required: {self.required_permissions}. User has: {user_permissions}")
        if not self.required_permissions.issubset(user_permissions):
            missing_perms = self.required_permissions - user_permissions
            logger.warning(f"Permission denied for user {current_user.id}. Missing: {missing_perms}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        logger.debug(f"Permission granted for user {current_user.id}.")


# --- Service Dependency Injectors ---

def get_settings_service(db: Session = Depends(get_db)) -> SettingsService:
    """Provides an instance of SettingsService."""
    logger.debug("Providing SettingsService instance.")
    return SettingsService(db)


def get_enum_service(db: Session = Depends(get_db)) -> EnumService:
    """Provides an instance of EnumService."""
    logger.debug("Providing EnumService instance.")
    return EnumService(db=db)


def get_property_definition_service(
        db: Session = Depends(get_db),
        enum_service: EnumService = Depends(get_enum_service)
) -> PropertyDefinitionService:
    """Provides an instance of PropertyDefinitionService."""
    logger.debug("Providing PropertyDefinitionService instance.")
    property_repo = PropertyDefinitionRepository(session=db)
    return PropertyDefinitionService(
        session=db,
        repository=property_repo,
        enum_service=enum_service
    )


def get_material_type_service(
        db: Session = Depends(get_db),
        property_service: PropertyDefinitionService = Depends(get_property_definition_service)
) -> MaterialTypeService:
    """Provides an instance of MaterialTypeService."""
    logger.debug("Providing MaterialTypeService instance.")
    material_type_repo = MaterialTypeRepository(session=db)
    return MaterialTypeService(
        session=db,
        repository=material_type_repo,
        property_repository=property_service.repository
    )


def get_dynamic_material_service(
        db: Session = Depends(get_db),
        property_service: PropertyDefinitionService = Depends(get_property_definition_service),
        material_type_service: MaterialTypeService = Depends(get_material_type_service),
        security_context=Depends(get_security_context),
        settings_service: SettingsService = Depends(get_settings_service)
) -> DynamicMaterialService:
    """Provides an instance of DynamicMaterialService."""
    logger.debug("Providing DynamicMaterialService instance.")
    dynamic_material_repo = DynamicMaterialRepository(session=db)
    return DynamicMaterialService(
        session=db,
        repository=dynamic_material_repo,
        property_service=property_service,
        material_type_service=material_type_service,
        security_context=security_context,
        settings_service=settings_service
    )


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


def get_material_service(
        db: Session = Depends(get_db),
        security_context=Depends(get_security_context),
        settings_service: SettingsService = Depends(get_settings_service)
) -> MaterialService:
    """Provides an instance of MaterialService."""
    logger.debug("Providing MaterialService instance.")
    material_repo = MaterialRepository(session=db)
    return MaterialService(
        session=db,
        repository=material_repo,
        security_context=security_context,
        settings_service=settings_service
    )


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

def get_workflow_service(
    db: Session = Depends(get_db),
    security_context=Depends(get_security_context)
) -> WorkflowService:
    """Provides an instance of WorkflowService."""
    logger.debug("Providing WorkflowService instance.")
    return WorkflowService(
        session=db,
        security_context=security_context
    )

def get_workflow_execution_service(
    db: Session = Depends(get_db),
    workflow_service: WorkflowService = Depends(get_workflow_service)
) -> WorkflowExecutionService:
    """Provides an instance of WorkflowExecutionService."""
    logger.debug("Providing WorkflowExecutionService instance.")
    return WorkflowExecutionService(
        session=db,
        workflow_service=workflow_service
    )

def get_workflow_navigation_service(
    db: Session = Depends(get_db),
    execution_service: WorkflowExecutionService = Depends(get_workflow_execution_service)
) -> WorkflowNavigationService:
    """Provides an instance of WorkflowNavigationService."""
    logger.debug("Providing WorkflowNavigationService instance.")
    return WorkflowNavigationService(
        session=db,
        execution_service=execution_service
    )

def get_workflow_import_export_service(
    db: Session = Depends(get_db),
    workflow_service: WorkflowService = Depends(get_workflow_service)
) -> WorkflowImportExportService:
    """Provides an instance of WorkflowImportExportService."""
    logger.debug("Providing WorkflowImportExportService instance.")
    return WorkflowImportExportService(
        session=db,
        workflow_service=workflow_service
    )