# File: app/core/exceptions.py

from typing import Dict, Any, List, Optional
import json
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator

# Assuming these imports are needed by schemas defined later in the file
# If not, they can be removed.
# from app.db.models.enums import (
#     CustomerStatus,
#     CustomerTier,
#     CustomerSource,
#     CommunicationChannel,
#     CommunicationType,
# )
# from app.schemas.customer import CustomerBase


class HideSyncException(Exception):
    """Base exception for all HideSync errors."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a HideSync exception.

        Args:
            message: Human-readable error message
            code: Optional machine-processable error code
            details: Additional error details
        """
        self.message = message
        self.code = code or "GENERIC_ERROR"  # Provide a default if None
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary for API responses.

        Returns:
            Dictionary representation of the exception
        """
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "timestamp": datetime.now().isoformat(),
        }


# Domain-specific exceptions
class DomainException(HideSyncException):
    """Base exception for domain-related errors."""

    CODE_PREFIX = "DOMAIN_"


class EntityNotFoundException(DomainException):
    """Raised when a requested entity does not exist."""

    def __init__(self, entity_type: str, entity_id: Any):
        super().__init__(
            f"{entity_type} with ID {entity_id} not found",
            f"{self.CODE_PREFIX}001",
            {"entity_type": entity_type, "entity_id": entity_id},
        )


# Material-related exceptions
class MaterialException(HideSyncException):
    """Base exception for material-related errors."""

    CODE_PREFIX = "MATERIAL_"


class MaterialNotFoundException(MaterialException):
    """Raised when a requested material does not exist."""

    def __init__(self, material_id: int):
        super().__init__(
            f"Material with ID {material_id} not found",
            f"{self.CODE_PREFIX}001",
            {"material_id": material_id},
        )


class InsufficientInventoryException(MaterialException):
    """Raised when attempting to use more material than available."""

    def __init__(self, material_id: int, requested: float, available: float):
        super().__init__(
            f"Insufficient inventory for material {material_id}: requested {requested}, available {available}",
            f"{self.CODE_PREFIX}002",
            {
                "material_id": material_id,
                "requested": requested,
                "available": available,
            },
        )


# Project-related exceptions
class ProjectException(HideSyncException):
    """Base exception for project-related errors."""

    CODE_PREFIX = "PROJECT_"


class ProjectNotFoundException(ProjectException):
    """Raised when a requested project does not exist."""

    def __init__(self, project_id: int):
        super().__init__(
            f"Project with ID {project_id} not found",
            f"{self.CODE_PREFIX}001",
            {"project_id": project_id},
        )


class InvalidProjectStatusTransitionException(ProjectException):
    """Raised when an invalid project status transition is attempted."""

    def __init__(self, project_id: int, current_status: str, new_status: str):
        super().__init__(
            f"Invalid status transition for project {project_id}: {current_status} -> {new_status}",
            f"{self.CODE_PREFIX}002",
            {
                "project_id": project_id,
                "current_status": current_status,
                "new_status": new_status,
            },
        )


# Customer-related exceptions
class CustomerException(HideSyncException):
    """Base exception for customer-related errors."""

    CODE_PREFIX = "CUSTOMER_"


class CustomerNotFoundException(CustomerException):
    """Raised when a requested customer does not exist."""

    def __init__(self, customer_id: int):
        super().__init__(
            f"Customer with ID {customer_id} not found",
            f"{self.CODE_PREFIX}001",
            {"customer_id": customer_id},
        )


# Validation exceptions
class ValidationException(HideSyncException):
    """Raised when input validation fails."""

    def __init__(
        self, message: str, validation_errors: Optional[Dict[str, List[str]]] = None
    ):  # Made errors optional
        super().__init__(
            message, "VALIDATION_001", {"validation_errors": validation_errors or {}}
        )


# Concurrency exceptions
class ConcurrentModificationException(HideSyncException):
    """Raised when a concurrent modification is detected."""

    def __init__(
        self,
        message: str,
        expected_version: Optional[int] = None,
        actual_version: Optional[int] = None,
    ):
        details = {}
        if expected_version is not None:
            details["expected_version"] = expected_version
        if actual_version is not None:
            details["actual_version"] = actual_version
        super().__init__(message, "CONCURRENCY_001", details)


# Security exceptions
class SecurityException(HideSyncException):
    """Base exception for security-related errors."""

    CODE_PREFIX = "SECURITY_"


class UnauthorizedException(SecurityException):
    """Raised when a user is not authorized to perform an action."""

    def __init__(self, message: str = "Unauthorized access"):
        super().__init__(message, f"{self.CODE_PREFIX}001", {})


class ForbiddenException(SecurityException):
    """Raised when a user is forbidden from accessing a resource."""

    def __init__(self, resource_type: str, resource_id: Any = None):
        details = {"resource_type": resource_type}
        if resource_id is not None:
            details["resource_id"] = resource_id
        super().__init__(
            f"Access forbidden to {resource_type}"
            + (f" with ID {resource_id}" if resource_id else ""),
            f"{self.CODE_PREFIX}002",
            details,
        )


class AuthenticationException(SecurityException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, f"{self.CODE_PREFIX}003", {})


# Integration exceptions
class IntegrationException(HideSyncException):
    """Base exception for integration-related errors."""

    CODE_PREFIX = "INTEGRATION_"


class ExternalServiceException(IntegrationException):
    """Raised when an external service call fails."""

    def __init__(
        self, service_name: str, message: str, original_error: Optional[str] = None
    ):
        details = {"service_name": service_name}
        if original_error:
            details["original_error"] = original_error
        super().__init__(
            f"Error from external service {service_name}: {message}",
            f"{self.CODE_PREFIX}001",
            details,
        )


# Business rule exceptions
class BusinessRuleException(HideSyncException):
    """Raised when a business rule or constraint is violated."""

    CODE_PREFIX = "BUSINESS_"

    def __init__(
        self,
        message: str,
        rule_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        error_details = details or {}
        if rule_name:
            error_details["rule_name"] = rule_name
        super().__init__(message, f"{self.CODE_PREFIX}001", error_details)


class BusinessRuleError(BusinessRuleException):
    """Alternative name for BusinessRuleException for backward compatibility."""

    pass


# Concurrent operation exceptions
class ConcurrentOperationException(HideSyncException):
    """Raised when a concurrent operation fails."""

    CODE_PREFIX = "CONCURRENT_"

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        super().__init__(message, f"{self.CODE_PREFIX}001", error_details)


# Storage exceptions
class StorageException(HideSyncException):
    """Base exception for storage-related errors."""

    CODE_PREFIX = "STORAGE_"

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, f"{self.CODE_PREFIX}001", details or {})


class InvalidPathException(StorageException):
    """Raised when an invalid file path is provided."""

    def __init__(self, path: str, reason: Optional[str] = None):
        details = {"path": path}
        if reason:
            details["reason"] = reason
        message = f"Invalid path: {path}"
        if reason:
            message += f" - {reason}"
        super().__init__(message=message, details=details)


class StorageLocationNotFoundException(StorageException):
    """Raised when a requested storage location does not exist."""

    def __init__(self, location_id: Any):
        message = f"Storage location with ID {location_id} not found"
        details = {"location_id": location_id}
        super().__init__(message=message, details=details)


# Tool-related exceptions
class ToolException(HideSyncException):
    """Base exception for tool-related errors."""

    CODE_PREFIX = "TOOL_"


class ToolNotFoundException(ToolException):  # Added specific ToolNotFoundException
    """Raised when a requested tool does not exist."""

    def __init__(self, tool_id: int):
        super().__init__(
            f"Tool with ID {tool_id} not found",
            f"{self.CODE_PREFIX}002",  # Assign a new code
            {"tool_id": tool_id},
        )


class ToolNotAvailableException(ToolException):
    """Raised when a tool is not available for checkout or use."""

    def __init__(
        self,
        message: str,
        tool_id: Optional[int] = None,
        current_status: Optional[str] = None,
    ):  # Allow passing message directly
        details = {}
        if tool_id is not None:
            details["tool_id"] = tool_id
        if current_status is not None:
            details["current_status"] = current_status
        super().__init__(
            message,  # Use the provided message
            f"{self.CODE_PREFIX}001",
            details,
        )


# --- ADDED DEFINITIONS START ---


class MaintenanceNotFoundException(ToolException):
    """Raised when a requested tool maintenance record does not exist."""

    def __init__(self, maintenance_id: int):
        """
        Initialize the MaintenanceNotFoundException.

        Args:
            maintenance_id: The ID of the maintenance record that was not found.
        """
        super().__init__(
            message=f"Tool maintenance record with ID {maintenance_id} not found",
            code=f"{self.CODE_PREFIX}003",  # Assign a specific code (e.g., TOOL_003)
            details={"maintenance_id": maintenance_id},
        )


class CheckoutNotFoundException(ToolException):
    """Raised when a requested tool checkout record does not exist."""

    def __init__(self, checkout_id: int):
        """
        Initialize the CheckoutNotFoundException.

        Args:
            checkout_id: The ID of the checkout record that was not found.
        """
        super().__init__(
            message=f"Tool checkout record with ID {checkout_id} not found",
            code=f"{self.CODE_PREFIX}004",  # Assign a specific code (e.g., TOOL_004)
            details={"checkout_id": checkout_id},
        )


# --- ADDED DEFINITIONS END ---


class InvalidStatusTransitionException(BusinessRuleException):
    """Raised when an invalid status transition is attempted."""

    def __init__(self, message: str, allowed_transitions: Optional[List[str]] = None):
        details = {}
        if allowed_transitions is not None:
            details["allowed_transitions"] = allowed_transitions
        super().__init__(
            message, rule_name="INVALID_STATUS_TRANSITION", details=details
        )


class DuplicateEntityException(HideSyncException):
    """Raised when an attempt is made to create an entity that already exists."""

    def __init__(
        self,
        message: str = "Duplicate entity detected",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, "DUPLICATE_ENTITY", details or {})


class PermissionDeniedException(SecurityException):
    """Raised when a user lacks permission for an action (legacy or specific use)."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, f"{self.CODE_PREFIX}004", {})  # Example code


class FileStorageException(StorageException):
    """
    Exception raised for file storage-specific errors.
    """

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        error_details = details or {}
        if file_path:
            error_details["file_path"] = file_path
        if operation:
            error_details["operation"] = operation
        super().__init__(message=message, details=error_details)


class DatabaseException(HideSyncException):
    """
    Exception raised for database-related errors.
    """

    CODE_PREFIX = "DATABASE_"

    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        entity_type: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        error_details = details or {}
        if query:
            error_details["query"] = query
        if entity_type:
            error_details["entity_type"] = entity_type
        code = error_code or f"{self.CODE_PREFIX}001"
        super().__init__(message=message, code=code, details=error_details)


class ConnectionPoolExhaustedException(DatabaseException):
    """
    Exception raised when the database connection pool is exhausted.
    """

    def __init__(
        self,
        message: str = "Database connection pool exhausted",
        timeout: Optional[int] = None,
        pool_size: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        error_details = details or {}
        if timeout is not None:
            error_details["timeout"] = timeout
        if pool_size is not None:
            error_details["pool_size"] = pool_size
        super().__init__(
            message=message, error_code=f"{self.CODE_PREFIX}002", details=error_details
        )


class EncryptionKeyMissingException(SecurityException):
    """
    Exception raised when an encryption key is required but not available.
    """

    def __init__(
        self,
        message: str = "Encryption key is missing or invalid",
        key_source: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        error_details = details or {}
        if key_source:
            error_details["key_source"] = key_source
        super().__init__(
            message=message, code=f"{self.CODE_PREFIX}005", details=error_details
        )


class SupplierException(HideSyncException):
    """Base exception for supplier-related errors."""

    CODE_PREFIX = "SUPPLIER_"


class SupplierNotFoundException(SupplierException):
    """Raised when a requested supplier does not exist."""

    def __init__(self, supplier_id: int):
        super().__init__(
            message=f"Supplier with ID {supplier_id} not found",
            code=f"{self.CODE_PREFIX}001",
            details={"supplier_id": supplier_id},
        )


# --- (Existing code ends here) ---
