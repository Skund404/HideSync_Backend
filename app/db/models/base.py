# File: app/db/models/base.py
"""
Base models and mixins for the Leathercraft ERP system.

This module provides the foundation for all database models in the system, including:
- Base SQLAlchemy model class
- Common mixins for shared functionality (timestamps, auditing, validation, etc.)
- Model registry for tracking and managing model classes
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, TypeVar, Set, ClassVar
import json
import uuid
import re

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, JSON, event
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
from sqlalchemy.orm import validates, Session
from sqlalchemy import MetaData

# Create the SQLAlchemy base

Base = declarative_base(metadata=MetaData())


# Type variable for model classes
T = TypeVar("T", bound="AbstractBase")


class ModelValidationError(ValueError):
    """
    Exception raised for model validation errors.

    Attributes:
        model: The model instance that failed validation
        field: The field that failed validation
        message: Explanation of the error
    """

    def __init__(self, model: Any, field: str, message: str):
        self.model = model
        self.field = field
        self.message = message
        super().__init__(
            f"Validation error in {model.__class__.__name__}.{field}: {message}"
        )


class ModelRegistry:
    """
    Registry for tracking and managing model classes.

    This class maintains a registry of all model types to facilitate operations
    across models such as migrations, validation, and audit logging.
    """

    _models: Dict[str, Type[Base]] = {}

    @classmethod
    def register(cls, model_class: Type[Base]) -> None:
        """
        Register a model class in the registry.

        Args:
            model_class: The model class to register
        """
        cls._models[model_class.__name__] = model_class

    @classmethod
    def get_model(cls, name: str) -> Optional[Type[Base]]:
        """
        Get a model class by name.

        Args:
            name: The name of the model class

        Returns:
            The model class if found, None otherwise
        """
        return cls._models.get(name)

    @classmethod
    def get_all_models(cls) -> Dict[str, Type[Base]]:
        """
        Get all registered model classes.

        Returns:
            Dictionary mapping model names to model classes
        """
        return cls._models.copy()


class ValidationMixin:
    """
    Mixin providing data validation capabilities.

    This mixin adds methods for validating model data before saving to the database,
    including field-level validation, cross-field validation, and custom business rules.
    """

    # Set of fields that should be validated
    __validated_fields__: ClassVar[Set[str]] = set()

    def validate(self) -> None:
        """
        Validate all fields in the model.

        Raises:
            ModelValidationError: If validation fails for any field
        """
        for field in self.__validated_fields__:
            if hasattr(self, f"validate_{field}"):
                value = getattr(self, field)
                validator = getattr(self, f"validate_{field}")
                validator(field, value)

    @validates("email")
    def validate_email(self, key: str, email: Optional[str]) -> Optional[str]:
        """
        Validate email format.

        Args:
            key: Field name ('email')
            email: Email address to validate

        Returns:
            The validated email address

        Raises:
            ModelValidationError: If email format is invalid
        """
        if email is not None:
            email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_pattern, email):
                raise ModelValidationError(self, key, "Invalid email format")
        return email

    @validates("phone")
    def validate_phone(self, key: str, phone: Optional[str]) -> Optional[str]:
        """
        Validate phone number format.

        Args:
            key: Field name ('phone')
            phone: Phone number to validate

        Returns:
            The validated phone number

        Raises:
            ModelValidationError: If phone format is invalid
        """
        if phone is not None:
            # Remove all non-numeric characters for validation
            digits_only = re.sub(r"\D", "", phone)
            # Check if we have a reasonable number of digits
            if not (7 <= len(digits_only) <= 15):
                raise ModelValidationError(
                    self, key, "Phone number must have 7-15 digits"
                )
        return phone


class TimestampMixin:
    """
    Mixin providing automatic timestamp functionality.

    Adds created_at and updated_at timestamps that are automatically
    maintained when records are created or updated.
    """

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CostingMixin:
    """
    Mixin providing cost tracking and calculation functionality.

    Adds fields and methods for tracking costs, calculating margins, and
    maintaining pricing information.
    """

    cost_price = Column(Float, nullable=True)
    retail_price = Column(Float, nullable=True)
    wholesale_price = Column(Float, nullable=True)
    cost_breakdown = Column(JSON, nullable=True)

    def calculate_margin(self, price_type: str = "retail") -> Optional[float]:
        """
        Calculate the profit margin based on cost and specified price.

        Args:
            price_type: Type of price to use ('retail' or 'wholesale')
        """
        if not self.cost_price:
            return None

        price = getattr(self, f"{price_type}_price", None)
        if not price:
            return None

        return ((price - self.cost_price) / price) * 100


class TrackingMixin:
    """
    Mixin providing tracking information for model instances.

    Adds fields for tracking who created and last modified records,
    as well as source information for audit trail purposes.
    """

    created_by = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)
    source = Column(
        String(50), nullable=True
    )  # Where the record came from (e.g., 'manual', 'import', 'sync')
    source_id = Column(String(100), nullable=True)  # Original ID in the source system


class ComplianceMixin:
    """
    Mixin providing compliance-related functionality.

    Adds fields and methods for tracking compliance information,
    such as GDPR consent, privacy policy versions, etc.
    """

    consent_version = Column(String(20), nullable=True)
    consent_date = Column(DateTime, nullable=True)
    is_gdpr_compliant = Column(Boolean, default=False)
    compliance_notes = Column(JSON, nullable=True)

    def record_consent(self, version: str) -> None:
        """
        Record that consent has been given for a specific version.

        Args:
            version: Version of terms/privacy policy that was consented to
        """
        self.consent_version = version
        self.consent_date = datetime.now(timezone.utc)
        self.is_gdpr_compliant = True


class AuditMixin:
    """
    Mixin providing comprehensive audit trail functionality.

    Maintains a history of changes to model instances, including
    who made the changes, when, and what was changed.
    """

    change_history = Column(JSON, default=lambda: [])

    def record_change(self, user: str, changes: Dict[str, Any]) -> None:
        """
        Record a change to the model instance.

        Args:
            user: Username or ID of the user who made the change
            changes: Dictionary of changes {field_name: new_value}
        """
        if self.change_history is None:
            self.change_history = []

        history_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": user,
            "changes": changes,
        }

        self.change_history.append(history_entry)


class AbstractBase(Base):
    """
    Abstract base class for all model entities.

    Provides common functionality and structure for all models,
    including primary key, UUID, and standard behavior.

    Attributes:
        id: Primary key ID (auto-incremented)
        uuid: Unique identifier (UUID) for the record
    """

    __abstract__ = True
    # __table_args__ = {'extend_existing': True} #Added it to Base.

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, default=lambda: str(uuid.uuid4()))
    is_active = Column(Boolean, default=True)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the model instance to a dictionary.

        Returns:
            Dictionary representation of the model instance
        """
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """
        Create a model instance from a dictionary.

        Args:
            data: Dictionary containing field values

        Returns:
            New model instance
        """
        return cls(
            **{k: v for k, v in data.items() if k in cls.__table__.columns.keys()}
        )


# Register model class events
@event.listens_for(AbstractBase, "after_insert", propagate=True)
def after_insert(mapper, connection, target):
    """Register models after insert to track model registry."""
    if hasattr(target, "validate"):
        target.validate()

    # Register the model class if not already registered
    ModelRegistry.register(target.__class__)