# app/db/enum_patch.py
"""
SQLAlchemy Enum type patch for case-insensitive handling.

This module patches SQLAlchemy's Enum type implementation to handle
case differences between database values and enum definitions.
"""

import logging
from sqlalchemy.sql import sqltypes
import enum

logger = logging.getLogger(__name__)

# Store original method that we'll override
original_object_value_for_elem = sqltypes.Enum._object_value_for_elem

# Case-insensitive lookup cache for all enum types
_enum_case_maps = {}

def _build_case_map(enum_class):
    """Build case-insensitive lookup maps for an enum class."""
    if enum_class in _enum_case_maps:
        return _enum_case_maps[enum_class]
        
    name_map = {}
    value_map = {}
    
    for member in enum_class:
        # Map lowercase names to actual enum members
        if hasattr(member, 'name'):
            name_map[member.name.lower()] = member
            
        # Map lowercase string values to enum members
        if hasattr(member, 'value') and isinstance(member.value, str):
            value_map[member.value.lower()] = member
    
    _enum_case_maps[enum_class] = {
        'names': name_map,
        'values': value_map
    }
    
    return _enum_case_maps[enum_class]

def case_insensitive_object_value_for_elem(self, value):
    """Case-insensitive version of Enum._object_value_for_elem."""
    if value is None:
        return None
        
    # Handle non-string values normally
    if not isinstance(value, str):
        return original_object_value_for_elem(self, value)
    
    # Try case-insensitive lookup for strings
    enum_class = self.enum_class
    if enum_class:
        case_map = _build_case_map(enum_class)
        value_lower = value.lower()
        
        # Try to match by value first 
        if value_lower in case_map['values']:
            return case_map['values'][value_lower]
            
        # Then try by name
        if value_lower in case_map['names']:
            return case_map['names'][value_lower]
    
    # Fall back to original implementation if no match found
    try:
        return original_object_value_for_elem(self, value)
    except LookupError as e:
        # Log before raising to help with debugging
        logger.warning(
            f"Case-insensitive lookup failed for value '{value}' in enum {enum_class.__name__ if enum_class else 'unknown'}"
        )
        
        # For safety - provide all valid options
        valid_options = []
        if enum_class:
            for member in enum_class:
                valid_options.append(f"{member.name}")
                
        if valid_options:
            logger.info(f"Valid options for {enum_class.__name__}: {', '.join(valid_options)}")
        
        raise

# Apply the patch
sqltypes.Enum._object_value_for_elem = case_insensitive_object_value_for_elem

logger.info("SQLAlchemy Enum type patched for case-insensitive handling")