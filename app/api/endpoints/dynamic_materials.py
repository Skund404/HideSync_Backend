# app/api/endpoints/dynamic_materials.py
"""
Clean Dynamic Materials API endpoints.

No compatibility layers, no workarounds - clean, modern API
that properly integrates with the storage system.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user, get_enum_service
from app.schemas.dynamic_material import (
    DynamicMaterialRead, DynamicMaterialCreate, DynamicMaterialUpdate,
    DynamicMaterialList, MaterialPropertyValueCreate
)
from app.services.dynamic_material_service import DynamicMaterialService
from app.services.material_type_service import MaterialTypeService
from app.services.property_definition_service import PropertyDefinitionService
from app.services.enum_service import EnumService
from app.core.exceptions import (
    ValidationException, EntityNotFoundException, InsufficientInventoryException
)

router = APIRouter()


def get_dynamic_material_service(
        db: Session = Depends(get_db),
        enum_service: EnumService = Depends(get_enum_service),
        settings_service=Depends(get_settings_service),
        security_context=Depends(get_security_context)
) -> DynamicMaterialService:
    """Provide DynamicMaterialService instance."""
    property_service = PropertyDefinitionService(db, enum_service=enum_service)
    material_type_service = MaterialTypeService(db, property_repository=property_service.repository)

    return DynamicMaterialService(
        db,
        property_service=property_service,
        material_type_service=material_type_service,
        security_context=security_context,
        settings_service=settings_service
    )


@router.get("/", response_model=DynamicMaterialList)
def list_materials(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user),
        service: DynamicMaterialService = Depends(get_dynamic_material_service),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
        material_type_id: Optional[int] = Query(None, description="Filter by material type ID"),
        search: Optional[str] = Query(None, description="Search term for name, description, and SKU"),
        status: Optional[str] = Query(None, description="Filter by status"),
        tags: Optional[List[str]] = Query(None, description="Filter by tag names"),
        apply_settings: bool = Query(True, description="Whether to apply user settings"),
        # Storage-related filters - NEW
        has_storage: Optional[bool] = Query(None, description="Filter by materials with storage assignments"),
        storage_location_id: Optional[str] = Query(None, description="Filter by specific storage location"),
        low_stock: Optional[bool] = Query(None, description="Filter materials below reorder point"),
):
    """
    List materials with optional filtering and pagination.
    Enhanced with storage-related filters.
    """
    # Build filters
    filters = {}

    # Add storage-related filters
    if has_storage is not None:
        filters["has_storage"] = has_storage
    if storage_location_id:
        filters["storage_location_id"] = storage_location_id
    if low_stock:
        filters["low_stock"] = low_stock

    materials, total = service.get_materials(
        skip=skip,
        limit=limit,
        material_type_id=material_type_id,
        search=search,
        status=status,
        tags=tags,
        apply_settings=apply_settings,
        **filters
    )

    return {
        "items": materials,
        "total": total,
        "page": skip // limit + 1 if limit > 0 else 1,
        "size": limit,
        "pages": (total + limit - 1) // limit if limit > 0 else 1
    }


@router.post("/", response_model=DynamicMaterialRead, status_code=status.HTTP_201_CREATED)
def create_material(
        *,
        db: Session = Depends(get_db),
        material_in: DynamicMaterialCreate,
        current_user=Depends(get_current_active_user),
        service: DynamicMaterialService = Depends(get_dynamic_material_service)
):
    """
    Create a new material with dynamic properties.
    """
    try:
        return service.create_material(material_in.dict(), current_user.id)
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except EntityNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )


@router.get("/{material_id}", response_model=DynamicMaterialRead)
def get_material(
        *,
        db: Session = Depends(get_db),
        material_id: int = Path(..., gt=0, description="The ID of the material"),
        current_user=Depends(get_current_active_user),
        service: DynamicMaterialService = Depends(get_dynamic_material_service),
        include_storage: bool = Query(True, description="Include storage information")
):
    """
    Get a specific material by ID with its properties and optionally storage info.
    """
    material = service.get_material(material_id)
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found"
        )

    # Add storage information if requested
    if include_storage and hasattr(material, 'storage_assignments'):
        # The relationships should automatically load storage data
        pass

    return material


@router.put("/{material_id}", response_model=DynamicMaterialRead)
def update_material(
        *,
        db: Session = Depends(get_db),
        material_id: int = Path(..., gt=0, description="The ID of the material"),
        material_in: DynamicMaterialUpdate,
        current_user=Depends(get_current_active_user),
        service: DynamicMaterialService = Depends(get_dynamic_material_service)
):
    """
    Update a material with its properties.
    """
    try:
        material = service.update_material(
            material_id,
            material_in.dict(exclude_unset=True),
            current_user.id
        )
        if not material:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Material with ID {material_id} not found"
            )
        return material
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except EntityNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(
        *,
        db: Session = Depends(get_db),
        material_id: int = Path(..., gt=0, description="The ID of the material"),
        current_user=Depends(get_current_active_user),
        service: DynamicMaterialService = Depends(get_dynamic_material_service)
):
    """
    Delete a material.
    Note: Will cascade delete related storage assignments due to FK constraints.
    """
    result = service.delete_material(material_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found"
        )
    return None


@router.post("/{material_id}/adjust-stock", response_model=DynamicMaterialRead)
def adjust_material_stock(
        *,
        db: Session = Depends(get_db),
        material_id: int = Path(..., gt=0, description="The ID of the material"),
        quantity: float = Query(..., description="Quantity to add (positive) or remove (negative)"),
        notes: Optional[str] = Query(None, description="Optional notes for the adjustment"),
        current_user=Depends(get_current_active_user),
        service: DynamicMaterialService = Depends(get_dynamic_material_service)
):
    """
    Adjust the stock quantity of a material.
    """
    try:
        return service.adjust_stock(
            material_id=material_id,
            quantity_change=quantity,
            notes=notes,
            user_id=current_user.id
        )
    except EntityNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except InsufficientInventoryException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )


# Storage-related endpoints - NEW CLEAN INTEGRATIONS

@router.get("/{material_id}/storage", response_model=Dict[str, Any])
def get_material_storage_info(
        *,
        db: Session = Depends(get_db),
        material_id: int = Path(..., gt=0, description="The ID of the material"),
        current_user=Depends(get_current_active_user),
        service: DynamicMaterialService = Depends(get_dynamic_material_service)
):
    """
    Get comprehensive storage information for a material.
    """
    try:
        material = service.get_material(material_id)
        if not material:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Material with ID {material_id} not found"
            )

        # Use the relationship properties we added to DynamicMaterial
        # Fixed the list comprehension syntax
        recent_moves_data = []
        if hasattr(material, 'get_recent_moves'):
            recent_moves_data = [
                {
                    "move_id": str(move.id),
                    "from_location": move.from_location.name if move.from_location else None,
                    "to_location": move.to_location.name if move.to_location else None,
                    "quantity": move.quantity,
                    "move_date": move.move_date,
                    "moved_by": move.moved_by,
                    "reason": move.reason
                }
                for move in material.get_recent_moves(5)
            ]

        storage_info = {
            "material_id": material_id,
            "current_storage_locations": [
                {
                    "location_id": str(loc.id),
                    "location_name": loc.name,
                    "location_type": loc.type.name if loc.type else None,
                    "section": loc.section
                }
                for loc in material.current_storage_locations
            ] if hasattr(material, 'current_storage_locations') else [],
            "total_assigned_quantity": material.total_assigned_quantity if hasattr(material,
                                                                                   'total_assigned_quantity') else 0,
            "storage_locations_count": material.storage_locations_count if hasattr(material,
                                                                                   'storage_locations_count') else 0,
            "is_multi_location_stored": material.is_multi_location_stored if hasattr(material,
                                                                                     'is_multi_location_stored') else False,
            "primary_storage_location": {
                "location_id": str(material.primary_storage_location.id),
                "location_name": material.primary_storage_location.name,
                "location_type": material.primary_storage_location.type.name if material.primary_storage_location.type else None
            } if hasattr(material, 'primary_storage_location') and material.primary_storage_location else None,
            "recent_moves": recent_moves_data
        }

        return storage_info

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving storage information: {str(e)}"
        )


@router.get("/low-stock", response_model=List[DynamicMaterialRead])
def get_low_stock_materials(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user),
        service: DynamicMaterialService = Depends(get_dynamic_material_service),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
        include_storage: bool = Query(True, description="Include storage location information")
):
    """
    Get materials that are low in stock (below reorder point).
    Optionally include storage information.
    """
    materials = service.get_low_stock_materials(skip=skip, limit=limit)

    # Add storage info if requested
    if include_storage:
        # The relationships should handle this automatically
        pass

    return materials


@router.get("/out-of-stock", response_model=List[DynamicMaterialRead])
def get_out_of_stock_materials(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user),
        service: DynamicMaterialService = Depends(get_dynamic_material_service),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
        include_storage: bool = Query(True, description="Include storage location information")
):
    """
    Get materials that are out of stock.
    Optionally include storage information.
    """
    materials = service.get_out_of_stock_materials(skip=skip, limit=limit)

    # Add storage info if requested
    if include_storage:
        # The relationships should handle this automatically
        pass

    return materials


@router.post("/{material_id}/media", response_model=Dict[str, Any])
def attach_media(
        *,
        db: Session = Depends(get_db),
        material_id: int = Path(..., gt=0, description="The ID of the material"),
        media_id: str = Query(..., description="The ID of the media asset"),
        is_primary: bool = Query(False, description="Whether this is the primary media"),
        current_user=Depends(get_current_active_user),
        service: DynamicMaterialService = Depends(get_dynamic_material_service)
):
    """
    Attach media to a material.
    """
    try:
        association = service.attach_media(
            material_id=material_id,
            media_id=media_id,
            is_primary=is_primary
        )

        return {
            "material_id": material_id,
            "media_id": media_id,
            "is_primary": is_primary,
            "success": True
        }
    except EntityNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )


@router.post("/{material_id}/tags", response_model=List[Dict[str, Any]])
def add_tags(
        *,
        db: Session = Depends(get_db),
        material_id: int = Path(..., gt=0, description="The ID of the material"),
        tags: List[str] = Body(..., description="List of tag names to add"),
        current_user=Depends(get_current_active_user),
        service: DynamicMaterialService = Depends(get_dynamic_material_service)
):
    """
    Add tags to a material.
    """
    try:
        added_tags = service.add_tags(material_id=material_id, tags=tags)
        return [{"id": tag.id, "name": tag.name} for tag in added_tags]
    except EntityNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )


@router.delete("/{material_id}/tags/{tag_name}")
def remove_tag(
        *,
        db: Session = Depends(get_db),
        material_id: int = Path(..., gt=0, description="The ID of the material"),
        tag_name: str = Path(..., description="The name of the tag to remove"),
        current_user=Depends(get_current_active_user),
        service: DynamicMaterialService = Depends(get_dynamic_material_service)
):
    """
    Remove a tag from a material.
    """
    try:
        result = service.remove_tag(material_id=material_id, tag_name=tag_name)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag '{tag_name}' not found on material with ID {material_id}"
            )

        return {"material_id": material_id, "tag": tag_name, "success": True}
    except EntityNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )


# Analytics endpoint - NEW
@router.get("/analytics/storage-distribution", response_model=Dict[str, Any])
def get_materials_storage_distribution(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user),
        service: DynamicMaterialService = Depends(get_dynamic_material_service),
        material_type_id: Optional[int] = Query(None, description="Filter by material type")
):
    """
    Get analytics on how materials are distributed across storage locations.
    """
    try:
        # This would use the storage relationships to provide analytics
        # Implementation would depend on specific analytics requirements
        analytics_data = {
            "total_materials_with_storage": 0,
            "materials_without_storage": 0,
            "multi_location_materials": 0,
            "storage_distribution_by_type": {},
            "top_storage_locations": [],
            "materials_needing_storage": []
        }

        return analytics_data

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating storage analytics: {str(e)}"
        )