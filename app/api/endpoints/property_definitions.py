# app/api/endpoints/property_definitions.py

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user, get_enum_service
from app.schemas.dynamic_material import PropertyDefinitionRead, PropertyDefinitionCreate, PropertyDefinitionUpdate, \
    PropertyEnumOptionRead, PropertyEnumOptionCreate
from app.services.property_definition_service import PropertyDefinitionService
from app.services.enum_service import EnumService
from app.core.exceptions import ValidationException

router = APIRouter()


def get_property_definition_service(
        db: Session = Depends(get_db),
        enum_service: EnumService = Depends(get_enum_service)
) -> PropertyDefinitionService:
    """Provide PropertyDefinitionService instance."""
    return PropertyDefinitionService(db, enum_service=enum_service)


@router.get("/", response_model=List[PropertyDefinitionRead])
def list_property_definitions(
        *,
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user),
        service: PropertyDefinitionService = Depends(get_property_definition_service),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
        include_system: bool = Query(True, description="Include system properties"),
        data_type: Optional[str] = Query(None, description="Filter by data type")
):
    """
    List all property definitions with optional pagination and filtering.
    """
    return service.get_property_definitions(
        skip=skip,
        limit=limit,
        include_system=include_system,
        data_type=data_type
    )


@router.post("/", response_model=PropertyDefinitionRead, status_code=status.HTTP_201_CREATED)
def create_property_definition(
        *,
        db: Session = Depends(get_db),
        property_definition_in: PropertyDefinitionCreate,
        current_user=Depends(get_current_active_user),
        service: PropertyDefinitionService = Depends(get_property_definition_service)
):
    """
    Create a new property definition.
    """
    try:
        return service.create_property_definition(
            property_definition_in.dict(),
            current_user.id
        )
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


@router.get("/{property_id}", response_model=PropertyDefinitionRead)
def get_property_definition(
        *,
        db: Session = Depends(get_db),
        property_id: int = Path(..., gt=0, description="The ID of the property definition"),
        current_user=Depends(get_current_active_user),
        service: PropertyDefinitionService = Depends(get_property_definition_service)
):
    """
    Get a specific property definition by ID.
    """
    property_definition = service.get_property_definition(property_id)
    if not property_definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property definition with ID {property_id} not found"
        )
    return property_definition


@router.put("/{property_id}", response_model=PropertyDefinitionRead)
def update_property_definition(
        *,
        db: Session = Depends(get_db),
        property_id: int = Path(..., gt=0, description="The ID of the property definition"),
        property_definition_in: PropertyDefinitionUpdate,
        current_user=Depends(get_current_active_user),
        service: PropertyDefinitionService = Depends(get_property_definition_service)
):
    """
    Update a property definition.
    """
    try:
        property_definition = service.update_property_definition(
            property_id,
            property_definition_in.dict(exclude_unset=True),
            current_user.id
        )
        if not property_definition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Property definition with ID {property_id} not found"
            )
        return property_definition
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


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property_definition(
        *,
        db: Session = Depends(get_db),
        property_id: int = Path(..., gt=0, description="The ID of the property definition"),
        current_user=Depends(get_current_active_user),
        service: PropertyDefinitionService = Depends(get_property_definition_service)
):
    """
    Delete a property definition.

    System properties cannot be deleted.
    Properties used by material types cannot be deleted.
    """
    result = service.delete_property_definition(property_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to delete property definition. It may be a system property or used by material types."
        )
    return None


@router.get("/{property_id}/enum-values", response_model=List[Dict[str, Any]])
def get_property_enum_values(
        *,
        db: Session = Depends(get_db),
        property_id: int = Path(..., gt=0, description="The ID of the property definition"),
        locale: str = Query("en", description="Locale for translations"),
        current_user=Depends(get_current_active_user),
        service: PropertyDefinitionService = Depends(get_property_definition_service)
):
    """
    Get enum values for a property.

    Includes values from the dynamic enum system if the property uses it,
    or custom enum options if it doesn't.
    """
    property_definition = service.get_property_definition(property_id)
    if not property_definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property definition with ID {property_id} not found"
        )

    # Check if it's an enum property
    if property_definition.data_type != "enum":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Property definition with ID {property_id} is not an enum property"
        )

    return service.get_enum_values(property_id, locale)


@router.post("/{property_id}/enum-options", response_model=PropertyEnumOptionRead, status_code=status.HTTP_201_CREATED)
def add_enum_option(
        *,
        db: Session = Depends(get_db),
        property_id: int = Path(..., gt=0, description="The ID of the property definition"),
        option_in: PropertyEnumOptionCreate,
        current_user=Depends(get_current_active_user),
        service: PropertyDefinitionService = Depends(get_property_definition_service)
):
    """
    Add an enum option to a property.

    Only applies to enum properties that don't use the dynamic enum system.
    """
    try:
        option = service.add_enum_option(
            property_id=property_id,
            value=option_in.value,
            display_value=option_in.display_value,
            color=option_in.color,
            display_order=option_in.display_order
        )

        if not option:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not add enum option. Property may not be an enum type or may use the dynamic enum system."
            )

        return option
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


@router.delete("/{property_id}/enum-options/{option_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_enum_option(
        *,
        db: Session = Depends(get_db),
        property_id: int = Path(..., gt=0, description="The ID of the property definition"),
        option_id: int = Path(..., gt=0, description="The ID of the enum option"),
        current_user=Depends(get_current_active_user),
        service: PropertyDefinitionService = Depends(get_property_definition_service)
):
    """
    Delete an enum option from a property.

    Only applies to enum properties that don't use the dynamic enum system.
    """
    result = service.delete_enum_option(property_id, option_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to delete enum option. Property may not be an enum type, may use the dynamic enum system, or option might not exist."
        )
    return None