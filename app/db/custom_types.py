"""
Custom SQLAlchemy column types for HideSync.

This module provides specialized column types that extend SQLAlchemy's functionality,
particularly for handling case-insensitive enum values in the database.
"""

from sqlalchemy import types
from sqlalchemy.types import Enum, TypeDecorator
import enum
import logging
from typing import Dict, Any, Optional, Type, Union, Set

logger = logging.getLogger(__name__)


class CaseInsensitiveEnum(TypeDecorator):
    """
    SQLAlchemy column type for case-insensitive Enum handling.

    This type allows database values that differ only in case from their enum
    counterparts to be correctly mapped to the appropriate enum members.
    It works with:
    - Different case in member names (e.g., "IN_STOCK" vs "in_stock")
    - Different case in member values (e.g., enum.value "in_stock" vs DB "IN_STOCK")

    Usage:
        class MyModel(Base):
            status = Column(CaseInsensitiveEnum(SomeEnum), default=SomeEnum.ACTIVE)
    """
    impl = Enum
    cache_ok = True

    def __init__(self, enum_class, **kw):
        """
        Initialize with the enum class and build lookup maps.

        Args:
            enum_class: The enum class to use
            **kw: Additional arguments for the Enum constructor
        """
        self.enum_class = enum_class

        # Build case-insensitive lookup maps
        self._build_lookup_maps()

        super(CaseInsensitiveEnum, self).__init__(enum_class, **kw)

    def _build_lookup_maps(self):
        """Build case-insensitive lookup dictionaries for faster matching."""
        # Map for lowercase enum names to actual enum members
        self._name_map = {
            member.name.lower(): member
            for member in self.enum_class
        }

        # Map for lowercase enum values to actual enum members (for string values)
        self._value_map = {}
        for member in self.enum_class:
            if isinstance(member.value, str):
                self._value_map[member.value.lower()] = member

        # Create a set of all valid lowercase names and values for quick validation
        self._valid_lowercase = set(self._name_map.keys()) | set(self._value_map.keys())

        # Track seen values for warning about inconsistent cases
        self._seen_variants: Dict[str, Set[str]] = {}

    def process_bind_param(self, value, dialect):
        """
        Process the value before sending to database.

        Args:
            value: The value from Python code
            dialect: SQLAlchemy dialect

        Returns:
            The value to store in database
        """
        if value is None:
            return None

        # If it's already an enum member, use its value
        if isinstance(value, self.enum_class):
            return value.value

        # If it's a string, try to find matching enum
        if isinstance(value, str):
            value_lower = value.lower()

            # First check if it matches an enum name
            if value_lower in self._name_map:
                enum_member = self._name_map[value_lower]
                return enum_member.value

            # Then check if it matches an enum value
            if value_lower in self._value_map:
                enum_member = self._value_map[value_lower]
                return enum_member.value

            # Record this unknown value for logging
            self._log_unknown_value(value)

        # If we reach here, let the default implementation handle it
        try:
            return super(CaseInsensitiveEnum, self).process_bind_param(value, dialect)
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(
                f"Failed to convert value '{value}' to {self.enum_class.__name__}: {str(e)}. "
                f"Valid values are: {', '.join(sorted(self._valid_lowercase))}"
            )
            return value  # Return as-is and let the database handle any errors

    def process_result_value(self, value, dialect):
        """
        Process the value from database query results.

        Args:
            value: The database value
            dialect: SQLAlchemy dialect

        Returns:
            The corresponding enum member
        """
        if value is None:
            return None

        # Check for case-insensitive string matches
        if isinstance(value, str):
            value_lower = value.lower()

            # Check original casing in mapping
            if value != value_lower:
                # Log if this is the first time we've seen this mixed-case variant
                self._record_case_variant(value)

            # First try to match by enum value (most common case)
            if value_lower in self._value_map:
                return self._value_map[value_lower]

            # Then try by enum name
            if value_lower in self._name_map:
                return self._name_map[value_lower]

        # Try the standard approach as fallback
        try:
            return super(CaseInsensitiveEnum, self).process_result_value(value, dialect)
        except (ValueError, KeyError, TypeError) as e:
            # Instead of raising an exception, log a warning and return None
            logger.warning(
                f"Could not convert '{value}' to {self.enum_class.__name__} enum: {str(e)}. "
                f"Valid values are: {', '.join(sorted(self._valid_lowercase))}"
            )
            return None

    def _record_case_variant(self, value: str) -> None:
        """
        Record case variants for logging and analysis.

        Args:
            value: The database value with potentially inconsistent case
        """
        lower_value = value.lower()

        if lower_value not in self._seen_variants:
            self._seen_variants[lower_value] = {value}

            # Only log if we have a corresponding enum
            if lower_value in self._value_map or lower_value in self._name_map:
                canonical = None
                if lower_value in self._value_map:
                    canonical = self._value_map[lower_value].value
                elif lower_value in self._name_map:
                    canonical = self._name_map[lower_value].name

                logger.info(
                    f"Found case variant for {self.enum_class.__name__}: "
                    f"'{value}' (canonical form: '{canonical}')"
                )
        elif value not in self._seen_variants[lower_value]:
            self._seen_variants[lower_value].add(value)
            logger.debug(f"Found additional case variant: '{value}'")

    def _log_unknown_value(self, value: str) -> None:
        """
        Log warning for unknown values.

        Args:
            value: The unknown value
        """
        logger.warning(
            f"Value '{value}' is not a valid {self.enum_class.__name__} enum member. "
            f"Valid values are: {', '.join(sorted(self._valid_lowercase))}"
        )