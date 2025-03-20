# File: app/api/endpoints/storage.py
"""
Storage API endpoints for HideSync.

This module provides endpoints for managing storage locations, cells,
assignments, and movements of inventory items between locations.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.schemas.compatibility import(
    StorageLocation,
    StorageLocationCreate,
    StorageLocationUpdate,
    StorageCell,
    StorageCellCreate,
    StorageAssignment,
    StorageAssignmentCreate,
    StorageMove,
    StorageMoveCreate,
    StorageSearchParams,
    StorageOccupancyReport,
)
from app.services.storage_location_service import StorageLocationService
from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,

    StorageLocationNotFoundException,
)
from app.core.exceptions import InsufficientInventoryException as InsufficientQuantityException


router = APIRouter()


@router.get("/locations", response_model=List[StorageLocation])
def list_storage_locations(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    type: Optional[str] = Query(None, description="Filter by location type"),
    section: Optional[str] = Query(None, description="Filter by section"),
    status: Optional[str] = Query(None, description="Filter by location status"),
    search: Optional[str] = Query(None, description="Search term for name"),
) -> List[StorageLocation]:
    """
    Retrieve storage locations with optional filtering and pagination.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        type: Optional filter by location type
        section: Optional filter by section
        status: Optional filter by location status
        search: Optional search term for name

    Returns:
        List of storage location records
    """
    search_params = StorageSearchParams(
        type=type, section=section, status=status, search=search
    )

    storage_service = StorageLocationService(db)
    return storage_service.get_storage_locations(
        skip=skip, limit=limit, search_params=search_params
    )


@router.post(
    "/locations", response_model=StorageLocation, status_code=status.HTTP_201_CREATED
)
def create_storage_location(
    *,
    db: Session = Depends(get_db),
    location_in: StorageLocationCreate,
    current_user: Any = Depends(get_current_active_user),
) -> StorageLocation:
    """
    Create a new storage location.

    Args:
        db: Database session
        location_in: Storage location data for creation
        current_user: Currently authenticated user

    Returns:
        Created storage location information

    Raises:
        HTTPException: If creation fails due to business rules
    """
    storage_service = StorageLocationService(db)
    try:
        return storage_service.create_storage_location(location_in, current_user.id)
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/locations/{location_id}", response_model=StorageLocation)
def get_storage_location(
    *,
    db: Session = Depends(get_db),
    location_id: str = Path(
        ..., description="The ID of the storage location to retrieve"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> StorageLocation:
    """
    Get detailed information about a specific storage location.

    Args:
        db: Database session
        location_id: ID of the storage location to retrieve
        current_user: Currently authenticated user

    Returns:
        Storage location information

    Raises:
        HTTPException: If the storage location doesn't exist
    """
    storage_service = StorageLocationService(db)
    try:
        return storage_service.get_storage_location(location_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage location with ID {location_id} not found",
        )


@router.put("/locations/{location_id}", response_model=StorageLocation)
def update_storage_location(
    *,
    db: Session = Depends(get_db),
    location_id: str = Path(
        ..., description="The ID of the storage location to update"
    ),
    location_in: StorageLocationUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> StorageLocation:
    """
    Update a storage location.

    Args:
        db: Database session
        location_id: ID of the storage location to update
        location_in: Updated storage location data
        current_user: Currently authenticated user

    Returns:
        Updated storage location information

    Raises:
        HTTPException: If the storage location doesn't exist or update violates business rules
    """
    storage_service = StorageLocationService(db)
    try:
        return storage_service.update_storage_location(
            location_id, location_in, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage location with ID {location_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_storage_location(
    *,
    db: Session = Depends(get_db),
    location_id: str = Path(
        ..., description="The ID of the storage location to delete"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> None:
    """
    Delete a storage location.

    Args:
        db: Database session
        location_id: ID of the storage location to delete
        current_user: Currently authenticated user

    Raises:
        HTTPException: If the storage location doesn't exist or can't be deleted
    """
    storage_service = StorageLocationService(db)
    try:
        storage_service.delete_storage_location(location_id, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage location with ID {location_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Storage cells
@router.get("/locations/{location_id}/cells", response_model=List[StorageCell])
def list_storage_cells(
    *,
    db: Session = Depends(get_db),
    location_id: str = Path(..., description="The ID of the storage location"),
    current_user: Any = Depends(get_current_active_user),
    occupied: Optional[bool] = Query(None, description="Filter by occupied status"),
) -> List[StorageCell]:
    """
    Retrieve cells for a storage location.

    Args:
        db: Database session
        location_id: ID of the storage location
        current_user: Currently authenticated user
        occupied: Optional filter by occupied status

    Returns:
        List of storage cell records

    Raises:
        HTTPException: If the storage location doesn't exist
    """
    storage_service = StorageLocationService(db)
    try:
        return storage_service.get_storage_cells(location_id, occupied)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage location with ID {location_id} not found",
        )


@router.post(
    "/locations/{location_id}/cells",
    response_model=StorageCell,
    status_code=status.HTTP_201_CREATED,
)
def create_storage_cell(
    *,
    db: Session = Depends(get_db),
    location_id: str = Path(..., description="The ID of the storage location"),
    cell_in: StorageCellCreate,
    current_user: Any = Depends(get_current_active_user),
) -> StorageCell:
    """
    Create a new storage cell for a location.

    Args:
        db: Database session
        location_id: ID of the storage location
        cell_in: Storage cell data for creation
        current_user: Currently authenticated user

    Returns:
        Created storage cell information

    Raises:
        HTTPException: If the storage location doesn't exist or creation fails
    """
    storage_service = StorageLocationService(db)
    try:
        return storage_service.create_storage_cell(
            location_id, cell_in, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage location with ID {location_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Storage assignments
@router.get("/assignments", response_model=List[StorageAssignment])
def list_storage_assignments(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    item_id: Optional[int] = Query(None, ge=1, description="Filter by item ID"),
    item_type: Optional[str] = Query(None, description="Filter by item type"),
    location_id: Optional[str] = Query(
        None, description="Filter by storage location ID"
    ),
) -> List[StorageAssignment]:
    """
    Retrieve storage assignments with optional filtering.

    Args:
        db: Database session
        current_user: Currently authenticated user
        item_id: Optional filter by item ID
        item_type: Optional filter by item type
        location_id: Optional filter by storage location ID

    Returns:
        List of storage assignment records
    """
    storage_service = StorageLocationService(db)
    return storage_service.get_storage_assignments(
        item_id=item_id, item_type=item_type, location_id=location_id
    )


@router.post(
    "/assignments",
    response_model=StorageAssignment,
    status_code=status.HTTP_201_CREATED,
)
def create_storage_assignment(
    *,
    db: Session = Depends(get_db),
    assignment_in: StorageAssignmentCreate,
    current_user: Any = Depends(get_current_active_user),
) -> StorageAssignment:
    """
    Create a new storage assignment.

    Args:
        db: Database session
        assignment_in: Storage assignment data for creation
        current_user: Currently authenticated user

    Returns:
        Created storage assignment information

    Raises:
        HTTPException: If creation fails
    """
    storage_service = StorageLocationService(db)
    try:
        return storage_service.create_storage_assignment(assignment_in, current_user.id)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except StorageCapacityExceededException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Storage location capacity exceeded",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_storage_assignment(
    *,
    db: Session = Depends(get_db),
    assignment_id: str = Path(
        ..., description="The ID of the storage assignment to delete"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> None:
    """
    Delete a storage assignment.

    Args:
        db: Database session
        assignment_id: ID of the storage assignment to delete
        current_user: Currently authenticated user

    Raises:
        HTTPException: If the storage assignment doesn't exist
    """
    storage_service = StorageLocationService(db)
    try:
        storage_service.delete_storage_assignment(assignment_id, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage assignment with ID {assignment_id} not found",
        )


# Storage moves
@router.get("/moves", response_model=List[StorageMove])
def list_storage_moves(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    item_id: Optional[int] = Query(None, ge=1, description="Filter by item ID"),
    item_type: Optional[str] = Query(None, description="Filter by item type"),
) -> List[StorageMove]:
    """
    Retrieve storage moves with optional filtering and pagination.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        item_id: Optional filter by item ID
        item_type: Optional filter by item type

    Returns:
        List of storage move records
    """
    storage_service = StorageLocationService(db)
    return storage_service.get_storage_moves(
        skip=skip, limit=limit, item_id=item_id, item_type=item_type
    )


@router.post("/moves", response_model=StorageMove, status_code=status.HTTP_201_CREATED)
def create_storage_move(
    *,
    db: Session = Depends(get_db),
    move_in: StorageMoveCreate,
    current_user: Any = Depends(get_current_active_user),
) -> StorageMove:
    """
    Create a new storage move.

    Args:
        db: Database session
        move_in: Storage move data for creation
        current_user: Currently authenticated user

    Returns:
        Created storage move information

    Raises:
        HTTPException: If move creation fails
    """
    storage_service = StorageLocationService(db)
    try:
        return storage_service.create_storage_move(move_in, current_user.id)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except StorageLocationNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except StorageCapacityExceededException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target storage location capacity exceeded",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/occupancy", response_model=StorageOccupancyReport)
def get_storage_occupancy_report(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    section: Optional[str] = Query(None, description="Filter by section"),
    type: Optional[str] = Query(None, description="Filter by location type"),
) -> StorageOccupancyReport:
    """
    Get storage occupancy report.

    Args:
        db: Database session
        current_user: Currently authenticated user
        section: Optional filter by section
        type: Optional filter by location type

    Returns:
        Storage occupancy report
    """
    storage_service = StorageLocationService(db)
    return storage_service.get_storage_occupancy_report(section, type)
