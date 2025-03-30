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


from typing import List, Optional, Any
from fastapi import Query, Depends
from sqlalchemy.orm import Session


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
    """
    logger.info(f"Getting storage locations with service pattern")

    try:
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

        # Use service pattern for data access
        storage_service = StorageLocationService(db)
        locations = storage_service.get_storage_locations(
            skip=skip, limit=limit, search_params=search_params
        )

        # Convert enum values before returning to FastAPI
        for location in locations:
            try:
                convert_enum_values(location)
            except Exception as e:
                logger.error(f"Error converting enums for location {location.id}: {e}")
                # Continue with other locations

        logger.info(f"Retrieved {len(locations)} storage locations")

        # Return a list of dictionaries instead of model objects to avoid serialization issues
        try:
            return [dict(location) if hasattr(location, '__dict__') else location for location in locations]
        except Exception as e:
            logger.error(f"Error during final serialization: {e}", exc_info=True)
            # If serialization fails, try to extract just the basic fields
            basic_locations = []
            for loc in locations:
                try:
                    basic_loc = {
                        "id": str(getattr(loc, 'id', '')),
                        "name": str(getattr(loc, 'name', 'Unknown')),
                        "type": getattr(loc, 'type', 'other'),
                        "section": getattr(loc, 'section', ''),
                        "capacity": int(getattr(loc, 'capacity', 0)),
                        "utilized": int(getattr(loc, 'utilized', 0)),
                        "status": getattr(loc, 'status', 'ACTIVE'),
                        "dimensions": {"width": 4, "height": 4},
                    }
                    basic_locations.append(basic_loc)
                except Exception as e2:
                    logger.error(f"Error extracting basic fields for location: {e2}")
            return basic_locations

    except Exception as e:
        logger.error(f"Error retrieving storage locations: {e}", exc_info=True)
        # Return empty list on error to prevent frontend errors
        return []

def convert_enum_values(obj):
    """Convert any enum values to their string representation."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == 'type' and isinstance(value, str) and '.' in value:
                # Convert "StorageLocationType.CABINET" to "cabinet"
                obj[key] = value.split('.')[-1].lower()
            elif key == 'type' and hasattr(value, 'value'):
                # Convert enum objects to their string value
                obj[key] = value.value.lower()
    elif hasattr(obj, '__dict__'):
        if hasattr(obj, 'type'):
            if isinstance(obj.type, str) and '.' in obj.type:
                obj.type = obj.type.split('.')[-1].lower()
            elif hasattr(obj.type, 'value'):
                obj.type = obj.type.value.lower()
    return obj

@router.post("/locations", response_model=StorageLocation, status_code=status.HTTP_201_CREATED)
def create_storage_location(
        *,
        db: Session = Depends(get_db),
        location_in: StorageLocationCreate,
        current_user: Any = Depends(get_current_active_user),
) -> StorageLocation:
    """
    Create a new storage location.
    """
    # Convert to dict and fix the type
    location_dict = dict(location_in)

    # Fix the type field by removing enum prefix and converting to lowercase
    if "type" in location_dict and isinstance(location_dict["type"], str):
        type_value = location_dict["type"]
        # Remove enum prefix if present (StorageLocationType.CABINET -> cabinet)
        if "." in type_value:
            type_value = type_value.split(".")[-1]
        location_dict["type"] = type_value.lower()

    storage_service = StorageLocationService(db)
    try:
        result = storage_service.create_storage_location(location_dict, current_user.id)

        # Ensure the result type is a string, not an enum
        if hasattr(result, 'type') and hasattr(result.type, 'value'):
            result.type = result.type.value
        elif isinstance(result, dict) and 'type' in result:
            if hasattr(result['type'], 'value'):
                result['type'] = result['type'].value

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

def _format_location_for_api(self, location) -> Dict[str, Any]:
    """
    Format a storage location object for API response with robust error handling.
    Ensures enum values are converted to strings.
    """
    try:
        # Handle empty location
        if not location:
            logger.warning("Attempting to format None location object")
            return {
                "id": "unknown",
                "name": "Unknown Location",
                "type": "other",
                "status": "UNKNOWN"
            }

        # Create a base dictionary
        result = {}

        # Get ID with type handling
        try:
            location_id = getattr(location, 'id', None)
            if location_id is None:
                location_id = getattr(location, 'uuid', 'unknown')
            result["id"] = str(location_id)
        except Exception:
            result["id"] = "unknown"

        # Safely get attributes with defaults
        attributes = {
            "name": ("name", "Unknown Location", str),
            "section": ("section", "", str),
            "description": ("description", "", str),
            "capacity": ("capacity", 0, int),
            "utilized": ("utilized", 0, int),
            "status": ("status", "ACTIVE", str),
            "parent_id": ("parent_id", None, lambda x: str(x) if x else None)
        }

        for key, (attr_name, default, converter) in attributes.items():
            try:
                value = getattr(location, attr_name, default)
                if value is not None:
                    result[key] = converter(value)
                else:
                    result[key] = default
            except Exception:
                result[key] = default

        # Special handling for type field to ensure it's a string
        try:
            type_value = getattr(location, 'type', 'other')

            # Convert enum to string if it's an enum
            if hasattr(type_value, 'value'):
                result["type"] = type_value.value.lower()
            # If it's already a string but contains enum prefix
            elif isinstance(type_value, str) and '.' in type_value:
                result["type"] = type_value.split('.')[-1].lower()
            # If it's a string, ensure it's lowercase
            elif isinstance(type_value, str):
                result["type"] = type_value.lower()
            else:
                result["type"] = "other"
        except Exception:
            result["type"] = "other"

        # Handle dimensions with special care
        try:
            dimensions = getattr(location, 'dimensions', None)
            if dimensions:
                # Handle string format (JSON)
                if isinstance(dimensions, str):
                    try:
                        import json
                        dimensions = json.loads(dimensions)
                    except:
                        dimensions = {"width": 4, "height": 4}
                # Handle dict format
                elif isinstance(dimensions, dict):
                    pass
                # Handle other formats
                else:
                    dimensions = {"width": 4, "height": 4}
            else:
                dimensions = {"width": 4, "height": 4}

            result["dimensions"] = dimensions
        except Exception:
            result["dimensions"] = {"width": 4, "height": 4}

        # Add timestamps if available
        for timestamp in ["created_at", "updated_at", "last_modified"]:
            try:
                value = getattr(location, timestamp, None)
                if value:
                    if hasattr(value, 'isoformat'):
                        result[timestamp] = value.isoformat()
                    else:
                        result[timestamp] = str(value)
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"Error formatting location for API: {e}")
        # Return minimal safe dictionary
        return {
            "id": str(getattr(location, 'id', 'unknown')),
            "name": "Error Formatting Location",
            "type": "other",
            "status": "UNKNOWN",
            "capacity": 0,
            "utilized": 0,
            "dimensions": {"width": 4, "height": 4},
            "_error": str(e)
        }
def _convert_enum_values(obj):
    """Convert any enum values to their string representation."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == 'type' and isinstance(value, str) and '.' in value:
                # Convert "StorageLocationType.CABINET" to "cabinet"
                obj[key] = value.split('.')[-1].lower()
            elif key == 'type' and hasattr(value, 'value'):
                # Convert enum objects to their string value
                obj[key] = value.value.lower()
    elif hasattr(obj, '__dict__'):
        if hasattr(obj, 'type'):
            if isinstance(obj.type, str) and '.' in obj.type:
                obj.type = obj.type.split('.')[-1].lower()
            elif hasattr(obj.type, 'value'):
                obj.type = obj.type.value.lower()
    return obj


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
    """
    storage_service = StorageLocationService(db)
    try:
        return storage_service.update_storage_location(
            location_id, location_in.dict(exclude_unset=True), current_user.id
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
    """
    logger.info(f"Getting cells for location {location_id}")

    storage_service = StorageLocationService(db)
    try:
        # First verify location exists
        try:
            storage_service.get_storage_location(location_id)
        except StorageLocationNotFoundException:
            logger.warning(f"Storage location {location_id} not found")
            # Return fallback grid for frontend compatibility
            fallback_grid = []
            for row in range(1, 5):
                for col in range(1, 5):
                    fallback_grid.append({
                        "id": f"cell_{location_id}_{row}_{col}",
                        "storage_id": location_id,
                        "position": {"row": row, "column": col},
                        "occupied": False,
                        "material_id": None
                    })
            return fallback_grid

        # Get cells with optional filter
        cells = storage_service.get_storage_cells(location_id, occupied)
        logger.info(f"Retrieved {len(cells)} cells for location {location_id}")
        return cells

    except Exception as e:
        logger.error(f"Error retrieving cells: {e}", exc_info=True)
        # Create a fallback grid for error cases
        fallback_grid = []
        for row in range(1, 5):
            for col in range(1, 5):
                fallback_grid.append({
                    "id": f"cell_{location_id}_{row}_{col}",
                    "storage_id": location_id,
                    "position": {"row": row, "column": col},
                    "occupied": False,
                    "material_id": None
                })
        return fallback_grid


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
    """
    storage_service = StorageLocationService(db)
    try:
        return storage_service.create_storage_cell(
            location_id, cell_in, current_user.id
        )
    except StorageLocationNotFoundException:
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
    """
    storage_service = StorageLocationService(db)
    try:
        return storage_service.get_storage_assignments(
            item_id=item_id, item_type=item_type, location_id=location_id
        )
    except Exception as e:
        logger.error(f"Error retrieving storage assignments: {e}", exc_info=True)
        return []


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
    """
    storage_service = StorageLocationService(db)
    try:
        return storage_service.create_storage_assignment(
            assignment_in.dict(), current_user.id
        )
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
    """
    storage_service = StorageLocationService(db)
    try:
        return storage_service.get_storage_moves(
            skip=skip, limit=limit, item_id=item_id, item_type=item_type
        )
    except Exception as e:
        logger.error(f"Error retrieving storage moves: {e}", exc_info=True)
        return []


@router.post("/moves", response_model=StorageMove, status_code=status.HTTP_201_CREATED)
def create_storage_move(
        *,
        db: Session = Depends(get_db),
        move_in: StorageMoveCreate,
        current_user: Any = Depends(get_current_active_user),
) -> StorageMove:
    """
    Create a new storage move.
    """
    storage_service = StorageLocationService(db)
    try:
        return storage_service.create_storage_move(move_in.dict(), current_user.id)
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
    """
    logger.info(f"Generating storage occupancy report, section={section}, type={type}")

    storage_service = StorageLocationService(db)
    try:
        report = storage_service.get_storage_occupancy_report(section, type)
        logger.info(f"Successfully generated occupancy report with {report['total_locations']} locations")
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