# File: app/api/endpoints/components.py
"""
Components API endpoints for the HideSync system.

This module defines the API endpoints for managing components within the HideSync system,
including component creation, retrieval, updates, and specialized operations like
batch creation and duplication. Components represent individual pieces of a pattern
that can be assembled into complete leatherworking projects.
"""

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Body, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.exceptions import (
    EntityNotFoundException,
    ValidationException,
    BusinessRuleException,
)
from app.db.session import get_db
from app.schemas.compatibility import (
    ComponentCreate,
    ComponentResponse,
    ComponentUpdate,
    ComponentListResponse,
    ComponentMaterialCreate,
    ComponentMaterialResponse,
)
from app.services.component_service import ComponentService
from app.services.material_service import MaterialService
from app.services.pattern_service import PatternService

router = APIRouter()


@router.get("/", response_model=ComponentListResponse)
def list_components(
    name: Optional[str] = Query(None, description="Filter by component name"),
    component_type: Optional[str] = Query(None, description="Filter by component type"),
    pattern_id: Optional[int] = Query(None, description="Filter by pattern ID"),
    skip: int = Query(0, description="Number of records to skip"),
    limit: int = Query(100, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Get a list of components with optional filtering.
    """
    component_service = ComponentService(db)

    # Build filter parameters
    filters = {}
    if name:
        filters["name"] = name
    if component_type:
        filters["componentType"] = component_type
    if pattern_id:
        filters["patternId"] = pattern_id

    components = component_service.list(skip=skip, limit=limit, **filters)
    total = component_service.count(**filters)

    return {"items": components, "total": total, "skip": skip, "limit": limit}


@router.post("/", response_model=ComponentResponse, status_code=status.HTTP_201_CREATED)
def create_component(
    component_data: ComponentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Create a new component.
    """
    component_service = ComponentService(db)

    try:
        component = component_service.create_component(component_data.dict())
        return component
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{component_id}", response_model=ComponentResponse)
def get_component(
    component_id: int = Path(..., description="The ID of the component to retrieve"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Get a component by ID.
    """
    component_service = ComponentService(db)
    component = component_service.get_component_with_details(component_id)

    if not component:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Component with ID {component_id} not found",
        )

    return component


@router.put("/{component_id}", response_model=ComponentResponse)
def update_component(
    component_id: int = Path(..., description="The ID of the component to update"),
    component_data: ComponentUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Update a component.
    """
    component_service = ComponentService(db)

    try:
        component = component_service.update_component(
            component_id, component_data.dict(exclude_unset=True)
        )
        return component
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Component with ID {component_id} not found",
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )


@router.delete("/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_component(
    component_id: int = Path(..., description="The ID of the component to delete"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> None:
    """
    Delete a component.
    """
    component_service = ComponentService(db)

    try:
        result = component_service.delete_component(component_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Component with ID {component_id} not found",
            )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Component with ID {component_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


# New endpoints for component management


@router.get("/by-pattern/{pattern_id}", response_model=List[ComponentResponse])
def get_components_by_pattern(
    pattern_id: int = Path(..., description="The ID of the pattern"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Get all components for a specific pattern.

    Returns a list of components associated with the specified pattern ID,
    including their material requirements and positioning data.
    """
    component_service = ComponentService(db)
    pattern_service = PatternService(db)

    # First verify the pattern exists
    pattern = pattern_service.get_by_id(pattern_id)
    if not pattern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern with ID {pattern_id} not found",
        )

    # Get components
    components = component_service.get_components_by_pattern(pattern_id)

    # Convert to detailed response
    detailed_components = []
    for component in components:
        detailed = component_service.get_component_with_details(component.id)
        detailed_components.append(detailed)

    return detailed_components


@router.post(
    "/batch",
    response_model=List[ComponentResponse],
    status_code=status.HTTP_201_CREATED,
)
def batch_create_components(
    components_data: List[ComponentCreate] = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Create multiple components in a single request.

    This endpoint allows for the efficient creation of multiple related components,
    which is particularly useful when creating a new pattern with all its components.
    """
    component_service = ComponentService(db)
    pattern_service = PatternService(db)

    created_components = []

    # Begin a transaction to ensure all components are created or none
    try:
        # Check if all pattern IDs exist first
        pattern_ids = set()
        for comp_data in components_data:
            if comp_data.patternId:
                pattern_ids.add(comp_data.patternId)

        for pattern_id in pattern_ids:
            pattern = pattern_service.get_by_id(pattern_id)
            if not pattern:
                raise EntityNotFoundException("Pattern", pattern_id)

        # Create all components
        for comp_data in components_data:
            component = component_service.create_component(comp_data.dict())
            created_components.append(component)

        return created_components
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{component_id}/duplicate", response_model=ComponentResponse)
def duplicate_component(
    component_id: int = Path(..., description="The ID of the component to duplicate"),
    override_data: Optional[ComponentUpdate] = Body(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Duplicate a component.

    Creates a new component based on an existing one, including all material
    requirements. Optionally allows overriding specific properties in the duplicated component.
    """
    component_service = ComponentService(db)

    try:
        # Get original component to verify it exists
        original = component_service.get_by_id(component_id)
        if not original:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Component with ID {component_id} not found",
            )

        # Duplicate the component
        override_dict = (
            override_data.dict(exclude_unset=True) if override_data else None
        )
        duplicated = component_service.clone_component(component_id, override_dict)

        return duplicated
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Component with ID {component_id} not found",
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )


# Material requirement endpoints


@router.post("/{component_id}/materials", response_model=ComponentMaterialResponse)
def add_material_requirement(
    component_id: int = Path(..., description="The ID of the component"),
    requirement_data: ComponentMaterialCreate = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Add a material requirement to a component.
    """
    component_service = ComponentService(db)
    material_service = MaterialService(db)

    try:
        # Check if component exists
        component = component_service.get_by_id(component_id)
        if not component:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Component with ID {component_id} not found",
            )

        # Check if material exists
        material = material_service.get_by_id(requirement_data.material_id)
        if not material:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Material with ID {requirement_data.material_id} not found",
            )

        # Add requirement
        requirement = component_service.add_material_requirement(
            component_id, requirement_data.dict()
        )

        return requirement
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors
        )


@router.get("/{component_id}/materials", response_model=List[ComponentMaterialResponse])
def get_material_requirements(
    component_id: int = Path(..., description="The ID of the component"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> Any:
    """
    Get all material requirements for a component.
    """
    component_service = ComponentService(db)

    # Check if component exists
    component = component_service.get_by_id(component_id)
    if not component:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Component with ID {component_id} not found",
        )

    # Get requirements
    requirements = component_service.get_component_materials(component_id)

    return requirements
