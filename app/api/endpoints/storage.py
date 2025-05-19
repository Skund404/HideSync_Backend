# File: app/api/endpoints/storage.py
"""
Storage API endpoints for the Dynamic Material Management System.

This module provides endpoints for managing storage locations, cells,
assignments, and movements following the same patterns as the dynamic
material API. Updated to support:
- Dynamic storage location types
- Settings-aware responses
- Theme integration
- Enhanced filtering and pagination
- Proper error handling
"""

from typing import Any, List, Optional, Dict
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db, get_settings_service, get_security_context
from app.schemas.storage import (
    StorageLocation,
    StorageLocationCreate,
    StorageLocationUpdate,
    StorageLocationList,
    StorageLocationType,
    StorageLocationTypeCreate,
    StorageLocationTypeUpdate,
    StorageLocationTypeList,
    StorageCell,
    StorageCellCreate,
    StorageCellList,
    StorageAssignment,
    StorageAssignmentCreate,
    StorageAssignmentList,
    StorageMove,
    StorageMoveCreate,
    StorageMoveList,
    StorageOccupancyReport,
    StorageUtilizationSyncResult,
    MaterialTypeStorageSummary,
    StorageOperationResult,
)
from app.services.storage_location_service import StorageLocationService
from app.services.settings_service import SettingsService
from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
    StorageLocationNotFoundException,
    InsufficientInventoryException,
    ValidationException,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_storage_location_service(
        db: Session = Depends(get_db),
        settings_service: SettingsService = Depends(get_settings_service),
        security_context=Depends(get_security_context)
) -> StorageLocationService:
    """Provide StorageLocationService instance with dependencies."""
    return StorageLocationService(
        session=db,
        settings_service=settings_service,
        security_context=security_context
    )


# --- Storage Location Types ---

@router.get("/location-types", response_model=StorageLocationTypeList)
def list_storage_location_types(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
        search: Optional[str] = Query(None, description="Search term for name"),
        visibility_level: Optional[str] = Query(None, description="Filter by visibility level"),
        apply_settings: bool = Query(True, description="Whether to apply user settings"),
) -> StorageLocationTypeList:
    """
    Retrieve storage location types with optional filtering and pagination.
    """
    logger.info("Getting storage location types")

    try:
        from app.repositories.storage_repository import StorageLocationTypeRepository

        repository = StorageLocationTypeRepository(db)

        # Build filters
        filters = {}
        if visibility_level:
            filters["visibility_level"] = visibility_level

        # Get types with properties
        types, total = repository.list_with_properties(
            skip=skip,
            limit=limit,
            search=search,
            **filters
        )

        # Calculate pagination
        page = skip // limit + 1 if limit > 0 else 1
        pages = (total + limit - 1) // limit if limit > 0 else 1

        return StorageLocationTypeList(
            items=types,
            total=total,
            page=page,
            pages=pages,
            page_size=limit,
        )

    except Exception as e:
        logger.error(f"Error retrieving storage location types: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving storage location types"
        )


@router.post("/location-types", response_model=StorageLocationType, status_code=status.HTTP_201_CREATED)
def create_storage_location_type(
        *,
        db: Session = Depends(get_db),
        type_in: StorageLocationTypeCreate,
        current_user: Any = Depends(get_current_active_user),
) -> StorageLocationType:
    """
    Create a new storage location type.
    """
    try:
        from app.repositories.storage_repository import StorageLocationTypeRepository

        repository = StorageLocationTypeRepository(db)
        type_data = type_in.dict()

        # Add created_by
        type_data["created_by"] = current_user.id

        # Create the type
        location_type = repository.create(type_data)
        return location_type

    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating storage location type: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating storage location type"
        )


@router.get("/location-types/{type_id}", response_model=StorageLocationType)
def get_storage_location_type(
        *,
        db: Session = Depends(get_db),
        type_id: int = Path(..., description="Storage location type ID"),
        current_user: Any = Depends(get_current_active_user),
) -> StorageLocationType:
    """
    Get a specific storage location type by ID.
    """
    try:
        from app.repositories.storage_repository import StorageLocationTypeRepository

        repository = StorageLocationTypeRepository(db)
        location_type = repository.get_by_id_with_properties(type_id)

        if not location_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Storage location type with ID {type_id} not found"
            )

        return location_type

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving storage location type: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving storage location type"
        )


# --- Storage Locations ---

@router.get("/locations", response_model=StorageLocationList)
def list_storage_locations(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
        storage_location_type_id: Optional[int] = Query(None, description="Filter by storage location type ID"),
        section: Optional[str] = Query(None, description="Filter by section"),
        status: Optional[str] = Query(None, description="Filter by location status"),
        search: Optional[str] = Query(None, description="Search term for name"),
        apply_settings: bool = Query(True, description="Whether to apply user settings"),
        # Storage-specific filters
        has_capacity: Optional[bool] = Query(None, description="Filter locations with available capacity"),
        parent_storage_id: Optional[str] = Query(None, description="Filter by parent storage location"),
) -> StorageLocationList:
    """
    Retrieve storage locations with optional filtering and pagination.
    Enhanced with storage-specific filters and settings integration.
    """
    logger.info("Getting storage locations with enhanced API")

    try:
        # Build filters
        filters = {}
        if has_capacity is not None:
            filters["has_capacity"] = has_capacity
        if parent_storage_id:
            filters["parent_storage_id"] = parent_storage_id

        # Get locations using the updated service
        locations, total = service.get_storage_locations(
            skip=skip,
            limit=limit,
            storage_location_type_id=storage_location_type_id,
            search=search,
            status=status,
            section=section,
            apply_settings=apply_settings,
            **filters
        )

        # Calculate pagination
        page = skip // limit + 1 if limit > 0 else 1
        pages = (total + limit - 1) // limit if limit > 0 else 1

        return StorageLocationList(
            items=locations,
            total=total,
            page=page,
            pages=pages,
            page_size=limit,
        )

    except Exception as e:
        logger.error(f"Error retrieving storage locations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving storage locations"
        )


@router.post("/locations", response_model=StorageLocation, status_code=status.HTTP_201_CREATED)
def create_storage_location(
        *,
        db: Session = Depends(get_db),
        location_in: StorageLocationCreate,
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service)
) -> StorageLocation:
    """
    Create a new storage location with dynamic properties.
    """
    try:
        location_data = location_in.dict()
        result = service.create_storage_location(location_data, current_user.id)
        return result

    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating storage location: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating storage location"
        )


@router.get("/locations/{location_id}", response_model=StorageLocation)
def get_storage_location(
        *,
        db: Session = Depends(get_db),
        location_id: str = Path(..., description="Storage location ID"),
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service),
        include_assignments: bool = Query(True, description="Include assignment information"),
        apply_settings: bool = Query(True, description="Whether to apply user settings"),
) -> StorageLocation:
    """
    Get a specific storage location by ID with its properties and optionally assignment info.
    """
    try:
        location = service.get_storage_location(location_id)

        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Storage location with ID {location_id} not found"
            )

        # Apply settings if requested
        if apply_settings and service.security_context and service.settings_service:
            user_id = getattr(getattr(service.security_context, 'current_user', None), 'id', None)
            if user_id:
                location = service.apply_settings_to_locations([location], user_id)[0]

        return location

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving storage location: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving storage location"
        )


@router.put("/locations/{location_id}", response_model=StorageLocation)
def update_storage_location(
        *,
        db: Session = Depends(get_db),
        location_id: str = Path(..., description="Storage location ID"),
        location_in: StorageLocationUpdate,
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service)
) -> StorageLocation:
    """
    Update a storage location with its properties.
    """
    try:
        location_data = location_in.dict(exclude_unset=True)
        location = service.update_storage_location(location_id, location_data, current_user.id)

        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Storage location with ID {location_id} not found"
            )

        return location

    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating storage location: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating storage location"
        )


@router.delete("/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_storage_location(
        *,
        db: Session = Depends(get_db),
        location_id: str = Path(..., description="Storage location ID"),
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service)
) -> None:
    """
    Delete a storage location.
    Note: Will check for active assignments and prevent deletion if any exist.
    """
    try:
        result = service.delete_storage_location(location_id, current_user.id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Storage location with ID {location_id} not found"
            )

    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting storage location: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting storage location"
        )


# --- Storage Cells ---

@router.get("/locations/{location_id}/cells", response_model=StorageCellList)
def list_storage_cells(
        *,
        db: Session = Depends(get_db),
        location_id: str = Path(..., description="Storage location ID"),
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service),
        occupied: Optional[bool] = Query(None, description="Filter by occupied status"),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
) -> StorageCellList:
    """
    Retrieve cells for a storage location with material information.
    """
    logger.info(f"Getting cells for location {location_id}")

    try:
        all_cells = service.get_storage_cells(location_id, occupied)

        # Apply pagination
        total_cells = len(all_cells)
        cells = all_cells[skip: skip + limit]

        return StorageCellList(
            items=cells,
            total=total_cells,
            page=skip // limit + 1,
            pages=(total_cells + limit - 1) // limit,
            page_size=limit,
        )

    except StorageLocationNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage location with ID {location_id} not found"
        )
    except Exception as e:
        logger.error(f"Error retrieving cells: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving storage cells"
        )


@router.post("/locations/{location_id}/cells", response_model=StorageCell, status_code=status.HTTP_201_CREATED)
def create_storage_cell(
        *,
        db: Session = Depends(get_db),
        location_id: str = Path(..., description="Storage location ID"),
        cell_in: StorageCellCreate,
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service)
) -> StorageCell:
    """
    Create a new storage cell for a location.
    """
    try:
        cell_data = cell_in.dict()
        cell_data["storage_id"] = location_id

        cell = service.cell_repository.create(cell_data)
        return cell

    except StorageLocationNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage location with ID {location_id} not found"
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating storage cell: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating storage cell"
        )


# --- Storage Assignments ---

@router.get("/assignments", response_model=StorageAssignmentList)
def list_storage_assignments(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service),
        material_id: Optional[int] = Query(None, ge=1, description="Filter by material ID"),
        material_type_id: Optional[int] = Query(None, ge=1, description="Filter by material type ID"),
        location_id: Optional[str] = Query(None, description="Filter by storage location ID"),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
        apply_settings: bool = Query(True, description="Whether to apply user settings"),
) -> StorageAssignmentList:
    """
    Retrieve storage assignments with optional filtering and pagination.
    Enhanced with settings integration.
    """
    try:
        assignments = service.get_storage_assignments(
            material_id=material_id,
            material_type_id=material_type_id,
            location_id=location_id,
            skip=skip,
            limit=limit
        )

        # Get total count (simplified for development)
        total_assignments = service.get_storage_assignments(
            material_id=material_id,
            material_type_id=material_type_id,
            location_id=location_id,
            skip=0,
            limit=10000
        )
        total = len(total_assignments)

        return StorageAssignmentList(
            items=assignments,
            total=total,
            page=skip // limit + 1,
            pages=(total + limit - 1) // limit,
            page_size=limit,
        )

    except Exception as e:
        logger.error(f"Error retrieving storage assignments: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving storage assignments"
        )


@router.post("/assignments", response_model=StorageAssignment, status_code=status.HTTP_201_CREATED)
def create_storage_assignment(
        *,
        db: Session = Depends(get_db),
        assignment_in: StorageAssignmentCreate,
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service)
) -> StorageAssignment:
    """
    Create a new storage assignment with proper material validation.
    """
    try:
        assignment_data = assignment_in.dict()
        assignment = service.create_storage_assignment(assignment_data, current_user.id)
        return assignment

    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating storage assignment: {e}", exc_info=True)
        if "capacity exceeded" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Storage location capacity exceeded"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating storage assignment"
        )


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_storage_assignment(
        *,
        db: Session = Depends(get_db),
        assignment_id: str = Path(..., description="Storage assignment ID"),
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service)
) -> None:
    """
    Delete a storage assignment.
    """
    try:
        result = service.delete_storage_assignment(assignment_id, current_user.id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Storage assignment with ID {assignment_id} not found"
            )

    except Exception as e:
        logger.error(f"Error deleting storage assignment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting storage assignment"
        )


# --- Storage Moves ---

@router.get("/moves", response_model=StorageMoveList)
def list_storage_moves(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
        material_id: Optional[int] = Query(None, ge=1, description="Filter by material ID"),
        material_type_id: Optional[int] = Query(None, ge=1, description="Filter by material type ID"),
        apply_settings: bool = Query(True, description="Whether to apply user settings"),
) -> StorageMoveList:
    """
    Retrieve storage moves with optional filtering and pagination.
    Enhanced with settings integration.
    """
    try:
        moves = service.get_storage_moves(
            skip=skip,
            limit=limit,
            material_id=material_id,
            material_type_id=material_type_id
        )

        # Get total count
        try:
            all_moves = service.get_storage_moves(
                skip=0,
                limit=10000,
                material_id=material_id,
                material_type_id=material_type_id,
            )
            total = len(all_moves)
        except Exception as e:
            logger.warning(f"Error counting moves: {e}")
            total = skip + len(moves)

        return StorageMoveList(
            items=moves,
            total=total,
            page=skip // limit + 1,
            pages=(total + limit - 1) // limit,
            page_size=limit,
        )

    except Exception as e:
        logger.error(f"Error retrieving storage moves: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving storage moves"
        )


@router.post("/moves", response_model=StorageMove, status_code=status.HTTP_201_CREATED)
def create_storage_move(
        *,
        db: Session = Depends(get_db),
        move_in: StorageMoveCreate,
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service)
) -> StorageMove:
    """
    Create a new storage move with proper material validation.
    """
    try:
        move_data = move_in.dict()
        move = service.create_storage_move(move_data, current_user.id)
        return move

    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except InsufficientInventoryException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating storage move: {e}", exc_info=True)
        if "capacity exceeded" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target storage location capacity exceeded"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating storage move"
        )


# --- Analytics and Reports ---

@router.get("/occupancy", response_model=StorageOccupancyReport)
def get_storage_occupancy_report(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service),
        section: Optional[str] = Query(None, description="Filter by section"),
        storage_location_type_id: Optional[int] = Query(None, description="Filter by storage location type ID"),
) -> StorageOccupancyReport:
    """
    Get comprehensive storage occupancy report.
    Updated to use dynamic storage location types.
    """
    logger.info(f"Generating storage occupancy report, section={section}, type_id={storage_location_type_id}")

    try:
        report = service.get_storage_occupancy_report(section, storage_location_type_id)
        return report

    except Exception as e:
        logger.error(f"Error generating occupancy report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating occupancy report"
        )


@router.get("/material-types-summary", response_model=MaterialTypeStorageSummary)
def get_material_types_in_storage_summary(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service)
) -> MaterialTypeStorageSummary:
    """
    Get summary of material types currently in storage.
    This leverages the DynamicMaterial relationships.
    """
    logger.info("Generating material types in storage summary")

    try:
        summary = service.assignment_repository.get_material_types_summary()

        return MaterialTypeStorageSummary(
            success=True,
            material_types=summary,
            total_types=len(summary),
        )

    except Exception as e:
        logger.error(f"Error generating material types summary: {e}", exc_info=True)
        return MaterialTypeStorageSummary(
            success=False,
            error=str(e),
            material_types={},
            total_types=0,
        )


# --- Enhanced Analytics (New) ---

@router.get("/analytics/storage-distribution", response_model=Dict[str, Any])
def get_storage_distribution_analytics(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service),
        storage_location_type_id: Optional[int] = Query(None, description="Filter by storage location type"),
        section: Optional[str] = Query(None, description="Filter by section"),
) -> Dict[str, Any]:
    """
    Get analytics on how materials are distributed across storage locations.
    Enhanced version that leverages dynamic storage location types.
    """
    try:
        # Get storage locations with filters
        locations, _ = service.get_storage_locations(
            skip=0,
            limit=10000,
            storage_location_type_id=storage_location_type_id,
            section=section,
            apply_settings=False
        )

        # Calculate distribution analytics
        analytics_data = {
            "total_locations": len(locations),
            "locations_with_assignments": 0,
            "locations_without_assignments": 0,
            "multi_material_locations": 0,
            "distribution_by_type": {},
            "distribution_by_section": {},
            "top_storage_locations": [],
            "locations_needing_attention": [],
            "capacity_efficiency": 0.0,
            "space_utilization_score": 0.0
        }

        total_capacity = 0
        total_utilized = 0
        locations_with_assignments = 0
        multi_material_locations = 0
        type_distribution = {}
        section_distribution = {}
        location_details = []

        for location in locations:
            capacity = location.capacity or 0
            utilized = location.utilized or 0
            assignment_count = len(location.assignments) if hasattr(location, 'assignments') else 0

            total_capacity += capacity
            total_utilized += utilized

            if assignment_count > 0:
                locations_with_assignments += 1

            if assignment_count > 1:
                multi_material_locations += 1

            # Group by storage location type
            if location.storage_location_type:
                type_name = location.storage_location_type.name
                if type_name not in type_distribution:
                    type_distribution[type_name] = {
                        "count": 0,
                        "total_capacity": 0,
                        "total_utilized": 0,
                        "assignments": 0
                    }
                type_distribution[type_name]["count"] += 1
                type_distribution[type_name]["total_capacity"] += capacity
                type_distribution[type_name]["total_utilized"] += utilized
                type_distribution[type_name]["assignments"] += assignment_count

            # Group by section
            section_name = location.section or "Unknown"
            if section_name not in section_distribution:
                section_distribution[section_name] = {
                    "count": 0,
                    "total_capacity": 0,
                    "total_utilized": 0,
                    "assignments": 0
                }
            section_distribution[section_name]["count"] += 1
            section_distribution[section_name]["total_capacity"] += capacity
            section_distribution[section_name]["total_utilized"] += utilized
            section_distribution[section_name]["assignments"] += assignment_count

            # Store location details for ranking
            utilization_pct = (utilized / capacity * 100) if capacity > 0 else 0
            location_details.append({
                "id": str(location.id),
                "name": location.name,
                "capacity": capacity,
                "utilized": utilized,
                "assignments": assignment_count,
                "utilization_percentage": round(utilization_pct, 1),
                "type": location.storage_location_type.name if location.storage_location_type else "Unknown"
            })

        # Calculate efficiency metrics
        analytics_data["locations_with_assignments"] = locations_with_assignments
        analytics_data["locations_without_assignments"] = len(locations) - locations_with_assignments
        analytics_data["multi_material_locations"] = multi_material_locations
        analytics_data["distribution_by_type"] = type_distribution
        analytics_data["distribution_by_section"] = section_distribution

        if total_capacity > 0:
            analytics_data["capacity_efficiency"] = round((total_utilized / total_capacity) * 100, 1)

        # Calculate space utilization score (locations with assignments vs total locations)
        if len(locations) > 0:
            analytics_data["space_utilization_score"] = round((locations_with_assignments / len(locations)) * 100, 1)

        # Get top storage locations by utilization
        sorted_locations = sorted(location_details, key=lambda x: x["utilization_percentage"], reverse=True)
        analytics_data["top_storage_locations"] = sorted_locations[:10]

        # Identify locations needing attention (very low or very high utilization)
        locations_needing_attention = [
            loc for loc in location_details
            if (loc["capacity"] > 0 and (loc["utilization_percentage"] >= 95 or loc["utilization_percentage"] <= 5))
        ]
        analytics_data["locations_needing_attention"] = locations_needing_attention

        return analytics_data

    except Exception as e:
        logger.error(f"Error generating storage distribution analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating storage analytics"
        )


# --- Material-Storage Integration (New) ---

@router.get("/materials/{material_id}/storage-info", response_model=Dict[str, Any])
def get_material_storage_info(
        *,
        db: Session = Depends(get_db),
        material_id: int = Path(..., gt=0, description="The ID of the material"),
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service)
) -> Dict[str, Any]:
    """
    Get comprehensive storage information for a specific material.
    This endpoint bridges the material and storage systems.
    """
    try:
        # Get assignments for this material
        assignments = service.assignment_repository.get_assignments_by_material(material_id)

        if not assignments:
            return {
                "material_id": material_id,
                "stored": False,
                "storage_locations": [],
                "total_assigned_quantity": 0.0,
                "storage_locations_count": 0,
                "recent_moves": []
            }

        # Process assignments
        storage_locations = []
        total_quantity = 0.0

        for assignment in assignments:
            if assignment.location:
                storage_locations.append({
                    "location_id": str(assignment.location.id),
                    "location_name": assignment.location.name,
                    "storage_location_type": {
                        "id": assignment.location.storage_location_type.id,
                        "name": assignment.location.storage_location_type.name,
                        "icon": assignment.location.storage_location_type.icon,
                        "color_scheme": assignment.location.storage_location_type.color_scheme
                    } if assignment.location.storage_location_type else None,
                    "section": assignment.location.section,
                    "quantity": assignment.quantity,
                    "assigned_date": assignment.assigned_date,
                    "position": assignment.position
                })
                total_quantity += assignment.quantity or 0.0

        # Get recent moves for this material
        recent_moves = service.move_repository.get_moves_by_material(material_id, skip=0, limit=5)
        move_data = []

        for move in recent_moves:
            move_info = {
                "move_id": str(move.id),
                "from_location": {
                    "id": str(move.from_location.id),
                    "name": move.from_location.name
                } if move.from_location else None,
                "to_location": {
                    "id": str(move.to_location.id),
                    "name": move.to_location.name
                } if move.to_location else None,
                "quantity": move.quantity,
                "move_date": move.move_date,
                "moved_by": move.moved_by,
                "reason": move.reason
            }
            move_data.append(move_info)

        return {
            "material_id": material_id,
            "stored": True,
            "storage_locations": storage_locations,
            "total_assigned_quantity": total_quantity,
            "storage_locations_count": len(storage_locations),
            "is_multi_location_stored": len(storage_locations) > 1,
            "primary_storage_location": storage_locations[0] if storage_locations else None,
            "recent_moves": move_data
        }

    except Exception as e:
        logger.error(f"Error retrieving material storage info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving material storage information"
        )


# --- Utility Operations ---

@router.post("/sync-utilization", response_model=StorageUtilizationSyncResult)
def sync_storage_utilization(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service)
) -> StorageUtilizationSyncResult:
    """
    Synchronize storage utilization counts from assignments.
    """
    try:
        result = service.update_storage_utilization_from_assignments()
        return StorageUtilizationSyncResult(
            success=True,
            message=f"Successfully synchronized storage utilization. Updated {result['updated_count']} locations.",
            updated_count=result["updated_count"],
            updated_locations=result["updated_locations"],
        )

    except Exception as e:
        logger.error(f"Error synchronizing storage utilization: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error synchronizing storage utilization: {str(e)}"
        )


# --- Settings Integration (New) ---

@router.get("/settings/storage-ui", response_model=Dict[str, Any])
def get_storage_ui_settings(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        settings_service: SettingsService = Depends(get_settings_service)
) -> Dict[str, Any]:
    """
    Get storage UI settings for the current user.
    """
    try:
        storage_ui = settings_service.get_setting(
            key="storage_ui",
            scope_type="user",
            scope_id=str(current_user.id)
        )

        if not storage_ui:
            # Return default settings
            storage_ui = {
                "card_view": {
                    "display_thumbnail": True,
                    "max_properties": 4,
                    "show_utilization": True
                },
                "list_view": {
                    "default_columns": ["name", "type", "capacity", "utilized", "section", "status"],
                    "show_thumbnail": True
                },
                "grid_view": {
                    "show_utilization": True,
                    "show_capacity": True,
                    "compact_mode": False
                }
            }

        return storage_ui

    except Exception as e:
        logger.error(f"Error retrieving storage UI settings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving storage UI settings"
        )


@router.put("/settings/storage-ui", response_model=Dict[str, Any])
def update_storage_ui_settings(
        *,
        db: Session = Depends(get_db),
        settings_data: Dict[str, Any],
        current_user: Any = Depends(get_current_active_user),
        settings_service: SettingsService = Depends(get_settings_service)
) -> Dict[str, Any]:
    """
    Update storage UI settings for the current user.
    """
    try:
        settings_service.set_setting(
            key="storage_ui",
            value=settings_data,
            scope_type="user",
            scope_id=str(current_user.id)
        )

        return {
            "success": True,
            "message": "Storage UI settings updated successfully",
            "settings": settings_data
        }

    except Exception as e:
        logger.error(f"Error updating storage UI settings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating storage UI settings"
        )


# --- System Monitoring ---

@router.get("/system/health", response_model=StorageOperationResult, include_in_schema=False)
def check_storage_system_health(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        service: StorageLocationService = Depends(get_storage_location_service)
) -> StorageOperationResult:
    """
    Check storage system health (admin only).
    """
    if not hasattr(current_user, "is_admin") or not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for health monitoring"
        )

    try:
        # Basic health checks
        locations, total_locations = service.get_storage_locations(skip=0, limit=1, apply_settings=False)
        assignments = service.get_storage_assignments(skip=0, limit=1)

        health_data = {
            "storage_service": "operational",
            "database_connection": "active",
            "locations_accessible": total_locations >= 0,
            "assignments_accessible": len(assignments) >= 0,
            "total_locations": total_locations,
            "dynamic_types_supported": True,
            "settings_integration": service.settings_service is not None,
            "timestamp": datetime.now().isoformat(),
        }

        return StorageOperationResult(
            success=True,
            message="Storage system is healthy",
            data=health_data,
        )

    except Exception as e:
        logger.error(f"Storage system health check failed: {e}", exc_info=True)
        return StorageOperationResult(
            success=False,
            message=f"Storage system health check failed: {str(e)}",
            data={"error": str(e)},
        )