# app/api/endpoints/materials.py

from typing import Any, List, Optional, Dict
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.schemas.material import (
    MaterialResponse as Material,
    MaterialCreate,
    MaterialUpdate,
    MaterialSearchParams,
)
from app.services.material_service import MaterialService
from app.core.exceptions import (
    EntityNotFoundException,
    MaterialNotFoundException,
    BusinessRuleException,
    ValidationException,
    InsufficientInventoryException,
)

router = APIRouter()


def serialize_for_response(data: Any) -> Any:
    """
    Convert data to be suitable for FastAPI response.
    Handles enum values, timestamps, and nested structures with proper material type handling.

    Args:
        data: The data to serialize

    Returns:
        Serialized data ready for FastAPI response
    """
    # Handle None values
    if data is None:
        return None

    # Handle lists
    if isinstance(data, list):
        return [serialize_for_response(item) for item in data]

    # Handle tuples
    if isinstance(data, tuple):
        if len(data) == 1:
            return serialize_for_response(data[0])
        return [serialize_for_response(item) for item in data]

    # Handle ORM models and objects with __dict__
    if hasattr(data, "__dict__"):
        result = {}

        # Try different potential field names for material type
        material_type_value = None

        # Check for materialType (camelCase)
        if hasattr(data, 'materialType'):
            material_type_value = data.materialType

        # Check for material_type (snake_case)
        elif hasattr(data, 'material_type'):
            material_type_value = data.material_type

        # Check for type as fallback
        elif hasattr(data, 'type'):
            material_type_value = data.type

        # Now serialize all fields normally
        for key, value in data.__dict__.items():
            # Skip SQLAlchemy internal attributes
            if key.startswith('_'):
                continue

            # Handle special fields
            if key in ('status', 'unit', 'quality'):
                if hasattr(value, 'value'):
                    result[key] = value.value
                elif isinstance(value, str):
                    result[key] = value
                elif isinstance(value, tuple) and len(value) == 1:
                    inner_val = value[0]
                    if hasattr(inner_val, 'value'):
                        result[key] = inner_val.value
                    else:
                        result[key] = str(inner_val)
                elif value is None:
                    # Default values for None
                    if key == 'status':
                        result[key] = 'in_stock'
                    elif key == 'unit':
                        result[key] = 'piece'
                    else:
                        result[key] = None
                else:
                    result[key] = str(value)
            else:
                # Handle normal fields
                if hasattr(value, 'value'):
                    result[key] = value.value
                elif isinstance(value, tuple) and len(value) == 1:
                    inner_val = value[0]
                    if hasattr(inner_val, 'value'):
                        result[key] = inner_val.value
                    else:
                        result[key] = str(inner_val)
                else:
                    result[key] = value

        # Now handle material type - this is the key part
        # If we found a material type field in the object, use its value
        if material_type_value is not None:
            # Extract the actual value
            if hasattr(material_type_value, 'value'):
                material_type_str = material_type_value.value
            elif isinstance(material_type_value, tuple) and len(material_type_value) > 0:
                if hasattr(material_type_value[0], 'value'):
                    material_type_str = material_type_value[0].value
                else:
                    material_type_str = str(material_type_value[0])
            else:
                material_type_str = str(material_type_value)

            # Normalize to lowercase for frontend
            material_mapping = {
                'LEATHER': 'leather',
                'HARDWARE': 'hardware',
                'SUPPLIES': 'supplies',
                'THREAD': 'thread',
                'FABRIC': 'fabric',
                'OTHER': 'other'
            }

            if material_type_str.upper() in material_mapping:
                result['materialType'] = material_mapping[material_type_str.upper()]
            else:
                result['materialType'] = material_type_str.lower()
        else:
            # If no material type found, try to infer from other fields

            # Method 1: Try to infer from name
            name = result.get('name', '').lower()
            if 'leather' in name or 'hide' in name or 'suede' in name or 'buttero' in name or 'chromexcel' in name:
                result['materialType'] = 'leather'
            elif 'buckle' in name or 'snap' in name or 'rivet' in name or 'hook' in name or 'hardware' in name:
                result['materialType'] = 'hardware'
            elif 'thread' in name or 'string' in name or 'cord' in name:
                result['materialType'] = 'thread'
            elif 'fabric' in name or 'canvas' in name or 'cloth' in name:
                result['materialType'] = 'fabric'
            else:
                # Default fallback if no material type can be determined
                result['materialType'] = 'supplies'

        # Check if our seeds have materialType field, it might be in a different case
        for key in list(result.keys()):
            key_lower = key.lower()
            if key_lower == 'materialtype' and key != 'materialType':
                # Found materialType in different case
                value = result.pop(key)

                # Normalize the value
                if isinstance(value, str):
                    material_mapping = {
                        'LEATHER': 'leather',
                        'HARDWARE': 'hardware',
                        'SUPPLIES': 'supplies',
                        'THREAD': 'thread',
                        'FABRIC': 'fabric',
                        'OTHER': 'other'
                    }

                    if value.upper() in material_mapping:
                        result['materialType'] = material_mapping[value.upper()]
                    else:
                        result['materialType'] = value.lower()
                else:
                    result['materialType'] = str(value).lower()

        # Look for seed data fields that might indicate type
        if 'materialType' not in result and 'itemType' in result and result['itemType'] == 'material':
            # This is seed data with itemType but no materialType

            # Check for notes or other fields to infer the type
            notes = result.get('notes', '').lower()
            if 'thickness' in notes or 'leather' in notes:
                result['materialType'] = 'leather'
            elif 'center bar style' in notes or 'hardware' in notes:
                result['materialType'] = 'hardware'
            else:
                # Default fallback for seed data
                result['materialType'] = 'supplies'

        # Ensure we have default values for important fields
        if 'status' not in result:
            result['status'] = 'in_stock'
        if 'quality' not in result:
            result['quality'] = 'standard'

        # Default empty strings for text fields
        for field in ['sku', 'supplierSku', 'storageLocation', 'description', 'notes', 'thumbnail']:
            if field not in result or result[field] is None:
                result[field] = ''

        # Map price to sellPrice if needed
        if 'price' in result and 'sellPrice' not in result:
            result['sellPrice'] = result['price']

        # Final check - ensure materialType exists
        if 'materialType' not in result or result['materialType'] is None:
            result['materialType'] = 'supplies'

        return result

    # Handle dictionaries
    if isinstance(data, dict):
        result = {}

        # Process all fields in the dictionary
        for k, v in data.items():
            # Special handling for material type
            if k.lower() == 'materialtype':
                if v is None:
                    # Try to infer from other fields in dict
                    name = data.get('name', '').lower()
                    if 'leather' in name or 'hide' in name or 'suede' in name:
                        result['materialType'] = 'leather'
                    elif 'hardware' in name or 'buckle' in name or 'rivet' in name:
                        result['materialType'] = 'hardware'
                    else:
                        result['materialType'] = 'supplies'
                else:
                    # Handle based on value type
                    if hasattr(v, 'value'):
                        material_value = v.value
                    elif isinstance(v, tuple) and len(v) > 0:
                        if hasattr(v[0], 'value'):
                            material_value = v[0].value
                        else:
                            material_value = str(v[0])
                    else:
                        material_value = str(v)

                    # Normalize to lowercase for frontend
                    material_mapping = {
                        'LEATHER': 'leather',
                        'HARDWARE': 'hardware',
                        'SUPPLIES': 'supplies',
                        'THREAD': 'thread',
                        'FABRIC': 'fabric',
                        'OTHER': 'other'
                    }

                    if material_value.upper() in material_mapping:
                        result['materialType'] = material_mapping[material_value.upper()]
                    else:
                        result['materialType'] = material_value.lower()
            # Special handling for other enum fields
            elif k in ('status', 'unit', 'quality'):
                if v is None:
                    # Default values for None
                    if k == 'status':
                        result[k] = 'in_stock'
                    elif k == 'unit':
                        result[k] = 'piece'
                    else:
                        result[k] = None
                elif hasattr(v, 'value'):
                    result[k] = v.value
                elif isinstance(v, tuple) and len(v) > 0:
                    if hasattr(v[0], 'value'):
                        result[k] = v[0].value
                    else:
                        result[k] = str(v[0])
                else:
                    result[k] = v
            # Handle price mapping
            elif k == 'price':
                result['sellPrice'] = v
            # Other fields
            else:
                result[k] = v

        # Final check - ensure materialType exists
        if 'materialType' not in result:
            # Look for differently cased keys
            for k in list(result.keys()):
                if k.lower() == 'materialtype' and k != 'materialType':
                    # Found materialType with different casing
                    result['materialType'] = result.pop(k)
                    break

            # Still missing, use default
            if 'materialType' not in result:
                # Handle seed data with itemType
                if 'itemType' in result and result['itemType'] == 'material':
                    # Try to infer from other fields
                    notes = result.get('notes', '').lower()
                    if 'thickness' in notes or 'leather' in notes:
                        result['materialType'] = 'leather'
                    elif 'center bar' in notes or 'hardware' in notes:
                        result['materialType'] = 'hardware'
                    else:
                        result['materialType'] = 'supplies'
                else:
                    # Last resort fallback
                    result['materialType'] = 'supplies'

        # Ensure other required fields exist
        if 'status' not in result:
            result['status'] = 'in_stock'
        if 'quality' not in result:
            result['quality'] = 'standard'

        # Default empty strings for text fields
        for field in ['sku', 'supplierSku', 'storageLocation', 'description', 'notes', 'thumbnail']:
            if field not in result or result[field] is None:
                result[field] = ''

        return result

    # Handle enum values
    if isinstance(data, Enum):
        return data.value

    # Return regular values unchanged
    return data


@router.get(
    "/",
    # We can safely disable response validation to avoid schema conflicts
)
def list_materials(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(
            100, ge=1, le=1000, description="Maximum number of records to return"
        ),
        material_type: Optional[str] = Query(None, description="Filter by material type"),
        quality: Optional[str] = Query(None, description="Filter by material quality"),
        in_stock: Optional[bool] = Query(None, description="Filter by availability"),
        search: Optional[str] = Query(None, description="Search term for name"),
):
    """Retrieve materials with optional filtering and pagination."""
    search_params = MaterialSearchParams(
        material_type=material_type, quality=quality, in_stock=in_stock, search=search
    )

    material_service = MaterialService(db)
    materials = material_service.get_materials(
        skip=skip, limit=limit, search_params=search_params
    )

    # Use our improved serialization function
    serialized_materials = [serialize_for_response(m) for m in materials]

    return serialized_materials


@router.post(
    "/",
    # Disable response model validation
    status_code=status.HTTP_201_CREATED
)
def create_material(
        *,
        db: Session = Depends(get_db),
        material_in: MaterialCreate,
        current_user: Any = Depends(get_current_active_user),
):
    """Create a new material."""
    material_service = MaterialService(db)
    try:
        material = material_service.create_material(material_in, current_user.id)
        return serialize_for_response(material)
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{material_id}",
)
def get_material(
        *,
        db: Session = Depends(get_db),
        material_id: int = Path(
            ..., ge=1, description="The ID of the material to retrieve"
        ),
        current_user: Any = Depends(get_current_active_user),
):
    """
    Get detailed information about a specific material.
    """
    material_service = MaterialService(db)
    try:
        material = material_service.get_material(material_id)
        return serialize_for_response(material)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )


@router.put(
    "/{material_id}",
)
def update_material(
        *,
        db: Session = Depends(get_db),
        material_id: int = Path(..., ge=1, description="The ID of the material to update"),
        material_in: MaterialUpdate,
        current_user: Any = Depends(get_current_active_user),
):
    """
    Update a material.
    """
    material_service = MaterialService(db)
    try:
        material = material_service.update_material(
            material_id, material_in, current_user.id
        )
        return serialize_for_response(material)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(
        *,
        db: Session = Depends(get_db),
        material_id: int = Path(..., ge=1, description="The ID of the material to delete"),
        current_user: Any = Depends(get_current_active_user),
) -> None:
    """
    Delete a material.
    """
    material_service = MaterialService(db)
    try:
        material_service.delete_material(material_id, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{material_id}/adjust-stock")
def adjust_material_stock(
        *,
        db: Session = Depends(get_db),
        material_id: int = Path(..., ge=1, description="The ID of the material"),
        quantity: float = Query(
            ..., description="Quantity to add (positive) or remove (negative)"
        ),
        notes: Optional[str] = Query(None, description="Notes for this stock adjustment"),
        current_user: Any = Depends(get_current_active_user),
):
    """
    Adjust the stock quantity of a material.
    """
    material_service = MaterialService(db)
    try:
        material = material_service.adjust_stock(
            material_id, quantity, notes, current_user.id
        )
        return serialize_for_response(material)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )
    except InsufficientInventoryException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient quantity available for this adjustment",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/low-stock")
def get_low_stock_materials(
        *,
        db: Session = Depends(get_db),
        threshold_percentage: float = Query(
            20.0, ge=0, le=100, description="Threshold percentage for considering low stock"
        ),
        current_user: Any = Depends(get_current_active_user),
):
    """
    Get materials that are low in stock (below reorder threshold).
    """
    material_service = MaterialService(db)
    materials = material_service.get_low_stock_materials(threshold_percentage)
    return [serialize_for_response(m) for m in materials]


@router.get("/by-storage/{location_id}")
def get_materials_by_storage_location(
        *,
        db: Session = Depends(get_db),
        location_id: int = Path(..., ge=1, description="Storage location ID"),
        current_user: Any = Depends(get_current_active_user),
):
    """
    Get materials stored at a specific location.
    """
    material_service = MaterialService(db)
    materials = material_service.get_materials_by_storage_location(location_id)
    return [serialize_for_response(m) for m in materials]