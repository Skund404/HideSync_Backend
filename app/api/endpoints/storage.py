# File: app/api/endpoints/storage.py
"""
Storage API endpoints for HideSync.

This module provides endpoints for managing storage locations, cells,
assignments, and movements of inventory items between locations.
"""

from typing import Any, List, Optional, Dict
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_current_active_user, get_db
from app.schemas.compatibility import (
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
from app.core.exceptions import (
    InsufficientInventoryException as InsufficientQuantityException,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/locations")
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
        sort_by: str = Query("name", description="Field to sort by"),
        sort_dir: str = Query("asc", description="Sort direction (asc or desc)")
) -> Dict[str, Any]:
    """
    Retrieve storage locations with optional filtering and pagination.
    Returns a paginated response with total count and page information.
    """
    logger.info(f"Getting storage locations with optimized pagination")

    try:
        # Validate sort direction
        if sort_dir.lower() not in ["asc", "desc"]:
            sort_dir = "asc"

        # Build search parameters
        search_params = {}
        if type:
            search_params["type"] = type
        if section:
            search_params["section"] = section
        if status:
            search_params["status"] = status
        if search:
            search_params["search"] = search

        # Add sorting parameters
        search_params["sort_by"] = sort_by
        search_params["sort_dir"] = sort_dir

        # Initialize service
        storage_service = StorageLocationService(db)

        # First get total count
        # Since there's no direct count method, we'll first get total count by
        # making a smaller query that counts results
        try:
            # Try to use repository method if available
            total = storage_service.repository.count(
                **{k: v for k, v in search_params.items() if k not in ["sort_by", "sort_dir"]}
            )
        except (AttributeError, Exception) as e:
            logger.warning(f"Count method not available, will estimate total: {e}")
            # If no count method, we'll estimate using a full query with no limit
            try:
                # Try to get a quick count by getting IDs only
                temp_locations = storage_service.get_storage_locations(
                    skip=0,
                    limit=10000,  # Large limit, but not unlimited to prevent memory issues
                    search_params=search_params
                )
                total = len(temp_locations)
            except Exception as e2:
                logger.warning(f"Failed to get count estimation: {e2}")
                total = None

        # Get paginated locations
        locations = storage_service.get_storage_locations(
            skip=skip, limit=limit, search_params=search_params
        )

        # If we couldn't get an accurate count earlier, estimate based on results
        if total is None:
            total = skip + len(locations)
            # If we got exactly the limit, there might be more
            if len(locations) >= limit:
                total += 1

        logger.info(f"Retrieved {len(locations)} storage locations")

        # Calculate pagination information
        page = skip // limit + 1 if limit > 0 else 1
        pages = (total + limit - 1) // limit if limit > 0 else 1

        # Return frontend-friendly paginated response
        return {
            "items": locations,  # Already formatted by the service
            "total": total,
            "page": page,
            "pages": pages,
            "page_size": limit
        }

    except Exception as e:
        logger.error(f"Error retrieving storage locations: {e}", exc_info=True)
        # Return empty paginated response to prevent frontend errors
        return {
            "items": [],
            "total": 0,
            "page": 1,
            "pages": 0,
            "page_size": limit
        }


@router.post("/locations", status_code=status.HTTP_201_CREATED)
def create_storage_location(
        *,
        db: Session = Depends(get_db),
        location_in: StorageLocationCreate,
        current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Create a new storage location.
    """
    # Convert to dict and fix the type
    location_dict = location_in.dict() if hasattr(location_in, 'dict') else dict(location_in)

    # Fix the type field by removing enum prefix and converting to lowercase
    if "type" in location_dict and isinstance(location_dict["type"], str):
        type_value = location_dict["type"]
        # Remove enum prefix if present (StorageLocationType.CABINET -> cabinet)
        if "." in type_value:
            type_value = type_value.split(".")[-1]
        location_dict["type"] = type_value.lower()

    storage_service = StorageLocationService(db)
    try:
        # The create_storage_location method already formats the result
        result = storage_service.create_storage_location(location_dict, current_user.id)
        return result
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/sync-utilization", status_code=status.HTTP_200_OK)
def sync_storage_utilization(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
):
    """
    Synchronize storage utilization counts from assignments.

    This endpoint updates the 'utilized' field in storage_locations based on
    the actual assignments in the storage_assignments table.
    """
    storage_service = StorageLocationService(db)
    try:
        result = storage_service.update_storage_utilization_from_assignments()
        return {
            "success": True,
            "message": f"Successfully synchronized storage utilization. Updated {result['updated_count']} locations.",
            "updated_locations": result["updated_locations"]
        }
    except Exception as e:
        logger.error(f"Error synchronizing storage utilization: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error synchronizing storage utilization: {str(e)}"
        )


@router.put("/locations/{location_id}")
def update_storage_location(
        *,
        db: Session = Depends(get_db),
        location_id: str = Path(
            ..., description="The ID of the storage location to update"
        ),
        location_in: StorageLocationUpdate,
        current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Update a storage location.
    """
    storage_service = StorageLocationService(db)
    try:
        # Update method already formats the response correctly
        location_data = location_in.dict(exclude_unset=True) if hasattr(location_in, 'dict') else dict(location_in)
        return storage_service.update_storage_location(
            location_id, location_data, current_user.id
        )
    except StorageLocationNotFoundException:
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
    """
    storage_service = StorageLocationService(db)
    try:
        storage_service.delete_storage_location(location_id, current_user.id)
    except StorageLocationNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage location with ID {location_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Storage cells
@router.get("/locations/{location_id}/cells")
def list_storage_cells(
        *,
        db: Session = Depends(get_db),
        location_id: str = Path(..., description="The ID of the storage location"),
        current_user: Any = Depends(get_current_active_user),
        occupied: Optional[bool] = Query(None, description="Filter by occupied status"),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
        sort_by: str = Query("position.row", description="Field to sort by"),
        sort_dir: str = Query("asc", description="Sort direction (asc or desc)")
) -> Dict[str, Any]:
    """
    Retrieve cells for a storage location with pagination.
    Returns a paginated response with total count and page information.
    """
    logger.info(f"Getting cells for location {location_id}")

    # Validate sort direction
    if sort_dir.lower() not in ["asc", "desc"]:
        sort_dir = "asc"

    storage_service = StorageLocationService(db)
    try:
        # First check if location exists
        try:
            storage_service.get_storage_location(location_id)
        except StorageLocationNotFoundException:
            logger.warning(f"Storage location {location_id} not found")
            # Return fallback grid for frontend compatibility in proper pagination format
            fallback_grid = []
            total_cells = 16  # 4x4 grid

            for row in range(1, 5):
                for col in range(1, 5):
                    if len(fallback_grid) >= limit:
                        break
                    if (row - 1) * 4 + (col - 1) >= skip:
                        fallback_grid.append({
                            "id": f"cell_{location_id}_{row}_{col}",
                            "storage_id": location_id,
                            "position": {"row": row, "column": col},
                            "occupied": False,
                            "material_id": None
                        })

            # Return paginated response
            return {
                "items": fallback_grid,
                "total": total_cells,
                "page": skip // limit + 1,
                "pages": (total_cells + limit - 1) // limit,
                "page_size": limit
            }

        # Get total count of cells for pagination
        total = None
        try:
            # Try to get count efficiently if repository has method
            all_cells = storage_service.get_storage_cells(location_id, occupied)
            total = len(all_cells)

            # Apply pagination manually since the service method doesn't
            # support pagination directly
            cells = all_cells[skip:skip + limit]
        except Exception as e:
            logger.error(f"Error getting cells: {e}", exc_info=True)
            # Create a fallback grid as in the original code
            cells = []
            for row in range(1, 5):
                for col in range(1, 5):
                    cells.append({
                        "id": f"cell_{location_id}_{row}_{col}",
                        "storage_id": location_id,
                        "position": {"row": row, "column": col},
                        "occupied": False,
                        "material_id": None
                    })
            total = len(cells)

        logger.info(f"Retrieved {len(cells)} cells for location {location_id}")

        # Return paginated response
        return {
            "items": cells,
            "total": total,
            "page": skip // limit + 1,
            "pages": (total + limit - 1) // limit,
            "page_size": limit
        }

    except Exception as e:
        logger.error(f"Error retrieving cells: {e}", exc_info=True)
        # Create a fallback grid for error cases with proper pagination format
        fallback_grid = []
        total_cells = 16  # Standard 4x4 grid

        for row in range(1, 5):
            for col in range(1, 5):
                if len(fallback_grid) >= limit:
                    break
                if (row - 1) * 4 + (col - 1) >= skip:
                    fallback_grid.append({
                        "id": f"cell_{location_id}_{row}_{col}",
                        "storage_id": location_id,
                        "position": {"row": row, "column": col},
                        "occupied": False,
                        "material_id": None
                    })

        return {
            "items": fallback_grid,
            "total": total_cells,
            "page": skip // limit + 1,
            "pages": (total_cells + limit - 1) // limit,
            "page_size": limit
        }


@router.post(
    "/locations/{location_id}/cells",
    status_code=status.HTTP_201_CREATED,
)
def create_storage_cell(
        *,
        db: Session = Depends(get_db),
        location_id: str = Path(..., description="The ID of the storage location"),
        cell_in: StorageCellCreate,
        current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Create a new storage cell for a location.
    """
    storage_service = StorageLocationService(db)
    try:
        cell = storage_service.create_storage_cell(
            location_id, cell_in, current_user.id
        )

        # Return formatted cell data
        return cell  # The service should already format this
    except StorageLocationNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage location with ID {location_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Storage assignments
@router.get("/assignments")
def list_storage_assignments(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        item_id: Optional[int] = Query(None, ge=1, description="Filter by item ID"),
        item_type: Optional[str] = Query(None, description="Filter by item type"),
        location_id: Optional[str] = Query(None, description="Filter by storage location ID"),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
        sort_by: str = Query("created_at", description="Field to sort by"),
        sort_dir: str = Query("desc", description="Sort direction (asc or desc)")
) -> Dict[str, Any]:
    """
    Retrieve storage assignments with optional filtering and pagination.
    Returns a paginated response with total count and page information.
    """
    # Validate sort direction
    if sort_dir.lower() not in ["asc", "desc"]:
        sort_dir = "desc"  # Default for assignments is newest first

    storage_service = StorageLocationService(db)
    try:
        # Since there's no direct pagination support in the service method,
        # we'll need to get all assignments first and paginate in memory
        assignments = storage_service.get_storage_assignments(
            item_id=item_id,
            item_type=item_type,
            location_id=location_id
        )

        # Get total count for pagination
        total = len(assignments)

        # Apply pagination manually
        paginated_assignments = assignments[skip:skip + limit]

        # Return paginated response
        return {
            "items": paginated_assignments,
            "total": total,
            "page": skip // limit + 1,
            "pages": (total + limit - 1) // limit,
            "page_size": limit
        }
    except Exception as e:
        logger.error(f"Error retrieving storage assignments: {e}", exc_info=True)
        # Return empty paginated response
        return {
            "items": [],
            "total": 0,
            "page": 1,
            "pages": 0,
            "page_size": limit
        }


@router.post(
    "/assignments",
    status_code=status.HTTP_201_CREATED,
)
def create_storage_assignment(
        *,
        db: Session = Depends(get_db),
        assignment_in: StorageAssignmentCreate,
        current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Create a new storage assignment.
    """
    storage_service = StorageLocationService(db)
    try:
        assignment_data = assignment_in.dict() if hasattr(assignment_in, 'dict') else dict(assignment_in)
        assignment = storage_service.create_storage_assignment(
            assignment_data, current_user.id
        )
        return assignment  # The service should already format this
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        if "capacity exceeded" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Storage location capacity exceeded",
            )
        else:
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
@router.get("/moves")
def list_storage_moves(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
        item_id: Optional[int] = Query(None, ge=1, description="Filter by item ID"),
        item_type: Optional[str] = Query(None, description="Filter by item type"),
        sort_by: str = Query("created_at", description="Field to sort by"),
        sort_dir: str = Query("desc", description="Sort direction (asc or desc)")
) -> Dict[str, Any]:
    """
    Retrieve storage moves with optional filtering and pagination.
    Returns a paginated response with total count and page information.
    """
    # Validate sort direction
    if sort_dir.lower() not in ["asc", "desc"]:
        sort_dir = "desc"  # Default for moves is newest first

    storage_service = StorageLocationService(db)
    try:
        # The service method already supports pagination
        moves = storage_service.get_storage_moves(
            skip=skip,
            limit=limit,
            item_id=item_id,
            item_type=item_type
        )

        # Try to get total count for more accurate pagination
        # Since there's no direct count method, we'll need to make an estimation
        total = None
        try:
            # Try to get all moves to count them - this is not efficient,
            # but it's a fallback without a direct count method
            all_moves = storage_service.get_storage_moves(
                skip=0,
                limit=10000,  # Large but not unlimited
                item_id=item_id,
                item_type=item_type
            )
            total = len(all_moves)
        except Exception as e:
            logger.warning(f"Error counting moves: {e}")
            # If we couldn't get the count, estimate based on results
            total = skip + len(moves)
            if len(moves) >= limit:
                total += 1

        # Return paginated response
        return {
            "items": moves,
            "total": total,
            "page": skip // limit + 1,
            "pages": (total + limit - 1) // limit,
            "page_size": limit
        }
    except Exception as e:
        logger.error(f"Error retrieving storage moves: {e}", exc_info=True)
        # Return empty paginated response
        return {
            "items": [],
            "total": 0,
            "page": 1,
            "pages": 0,
            "page_size": limit
        }


@router.post("/moves", status_code=status.HTTP_201_CREATED)
def create_storage_move(
        *,
        db: Session = Depends(get_db),
        move_in: StorageMoveCreate,
        current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Create a new storage move.
    """
    storage_service = StorageLocationService(db)
    try:
        move_data = move_in.dict() if hasattr(move_in, 'dict') else dict(move_in)
        move = storage_service.create_storage_move(move_data, current_user.id)
        return move  # The service should already format this
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except StorageLocationNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        if "capacity exceeded" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target storage location capacity exceeded",
            )
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/occupancy")
def get_storage_occupancy_report(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
        section: Optional[str] = Query(None, description="Filter by section"),
        type: Optional[str] = Query(None, description="Filter by location type"),
) -> Dict[str, Any]:
    """
    Get storage occupancy report.
    """
    logger.info(f"Generating storage occupancy report, section={section}, type={type}")

    storage_service = StorageLocationService(db)
    try:
        report = storage_service.get_storage_occupancy_report(section, type)
        logger.info(f"Successfully generated occupancy report with {report.get('total_locations', 0)} locations")
        return report
    except Exception as e:
        logger.error(f"Error generating occupancy report: {e}", exc_info=True)
        # Return a minimal report to prevent frontend errors
        return {
            "total_locations": 0,
            "total_capacity": 0,
            "total_utilized": 0,
            "utilization_percentage": 0,
            "by_type": {},
            "by_section": {},
            "locations_by_type": {},
            "locations_by_section": {},
            "locations_at_capacity": 0,
            "locations_nearly_empty": 0,
            "most_utilized_locations": [],
            "least_utilized_locations": [],
            "recommendations": ["Unable to generate occupancy report"]
        }


# Add a monitoring endpoint as suggested in the guide
@router.get("/system/memory", include_in_schema=False)
def check_memory_usage(
        *,
        current_user: Any = Depends(get_current_active_user),
):
    """Check current memory usage (admin only)."""
    # Verify the user has admin permissions
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for memory usage monitoring"
        )

    try:
        import psutil
        import gc

        # Force garbage collection before measuring
        gc.collect()

        # Get memory info
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)

        # Get database connection pool info if possible
        pool_info = {
            "total_connections": "N/A",
            "idle_connections": "N/A",
            "in_use_connections": "N/A"
        }

        return {
            "memory_usage_mb": round(memory_mb, 2),
            "percent_memory": round(process.memory_percent(), 2),
            "db_connections": pool_info.get("total_connections", "N/A"),
            "db_idle_connections": pool_info.get("idle_connections", "N/A"),
            "db_in_use_connections": pool_info.get("in_use_connections", "N/A"),
            "gc_counts": gc.get_count()
        }
    except ImportError:
        return {"error": "psutil module not available for memory monitoring"}
    except Exception as e:
        logger.error(f"Error checking memory usage: {e}", exc_info=True)
        return {"error": f"Error monitoring memory: {str(e)}"}