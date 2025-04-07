# File: app/api/deps.py
"""
FastAPI dependencies for HideSync.

Provides dependency functions for database sessions, user authentication/authorization,
and service injection for API routes.
"""

import logging
from datetime import datetime
from typing import Generator, Optional, Any, Dict, List, Union # Added Dict, List, Union

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError, BaseModel # Import BaseModel if needed for TokenPayload
from sqlalchemy.orm import Session

# --- App Imports ---
# Adjust paths based on your project structure
from app.core import security
from app.core.config import settings
from app.db.session import SessionLocal, get_db # Import get_db directly
from app.services.user_service import UserService
from app.db.models.user import User
# Import Schemas used here
from app.schemas.token import TokenPayload # Assuming this schema exists
# Import Services & Repositories needed for injection
from app.services.inventory_service import InventoryService
from app.services.product_service import ProductService

# Import Repositories used by services instantiated here
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.inventory_transaction_repository import InventoryTransactionRepository
from app.repositories.product_repository import ProductRepository


# Import other services if they are dependencies for the main ones
# from app.services.material_service import MaterialService
# from app.services.tool_service import ToolService
# from app.services.supplier_service import SupplierService

logger = logging.getLogger(__name__) # Setup logger

# --- Authentication ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token") # Use API_V1_STR

# --- Database Session Dependency (Using the one from db.session) ---
# from app.db.session import get_db # Imported above

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
        token_data = TokenPayload.model_validate(payload) # Pydantic v2 validation

        if token_data.exp is None or datetime.fromtimestamp(token_data.exp) < datetime.utcnow(): # Use utcnow()
            logger.warning(f"Token expired for sub: {token_data.sub}")
            raise credentials_exception # Re-use exception for expired token

        if token_data.sub is None:
            logger.error("Token payload missing 'sub' (user id).")
            raise credentials_exception

    except (JWTError, ValidationError) as e:
        logger.error(f"Token validation failed: {e}", exc_info=True)
        raise credentials_exception

    try:
        user_service = UserService(db) # Instantiate service here
        user_id = int(token_data.sub) # Ensure subject is treated as int ID
        user = user_service.get_by_id(user_id)
        if user is None:
            logger.warning(f"User with ID {user_id} from token not found in DB.")
            raise credentials_exception
        return user
    except ValueError:
         logger.error(f"Invalid user ID format in token 'sub': {token_data.sub}")
         raise credentials_exception
    except Exception as e:
        logger.error(f"Error fetching user during authentication: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during authentication.")


def get_current_active_user(
        current_user: User = Depends(get_current_user),
) -> User:
    """ Gets current user and verifies they are active. """
    if not current_user.is_active:
        logger.warning(f"Authentication attempt by inactive user: {current_user.email} (ID: {current_user.id})")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


def get_current_active_superuser(
        current_user: User = Depends(get_current_active_user), # Chain dependency
) -> User:
    """ Gets current active user and verifies superuser status. """
    if not current_user.is_superuser:
        logger.warning(f"Superuser access denied for user: {current_user.email} (ID: {current_user.id})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have sufficient privileges"
        )
    logger.info(f"Superuser access granted for user: {current_user.email} (ID: {current_user.id})")
    return current_user


# --- Permissions Checker Dependency (Example - keep if needed) ---
class PermissionsChecker:
    """ Dependency class to check if user has required permissions. """
    def __init__(self, required_permissions: List[str]):
        self.required_permissions = set(required_permissions)

    def __call__(self, current_user: User = Depends(get_current_active_user)):
        user_permissions = set(role.name for role in getattr(current_user, 'roles', [])) # Safely access roles
        logger.debug(f"Checking permissions for user {current_user.id}. Required: {self.required_permissions}. User has: {user_permissions}")
        if not self.required_permissions.issubset(user_permissions):
            logger.warning(f"Permission denied for user {current_user.id}. Missing: {self.required_permissions - user_permissions}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        logger.debug(f"Permission granted for user {current_user.id}.")


# --- Service Dependency Injectors ---

# Note: For larger applications, consider a more robust DI container (e.g., python-dependency-injector, fastapi-injector)
# This manual approach can lead to complex dependencies between these getter functions.

# Injectors for services needed by ProductService and InventoryService first
# (Add injectors for MaterialService, ToolService, SupplierService if they are needed)



# ProductService needs InventoryService, but InventoryService needs ProductService.
# This creates a circular dependency if injected directly like this.
#
# SOLUTION: Inject the *Session* into the services, and let the services
# instantiate *repositories* directly. Avoid injecting services into each other
# directly in the dependency getters if possible, unless using a proper DI container
# that handles circular dependencies.
#
# REVISED APPROACH: Services get Session, instantiate their own primary repo.
# If Service A needs to *call* Service B, it can instantiate Service B within its method,
# passing the *same session*. This is less clean than full DI but avoids circular deps here.
#
# ALTERNATIVE (Shown below): Use placeholder functions and resolve later, or use a Factory.
# Let's try resolving by passing the session and letting services get what they need.

# Revised Injectors (Simpler, avoids circular dependency between getters)


# Internal helpers to manage potential circular dependencies if needed,
# though ideally services shouldn't directly depend on each other's full instances
# in their constructors passed via FastAPI Depends.
# They could potentially get other services via a factory or request state if needed.

# --- RECOMMENDED SIMPLIFIED APPROACH for FastAPI Depends ---
# Inject SESSION, services instantiate their OWN repositories.
# If Service A needs Service B logic, it INSTANTIATES Service B with the SAME session.

def get_product_service_simple(db: Session = Depends(get_db)) -> ProductService:
     """Simple injector providing ProductService with session."""
     logger.debug("(Simple) Providing ProductService instance.")
     # ProductService __init__ will need to accept session and potentially other services directly
     # OR instantiate InventoryService itself using the passed session.
     # Let's assume ProductService instantiates InventoryService internally:
     # Simplified constructor: ProductService(session, ...)
     return ProductService(session=db) # Requires ProductService to handle InventoryService instantiation

def get_inventory_service_simple(db: Session = Depends(get_db)) -> InventoryService:
     """Simple injector providing InventoryService with session."""
     logger.debug("(Simple) Providing InventoryService instance.")
     # InventoryService __init__ will need to accept session and potentially ProductService etc.
     # OR instantiate ProductService itself using the passed session.
     # Simplified constructor: InventoryService(session, ...)
     return InventoryService(session=db) # Requires InventoryService to handle ProductService instantiation

# Choose ONE approach (complex cross-injection OR simplified session injection).
# The **simplified approach** is generally easier to manage with FastAPI's built-in Depends.
# Let's stick with the simplified one for the final version.

# --- FINAL Simplified Injectors ---

def get_product_service(db: Session = Depends(get_db)) -> ProductService:
    """Injector providing ProductService with session.
       It instantiates its own repo and the InventoryService it depends on.
    """
    logger.debug("Providing ProductService instance (deps).")
    product_repo = ProductRepository(session=db)

    # Instantiate the InventoryService needed by ProductService constructor
    # We directly call the corrected get_inventory_service here
    inventory_service_instance = get_inventory_service(db=db)  # Pass the db session

    # ** Modify ProductService __init__ to accept inventory_service **
    return ProductService(
        session=db,
        repository=product_repo,
        inventory_service=inventory_service_instance  # Pass the created instance
    )


def get_inventory_service(db: Session = Depends(get_db)) -> InventoryService:
    """Injector providing InventoryService with session.
       It instantiates its own repos. It does NOT get ProductService injected here
       to avoid circular dependency issues in the injectors themselves.
       Methods needing ProductService will get it via the lazy property.
    """
    logger.debug("Providing InventoryService instance (deps).")
    inv_repo = InventoryRepository(session=db)
    inv_tx_repo = InventoryTransactionRepository(session=db)
    # ** Modify InventoryService __init__ to accept session and instantiate/lazy load ProductService **
    # Pass other services needed by InventoryService's __init__ if any (e.g., MaterialService)
    return InventoryService(
        session=db,
        repository=inv_repo,
        transaction_repository=inv_tx_repo
        # Add other necessary service injections here if InventoryService needs them directly at init
        # product_service=None, # Explicitly None if using lazy loading property inside
    )

# Add injectors for other services following the simplified pattern...