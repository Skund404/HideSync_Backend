# File: app/db/custom_types.py

"""
Custom SQLAlchemy column types for HideSync.

This module provides specialized column types that extend SQLAlchemy's functionality,
particularly for handling case-insensitive enum values.
Date/Time handling now uses standard SQLAlchemy types assuming clean DB data.
"""

from sqlalchemy import types
from sqlalchemy.types import Enum, TypeDecorator # Keep Enum, TypeDecorator
# REMOVE: from sqlalchemy.types import Date, DateTime # No longer needed here
import enum
import logging
from typing import Dict, Any, Optional, Type, Union, Set
# REMOVE: from datetime import datetime, date # No longer needed here
from sqlalchemy.engine import Dialect

# Ensure logger is configured to show debug messages if needed
logger = logging.getLogger(__name__)


class CaseInsensitiveEnum(TypeDecorator):
    """
    SQLAlchemy column type for case-insensitive Enum handling.
    ... (rest of CaseInsensitiveEnum remains unchanged) ...
    """
    impl = Enum
    cache_ok = True

    def __init__(self, enum_class, **kw):
        self.enum_class = enum_class
        self._build_lookup_maps()
        super(CaseInsensitiveEnum, self).__init__(enum_class, **kw)

    def _build_lookup_maps(self):
        self._name_map = {member.name.lower(): member for member in self.enum_class}
        self._value_map = {}
        for member in self.enum_class:
            if isinstance(member.value, str):
                self._value_map[member.value.lower()] = member
        self._valid_lowercase = set(self._name_map.keys()) | set(self._value_map.keys())
        self._seen_variants: Dict[str, Set[str]] = {}

    def process_bind_param(self, value, dialect):
        if value is None: return None
        if isinstance(value, self.enum_class): return value.value
        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower in self._name_map: return self._name_map[value_lower].value
            if value_lower in self._value_map: return self._value_map[value_lower].value
            self._log_unknown_value(value)
        try:
            return super(CaseInsensitiveEnum, self).process_bind_param(value, dialect)
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Failed to convert value '{value}' to {self.enum_class.__name__}: {str(e)}. Valid values are: {', '.join(sorted(self._valid_lowercase))}")
            return value

    def process_result_value(self, value, dialect):
        if value is None: return None
        if isinstance(value, str):
            value_lower = value.lower()
            if value != value_lower: self._record_case_variant(value)
            if value_lower in self._value_map: return self._value_map[value_lower]
            if value_lower in self._name_map: return self._name_map[value_lower]
        try:
            return super(CaseInsensitiveEnum, self).process_result_value(value, dialect)
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Could not convert '{value}' to {self.enum_class.__name__} enum: {str(e)}. Valid values are: {', '.join(sorted(self._valid_lowercase))}")
            return None

    def _record_case_variant(self, value: str) -> None:
        lower_value = value.lower()
        if lower_value not in self._seen_variants:
            self._seen_variants[lower_value] = {value}
            if lower_value in self._value_map or lower_value in self._name_map:
                canonical = self._value_map[lower_value].value if lower_value in self._value_map else self._name_map[lower_value].name
                logger.info(f"Found case variant for {self.enum_class.__name__}: '{value}' (canonical form: '{canonical}')")
        elif value not in self._seen_variants[lower_value]:
            self._seen_variants[lower_value].add(value)
            logger.debug(f"Found additional case variant: '{value}'")

    def _log_unknown_value(self, value: str) -> None:
        logger.warning(f"Value '{value}' is not a valid {self.enum_class.__name__} enum member. Valid values are: {', '.join(sorted(self._valid_lowercase))}")


# --- REMOVED SafeDate Class ---
# class SafeDate(TypeDecorator): ...


# --- REMOVED SafeDateTime Class ---
# class SafeDateTime(TypeDecorator): ...

# Add any other custom types you have here...