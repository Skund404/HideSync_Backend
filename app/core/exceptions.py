# File: app/core/exceptions.py

from typing import Dict, Any, List, Optional

from typing import Dict, List, Any
import json
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator

from app.db.models.enums import (
    CustomerStatus,
    CustomerTier,
    CustomerSource,
    CommunicationChannel,
    CommunicationType,
)
from app.schemas.customer import CustomerBase


class HideSyncException(Exception):
    """Base exception for all HideSync errors."""

    def __init__(
        self, message: str, code: str, details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a HideSync exception.

        Args:
            message: Human-readable error message
            code: Machine-processable error code
            details: Additional error details
        """
        self.message = message
        self.code = code
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
        """
        Initialize entity not found exception.

        Args:
            entity_type: Type of entity that was not found
            entity_id: ID of the entity that was not found
        """
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
        """
        Initialize material not found exception.

        Args:
            material_id: ID of the material that was not found
        """
        super().__init__(
            f"Material with ID {material_id} not found",
            f"{self.CODE_PREFIX}001",
            {"material_id": material_id},
        )


class InsufficientInventoryException(MaterialException):
    """Raised when attempting to use more material than available."""

    def __init__(self, material_id: int, requested: float, available: float):
        """
        Initialize insufficient inventory exception.

        Args:
            material_id: ID of the material
            requested: Quantity requested
            available: Quantity available
        """
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
        """
        Initialize project not found exception.

        Args:
            project_id: ID of the project that was not found
        """
        super().__init__(
            f"Project with ID {project_id} not found",
            f"{self.CODE_PREFIX}001",
            {"project_id": project_id},
        )


class InvalidProjectStatusTransitionException(ProjectException):
    """Raised when an invalid project status transition is attempted."""

    def __init__(self, project_id: int, current_status: str, new_status: str):
        """
        Initialize invalid project status transition exception.

        Args:
            project_id: ID of the project
            current_status: Current status of the project
            new_status: Attempted new status
        """
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
        """
        Initialize customer not found exception.

        Args:
            customer_id: ID of the customer that was not found
        """
        super().__init__(
            f"Customer with ID {customer_id} not found",
            f"{self.CODE_PREFIX}001",
            {"customer_id": customer_id},
        )


# Validation exceptions
class ValidationException(HideSyncException):
    """Raised when input validation fails."""

    def __init__(self, message: str, validation_errors: Dict[str, List[str]]):
        """
        Initialize validation exception.

        Args:
            message: Human-readable error message
            validation_errors: Dictionary of field names to error messages
        """
        super().__init__(
            message, "VALIDATION_001", {"validation_errors": validation_errors}
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
        """
        Initialize concurrent modification exception.

        Args:
            message: Human-readable error message
            expected_version: Expected version of the entity
            actual_version: Actual version of the entity
        """
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
        """
        Initialize unauthorized exception.

        Args:
            message: Human-readable error message
        """
        super().__init__(message, f"{self.CODE_PREFIX}001", {})


class ForbiddenException(SecurityException):
    """Raised when a user is forbidden from accessing a resource."""

    def __init__(self, resource_type: str, resource_id: Any = None):
        """
        Initialize forbidden exception.

        Args:
            resource_type: Type of resource being accessed
            resource_id: Optional ID of the resource
        """
        details = {"resource_type": resource_type}
        if resource_id is not None:
            details["resource_id"] = resource_id

        super().__init__(
            f"Access forbidden to {resource_type}"
            + (f" with ID {resource_id}" if resource_id else ""),
            f"{self.CODE_PREFIX}002",
            details,
        )


# Integration exceptions
class IntegrationException(HideSyncException):
    """Base exception for integration-related errors."""

    CODE_PREFIX = "INTEGRATION_"


class ExternalServiceException(IntegrationException):
    """Raised when an external service call fails."""

    def __init__(
        self, service_name: str, message: str, original_error: Optional[str] = None
    ):
        """
        Initialize external service exception.

        Args:
            service_name: Name of the external service
            message: Human-readable error message
            original_error: Optional original error message from the external service
        """
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
        """
        Initialize business rule exception.

        Args:
            message: Human-readable error message
            rule_name: Optional name of the business rule that was violated
            details: Additional details about the violation
        """
        error_details = details or {}
        if rule_name:
            error_details["rule_name"] = rule_name

        super().__init__(message, f"{self.CODE_PREFIX}001", error_details)


class BusinessRuleError(BusinessRuleException):
    """
    Alternative name for BusinessRuleException for backward compatibility.

    This class exists to maintain compatibility with existing code that
    might use BusinessRuleError instead of BusinessRuleException.
    """

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
        """
        Initialize concurrent operation exception.

        Args:
            message: Human-readable error message
            operation: Optional name of the operation that failed
            details: Additional details about the failure
        """
        error_details = details or {}
        if operation:
            error_details["operation"] = operation

        super().__init__(message, f"{self.CODE_PREFIX}001", error_details)


# Storage exceptions
class StorageException(HideSyncException):
    """Raised when a storage operation fails."""

    CODE_PREFIX = "STORAGE_"

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialize storage exception.

        Args:
            message: Human-readable error message
            details: Additional details about the storage error
        """
        super().__init__(message, f"{self.CODE_PREFIX}001", details or {})


class InvalidPathException(StorageException):
    """Raised when an invalid file path is provided."""

    def __init__(self, path: str, reason: Optional[str] = None):
        """
        Initialize invalid path exception.

        Args:
            path: The invalid path
            reason: Optional reason why the path is invalid
        """
        details = {"path": path}
        if reason:
            details["reason"] = reason

        message = f"Invalid path: {path}"
        if reason:
            message += f" - {reason}"

        super().__init__(message, details)


class SecurityException(HideSyncException):
    """Exception raised for security-related errors."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        self.status_code = 500  # Internal server error for security issues


# Storage-related exceptions
class StorageException(HideSyncException):
    """Base exception for storage-related errors."""

    CODE_PREFIX = "STORAGE_"


# If you don't already have this class defined
class StorageLocationNotFoundException(StorageException):
    """Raised when a requested storage location does not exist."""

    def __init__(self, location_id: Any):
        """
        Initialize storage location not found exception.

        Args:
            location_id: ID of the storage location that was not found
        """
        super().__init__(
            f"Storage location with ID {location_id} not found",
            f"{self.CODE_PREFIX}002",  # Using 002 to follow your pattern
            {"location_id": location_id},
        )


# Tool-related exceptions
class ToolException(HideSyncException):
    """Base exception for tool-related errors."""

    CODE_PREFIX = "TOOL_"


class ToolNotAvailableException(ToolException):
    """Raised when a tool is not available for checkout or use."""

    def __init__(self, tool_id: int, reason: str = "Tool is currently unavailable"):
        """
        Initialize tool not available exception.

        Args:
            tool_id: ID of the tool
            reason: Optional reason why the tool is unavailable
        """
        super().__init__(
            f"Tool with ID {tool_id} is not available: {reason}",
            f"{self.CODE_PREFIX}001",
            {"tool_id": tool_id, "reason": reason},
        )


class AuthenticationException(SecurityException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        """
        Initialize authentication exception.

        Args:
            message: Human-readable error message
        """
        super().__init__(message, f"{self.CODE_PREFIX}003", {})


class CustomerStatusUpdate(BaseModel):
    """Schema for customer status update requests."""

    status: CustomerStatus = Field(
        ..., description="New status to assign to the customer"
    )
    reason: Optional[str] = Field(None, description="Reason for the status change")


class CustomerTierUpdate(BaseModel):
    """Schema for customer tier update requests."""

    tier: CustomerTier = Field(..., description="New tier to assign to the customer")
    reason: Optional[str] = Field(None, description="Reason for the tier change")


# For communications
class CustomerCommunicationBase(BaseModel):
    """Base schema for customer communication data."""

    communication_date: Optional[datetime] = Field(
        None, description="Date and time of the communication"
    )
    channel: CommunicationChannel = Field(..., description="Communication channel used")
    communication_type: CommunicationType = Field(
        ..., description="Type of communication"
    )
    subject: Optional[str] = Field(None, description="Subject of the communication")
    content: str = Field(..., description="Content of the communication")
    direction: str = Field(
        "OUTBOUND", description="Direction of communication (INBOUND/OUTBOUND)"
    )
    needs_response: Optional[bool] = Field(
        False, description="Whether this communication needs a response"
    )
    related_entity_type: Optional[str] = Field(
        None, description="Type of related entity (sale, project, etc.)"
    )
    related_entity_id: Optional[str] = Field(None, description="ID of related entity")
    meta_data: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @validator("meta_data", pre=True)
    def validate_meta_data(cls, v):
        """Convert string to dict if needed."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v or {}


class CustomerCommunicationCreate(CustomerCommunicationBase):
    """Schema for creating customer communication records."""

    pass


class CustomerCommunicationResponse(CustomerCommunicationBase):
    """Schema for customer communication responses."""

    id: int = Field(..., description="ID of the communication record")
    customer_id: int = Field(..., description="ID of the customer")
    staff_id: Optional[int] = Field(None, description="ID of the staff member")
    response_content: Optional[str] = Field(
        None, description="Content of the response if any"
    )
    response_date: Optional[datetime] = Field(
        None, description="Date of the response if any"
    )
    created_at: datetime = Field(..., description="Date the record was created")
    updated_at: datetime = Field(..., description="Date the record was last updated")

    class Config:
        from_attributes = True


# For analytics
class CustomerAnalytics(BaseModel):
    """Schema for customer analytics data."""

    total_customers: int = Field(..., description="Total number of customers")
    active_customers: int = Field(..., description="Number of active customers")
    new_customers_30d: int = Field(..., description="New customers in the last 30 days")
    customer_distribution: Dict[str, Dict[str, int]] = Field(
        ..., description="Distribution of customers by status, tier, source"
    )
    average_lifetime_value: float = Field(
        ..., description="Average customer lifetime value"
    )
    top_customers: List[Dict[str, Any]] = Field(
        ..., description="Top customers by sales volume"
    )


# For bulk import/export
class CustomerImportRow(CustomerBase):
    """Schema for a single customer row in import data."""

    pass


class CustomerImport(BaseModel):
    """Schema for bulk customer import requests."""

    customers: List[CustomerImportRow] = Field(
        ..., description="List of customers to import"
    )
    update_existing: bool = Field(
        False, description="Whether to update existing customers"
    )


class BulkImportResult(BaseModel):
    """Schema for bulk import operation results."""

    total_processed: int = Field(..., description="Total number of records processed")
    created: int = Field(..., description="Number of records created")
    updated: int = Field(..., description="Number of records updated")
    failed: int = Field(..., description="Number of records that failed to import")
    errors: List[Dict[str, Any]] = Field(..., description="Details of import errors")

# Add this to app/core/exceptions.py, after the ProjectException classes

class InvalidStatusTransitionException(BusinessRuleException):
    """Raised when an invalid status transition is attempted."""

    def __init__(
        self,
        message: str,
        allowed_transitions: Optional[List[str]] = None
    ):
        """
        Initialize invalid status transition exception.

        Args:
            message: Human-readable error message describing the invalid transition
            allowed_transitions: Optional list of allowed status transitions
        """
        details = {}
        if allowed_transitions is not None:
            details["allowed_transitions"] = allowed_transitions

        super().__init__(message, "INVALID_STATUS_TRANSITION", details)


class DuplicateEntityException(HideSyncException):
    """Raised when an attempt is made to create an entity that already exists."""

    def __init__(self, message: str = "Duplicate entity detected", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "DUPLICATE_ENTITY", details or {})