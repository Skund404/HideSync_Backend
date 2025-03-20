# File: app/api/endpoints/materials.py
"""
Material API endpoints for HideSync.

This module provides endpoints for managing material data,
including inventory tracking, material types, and related operations.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.schemas.material import (
    Material,
    MaterialCreate,
    MaterialUpdate,
    MaterialWithInventory,
    MaterialSearchParams,
)
from app.services.material_service import MaterialService
from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
    InsufficientQuantityException,
)

router = APIRouter()


@router.get("/", response_model=List[Material])
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
) -> List[Material]:
    """
    Retrieve materials with optional filtering and pagination.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        material_type: Optional filter by material type
        quality: Optional filter by material quality
        in_stock: Optional filter by stock availability
        search: Optional search term for name

    Returns:
        List of material records
    """
    search_params = MaterialSearchParams(
        material_type=material_type, quality=quality, in_stock=in_stock, search=search
    )

    material_service = MaterialService(db)
    return material_service.get_materials(
        skip=skip, limit=limit, search_params=search_params
    )


@router.post("/", response_model=Material, status_code=status.HTTP_201_CREATED)
def create_material(
    *,
    db: Session = Depends(get_db),
    material_in: MaterialCreate,
    current_user: Any = Depends(get_current_active_user),
) -> Material:
    """
    Create a new material.

    Args:
        db: Database session
        material_in: Material data for creation
        current_user: Currently authenticated user

    Returns:
        Created material information

    Raises:
        HTTPException: If material creation fails due to business rules
    """
    material_service = MaterialService(db)
    try:
        return material_service.create_material(material_in, current_user.id)
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{material_id}", response_model=Material)
def get_material(
    *,
    db: Session = Depends(get_db),
    material_id: int = Path(
        ..., ge=1, description="The ID of the material to retrieve"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> Material:
    """
    Get detailed information about a specific material.

    Args:
        db: Database session
        material_id: ID of the material to retrieve
        current_user: Currently authenticated user

    Returns:
        Material information

    Raises:
        HTTPException: If the material doesn't exist
    """
    material_service = MaterialService(db)
    try:
        return material_service.get_material(material_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )


@router.get("/{material_id}/with-inventory", response_model=MaterialWithInventory)
def get_material_with_inventory(
    *,
    db: Session = Depends(get_db),
    material_id: int = Path(..., ge=1, description="The ID of the material"),
    current_user: Any = Depends(get_current_active_user),
) -> MaterialWithInventory:
    """
    Get material information with inventory details.

    Args:
        db: Database session
        material_id: ID of the material
        current_user: Currently authenticated user

    Returns:
        Material information with inventory details

    Raises:
        HTTPException: If the material doesn't exist
    """
    material_service = MaterialService(db)
    try:
        return material_service.get_material_with_inventory(material_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )


@router.put("/{material_id}", response_model=Material)
def update_material(
    *,
    db: Session = Depends(get_db),
    material_id: int = Path(..., ge=1, description="The ID of the material to update"),
    material_in: MaterialUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> Material:
    """
    Update a material.

    Args:
        db: Database session
        material_id: ID of the material to update
        material_in: Updated material data
        current_user: Currently authenticated user

    Returns:
        Updated material information

    Raises:
        HTTPException: If the material doesn't exist or update violates business rules
    """
    material_service = MaterialService(db)
    try:
        return material_service.update_material(
            material_id, material_in, current_user.id
        )
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

    Args:
        db: Database session
        material_id: ID of the material to delete
        current_user: Currently authenticated user

    Raises:
        HTTPException: If the material doesn't exist or can't be deleted
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


@router.post("/{material_id}/adjust-stock", response_model=Material)
def adjust_material_stock(
    *,
    db: Session = Depends(get_db),
    material_id: int = Path(..., ge=1, description="The ID of the material"),
    quantity: float = Query(
        ..., description="Quantity to add (positive) or remove (negative)"
    ),
    notes: Optional[str] = Query(None, description="Notes for this stock adjustment"),
    current_user: Any = Depends(get_current_active_user),
) -> Material:
    """
    Adjust the stock quantity of a material.

    Args:
        db: Database session
        material_id: ID of the material
        quantity: Quantity to add (positive) or remove (negative)
        notes: Optional notes for this adjustment
        current_user: Currently authenticated user

    Returns:
        Updated material information

    Raises:
        HTTPException: If the material doesn't exist or adjustment isn't possible
    """
    material_service = MaterialService(db)
    try:
        return material_service.adjust_stock(
            material_id, quantity, notes, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {material_id} not found",
        )
    except InsufficientQuantityException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient quantity available for this adjustment",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
