
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, Tuple
from enum import Enum

# If you're importing the utility functions from utils.py


def normalize_material_type(value):
    """
    Convert material type values to consistent format.

    Handles case insensitive matching for material types.
    Maps uppercase enum keys like "HARDWARE" to proper enum values like "hardware".

    Args:
        value: Original material type value (string, enum, or tuple)

    Returns:
        Normalized string value for material type
    """
    if value is None:
        return None

    # Handle tuple cases
    if isinstance(value, tuple):
        if len(value) == 1:
            return normalize_material_type(value[0])
        return [normalize_material_type(item) for item in value]

    # Handle enum objects
    if hasattr(value, 'value'):
        return value.value

    # Handle string values - this is the key part
    if isinstance(value, str):
        # Map uppercase to lowercase - preserve the exact values as they appear in the enum
        material_type_mapping = {
            'LEATHER': 'leather',
            'HARDWARE': 'hardware',
            'SUPPLIES': 'supplies',
            'THREAD': 'thread',
            'FABRIC': 'fabric',
            'OTHER': 'other'
        }

        # Case insensitive match
        upper_value = value.upper()
        if upper_value in material_type_mapping:
            return material_type_mapping[upper_value]

    # Return original if no mapping found
    return value


def normalize_material_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize material data structure to match frontend expectations.

    Maps fields from backend/seed data format to frontend format:
    - Maps materialType with case-insensitive handling
    - Maps price to sellPrice
    - Drops unnecessary fields (purchaseId, total, etc.)
    - Adds required fields with defaults if missing

    Args:
        data: The original material data dictionary

    Returns:
        Normalized dictionary matching frontend expectations
    """
    if not data:
        return {}

    result = {}

    # Copy fields that map directly
    direct_fields = ['id', 'name', 'quantity', 'notes', 'sku', 'description']
    for field in direct_fields:
        if field in data:
            result[field] = data[field]

    # Special handling for materialType
    if 'materialType' in data:
        result['materialType'] = normalize_material_type(data['materialType'])

    # Map price to sellPrice
    if 'price' in data:
        result['sellPrice'] = data['price']
    elif 'cost' in data:
        result['sellPrice'] = data['cost']

    # Handle unit field
    if 'unit' in data:
        result['unit'] = data['unit']
    else:
        result['unit'] = 'piece'  # Default

    # Add required fields with defaults if missing
    if 'status' not in data:
        result['status'] = 'in_stock'

    if 'quality' not in data:
        result['quality'] = 'standard'

    # Add empty strings for optional fields if missing
    optional_fields = {
        'supplierSku': '',
        'storageLocation': '',
        'notes': '',
        'thumbnail': '',
    }

    for field, default in optional_fields.items():
        if field not in result or result[field] is None:
            result[field] = default

    return result


# Update the serialize_for_response function in app/api/endpoints/materials.py

def serialize_for_response(data: Any) -> Any:
    """
    Convert data to be suitable for FastAPI response validation.
    Handles enum values, timestamps, and nested structures.
    """
    # Handle None values
    if data is None:
        return None

    # Handle tuples that might contain enum values
    if isinstance(data, tuple):
        # If it's a single item tuple, extract the value
        if len(data) == 1:
            data = data[0]
            # If it's a string value from a tuple, return it directly
            if isinstance(data, str):
                return data
            # Otherwise continue with serialization
            return serialize_for_response(data)
        # For multi-item tuples, process each item
        return [serialize_for_response(item) for item in data]

    # Handle lists
    if isinstance(data, list):
        return [serialize_for_response(item) for item in data]

    # Handle ORM models and objects with __dict__
    if hasattr(data, "__dict__"):
        # Convert to dictionary first
        raw_dict = {}
        for key, value in data.__dict__.items():
            if not key.startswith('_'):  # Skip SQLAlchemy internal attributes
                raw_dict[key] = value

        # Use our normalize_material_data function to handle all field mappings
        return normalize_material_data(raw_dict)

    # Handle dictionaries
    if isinstance(data, dict):
        # Use our normalize_material_data function
        return normalize_material_data(data)

    # Handle enum values
    if isinstance(data, Enum):
        return data.value

    # Return regular values unchanged
    return data

