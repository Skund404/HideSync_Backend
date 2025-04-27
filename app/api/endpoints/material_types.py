# app/api/endpoints/material_types.py

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, UploadFile, File
from sqlalchemy.orm import Session
import json

from app.api.deps import get_db, get_current_active_user, get_enum_service
from app.schemas.dynamic_material import MaterialTypeRead, MaterialTypeCreate, MaterialTypeUpdate, \
    MaterialTypeImportExport
from app.services.material_type_service import MaterialTypeService
from app.services.property_definition_service import PropertyDefinitionService
from app.services.enum_service import EnumService
from app.core.exceptions import ValidationException

router = APIRouter()


def get_material_type_service(
        db: Session = Depends(get_db),
        enum_service: EnumService = Depends(get_enum_service)
) -> MaterialTypeService:
    """Provide MaterialTypeService instance."""
    property_service = PropertyDefinitionService(db, enum_service=enum_service)
    return MaterialTypeService(db, property_repository=property_service.repository)


@router.get("/", response_model=List[MaterialTypeRead])
def list_material_types(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user),
        service: MaterialTypeService = Depends(get_material_type_service),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
        include_system: bool = Query(True, description="Include system material types")
):
    """
    List all material types with optional pagination and filtering.
    """
    return service.get_material_types(
        skip=skip,
        limit=limit,
        include_system=include_system,
        user_tier=getattr(current_user, "tier", None)
    )


@router.post("/", response_model=MaterialTypeRead, status_code=status.HTTP_201_CREATED)
def create_material_type(
        *,
        db: Session = Depends(get_db),
        material_type_in: MaterialTypeCreate,
        current_user=Depends(get_current_active_user),
        service: MaterialTypeService = Depends(get_material_type_service)
):
    """
    Create a new material type.
    """
    try:
        return service.create_material_type(material_type_in.dict(), current_user.id)
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )


@router.get("/{material_type_id}", response_model=MaterialTypeRead)
def get_material_type(
        *,
        db: Session = Depends(get_db),
        material_type_id: int = Path(..., gt=0, description="The ID of the material type"),
        current_user=Depends(get_current_active_user),
        service: MaterialTypeService = Depends(get_material_type_service)
):
    """
    Get a specific material type by ID.
    """
    material_type = service.get_material_type(material_type_id)
    if not material_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material type with ID {material_type_id} not found"
        )
    return material_type


@router.put("/{material_type_id}", response_model=MaterialTypeRead)
def update_material_type(
        *,
        db: Session = Depends(get_db),
        material_type_id: int = Path(..., gt=0, description="The ID of the material type"),
        material_type_in: MaterialTypeUpdate,
        current_user=Depends(get_current_active_user),
        service: MaterialTypeService = Depends(get_material_type_service)
):
    """
    Update a material type.
    """
    try:
        material_type = service.update_material_type(
            material_type_id,
            material_type_in.dict(exclude_unset=True),
            current_user.id
        )
        if not material_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Material type with ID {material_type_id} not found"
            )
        return material_type
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )


@router.delete("/{material_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material_type(
        *,
        db: Session = Depends(get_db),
        material_type_id: int = Path(..., gt=0, description="The ID of the material type"),
        current_user=Depends(get_current_active_user),
        service: MaterialTypeService = Depends(get_material_type_service)
):
    """
    Delete a material type.

    System material types cannot be deleted.
    Material types with associated materials cannot be deleted.
    """
    result = service.delete_material_type(material_type_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to delete material type. It may be a system type or have materials associated with it."
        )
    return None


@router.get("/export", response_model=List[MaterialTypeImportExport])
def export_material_types(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user),
        service: MaterialTypeService = Depends(get_material_type_service),
        material_type_ids: Optional[List[int]] = Query(None, description="Optional list of material type IDs to export")
):
    """
    Export material types as JSON.

    Returns a list of material types in a format suitable for import.
    """
    return service.export_material_types(material_type_ids)


@router.post("/import", response_model=List[MaterialTypeRead], status_code=status.HTTP_201_CREATED)
def import_material_types(
        *,
        db: Session = Depends(get_db),
        file: UploadFile = File(...),
        current_user=Depends(get_current_active_user),
        service: MaterialTypeService = Depends(get_material_type_service)
):
    """
    Import material types from a JSON file.
    """
    try:
        content = file.file.read()
        import_data = json.loads(content.decode('utf-8'))

        # Validate import data
        if not isinstance(import_data, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid import format. Expected a list of material types."
            )

        # Import material types
        imported_types = service.import_material_types(import_data, current_user.id)
        return imported_types

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON format."
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
        )
    finally:
        file.file.close()