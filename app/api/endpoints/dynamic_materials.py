# app/api/endpoints/dynamic_materials.py

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from fastapi.responses import JSONResponse
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
        settings_service: SettingsService = Depends(get_settings_service),
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
        apply_settings: bool = Query(True, description="Whether to apply user settings")
):
    """
    List materials with optional filtering and pagination.
    """
    materials, total = service.get_materials(
        skip=skip,
        limit=limit,
        material_type_id=material_type_id,
        search=search,
        status=status,
        tags=tags,
        apply_settings=apply_settings
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
        service: DynamicMaterialService = Depends(get_dynamic_material_service)
):
    """
    Get a specific material by ID with its properties.
    """
    material = service.get_material(material_id)
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found"
        )
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


@router.get("/low-stock", response_model=List[DynamicMaterialRead])
def get_low_stock_materials(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user),
        service: DynamicMaterialService = Depends(get_dynamic_material_service),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
):
    """
    Get materials that are low in stock (below reorder point).
    """
    return service.get_low_stock_materials(skip=skip, limit=limit)


@router.get("/out-of-stock", response_model=List[DynamicMaterialRead])
def get_out_of_stock_materials(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user),
        service: DynamicMaterialService = Depends(get_dynamic_material_service),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
):
    """
    Get materials that are out of stock.
    """
    return service.get_out_of_stock_materials(skip=skip, limit=limit)


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