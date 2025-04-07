from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
import json

from app.core.events import DomainEvent
from app.core.exceptions import (
    HideSyncException,
    ValidationException,
    EntityNotFoundException,
    BusinessRuleException,
    DuplicateEntityException,
    StorageLocationNotFoundException,
)
from app.core.validation import validate_input, validate_entity
from app.db.models.enums import StorageLocationType
from app.db.models.storage import (
    StorageLocation,
    StorageCell,
    StorageAssignment,
    StorageMove,
)
from app.repositories.storage_repository import (
    StorageLocationRepository,
    StorageCellRepository,
    StorageAssignmentRepository,
    StorageMoveRepository,
)
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)

class StorageLocationDeleted(DomainEvent):
    """Event emitted when a storage location is deleted."""

    def __init__(
            self,
            location_id: str,
            user_id: Optional[int] = None,
    ):
        """
        Initialize storage location deleted event.
        """
        super().__init__()
        self.location_id = location_id
        self.user_id = user_id

class StorageLocationCreated(DomainEvent):
    """Event emitted when a storage location is created."""

    def __init__(
            self,
            location_id: str,
            location_name: str,
            location_type: str,
            user_id: Optional[int] = None,
    ):
        """
        Initialize storage location created event.

        Args:
            location_id: ID of the created storage location
            location_name: Name of the storage location
            location_type: Type of the storage location
            user_id: Optional ID of the user who created the storage location
        """
        super().__init__()
        self.location_id = location_id
        self.location_name = location_name
        self.location_type = location_type
        self.user_id = user_id


class StorageAssignmentCreated(DomainEvent):
    """Event emitted when materials are assigned to a storage location."""

    def __init__(
            self,
            assignment_id: str,
            material_id: int,
            location_id: str,
            quantity: float,
            user_id: Optional[int] = None,
    ):
        """
        Initialize storage assignment created event.

        Args:
            assignment_id: ID of the created assignment
            material_id: ID of the assigned material
            location_id: ID of the storage location
            quantity: Quantity assigned
            user_id: Optional ID of the user who made the assignment
        """
        super().__init__()
        self.assignment_id = assignment_id
        self.material_id = material_id
        self.location_id = location_id
        self.quantity = quantity
        self.user_id = user_id


class StorageMoveCreated(DomainEvent):
    """Event emitted when material is moved between storage locations."""

    def __init__(
            self,
            move_id: str,
            material_id: int,
            from_location_id: str,
            to_location_id: str,
            quantity: float,
            user_id: Optional[int] = None,
    ):
        """
        Initialize storage move created event.

        Args:
            move_id: ID of the created move record
            material_id: ID of the moved material
            from_location_id: Source location ID
            to_location_id: Destination location ID
            quantity: Quantity moved
            user_id: Optional ID of the user who initiated the move
        """
        super().__init__()
        self.move_id = move_id
        self.material_id = material_id
        self.from_location_id = from_location_id
        self.to_location_id = to_location_id
        self.quantity = quantity
        self.user_id = user_id


class StorageSpaceUpdated(DomainEvent):
    """Event emitted when storage capacity or utilization is updated."""

    def __init__(
            self,
            location_id: str,
            previous_capacity: int,
            new_capacity: int,
            previous_utilized: int,
            new_utilized: int,
            user_id: Optional[int] = None,
    ):
        """
        Initialize storage space updated event.

        Args:
            location_id: ID of the storage location
            previous_capacity: Previous capacity value
            new_capacity: New capacity value
            previous_utilized: Previous utilization value
            new_utilized: New utilization value
            user_id: Optional ID of the user who made the update
        """
        super().__init__()
        self.location_id = location_id
        self.previous_capacity = previous_capacity
        self.new_capacity = new_capacity
        self.previous_utilized = previous_utilized
        self.new_utilized = new_utilized
        self.user_id = user_id


# Validation functions
validate_storage_location = validate_entity(StorageLocation)
validate_storage_cell = validate_entity(StorageCell)
validate_storage_assignment = validate_entity(StorageAssignment)
validate_storage_move = validate_entity(StorageMove)


class StorageLocationService(BaseService[StorageLocation]):
    """
    Service for managing storage locations in the HideSync system.

    Provides functionality for:
    - Storage location creation and management
    - Cell management within locations
    - Material assignments to storage locations
    - Inventory movement tracking
    - Space utilization and optimization
    """

    def __init__(
            self,
            session: Session,
            location_repository=None,
            cell_repository=None,
            assignment_repository=None,
            move_repository=None,
            security_context=None,
            event_bus=None,
            cache_service=None,
            material_service=None,
            inventory_service=None,
    ):
        """
        Initialize StorageLocationService with dependencies.

        Args:
            session: Database session for persistence operations
            location_repository: Optional repository for storage locations
            cell_repository: Optional repository for storage cells
            assignment_repository: Optional repository for storage assignments
            move_repository: Optional repository for storage moves
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            material_service: Optional material service for material operations
            inventory_service: Optional inventory service for inventory operations
        """
        # Initialize the base service first
        super().__init__(
            session=session,
            repository_class=None,  # We'll set repository directly
            security_context=security_context,
            event_bus=event_bus,
            cache_service=cache_service,
        )

        # Set our specific repositories
        self.repository = location_repository or StorageLocationRepository(session)
        self.cell_repository = cell_repository or StorageCellRepository(session)
        self.assignment_repository = assignment_repository or StorageAssignmentRepository(session)
        self.move_repository = move_repository or StorageMoveRepository(session)

        # Set additional service-specific dependencies
        self.material_service = material_service
        self.inventory_service = inventory_service

    # Improve get_storage_location in app/services/storage_location_service.py

    # File: app/services/storage_location_service.py

    # Make sure these imports are present at the top of the file
    from typing import Dict, Any, List, Optional
    from sqlalchemy.orm import Session
    from sqlalchemy import func
    import logging
    from app.db.models.enums import StorageLocationType
    from app.db.models.storage import StorageLocation, StorageAssignment  # Import StorageAssignment

    logger = logging.getLogger(__name__)

    class StorageLocationService:  # Assuming this class structure exists
        # ... potentially other methods like __init__, _format_location_for_api etc. ...

        # Ensure self.repository (StorageLocationRepository) and
        # self.assignment_repository (StorageAssignmentRepository) are initialized
        # in the __init__ method of StorageLocationService.

        def get_storage_occupancy_report(self, section: Optional[str] = None, location_type: Optional[str] = None) -> \
        Dict[str, Any]:
            """
            Generate a storage occupancy report with accurate utilization calculations
            and item counts by type.

            Args:
                section: Optional filter by section
                location_type: Optional filter by location type

            Returns:
                Storage occupancy report dictionary matching the StorageOccupancyReport schema.
            """
            logger.info(f"Generating storage occupancy report. Filters: section={section}, type={location_type}")

            # Initialize results dictionary matching the StorageOccupancyReport Pydantic schema
            result = {
                "total_locations": 0,
                "total_capacity": 0.0,
                "total_utilized": 0.0,  # This will be based on location.utilized field initially
                "total_items": 0,  # Will be calculated from assignments
                "utilization_percentage": 0.0,
                "overall_usage_percentage": 0.0,  # Often same as utilization_percentage
                "items_by_type": {},  # Calculated from assignments
                "by_type": {},
                "by_section": {},
                "locations_by_type": {},
                "locations_by_section": {},
                "locations_at_capacity": 0,  # e.g., >= 95% utilized
                "locations_nearly_empty": 0,  # e.g., <= 10% utilized
                "most_utilized_locations": [],
                "least_utilized_locations": [],
                "recommendations": []
            }

            try:
                # --- 1. Get Locations and Calculate Location-Based Stats ---
                logger.debug("Fetching storage locations...")
                filters = {}
                if section: filters["section"] = section
                if location_type:
                    try:
                        # Convert string type to enum if repository expects it
                        filters["type"] = StorageLocationType[location_type.upper()]
                    except KeyError:
                        logger.warning(f"Invalid location type filter provided: {location_type}. Ignoring filter.")
                        # Optionally raise an error or just ignore the filter

                locations = self.repository.list(**filters)  # Assuming repository handles filtering
                result["total_locations"] = len(locations)
                logger.debug(f"Found {result['total_locations']} locations matching filters.")

                if not locations:
                    logger.warning("No storage locations found matching criteria. Returning empty report.")
                    return result  # Return default empty report if no locations found

                total_capacity = 0.0
                total_utilized_loc_field = 0.0
                by_type = {}
                by_section = {}
                locations_by_type = {}
                locations_by_section = {}
                location_utilization_details = {}  # Stores details for most/least lists
                locations_at_capacity = 0
                locations_nearly_empty = 0

                # Process each location
                for loc in locations:
                    loc_id = str(getattr(loc, 'id', 'unknown'))
                    capacity = float(getattr(loc, 'capacity', 0) or 0)
                    utilized = float(getattr(loc, 'utilized', 0) or 0)  # Utilized from the location record

                    total_capacity += capacity
                    total_utilized_loc_field += utilized

                    utilization_pct = (utilized / capacity * 100) if capacity > 0 else 0.0

                    # Store details for sorting later
                    location_utilization_details[loc_id] = {
                        "id": loc_id,
                        "name": getattr(loc, 'name', 'Unknown'),
                        "capacity": int(capacity),
                        "utilized": int(utilized),
                        "utilization_percentage": round(utilization_pct, 1)
                    }

                    # Group counts/stats by Type
                    loc_type_enum = getattr(loc, 'type', None)
                    loc_type_str = str(loc_type_enum.name) if loc_type_enum else "OTHER"  # Default to OTHER
                    locations_by_type[loc_type_str] = locations_by_type.get(loc_type_str, 0) + 1
                    type_stats = by_type.setdefault(loc_type_str, {"capacity": 0.0, "utilized": 0.0, "locations": 0,
                                                                   "utilization_percentage": 0.0})
                    type_stats["capacity"] += capacity
                    type_stats["utilized"] += utilized  # Aggregate location.utilized
                    type_stats["locations"] += 1

                    # Group counts/stats by Section
                    loc_section_str = getattr(loc, 'section', "Unknown") or "Unknown"
                    locations_by_section[loc_section_str] = locations_by_section.get(loc_section_str, 0) + 1
                    section_stats = by_section.setdefault(loc_section_str,
                                                          {"capacity": 0.0, "utilized": 0.0, "locations": 0,
                                                           "utilization_percentage": 0.0})
                    section_stats["capacity"] += capacity
                    section_stats["utilized"] += utilized  # Aggregate location.utilized
                    section_stats["locations"] += 1

                    # Check capacity thresholds (using location.utilized based percentage)
                    if capacity > 0:
                        if utilization_pct >= 95:
                            locations_at_capacity += 1
                        elif utilization_pct <= 10:
                            locations_nearly_empty += 1

                result["total_capacity"] = total_capacity
                result["total_utilized"] = total_utilized_loc_field  # Start with location field value
                result["locations_at_capacity"] = locations_at_capacity
                result["locations_nearly_empty"] = locations_nearly_empty

                # --- 2. Calculate Item Counts by Type from Assignments ---
                logger.debug("Calculating item counts by type from assignments...")
                try:
                    # Query assignments: group by material_type and count distinct material_id
                    # This assumes 'material_type' on StorageAssignment is a string like 'leather', 'hardware'
                    item_counts_query = self.session.query(
                        StorageAssignment.material_type,
                        func.count(StorageAssignment.material_id.distinct())  # Counts unique items per type
                        # OR: func.sum(StorageAssignment.quantity) # If you need sum of quantities
                    ).group_by(StorageAssignment.material_type).all()

                    # Process the query results into a dictionary, lowercasing the type
                    items_by_type_calc = {
                        str(item_type).lower(): count
                        for item_type, count in item_counts_query if item_type  # Ensure item_type is not None
                    }

                    # Ensure common types exist in the dictionary, even if count is 0
                    for common_type in ["leather", "hardware", "supplies", "other", "unknown"]:
                        items_by_type_calc.setdefault(common_type, 0)

                    result["items_by_type"] = items_by_type_calc
                    result["total_items"] = sum(items_by_type_calc.values())
                    logger.info(f"Successfully calculated item counts by type: {result['items_by_type']}")

                    # --- Optional Override Decision ---
                    # Decide if the sum of distinct items should override the 'total_utilized'
                    # This depends on whether 'location.utilized' is meant to track items or space.
                    # If 'utilized' tracks distinct items, you might want to update it here:
                    # if result["total_items"] != total_utilized_loc_field:
                    #    logger.warning(f"Total utilized from locations ({total_utilized_loc_field}) differs from distinct item count ({result['total_items']}). Using item count.")
                    #    result["total_utilized"] = float(result["total_items"])
                    # else:
                    #    result["total_utilized"] = total_utilized_loc_field # Keep location field value

                    # For now, we'll keep result["total_utilized"] based on the location field sum
                    # as it's more likely meant to track used slots/space rather than distinct items.
                    result["total_utilized"] = total_utilized_loc_field

                except Exception as e:
                    logger.error(f"Error calculating items_by_type from assignments: {e}", exc_info=True)
                    result["items_by_type"] = {"error": "Calculation failed"}  # Indicate error in result
                    result["total_items"] = None  # Indicate calculation failed
                    # Keep total_utilized based on location field as fallback

                # --- 3. Final Calculations & Formatting ---
                logger.debug("Performing final calculations for report...")
                final_total_utilized = result["total_utilized"]  # Use the determined total utilized

                if total_capacity > 0:
                    usage_pct = (final_total_utilized / total_capacity) * 100
                    result["utilization_percentage"] = round(usage_pct, 1)
                    result["overall_usage_percentage"] = round(usage_pct, 1)  # Assign same value

                # Calculate final percentages for by_type and by_section breakdowns
                # These percentages are based on the summed location.utilized values per group
                for stats in by_type.values():
                    cap = stats.get("capacity", 0.0)
                    ut = stats.get("utilized", 0.0)  # Utilized from location field sum for this group
                    stats["utilization_percentage"] = round((ut / cap) * 100, 1) if cap > 0 else 0.0

                for stats in by_section.values():
                    cap = stats.get("capacity", 0.0)
                    ut = stats.get("utilized", 0.0)  # Utilized from location field sum for this group
                    stats["utilization_percentage"] = round((ut / cap) * 100, 1) if cap > 0 else 0.0

                result["by_type"] = by_type
                result["by_section"] = by_section
                result["locations_by_type"] = locations_by_type  # Just the counts
                result["locations_by_section"] = locations_by_section  # Just the counts

                # Sort locations by utilization percentage for most/least utilized lists
                sorted_locations = sorted(
                    location_utilization_details.values(),
                    key=lambda x: x["utilization_percentage"],
                    reverse=True
                )

                # Populate most/least utilized lists (ensure structure matches Pydantic schema)
                result["most_utilized_locations"] = sorted_locations[:5]
                result["least_utilized_locations"] = [
                                                         loc for loc in reversed(sorted_locations) if
                                                         loc["capacity"] > 0 and loc["utilization_percentage"] > 0
                                                     ][:5]

                # --- 4. Generate Recommendations ---
                logger.debug("Generating recommendations...")
                recommendations = []
                usage_pct_final = result["utilization_percentage"]
                if usage_pct_final > 85:
                    recommendations.append(
                        "Overall utilization is high. Consider expanding storage or optimizing existing space.")
                elif usage_pct_final < 25:
                    recommendations.append("Overall utilization is low. Consider consolidating storage.")
                if result["locations_at_capacity"] > 0: recommendations.append(
                    f"Address {result['locations_at_capacity']} locations at or near capacity (>=95%).")
                if result["locations_nearly_empty"] > 0: recommendations.append(
                    f"Review {result['locations_nearly_empty']} nearly empty locations (<=10%) for potential consolidation.")
                # Add more recommendations based on by_type, by_section, etc. if needed
                result["recommendations"] = recommendations

                logger.info(f"Generated storage occupancy report successfully.")
                return result

            except Exception as e:
                logger.error(f"Major error generating storage occupancy report: {e}", exc_info=True)
                # Return the initialized result dictionary with defaults on major error
                result["recommendations"] = ["Error generating report."]  # Add error message
                return result


    # Just add this method to app/services/storage_location_service.py
    # Don't change any existing code - just add this new method

    def get_storage_cells(self, location_id, occupied=None):
        """
        Get cells for a storage location with optional filter.

        Args:
            location_id: ID of the storage location
            occupied: Optional filter for occupied status

        Returns:
            List of formatted storage cells
        """
        logger.info(f"Getting cells for storage location ID: {location_id}")

        try:
            # Query cells directly from repository
            cells = self.cell_repository.list(storage_id=location_id)

            # Format cells for API
            formatted_cells = []
            for cell in cells:
                # Basic cell info
                cell_data = {
                    "id": str(getattr(cell, "id", "")),
                    "storage_id": str(getattr(cell, "storage_id", location_id)),
                    "occupied": bool(getattr(cell, "occupied", False)),
                    "material_id": getattr(cell, "material_id", None),
                    "position": {"row": 1, "column": 1}  # Default position
                }

                # Parse position data if available
                position = getattr(cell, "position", None)
                if position:
                    if isinstance(position, str):
                        try:
                            import json
                            pos_data = json.loads(position)
                            if isinstance(pos_data, dict):
                                cell_data["position"] = pos_data
                        except:
                            pass
                    elif isinstance(position, dict):
                        cell_data["position"] = position

                # Apply filter if specified
                if occupied is None or cell_data["occupied"] == occupied:
                    formatted_cells.append(cell_data)

            logger.info(f"Retrieved {len(formatted_cells)} cells for location {location_id}")
            return formatted_cells

        except Exception as e:
            logger.error(f"Error getting cells for location {location_id}: {e}")

            # Generate a default grid as fallback
            default_cells = []
            for row in range(1, 5):
                for col in range(1, 5):
                    default_cells.append({
                        "id": f"default_{location_id}_{row}_{col}",
                        "storage_id": str(location_id),
                        "position": {"row": row, "column": col},
                        "occupied": False,
                        "material_id": None
                    })

            logger.warning(f"Returning default grid with {len(default_cells)} cells")
            return default_cells

    def get_storage_locations(
            self,
            skip: int = 0,
            limit: int = 100,
            search_params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get a list of storage locations with optional filtering and pagination.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            search_params: Optional search parameters for filtering (type, section, status, search)

        Returns:
            List of storage locations with properly formatted fields
        """
        logger.info(f"Getting storage locations with params: {search_params}, skip={skip}, limit={limit}")

        try:
            # Check cache first if available
            cache_key = None
            if self.cache_service:
                # Create a cache key based on parameters
                params_str = json.dumps(search_params or {})
                cache_key = f"StorageLocations:{params_str}:{skip}:{limit}"
                cached = self.cache_service.get(cache_key)
                if cached:
                    logger.info(f"Retrieved {len(cached)} storage locations from cache")
                    return cached

            # Build filters dictionary from search_params
            filters = {}
            if search_params:
                if search_params.get("type"):
                    filters["type"] = search_params["type"]
                if search_params.get("section"):
                    filters["section"] = search_params["section"]
                if search_params.get("status"):
                    filters["status"] = search_params["status"]
                if search_params.get("search"):
                    filters["name"] = search_params["search"]  # Use name field for search

            # Get locations from repository with pagination
            locations = self.repository.list(
                skip=skip,
                limit=limit,
                **filters
            )

            # Format locations for API
            formatted_locations = [self._format_location_for_api(loc) for loc in locations]

            # Add to cache if available
            if self.cache_service and cache_key:
                self.cache_service.set(cache_key, formatted_locations, ttl=300)  # 5 min TTL

            logger.info(f"Retrieved {len(formatted_locations)} storage locations")
            return formatted_locations

        except Exception as e:
            logger.error(f"Error fetching storage locations: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []  # Return empty list on error

    def _format_location_for_api(self, location) -> Dict[str, Any]:
        """
        Format a storage location object for API response with robust error handling.

        Args:
            location: Storage location object from database

        Returns:
            Dictionary with formatted storage location data
        """
        try:
            # Handle empty location
            if not location:
                logger.warning("Attempting to format None location object")
                return {
                    "id": "unknown",
                    "name": "Unknown Location",
                    "type": "unknown",
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
                "type": ("type", "other", str),
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
                "type": "unknown",
                "status": "UNKNOWN",
                "capacity": 0,
                "utilized": 0,
                "dimensions": {"width": 4, "height": 4},
                "_error": str(e)
            }

    def _calculate_utilization_statistics(self, location_id):
        """
        Calculate storage utilization statistics.

        Args:
            location_id: ID of the storage location

        Returns:
            Dictionary of utilization statistics
        """
        logger.info(f"Calculating utilization statistics for location {location_id}")

        # Default statistics
        stats = {
            "capacity": 0,
            "utilized": 0,
            "utilization_percentage": 0,
            "item_count": 0,
            "material_types": {},
            "by_status": {
                "active": 0,
                "reserved": 0,
                "in_use": 0
            }
        }

        try:
            # Get location to determine capacity
            try:
                location = self.repository.get_by_id(location_id)
                if location:
                    stats["capacity"] = getattr(location, "capacity", 0) or 0
                    stats["utilized"] = getattr(location, "utilized", 0) or 0

                    # Calculate percentage if capacity is not zero
                    if stats["capacity"] > 0:
                        stats["utilization_percentage"] = round(
                            (stats["utilized"] / stats["capacity"]) * 100, 1
                        )
            except Exception as e:
                logger.error(f"Error getting location for stats calculation: {e}")

        except Exception as e:
            logger.error(f"Error calculating utilization statistics: {e}")

        logger.info(f"Calculated utilization statistics for location {location_id}")
        return stats

    def _format_assignment_for_api(self, assignment):
        """
        Format a storage assignment for API response.

        Args:
            assignment: StorageAssignment model instance

        Returns:
            Dictionary of formatted assignment data
        """
        if not assignment:
            return None

        # Create base result with safe defaults
        result = {
            "id": str(getattr(assignment, "id", "")),
            "storage_id": str(getattr(assignment, "storage_id", "")),
            "material_id": getattr(assignment, "material_id", None),
            "material_type": getattr(assignment, "material_type", "material"),
            "quantity": float(getattr(assignment, "quantity", 0)),
            "position": None,
            "assigned_date": None,
            "assigned_by": getattr(assignment, "assigned_by", None),
            "notes": getattr(assignment, "notes", "")
        }

        # Handle position data
        position = getattr(assignment, "position", None)
        if position:
            # Parse JSON string
            if isinstance(position, str):
                try:
                    import json
                    parsed_position = json.loads(position)
                    if isinstance(parsed_position, dict):
                        result["position"] = parsed_position
                except:
                    pass
            # Use dict directly
            elif isinstance(position, dict):
                result["position"] = position

        # Handle assigned date
        assigned_date = getattr(assignment, "assigned_date", None)
        if assigned_date:
            if hasattr(assigned_date, "isoformat"):
                result["assigned_date"] = assigned_date.isoformat()
            else:
                result["assigned_date"] = str(assigned_date)

        return result

    def update_storage_utilization_from_assignments(self):
        """
        Synchronize storage utilization counts based on material assignments.

        This method scans all storage assignments and updates the 'utilized' count
        for each storage location accordingly.

        Returns:
            dict: Summary of synchronization results
        """
        logger.info("Synchronizing storage utilization from assignments")

        try:
            # Get all storage assignments
            all_assignments = self.assignment_repository.list()

            logger.info(f"Found {len(all_assignments)} storage assignments")

            # Count assignments per location
            location_counts = {}
            for assignment in all_assignments:
                loc_id = getattr(assignment, 'storage_id', None)
                if loc_id:
                    location_counts[loc_id] = location_counts.get(loc_id, 0) + 1

            # Update each storage location's utilized count
            updated_count = 0
            updated_locations = []

            for loc_id, count in location_counts.items():
                try:
                    loc = self.repository.get_by_id(loc_id)
                    if loc:
                        # Remember previous value for logging
                        previous_count = loc.utilized or 0

                        # Update the count
                        self.repository.update(loc_id, {"utilized": count})

                        updated_count += 1
                        updated_locations.append({
                            "id": loc_id,
                            "name": getattr(loc, 'name', 'Unknown'),
                            "previous_count": previous_count,
                            "new_count": count
                        })

                        logger.debug(
                            f"Updated location {getattr(loc, 'name', 'Unknown')} (ID: {loc_id}): "
                            f"utilized from {previous_count} to {count}")
                except Exception as loc_error:
                    logger.error(f"Error updating location {loc_id}: {loc_error}")

            logger.info(f"Successfully updated utilization for {updated_count} storage locations")

            return {
                "updated_count": updated_count,
                "updated_locations": updated_locations
            }

        except Exception as e:
            logger.error(f"Error synchronizing storage utilization: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    def get_storage_location(self, location_id: str):
        """
        Get a single storage location by ID with enhanced error handling and ID format flexibility.

        Args:
            location_id: ID of the storage location to retrieve (string, int, or UUID format)

        Returns:
            Storage location with properly formatted fields

        Raises:
            StorageLocationNotFoundException: If the location doesn't exist
        """
        logger.info(f"Getting storage location with ID: {location_id}")

        try:
            # Check cache first
            if self.cache_service:
                cache_key = f"StorageLocation:{location_id}"
                cached = self.cache_service.get(cache_key)
                if cached:
                    logger.info(f"Retrieved location from cache: {location_id}")
                    return cached

            # Get location from repository - try different formats
            location = None

            # Try the ID as provided
            try:
                location = self.repository.get_by_id(location_id)
                if location:
                    logger.debug(f"Found location with ID as provided: {location_id}")
            except Exception as e:
                logger.debug(f"Error getting location with ID as provided: {e}")

            # If not found and it's a numeric string, try as integer
            if not location and str(location_id).isdigit():
                try:
                    numeric_id = int(location_id)
                    location = self.repository.get_by_id(numeric_id)
                    if location:
                        logger.info(f"Found location using numeric ID: {numeric_id}")
                except Exception as e:
                    logger.debug(f"Error getting location with numeric ID {location_id}: {e}")

            # If still not found, try direct database query
            if not location:
                try:
                    from sqlalchemy import or_
                    from app.db.models.storage import StorageLocation

                    # Try multiple ID formats
                    location = self.session.query(StorageLocation).filter(
                        or_(
                            StorageLocation.id == location_id,
                            StorageLocation.id == str(location_id),
                            StorageLocation.uuid == location_id,
                            StorageLocation.name == location_id
                        )
                    ).first()

                    if location:
                        logger.info(f"Found location using direct query: {location.id}")
                except Exception as e:
                    logger.debug(f"Error with direct query: {e}")

            # If still not found, try listing all locations
            if not location:
                try:
                    logger.debug("Attempting to find location in full list...")
                    all_locations = self.repository.list(limit=100)

                    for loc in all_locations:
                        # Compare as strings to handle type mismatches
                        if str(loc.id) == str(location_id):
                            location = loc
                            logger.info(f"Found location in full list by ID: {loc.id}")
                            break
                except Exception as e:
                    logger.debug(f"Error listing all locations: {e}")

            # If we still don't have a location, check if we have mock data for testing
            if not location:
                try:
                    # This is for development/testing only
                    mock_locations = [
                        {
                            "id": "1",
                            "name": "Main Workshop Cabinet",
                            "type": "cabinet",
                            "section": "main_workshop",
                            "capacity": 100,
                            "utilized": 30,
                            "status": "ACTIVE",
                            "dimensions": {"width": 4, "height": 4}
                        },
                        {
                            "id": "2",
                            "name": "Tool Storage",
                            "type": "shelf",
                            "section": "tool_room",
                            "capacity": 50,
                            "utilized": 25,
                            "status": "ACTIVE",
                            "dimensions": {"width": 3, "height": 6}
                        }
                    ]

                    for mock_loc in mock_locations:
                        if str(mock_loc["id"]) == str(location_id):
                            logger.warning(f"Using mock data for location {location_id}")
                            return mock_loc
                except Exception:
                    pass

            # If we still don't have a location, raise the exception
            if not location:
                logger.error(f"Storage location not found: {location_id}")
                raise StorageLocationNotFoundException(location_id)

            # Format location for API
            formatted_location = self._format_location_for_api(location)

            # Add to cache
            if self.cache_service:
                self.cache_service.set(cache_key, formatted_location, ttl=3600)

            logger.info(f"Retrieved storage location: {formatted_location.get('name', 'Unknown')}")
            return formatted_location

        except StorageLocationNotFoundException:
            # Re-raise the same exception
            raise
        except Exception as e:
            logger.error(f"Error fetching storage location: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise StorageLocationNotFoundException(location_id)

    def get_storage_occupancy_report(self, section=None, location_type=None):
        """
        Generate a storage occupancy report with accurate utilization calculations.

        Args:
            section: Optional filter by section
            location_type: Optional filter by location type

        Returns:
            Storage occupancy report with metrics
        """
        logger.info("Generating storage occupancy report")

        # Initialize empty results with safe defaults
        result = {
            "total_locations": 0,
            "total_capacity": 0,
            "total_utilized": 0,
            "total_items": 0,
            "utilization_percentage": 0,
            "overall_usage_percentage": 0,
            "by_type": {},
            "by_section": {},
            "locations_by_type": {},
            "locations_by_section": {},
            "locations_at_capacity": 0,
            "locations_nearly_empty": 0,
            "most_utilized_locations": [],
            "least_utilized_locations": [],
            "recommendations": []
        }

        try:
            # Get all locations with repository method
            filters = {}
            if section:
                filters["section"] = section
            if location_type:
                filters["type"] = location_type

            locations = self.repository.list(**filters)

            # Calculate totals
            result["total_locations"] = len(locations)

            total_capacity = 0
            total_utilized = 0
            by_type = {}
            by_section = {}
            locations_by_type = {}
            locations_by_section = {}
            location_utilization = {}

            # Process each location
            for loc in locations:
                location_id = str(loc.id)
                capacity = loc.capacity or 0
                utilized = loc.utilized or 0

                # Add to totals
                total_capacity += capacity
                total_utilized += utilized

                # Store for later utilization calculation
                location_utilization[location_id] = {
                    "id": location_id,
                    "name": loc.name or "",
                    "capacity": capacity,
                    "utilized": utilized,
                    "utilization_percentage": round((utilized / capacity) * 100, 1) if capacity > 0 else 0
                }

                # Process location types
                loc_type = loc.type or "Unknown"
                if hasattr(loc_type, 'value'):
                    loc_type = loc_type.value
                locations_by_type[loc_type] = locations_by_type.get(loc_type, 0) + 1

                if loc_type not in by_type:
                    by_type[loc_type] = {
                        "capacity": 0,
                        "utilized": 0,
                        "locations": 0,
                        "utilization_percentage": 0
                    }
                by_type[loc_type]["capacity"] += capacity
                by_type[loc_type]["utilized"] += utilized
                by_type[loc_type]["locations"] += 1

                # Process sections
                loc_section = loc.section or "Unknown"
                locations_by_section[loc_section] = locations_by_section.get(loc_section, 0) + 1

                if loc_section not in by_section:
                    by_section[loc_section] = {
                        "capacity": 0,
                        "utilized": 0,
                        "locations": 0,
                        "utilization_percentage": 0
                    }
                by_section[loc_section]["capacity"] += capacity
                by_section[loc_section]["utilized"] += utilized
                by_section[loc_section]["locations"] += 1

                # Check for locations at capacity/empty
                if capacity > 0:
                    utilization_pct = (utilized / capacity) * 100
                    if utilization_pct >= 90:
                        result["locations_at_capacity"] += 1
                    elif utilization_pct <= 10:
                        result["locations_nearly_empty"] += 1

            # Get storage assignments to calculate actual item count
            try:
                # Get all storage assignments
                all_assignments = self.assignment_repository.list()

                # Count total items
                total_items = len(all_assignments)
                result["total_items"] = total_items

                # If stored assignments exist but utilized counts are zero,
                # recalculate utilization based on assignments
                if total_items > 0 and total_utilized == 0:
                    # Group assignments by location
                    location_items = {}
                    for assignment in all_assignments:
                        loc_id = str(getattr(assignment, "storage_id", ""))
                        if loc_id not in location_items:
                            location_items[loc_id] = 0
                        location_items[loc_id] += 1

                    # Update location utilization
                    for loc_id, count in location_items.items():
                        if loc_id in location_utilization:
                            location_utilization[loc_id]["utilized"] = count
                            if location_utilization[loc_id]["capacity"] > 0:
                                location_utilization[loc_id]["utilization_percentage"] = round(
                                    (count / location_utilization[loc_id]["capacity"]) * 100, 1
                                )

                    # Recalculate total utilized
                    total_utilized = sum(location_items.values())
                    result["total_utilized"] = total_utilized

                    # Update type and section utilization
                    for loc in locations:
                        loc_id = str(loc.id)
                        if loc_id in location_items:
                            loc_type = loc.type
                            if hasattr(loc_type, 'value'):
                                loc_type = loc_type.value

                            if loc_type in by_type:
                                by_type[loc_type]["utilized"] += location_items[loc_id]

                            loc_section = loc.section or "Unknown"
                            if loc_section in by_section:
                                by_section[loc_section]["utilized"] += location_items[loc_id]
                else:
                    # Use the original total_utilized
                    result["total_utilized"] = total_utilized

            except Exception as e:
                logger.error(f"Error calculating items from assignments: {e}")
                # If there was an error, still try to use the original utilized value
                result["total_items"] = total_utilized
                result["total_utilized"] = total_utilized

            # Update results
            result["total_capacity"] = total_capacity
            result["total_utilized"] = total_utilized

            if total_capacity > 0:
                usage_pct = (total_utilized / total_capacity) * 100
                result["utilization_percentage"] = round(usage_pct, 1)
                result["overall_usage_percentage"] = round(usage_pct, 1)

            # Calculate type utilization percentages
            for type_name, data in by_type.items():
                if data["capacity"] > 0:
                    data["utilization_percentage"] = round((data["utilized"] / data["capacity"]) * 100, 1)

            # Calculate section utilization percentages
            for section_name, data in by_section.items():
                if data["capacity"] > 0:
                    data["utilization_percentage"] = round((data["utilized"] / data["capacity"]) * 100, 1)

            result["by_type"] = by_type
            result["by_section"] = by_section
            result["locations_by_type"] = locations_by_type
            result["locations_by_section"] = locations_by_section

            # Sort locations by utilization for most/least utilized reports
            sorted_locations = sorted(
                location_utilization.values(),
                key=lambda x: x["utilization_percentage"],
                reverse=True
            )

            # Most utilized locations (top 5)
            result["most_utilized_locations"] = sorted_locations[:5]

            # Least utilized locations (bottom 5, excluding empty ones)
            result["least_utilized_locations"] = [
                                                     loc for loc in reversed(sorted_locations)
                                                     if loc["capacity"] > 0 and loc["utilization_percentage"] > 0
                                                 ][:5]

            # Add recommendations
            usage_pct = result["utilization_percentage"]
            if usage_pct > 80:
                result["recommendations"].append("Consider expanding storage capacity")
            elif usage_pct < 30:
                result["recommendations"].append("Consider consolidating storage")

            if result["locations_at_capacity"] > 0:
                result["recommendations"].append(
                    f"Address {result['locations_at_capacity']} locations at or near capacity")

            if result["locations_nearly_empty"] > 0:
                result["recommendations"].append(f"Review {result['locations_nearly_empty']} nearly empty locations")

            logger.info(
                f"Generated storage occupancy report: {result['total_locations']} locations, "
                f"{result['utilization_percentage']}% utilized, {result['total_items']} items stored")
            return result

        except Exception as e:
            logger.error(f"Error in storage occupancy report: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return result

    def _location_exists_by_name_and_section(self, name: str, section: Optional[str]) -> bool:
        """
        Check if a storage location exists with the given name and section.
        """
        if not name:
            return False

        # Create filter criteria
        filters = {"name": name}
        if section:
            filters["section"] = section

        # Check if any location matches the criteria
        existing_locations = self.repository.list(**filters)
        return len(existing_locations) > 0

    def get_storage_assignments(self, item_id=None, item_type=None, location_id=None, skip=0, limit=100):
        """
        Get storage assignments with pagination.

        Args:
            item_id: Optional filter by item ID
            item_type: Optional filter by item type
            location_id: Optional filter by storage location ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of storage assignments with properly formatted fields
        """
        logger.info(
            f"Getting storage assignments with filters: item_id={item_id}, item_type={item_type}, location_id={location_id}")

        try:
            # Set a safe limit to prevent memory errors
            MAX_RESULTS = 500
            actual_limit = min(limit, MAX_RESULTS)

            # Build filters dictionary
            filters = {}
            if item_id is not None:
                filters["material_id"] = item_id
            if item_type is not None:
                filters["material_type"] = item_type
            if location_id is not None:
                filters["storage_id"] = location_id

            # Use repository method with pagination
            assignments_db = self.assignment_repository.list(
                skip=skip,
                limit=actual_limit,
                **filters
            )

            # Process assignments for API
            assignments = []
            for assignment in assignments_db:
                formatted = self._format_assignment_for_api(assignment)

                # Add material details if available
                if self.material_service and formatted["material_id"]:
                    try:
                        material = self.material_service.get_by_id(formatted["material_id"])
                        if material:
                            formatted["material_name"] = material.name
                            formatted["material_unit"] = material.unit
                    except Exception as material_err:
                        logger.error(f"Error getting material info: {material_err}")

                assignments.append(formatted)

            logger.info(f"Retrieved {len(assignments)} storage assignments")
            return assignments

        except Exception as e:
            logger.error(f"Error fetching storage assignments: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []  # Return empty list on error

    def get_storage_location_with_details(self, location_id: str) -> Dict[str, Any]:
        """
        Get a storage location with comprehensive details.

        Args:
            location_id: ID of the storage location

        Returns:
            Storage location with cells, assignments, and space utilization

        Raises:
            StorageLocationNotFoundException: If location not found
        """
        # Check cache first
        if self.cache_service:
            cache_key = f"StorageLocation:detail:{location_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get location
        location = self.get_storage_location(location_id)
        if not location:
            raise StorageLocationNotFoundException(location_id)

        # Get cells from repository
        try:
            cells = self.cell_repository.list(storage_id=location_id)
            location["cells"] = [self._format_cell_for_api(cell) for cell in cells]
        except Exception as e:
            logger.error(f"Error getting cells for location {location_id}: {e}")
            location["cells"] = []

        # Get assignments from repository
        try:
            assignments = self.assignment_repository.list(storage_id=location_id)

            processed_assignments = []
            for assignment in assignments:
                formatted = self._format_assignment_for_api(assignment)

                # Add material details if available
                if self.material_service and formatted["material_id"]:
                    try:
                        material = self.material_service.get_by_id(formatted["material_id"])
                        if material:
                            formatted["material_name"] = material.name
                            formatted["material_unit"] = material.unit
                    except Exception as material_err:
                        logger.error(f"Error getting material info: {material_err}")

                processed_assignments.append(formatted)

            location["assignments"] = processed_assignments
        except Exception as e:
            logger.error(f"Error getting assignments for location {location_id}: {e}")
            location["assignments"] = []

        # Calculate utilization statistics
        location["utilization_stats"] = self._calculate_utilization_statistics(location_id)

        # Get recent moves
        try:
            # Get moves involving this location using repository
            source_moves = self.move_repository.list(
                from_storage_id=location_id,
                limit=10,
                order_by="move_date",
                order_dir="desc"
            )

            dest_moves = self.move_repository.list(
                to_storage_id=location_id,
                limit=10,
                order_by="move_date",
                order_dir="desc"
            )

            # Combine and sort
            all_moves = sorted(
                list(source_moves) + list(dest_moves),
                key=lambda x: x.move_date if x.move_date else datetime.min,
                reverse=True
            )[:10]

            # Format moves for API
            moves = []
            for move in all_moves:
                formatted = self._format_move_for_api(move)

                # Add direction indicator
                formatted["direction"] = "outgoing" if formatted["from_location_id"] == location_id else "incoming"

                # Add material details if available
                if self.material_service and formatted["material_id"]:
                    try:
                        material = self.material_service.get_by_id(formatted["material_id"])
                        if material:
                            formatted["material_name"] = material.name
                    except Exception as material_err:
                        logger.error(f"Error getting material info for move: {material_err}")

                # Add location names
                try:
                    from_loc = self.get_storage_location(formatted["from_location_id"])
                    if from_loc:
                        formatted["from_location_name"] = from_loc["name"]
                except:
                    formatted["from_location_name"] = "Unknown"

                try:
                    to_loc = self.get_storage_location(formatted["to_location_id"])
                    if to_loc:
                        formatted["to_location_name"] = to_loc["name"]
                except:
                    formatted["to_location_name"] = "Unknown"

                moves.append(formatted)

            location["recent_moves"] = moves
        except Exception as e:
            logger.error(f"Error getting moves for location {location_id}: {e}")
            location["recent_moves"] = []

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, location, ttl=3600)  # 1 hour TTL

        return location

    def delete_storage_location(self, location_id: str, user_id: Optional[int] = None) -> None:
        """
        Delete a storage location.

        Args:
            location_id: ID of the storage location to delete
            user_id: Optional ID of the user deleting the location

        Raises:
            StorageLocationNotFoundException: If location not found
            BusinessRuleException: If deletion violates business rules
        """
        with self.transaction():
            # Check if location exists
            location = self.repository.get_by_id(location_id)
            if not location:
                raise StorageLocationNotFoundException(location_id)

            # Check for existing assignments that would prevent deletion
            assignments = self.assignment_repository.list(storage_id=location_id)
            if assignments:
                raise BusinessRuleException(
                    f"Cannot delete storage location {location_id} because it has {len(assignments)} assignments",
                    "STORAGE_DELETE_HAS_ASSIGNMENTS"
                )

            # Delete the location
            self.repository.delete(location_id)

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"StorageLocation:{location_id}")
                self.cache_service.invalidate(f"StorageLocation:detail:{location_id}")

            # Publish event if event bus exists
            if self.event_bus:
                user_id_for_event = user_id or (
                    self.security_context.current_user.id
                    if self.security_context else None
                )
                # You'll need to add this event class at the top with other events
                self.event_bus.publish(
                    StorageLocationDeleted(
                        location_id=location_id,
                        user_id=user_id_for_event,
                    )
                )

    def _format_cell_for_api(self, cell):
        """
        Format a storage cell for API response.

        Args:
            cell: StorageCell model instance

        Returns:
            Dictionary of formatted cell data
        """
        if not cell:
            return None

        # Create base result with safe defaults
        result = {
            "id": str(getattr(cell, "id", "")),
            "storage_id": str(getattr(cell, "storage_id", "")),
            "position": {"row": 1, "column": 1},
            "occupied": bool(getattr(cell, "occupied", False)),
            "material_id": getattr(cell, "material_id", None)
        }

        # Handle position data
        position = getattr(cell, "position", None)
        if position:
            # Parse JSON string
            if isinstance(position, str):
                try:
                    import json
                    parsed_position = json.loads(position)
                    if isinstance(parsed_position, dict):
                        result["position"] = parsed_position
                except:
                    pass
            # Use dict directly
            elif isinstance(position, dict):
                result["position"] = position

        return result

    def _create_cells_for_location(self, location_id: str, dimensions: Dict[str, Any]) -> None:
        """
        Create storage cells for a location based on dimensions.

        Args:
            location_id: ID of the storage location
            dimensions: Dimensions object with width, height, etc.
        """
        width = dimensions.get("width", 0)
        height = dimensions.get("height", 0)

        # Skip if no dimensions
        if not width or not height:
            return

        # Create cells in grid format
        for row in range(1, height + 1):
            for col in range(1, width + 1):
                # Create position information
                position = {
                    "row": row,
                    "column": col
                }

                # Create cell
                cell_data = {
                    "storage_id": location_id,
                    "position": position,
                    "occupied": False
                }

                self.cell_repository.create(cell_data)

    @validate_input(validate_storage_location)
    def create_storage_location(self, data: Dict[str, Any], user_id: Optional[int] = None) -> StorageLocation:
        """
        Create a new storage location.
        """
        with self.transaction():
            # Check for duplicate name in the same section
            section = data.get("section")
            name = data.get("name", "")

            if self._location_exists_by_name_and_section(name, section):
                raise DuplicateEntityException(
                    f"Storage location with name '{name}' already exists in section '{section}'",
                    "STORAGE_001",
                    {"field": "name", "value": name, "section": section},
                )

            # Set default values if not provided
            if "status" not in data:
                data["status"] = "ACTIVE"

            if "utilized" not in data:
                data["utilized"] = 0

            # Remove relationship fields that might cause issues
            clean_data = {k: v for k, v in data.items() if k not in
                          ['cells', 'assignments', 'moves_from', 'moves_to']}

            # Create storage location
            location = self.repository.create(clean_data)

            # Create cells if dimensions are provided
            if "dimensions" in data and isinstance(data["dimensions"], dict):
                self._create_cells_for_location(location.id, data["dimensions"])

            if self._location_exists_by_name_and_section(name, section):
                # Simplify the exception to only use the message
                raise DuplicateEntityException(
                    f"Storage location with name '{name}' already exists in section '{section}'"
                )

            # Publish event if event bus exists
            if self.event_bus:
                user_id_for_event = user_id or (
                    self.security_context.current_user.id
                    if self.security_context else None
                )
                self.event_bus.publish(
                    StorageLocationCreated(
                        location_id=location.id,
                        location_name=location.name,
                        location_type=location.type,
                        user_id=user_id_for_event,
                    )
                )

            # Ensure ID is string for API compatibility
            location_formatted = self._format_location_for_api(location)

            return location_formatted

    def update_storage_utilization_from_materials(self):
        """
        Synchronize storage utilization counts based on material assignments.

        This method scans all materials with storage location assignments and
        updates the 'utilized' count for each storage location accordingly.

        Returns:
            bool: True if synchronization was successful
        """
        logger.info("Synchronizing storage utilization from material assignments")

        try:
            # Get all materials with storage locations
            from app.db.models.material import Material

            materials_with_location = self.session.query(Material).filter(
                Material.storage_location.isnot(None)
            ).all()

            logger.info(f"Found {len(materials_with_location)} materials with storage assignments")

            # Count materials per location
            location_counts = {}
            for material in materials_with_location:
                loc_id = material.storage_location
                location_counts[loc_id] = location_counts.get(loc_id, 0) + 1

            # Update each storage location's utilized count
            updated_count = 0
            for loc_id, count in location_counts.items():
                try:
                    loc = self.repository.get_by_id(loc_id)
                    if loc:
                        # Remember previous value for logging
                        previous_count = loc.utilized or 0

                        # Update the count
                        self.repository.update(loc_id, {"utilized": count})

                        updated_count += 1
                        logger.debug(
                            f"Updated location {loc.name} (ID: {loc_id}): utilized from {previous_count} to {count}")
                except Exception as loc_error:
                    logger.error(f"Error updating location {loc_id}: {loc_error}")

            logger.info(f"Successfully updated utilization for {updated_count} storage locations")
            return True

        except Exception as e:
            logger.error(f"Error synchronizing storage utilization: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def update_storage_location(
            self, location_id: str, data: Dict[str, Any], user_id: Optional[int] = None
    ) -> StorageLocation:
        """
        Update an existing storage location.

        Args:
            location_id: ID of the storage location
            data: Updated storage location data
            user_id: Optional ID of the user updating the location

        Returns:
            Updated storage location entity

        Raises:
            StorageLocationNotFoundException: If location not found
            ValidationException: If validation fails
            DuplicateEntityException: If name change would create a duplicate
        """
        with self.transaction():
            # Check if location exists
            location = self.repository.get_by_id(location_id)
            if not location:
                raise StorageLocationNotFoundException(location_id)

            # Check for duplicate name if changing name
            if "name" in data and data["name"] != location.name and "section" in data:
                if self._location_exists_by_name_and_section(
                        data["name"], data["section"]
                ):
                    raise DuplicateEntityException(
                        f"Storage location with name '{data['name']}' already exists in section '{data['section']}'",
                        "STORAGE_001",
                        {
                            "field": "name",
                            "value": data["name"],
                            "section": data["section"],
                        },
                    )

            # Check for capacity changes
            previous_capacity = location.capacity
            previous_utilized = location.utilized

            # Update location
            updated_location = self.repository.update(location_id, data)

            # If capacity or utilization changed, publish event
            if ("capacity" in data or "utilized" in data) and self.event_bus:
                user_id_for_event = user_id or (
                    self.security_context.current_user.id
                    if self.security_context else None
                )

                # Get updated values from the repository result
                new_capacity = updated_location.capacity if hasattr(updated_location, 'capacity') else 0
                new_utilized = updated_location.utilized if hasattr(updated_location, 'utilized') else 0

                self.event_bus.publish(
                    StorageSpaceUpdated(
                        location_id=location_id,
                        previous_capacity=previous_capacity,
                        new_capacity=new_capacity,
                        previous_utilized=previous_utilized,
                        new_utilized=new_utilized,
                        user_id=user_id_for_event,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"StorageLocation:{location_id}")
                self.cache_service.invalidate(f"StorageLocation:detail:{location_id}")

            # Format for API response
            updated_formatted = self._format_location_for_api(updated_location)

            return updated_formatted

    @validate_input(validate_storage_assignment)
    def assign_material_to_location(self, data: Dict[str, Any], user_id: Optional[int] = None) -> StorageAssignment:
        """
        Assign a material to a storage location.

        Args:
            data: Assignment data with material ID, location ID, quantity, etc.
            user_id: Optional ID of the user making the assignment

        Returns:
            Created storage assignment entity

        Raises:
            ValidationException: If validation fails
            StorageLocationNotFoundException: If location not found
            MaterialNotFoundException: If material not found
            StorageCapacityExceededException: If assignment would exceed location capacity
        """
        with self.transaction():
            # Get location using repository
            location_id = data.get("storage_id")
            location = self.repository.get_by_id(location_id)
            if not location:
                raise StorageLocationNotFoundException(location_id)

            # Check if material exists if material service is available
            material_id = data.get("material_id")
            if self.material_service and material_id:
                material = self.material_service.get_by_id(material_id)
                if not material:
                    from app.core.exceptions import MaterialNotFoundException
                    raise MaterialNotFoundException(material_id)

            # Check capacity constraints
            quantity = data.get("quantity", 0)
            if not self._has_sufficient_capacity(location_id, quantity):
                from app.core.exceptions import StorageCapacityExceededException
                raise StorageCapacityExceededException(
                    f"Assignment would exceed capacity of storage location {location_id}",
                    "STORAGE_002",
                    {
                        "location_id": location_id,
                        "current_utilized": location.utilized,
                        "capacity": location.capacity,
                        "requested_quantity": quantity,
                    },
                )

            # Set assigned date and user if not provided
            if "assigned_date" not in data:
                data["assigned_date"] = datetime.now()

            if "assigned_by" not in data and user_id:
                data["assigned_by"] = str(user_id)
            elif "assigned_by" not in data and self.security_context:
                data["assigned_by"] = str(self.security_context.current_user.id)

            # Create assignment
            assignment = self.assignment_repository.create(data)

            # Update location utilization
            current_utilized = location.utilized or 0
            self.repository.update(
                location_id, {"utilized": current_utilized + quantity}
            )

            # Publish event if event bus exists
            if self.event_bus:
                user_id_for_event = user_id or (
                    self.security_context.current_user.id
                    if self.security_context else None
                )
                self.event_bus.publish(
                    StorageAssignmentCreated(
                        assignment_id=assignment.id,
                        material_id=material_id,
                        location_id=location_id,
                        quantity=quantity,
                        user_id=user_id_for_event,
                    )
                )

            # Update material's storage location if material service is available
            if self.material_service and hasattr(
                    self.material_service, "update_storage_location"
            ):
                self.material_service.update_storage_location(
                    material_id=material_id, storage_location_id=location_id
                )

            # Invalidate cache
            if self.cache_service:
                self.cache_service.invalidate(f"StorageLocation:detail:{location_id}")

            # Format assignment for API response
            formatted_assignment = self._format_assignment_for_api(assignment)

            logger.info(f"Created storage assignment for material {material_id} in location {location_id}")
            return formatted_assignment