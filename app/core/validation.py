# File: app/core/validation.py

from typing import Dict, List, Any, Optional, Callable, Type, Union, TypeVar, cast
import inspect
import functools
import re
from datetime import datetime
from app.core.exceptions import ValidationException

T = TypeVar("T")


class ValidationResult:
    """Container for validation results."""

    def __init__(self):
        """Initialize an empty validation result."""
        self.errors: Dict[str, List[str]] = {}

    def add_error(self, field: str, message: str) -> None:
        """
        Add an error for a specific field.

        Args:
            field: Field name with the error
            message: Error message
        """
        if field not in self.errors:
            self.errors[field] = []
        self.errors[field].append(message)

    @property
    def is_valid(self) -> bool:
        """
        Check if validation passed (no errors).

        Returns:
            True if validation passed, False otherwise
        """
        return len(self.errors) == 0

    def __bool__(self) -> bool:
        """
        Boolean representation is is_valid.

        Returns:
            True if validation passed, False otherwise
        """
        return self.is_valid

    def to_dict(self) -> Dict[str, List[str]]:
        """
        Convert validation result to dictionary.

        Returns:
            Dictionary of field names to error messages
        """
        return self.errors


def validate_input(validator: Callable) -> Callable:
    """
    Decorator to validate service inputs.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Only validate the first argument if present
            if args:
                result = validator(args[0])
            else:
                # No arguments to validate
                result = ValidationResult()
                result.add_error("input", "No data provided for validation")

            # Raise exception if validation failed
            if not result.is_valid:
                raise ValidationException("Input validation failed", result.to_dict())

            # Call original function with all arguments
            return func(self, *args, **kwargs)

        return wrapper
    return decorator

def validate_entity(
    entity_class: Type, exclude_fields: Optional[List[str]] = None
) -> Callable:
    """
    Create a validator function for an entity.

    Args:
        entity_class: Entity class to validate against
        exclude_fields: Fields to exclude from validation

    Returns:
        Validation function
    """
    exclude_fields = exclude_fields or []

    def validator(data: Dict[str, Any]) -> ValidationResult:
        """
        Validate data against entity requirements.

        Args:
            data: Dictionary of entity data

        Returns:
            ValidationResult with any validation errors
        """
        result = ValidationResult()

        # Example validation logic (would be more sophisticated in practice)
        for field, requirements in getattr(
            entity_class, "FIELD_REQUIREMENTS", {}
        ).items():
            if field in exclude_fields or field not in data:
                continue

            value = data[field]

            # Required field check
            if requirements.get("required", False) and value is None:
                result.add_error(field, f"{field} is required")
                continue

            # Type validation
            expected_type = requirements.get("type")
            if (
                expected_type
                and value is not None
                and not isinstance(value, expected_type)
            ):
                result.add_error(
                    field, f"{field} must be of type {expected_type.__name__}"
                )

            # Min/max validation for numeric fields
            if isinstance(value, (int, float)):
                if "min" in requirements and value < requirements["min"]:
                    result.add_error(
                        field, f"{field} must be at least {requirements['min']}"
                    )
                if "max" in requirements and value > requirements["max"]:
                    result.add_error(
                        field, f"{field} must be at most {requirements['max']}"
                    )

            # Length validation for string fields
            if isinstance(value, str):
                if (
                    "min_length" in requirements
                    and len(value) < requirements["min_length"]
                ):
                    result.add_error(
                        field,
                        f"{field} must be at least {requirements['min_length']} characters",
                    )
                if (
                    "max_length" in requirements
                    and len(value) > requirements["max_length"]
                ):
                    result.add_error(
                        field,
                        f"{field} must be at most {requirements['max_length']} characters",
                    )

            # Custom validation
            custom_validator = requirements.get("validator")
            if custom_validator and not custom_validator(value):
                result.add_error(
                    field,
                    requirements.get("error_message", f"Invalid value for {field}"),
                )

        return result

    return validator


# Common validators
def validate_email(email: str) -> bool:
    """
    Validate email format.

    Args:
        email: Email address to validate

    Returns:
        True if email is valid, False otherwise
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """
    Validate phone number format.

    Args:
        phone: Phone number to validate

    Returns:
        True if phone number is valid, False otherwise
    """
    # Simple pattern: allows +, digits, spaces, dashes, parentheses
    pattern = r"^[+\d\s\-()]{8,20}$"
    return bool(re.match(pattern, phone))


def validate_date_not_in_past(date: datetime) -> bool:
    """
    Validate date is not in the past.

    Args:
        date: Date to validate

    Returns:
        True if date is not in the past, False otherwise
    """
    return date >= datetime.now()


# Validation helpers
def validate_required_fields(
    data: Dict[str, Any], required_fields: List[str]
) -> ValidationResult:
    """
    Validate that required fields are present and not None.

    Args:
        data: Dictionary of data to validate
        required_fields: List of required field names

    Returns:
        ValidationResult with any validation errors
    """
    result = ValidationResult()

    for field in required_fields:
        if field not in data or data[field] is None:
            result.add_error(field, f"{field} is required")

    return result


def validate_field_length(
    data: Dict[str, Any], field_lengths: Dict[str, Dict[str, int]]
) -> ValidationResult:
    """
    Validate string field lengths.

    Args:
        data: Dictionary of data to validate
        field_lengths: Dictionary of field names to min/max length requirements

    Returns:
        ValidationResult with any validation errors
    """
    result = ValidationResult()

    for field, requirements in field_lengths.items():
        if field not in data or data[field] is None:
            continue

        value = data[field]
        if not isinstance(value, str):
            continue

        if "min" in requirements and len(value) < requirements["min"]:
            result.add_error(
                field, f"{field} must be at least {requirements['min']} characters"
            )

        if "max" in requirements and len(value) > requirements["max"]:
            result.add_error(
                field, f"{field} must be at most {requirements['max']} characters"
            )

    return result


def validate_numeric_range(
    data: Dict[str, Any], numeric_ranges: Dict[str, Dict[str, Union[int, float]]]
) -> ValidationResult:
    """
    Validate numeric field ranges.

    Args:
        data: Dictionary of data to validate
        numeric_ranges: Dictionary of field names to min/max requirements

    Returns:
        ValidationResult with any validation errors
    """
    result = ValidationResult()

    for field, requirements in numeric_ranges.items():
        if field not in data or data[field] is None:
            continue

        value = data[field]
        if not isinstance(value, (int, float)):
            continue

        if "min" in requirements and value < requirements["min"]:
            result.add_error(field, f"{field} must be at least {requirements['min']}")

        if "max" in requirements and value > requirements["max"]:
            result.add_error(field, f"{field} must be at most {requirements['max']}")

    return result
