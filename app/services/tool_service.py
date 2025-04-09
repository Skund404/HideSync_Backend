# File: app/services/tool_service.py

from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime, timedelta, date
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
import os # Import os for environment variable check

# Import Events from app.core.events
from app.core.events import (
    DomainEvent, ToolCreated, ToolStatusChanged, ToolMaintenanceScheduled,
    ToolMaintenanceCompleted, ToolCheckedOut, ToolReturned
)
from app.core.exceptions import (
    HideSyncException, ValidationException, EntityNotFoundException,
    BusinessRuleException, ConcurrentOperationException, ToolNotAvailableException,
    InvalidStatusTransitionException, CheckoutNotFoundException, MaintenanceNotFoundException,
    ToolNotFoundException
)
# from app.core.validation import validate_input, validate_entity # Assuming these exist
from app.db.models.enums import ToolCategory
from app.db.models.tool import Tool, ToolMaintenance, ToolCheckout
from app.repositories.tool_repository import (
    ToolRepository, ToolMaintenanceRepository, ToolCheckoutRepository,
)
from app.services.base_service import BaseService
from app.schemas.tool import ToolSearchParams, MaintenanceSchedule, MaintenanceScheduleItem

# Configure logger
# Set logging level based on environment or config if needed
log_level = logging.DEBUG if os.environ.get("LOG_LEVEL", "INFO").upper() == "DEBUG" else logging.INFO
logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Helper Function for Robust Date/Datetime Parsing ---
def _parse_date_or_datetime(value: Any, field_name: str, expect_datetime: bool = False) -> Optional[Union[date, datetime]]:
    """ Safely parses input into a date or datetime object. Handles None, existing objects, and ISO strings. """
    if value is None:
        logger.debug(f"_parse_date_or_datetime ({field_name}): Input is None, returning None.")
        return None

    if isinstance(value, datetime):
        result = value if expect_datetime else value.date()
        logger.debug(f"_parse_date_or_datetime ({field_name}): Input is datetime, returning {result} (type: {type(result)}).")
        return result

    if isinstance(value, date):
        result = datetime.combine(value, datetime.min.time()) if expect_datetime else value
        logger.debug(f"_parse_date_or_datetime ({field_name}): Input is date, returning {result} (type: {type(result)}).")
        return result

    if isinstance(value, str):
        logger.debug(f"_parse_date_or_datetime ({field_name}): Input is string '{value}', attempting parse.")
        try:
            # Try parsing as full ISO datetime first (more specific)
            dt_str = value.split('.')[0] # Remove potential fractional seconds
            if 'Z' in dt_str: # Handle Z timezone indicator (treat as UTC)
                 dt_str = dt_str.replace('Z', '+00:00')
                 dt_obj = datetime.fromisoformat(dt_str)
                 logger.debug(f"_parse_date_or_datetime ({field_name}): Parsed '{value}' as datetime (with Z).")
            elif 'T' in dt_str: # Assume it's a datetime string
                 dt_obj = datetime.fromisoformat(dt_str)
                 logger.debug(f"_parse_date_or_datetime ({field_name}): Parsed '{value}' as datetime (with T).")
            else: # Assume it's just a date string (YYYY-MM-DD)
                 date_obj = date.fromisoformat(dt_str)
                 dt_obj = datetime.combine(date_obj, datetime.min.time()) # Convert to datetime
                 logger.debug(f"_parse_date_or_datetime ({field_name}): Parsed '{value}' as date-only string, converted to datetime.")

            result = dt_obj if expect_datetime else dt_obj.date()
            logger.debug(f"_parse_date_or_datetime ({field_name}): Final parsed result: {result} (type: {type(result)}).")
            return result
        except ValueError:
            # Try parsing just the date part if full datetime parse fails
            logger.debug(f"_parse_date_or_datetime ({field_name}): Full datetime parse failed, trying date-only fallback.")
            try:
                date_obj = date.fromisoformat(value.split('T')[0])
                result = datetime.combine(date_obj, datetime.min.time()) if expect_datetime else date_obj
                logger.debug(f"_parse_date_or_datetime ({field_name}): Fallback parse successful: {result} (type: {type(result)}).")
                return result
            except ValueError as e: # Catch the specific error
                logger.warning(f"Failed to parse string '{value}' for field '{field_name}'. Error: {e}")
                # Raise exception using the field_name passed into the function
                raise ValidationException(f"Invalid date/datetime format for {field_name}. Expected ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).") from e

    # If it's not None, date, datetime, or string, it's an invalid type
    logger.error(f"Invalid type provided for {field_name}: {type(value)}")
    raise ValidationException(f"Invalid type for {field_name}: {type(value)}. Expected date/datetime object or ISO string.")


# --- ToolService Class ---
class ToolService(BaseService[Tool]):
    """ Service for managing tools. """

    # --- Field Type Mapping (Model field -> expects datetime?) ---
    # Use model (snake_case) names as keys
    _tool_date_fields_map = {
        "purchase_date": False, "last_maintenance": False, "next_maintenance": False,
        "checked_out_date": True, "due_date": False,
        "created_at": True, "updated_at": True,
    }
    _checkout_date_fields_map = {
        "checked_out_date": True, "due_date": False, "returned_date": True,
        "created_at": True, "updated_at": True,
    }
    _maintenance_date_fields_map = {
        "date": False, "next_date": False,
        "created_at": True, "updated_at": True,
    }

    def __init__(
            self, session: Session, repository: Optional[ToolRepository] = None,
            maintenance_repository: Optional[ToolMaintenanceRepository] = None,
            checkout_repository: Optional[ToolCheckoutRepository] = None,
            event_bus=None, cache_service=None, inventory_service=None,
            project_service=None, supplier_service=None,
    ):
        self.session = session
        self.repository = repository or ToolRepository(session)
        self.maintenance_repository = maintenance_repository or ToolMaintenanceRepository(session)
        self.checkout_repository = checkout_repository or ToolCheckoutRepository(session)
        # Inject other services if needed
        self.inventory_service = inventory_service
        self.project_service = project_service
        self.supplier_service = supplier_service
        super().__init__(session=session, repository=self.repository, event_bus=event_bus, cache_service=cache_service)
        logger.info("ToolService initialized.")

    # --- COMPLETE METHOD DEFINITION ---
    def _preprocess_data_dates(self, data: Dict[str, Any], field_map: Dict[str, bool], is_update: bool = False):
        """ Converts date/datetime fields in data dict based on map, handles key casing, adds timestamps. Returns new dict. """
        if not data:
            logger.debug("_preprocess_data_dates: Input data is empty, returning as is.")
            return {} # Return empty dict if input is empty

        processed_data = {}
        now_dt = datetime.now()
        original_keys = list(data.keys()) # Keep original keys for iteration
        logger.debug(f"_preprocess_data_dates: Starting preprocessing for keys: {original_keys}")

        for field_key in original_keys:
            value = data[field_key]
            # Try to find the corresponding model field name (handle camelCase -> snake_case)
            model_field_name = field_key
            field_info = field_map.get(model_field_name)
            is_mapped_date_field = False # Flag to track if we found a match in the date map

            if field_info is not None:
                # Found a direct match (likely already snake_case) for a date field
                is_mapped_date_field = True
                logger.debug(f"_preprocess_data_dates: Direct map match found for date key '{field_key}'.")
            else:
                 # Try converting potential camelCase API key to snake_case model key
                 possible_model_key = ''.join(['_'+c.lower() if c.isupper() else c for c in field_key]).lstrip('_')
                 if possible_model_key != field_key: # Only proceed if conversion actually changed the key
                     field_info = field_map.get(possible_model_key)
                     if field_info is not None:
                          # Found a match after converting to snake_case for a date field
                          model_field_name = possible_model_key # Use the correct model key name
                          is_mapped_date_field = True
                          logger.debug(f"_preprocess_data_dates: Mapped API key '{field_key}' to model key '{model_field_name}' for date processing.")

            # Process based on whether it was found in the date map
            if is_mapped_date_field:
                expect_datetime = field_info # True if datetime, False if date
                try:
                    # Parse the incoming value using the helper
                    parsed_value = _parse_date_or_datetime(value, model_field_name, expect_datetime)
                    # Store with the SNAKE_CASE model key (important for repository update)
                    processed_data[model_field_name] = parsed_value
                    logger.debug(f"_preprocess_data_dates: Processed '{field_key}' (as '{model_field_name}') -> {repr(parsed_value)} (type: {type(parsed_value)})")
                except ValidationException as e:
                    logger.error(f"Date preprocessing failed for field '{field_key}' mapped to '{model_field_name}': {e}")
                    raise # Re-raise validation error
                except Exception as e: # Catch other potential parsing errors
                     logger.error(f"Unexpected error during date preprocessing for '{field_key}': {e}", exc_info=True)
                     # Use model_field_name in the exception message as it's more relevant internally
                     raise ValidationException(f"Error processing date field {model_field_name}.") from e
            else:
                # If not found in date map (neither original nor snake_case), keep original key and value
                # Convert camelCase to snake_case for non-date fields as well for consistency? Optional.
                # For now, just keep the key as received if not a mapped date field.
                snake_key_if_needed = ''.join(['_'+c.lower() if c.isupper() else c for c in field_key]).lstrip('_')
                processed_data[snake_key_if_needed] = value # Store with snake_case key anyway
                if field_key != snake_key_if_needed:
                     logger.debug(f"_preprocess_data_dates: Field '{field_key}' not in date map, storing value under snake_case key '{snake_key_if_needed}'.")
                else:
                     logger.debug(f"_preprocess_data_dates: Field '{field_key}' not in date map, keeping key and value.")


        # Add/update timestamps using snake_case keys if they exist in the map
        if not is_update and "created_at" in field_map and field_map["created_at"]:
            processed_data.setdefault("created_at", now_dt)
            logger.debug(f"_preprocess_data_dates: Setting default 'created_at': {processed_data.get('created_at')}")

        if "updated_at" in field_map and field_map["updated_at"]:
            processed_data["updated_at"] = now_dt # Always set on create/update
            logger.debug(f"_preprocess_data_dates: Setting 'updated_at': {processed_data.get('updated_at')}")

        # Log the final data dictionary before returning
        logger.debug(f"_preprocess_data_dates: Final processed data to be used: {processed_data}")
        # Return the new dictionary containing processed data
        return processed_data
    # --- END OF _preprocess_data_dates ---


    # --- Tool CRUD & Listing ---
    def delete_maintenance_record(self, maintenance_id: int, user_id: Optional[int] = None) -> None:
        """ Delete a maintenance record. """
        if not isinstance(maintenance_id, int) or maintenance_id <= 0:
            raise ValidationException(f"Invalid maintenance ID: {maintenance_id}")
        logger.info(f"User {user_id} attempting to delete maintenance {maintenance_id}")

        with self.transaction():
            maintenance = self.maintenance_repository.get_by_id(maintenance_id)
            if not maintenance:
                raise MaintenanceNotFoundException(maintenance_id=maintenance_id)

            # Optional: Add business rules for deletion
            # For example, you might want to prevent deletion of completed maintenance records
            if maintenance.status == "COMPLETED":
                raise BusinessRuleException(f"Cannot delete completed maintenance record {maintenance_id}.")

            try:
                self.maintenance_repository.delete(maintenance_id)
            except Exception as repo_e:
                logger.error(f"Repository delete failed for maintenance {maintenance_id}: {repo_e}", exc_info=True)
                raise HideSyncException(f"Database error deleting maintenance {maintenance_id}") from repo_e

            logger.info(f"Maintenance record {maintenance_id} deleted by user {user_id}.")

            # Invalidate caches
            self._invalidate_maintenance_caches(maintenance_id=maintenance_id, tool_id=maintenance.tool_id,
                                                list_too=True)
            # Also invalidate tool cache if this affects its maintenance status
            self._invalidate_tool_caches(tool_id=maintenance.tool_id, list_too=False, detail_too=True)

    def get_tools(self, skip: int = 0, limit: int = 100, search_params: Optional[ToolSearchParams] = None) -> List[Tool]:
        """ Get tools with filtering and pagination. """
        logger.debug(f"Fetching tools: skip={skip}, limit={limit}, params={search_params}")
        filters = {}
        search_term = None
        if search_params:
            search_term = search_params.search
            # Use model_dump() for Pydantic v2+ to get dict, exclude None
            filters = search_params.model_dump(exclude_unset=True, exclude_none=True, exclude={'search'})
            if "category" in filters:
                try:
                    # Ensure category value from enum is used if an enum object was passed,
                    # or convert string if string was passed.
                    cat_value = filters["category"]
                    if isinstance(cat_value, ToolCategory):
                        filters["category"] = cat_value # Pass enum directly to repo if it handles it
                    elif isinstance(cat_value, str):
                        filters["category"] = ToolCategory(cat_value.upper())
                    else:
                        raise ValidationException(f"Invalid category type: {type(cat_value)}")
                except ValueError:
                    raise ValidationException(f"Invalid category value: {filters['category']}")
            # TODO: Handle search_params.maintenance_due / checked_out filtering logic if needed
            if filters.pop('maintenance_due', None):
                # Example: add specific filter logic if repo supports it
                # filters['is_maintenance_due'] = True
                logger.warning("Filtering by maintenance_due not fully implemented in service yet.")
                pass
            if filters.pop('checked_out', None):
                 filters['status'] = 'CHECKED_OUT' # Simple status filter

        logger.debug(f"Repository filters: {filters}, Search term: {search_term}")
        try:
             if search_term:
                 tools = self.repository.search_tools(search_term, skip=skip, limit=limit, **filters)
             else:
                 tools = self.repository.list(skip=skip, limit=limit, **filters)
             logger.debug(f"Retrieved {len(tools)} tools.")
             return tools
        except Exception as e:
             # Catching specific errors can be helpful
             logger.error(f"Error retrieving tools from repository: {e}", exc_info=True)
             # Avoid raising HideSyncException for ValidationException
             if isinstance(e, ValidationException): raise e
             raise HideSyncException("Failed to retrieve tools.") from e

    def get_tool(self, tool_id: int) -> Tool:
        """ Get a tool by ID using base service method (handles cache). """
        if not isinstance(tool_id, int) or tool_id <= 0:
            raise ValidationException(f"Invalid tool ID: {tool_id}")

        logger.debug(f"Getting tool ID: {tool_id}")
        try:
             tool = self.get_by_id(tool_id) # BaseService method handles cache
             if not tool:
                 logger.warning(f"Tool {tool_id} not found in repository/cache.")
                 raise ToolNotFoundException(tool_id=tool_id)
             logger.debug(f"Retrieved tool {tool_id}")
             return tool
        except EntityNotFoundException: # Catch specific exception from base service if used
             logger.warning(f"Tool {tool_id} not found via get_by_id.")
             raise ToolNotFoundException(tool_id=tool_id)
        except Exception as e:
             logger.error(f"Error retrieving tool {tool_id}: {e}", exc_info=True)
             raise HideSyncException(f"Failed to retrieve tool {tool_id}.") from e

    def create_tool(self, data: Dict[str, Any], user_id: Optional[int] = None) -> Tool:
        """ Create a new tool, converting date strings to objects. """
        if not data: raise ValidationException("No data provided for tool creation")
        logger.info(f"User {user_id} attempting to create tool with data: { {k:v for k,v in data.items() if k != 'description'} }") # Avoid logging long description

        # --- Preprocess Data (Handles Dates and Key Conversion) ---
        try:
            processed_data = self._preprocess_data_dates(data, self._tool_date_fields_map, is_update=False)
        except ValidationException as e:
             logger.error(f"Validation error during data preprocessing for tool creation: {e}")
             raise
        # --- End Preprocess Data ---

        # --- Validation on potentially processed data ---
        if not processed_data.get("name"): raise ValidationException("Tool name required.")
        if not processed_data.get("category"): raise ValidationException("Tool category required.")

        # Ensure category is the Enum type or convert string
        if "category" in processed_data:
            cat_value = processed_data["category"]
            if isinstance(cat_value, str):
                try: processed_data["category"] = ToolCategory(cat_value.upper())
                except ValueError: raise ValidationException(f"Invalid category string: {cat_value}")
            elif not isinstance(cat_value, ToolCategory):
                 # If it was preprocessed from a different type somehow, raise error
                 raise ValidationException(f"Invalid category type after processing: {type(cat_value)}")
            # If it's already ToolCategory enum, it's fine

        processed_data.setdefault("status", "IN_STOCK") # Ensure status default

        if processed_data.get("purchase_price") is not None:
            try: purchase_price_float = float(processed_data["purchase_price"])
            except (ValueError, TypeError): raise ValidationException("Invalid purchase price format.")
            if purchase_price_float < 0: raise ValidationException("Purchase price cannot be negative.")
            processed_data["purchase_price"] = purchase_price_float # Ensure float type

        if processed_data.get("maintenance_interval") is not None:
             try: maint_interval_int = int(processed_data["maintenance_interval"])
             except (ValueError, TypeError): raise ValidationException("Invalid maintenance interval format.")
             if maint_interval_int <= 0: raise ValidationException("Maintenance interval must be positive.")
             processed_data["maintenance_interval"] = maint_interval_int # Ensure int type

        if processed_data.get("supplier_id") is not None:
             try: processed_data["supplier_id"] = int(processed_data["supplier_id"])
             except (ValueError, TypeError): raise ValidationException("Invalid supplier ID format.")
        # --- End Validation ---

        with self.transaction():
            try:
                logger.debug(f"create_tool: Data being passed to repository.create: {processed_data}")
                tool = self.repository.create(processed_data) # Pass processed data
            except Exception as repo_e:
                logger.error(f"Repository create tool failed: {repo_e}", exc_info=True)
                raise HideSyncException("Database error creating tool.") from repo_e

            logger.info(f"Tool {tool.id} ({tool.name}) created by user {user_id}.")
            self._handle_inventory_adjustment(tool, 1, "INITIAL_STOCK", f"New tool '{tool.name}' added", user_id)
            self._publish_tool_created_event(tool, user_id)

            # Use Python date object if available for scheduling initial maintenance
            next_maint_date = tool.next_maintenance if isinstance(tool.next_maintenance, date) else None
            if not next_maint_date and tool.maintenance_interval and tool.maintenance_interval > 0:
                 logger.debug(f"Scheduling initial maintenance for new tool {tool.id}")
                 self._schedule_initial_maintenance_if_needed(tool, tool.maintenance_interval, user_id)
            elif next_maint_date:
                 logger.debug(f"New tool {tool.id} already has next_maintenance set: {next_maint_date}, skipping initial schedule.")

            self._invalidate_tool_caches(tool.id, list_too=True)
            return tool

    # --- COMPLETE METHOD DEFINITION ---
    def update_tool(self, tool_id: int, data: Dict[str, Any], user_id: Optional[int] = None) -> Tool:
        """ Update an existing tool, converting date strings to objects and handling key cases. """
        if not isinstance(tool_id, int) or tool_id <= 0:
             raise ValidationException(f"Invalid tool ID: {tool_id}")
        if not data:
             raise ValidationException("No data provided for tool update")
        logger.info(f"User {user_id} attempting to update tool {tool_id}")

        # Log Incoming Data (make a copy to avoid modifying the original dict passed in)
        incoming_data_copy = data.copy()
        logger.debug(f"update_tool: Incoming raw data before preprocessing: {incoming_data_copy}")

        # --- Preprocess Data (Handles Dates and Key Conversion: camelCase -> snake_case for mapped fields) ---
        # This will convert keys like 'nextMaintenance' to 'next_maintenance' if found in the map
        # and parse date/datetime values. It returns a *new* dictionary.
        try:
            processed_data = self._preprocess_data_dates(data, self._tool_date_fields_map, is_update=True)
        except ValidationException as e:
             logger.error(f"Validation error during data preprocessing for tool {tool_id}: {e}")
             raise # Propagate validation errors immediately
        # --- End Preprocess Data ---

        # --- Validation on potentially processed data ---
        # Check category using the potentially processed key 'category'
        if "category" in processed_data and processed_data.get("category"):
            cat_value = processed_data["category"]
            if isinstance(cat_value, str):
                try: processed_data["category"] = ToolCategory(cat_value.upper())
                except ValueError: raise ValidationException(f"Invalid category string: {cat_value}")
            elif not isinstance(cat_value, ToolCategory):
                # If it's not a string or the expected Enum, raise error
                raise ValidationException(f"Invalid category type after processing: {type(cat_value)}")
            # If it's already ToolCategory enum, it's fine

        # Check numeric fields using snake_case keys after preprocessing
        if processed_data.get("purchase_price") is not None:
             try: purchase_price_float = float(processed_data["purchase_price"])
             except (ValueError, TypeError): raise ValidationException("Invalid purchase price format.")
             if purchase_price_float < 0: raise ValidationException("Purchase price cannot be negative.")
             processed_data["purchase_price"] = purchase_price_float # Ensure it's float

        if processed_data.get("maintenance_interval") is not None:
             try: maint_interval_int = int(processed_data["maintenance_interval"])
             except (ValueError, TypeError): raise ValidationException("Invalid maintenance interval format.")
             if maint_interval_int <= 0: raise ValidationException("Maintenance interval must be positive.")
             processed_data["maintenance_interval"] = maint_interval_int # Ensure it's int

        if processed_data.get("supplier_id") is not None:
            # Allow null/None explicitly or ensure it's int
            if processed_data["supplier_id"] is not None:
                 try: processed_data["supplier_id"] = int(processed_data["supplier_id"])
                 except (ValueError, TypeError): raise ValidationException("Invalid supplier ID format.")
        # --- End Validation ---

        # Remove fields not meant for direct update if necessary (e.g., calculated fields sent from FE)
        # Example: fields_to_exclude = {'is_checked_out', 'maintenance_due', 'days_since_purchase', 'supplier_rel'}
        # processed_data = {k: v for k, v in processed_data.items() if k not in fields_to_exclude}

        if not processed_data:
             logger.warning(f"No valid data remaining after preprocessing for tool {tool_id} update.")
             # Depending on desired behavior, either raise or return existing tool
             raise ValidationException("No valid update data provided after processing.")

        with self.transaction():
            tool = self.repository.get_by_id(tool_id) # Fetch existing
            if not tool:
                raise ToolNotFoundException(tool_id=tool_id)

            previous_status = tool.status
            # Use processed_data which has snake_case 'status' key if provided
            new_status = processed_data.get("status", previous_status)
            if new_status != previous_status:
                self._validate_status_transition(previous_status, new_status) # Use internal helper

            try:
                # --- Log Data Going to Repository ---
                # Ensure we pass the dictionary with processed snake_case keys
                logger.debug(f"update_tool: Data being passed to repository.update for tool {tool_id}: {processed_data}")
                updated_tool = self.repository.update(tool_id, processed_data) # Pass the processed data
                if not updated_tool:
                     # This case might happen if repository.update returns None on failure/no change
                     logger.error(f"Repository update returned None for tool {tool_id}.")
                     raise HideSyncException(f"Failed to update tool {tool_id} in repository.")

            except ConcurrentOperationException as coe:
                 logger.warning(f"Concurrent update detected for tool {tool_id}: {coe}")
                 raise # Re-raise concurrency errors
            except Exception as repo_e:
                logger.error(f"Repository update failed for tool {tool_id}: {repo_e}", exc_info=True)
                # Consider specific exception types from repo if available
                raise HideSyncException(f"Database error updating tool {tool_id}") from repo_e

            logger.info(f"Tool {tool_id} updated successfully by user {user_id}.")
            # Publish status change event if applicable
            if new_status != previous_status:
                # Pass reason from processed_data if available (now snake_case)
                reason = processed_data.get("status_change_reason") # Assuming snake_case key if present
                self._publish_tool_status_changed_event(
                    tool_id, previous_status, new_status, reason, user_id
                )
            # Invalidate cache entries
            self._invalidate_tool_caches(tool_id, list_too=True)
            return updated_tool # Return the updated ORM object
    # --- END OF update_tool ---

    def delete_tool(self, tool_id: int, user_id: Optional[int] = None) -> None:
        """ Delete a tool. """
        if not isinstance(tool_id, int) or tool_id <= 0:
            raise ValidationException(f"Invalid tool ID: {tool_id}")
        logger.info(f"User {user_id} attempting to delete tool {tool_id}")

        with self.transaction():
            tool = self.repository.get_by_id(tool_id)
            if not tool:
                raise ToolNotFoundException(tool_id=tool_id)
            # Business rule: Cannot delete if checked out
            if tool.status == "CHECKED_OUT":
                raise BusinessRuleException(f"Cannot delete checked out tool {tool_id}.")
            # Optional: Add checks for active maintenance?

            try:
                # Store name before deletion for logging/events
                tool_name = tool.name
                self.repository.delete(tool_id)
            except Exception as repo_e:
                logger.error(f"Repository delete failed for tool {tool_id}: {repo_e}", exc_info=True)
                raise HideSyncException(f"Database error deleting tool {tool_id}") from repo_e

            logger.info(f"Tool {tool_id} ({tool_name}) deleted by user {user_id}.")
            # Handle inventory adjustment (passing original tool object)
            self._handle_inventory_adjustment(tool, -1, "DISPOSAL", f"Tool '{tool_name}' deleted", user_id)
            # Invalidate caches
            self._invalidate_tool_caches(tool_id, list_too=True, detail_too=True)
            # Invalidate related caches (maintenance and checkouts for this tool ID)
            self._invalidate_maintenance_caches(tool_id=tool_id, list_too=True)
            self._invalidate_checkout_caches(tool_id=tool_id, list_too=True)
            # Note: Event for deletion could be published here if needed


    # --- Checkout Operations ---
    def get_checkouts(self, status: Optional[str] = None, tool_id: Optional[int] = None,
                      project_id: Optional[int] = None, user_id: Optional[int] = None,
                      skip: int = 0, limit: int = 100) -> List[ToolCheckout]:
        """ Get tool checkouts with filtering. """
        filters = {}
        if status: filters["status"] = status
        if tool_id is not None:
            if not isinstance(tool_id, int) or tool_id <= 0: raise ValidationException(f"Invalid tool ID: {tool_id}")
            filters["tool_id"] = tool_id # Match repo/model key
        if project_id is not None:
            if not isinstance(project_id, int) or project_id <= 0: raise ValidationException(f"Invalid project ID: {project_id}")
            filters["project_id"] = project_id # Match repo/model key
        if user_id is not None: # Assuming user_id corresponds to checked_out_by
            # Repo needs to handle filtering by checked_out_by (might need specific method)
            # filters["checked_out_by_user_id"] = user_id # Example if repo supports it
            logger.warning("Filtering checkouts by user_id not fully implemented in service layer.")
            pass

        logger.debug(f"Fetching checkouts: filters={filters}, skip={skip}, limit={limit}")
        try:
             checkouts = self.checkout_repository.list(skip=skip, limit=limit, **filters)
             logger.debug(f"Retrieved {len(checkouts)} checkouts.")
             return checkouts
        except Exception as e:
             logger.error(f"Error retrieving checkouts from repository: {e}", exc_info=True)
             raise HideSyncException("Failed to retrieve checkouts.") from e


    def checkout_tool(self, data: Dict[str, Any], user_id: Optional[int] = None) -> ToolCheckout:
        """ Check out a tool, converting date strings to objects. """
        if not data: raise ValidationException("No data provided for checkout")
        logger.info(f"User {user_id} attempting checkout with data: {data}")

        # Preprocess data (handles date/time keys and values)
        try:
            processed_data = self._preprocess_data_dates(data, self._checkout_date_fields_map, is_update=False)
        except ValidationException as e:
            logger.error(f"Validation error during checkout data preprocessing: {e}")
            raise

        # --- Validation on processed data ---
        tool_id = processed_data.get("tool_id")
        checked_out_by = processed_data.get("checked_out_by")
        due_date_obj = processed_data.get("due_date")
        project_id = processed_data.get("project_id")
        # Checked out date will be added by preprocessing or defaults below

        if not tool_id: raise ValidationException("Tool ID required.")
        if not isinstance(tool_id, int) or tool_id <= 0: raise ValidationException(f"Invalid tool ID: {tool_id}")
        if not checked_out_by: raise ValidationException("'checked_out_by' required.")
        if not due_date_obj: raise ValidationException("Due date required.") # Preprocessor should have created this
        if not isinstance(due_date_obj, date): raise ValidationException("Due date must be a valid date.")
        if project_id is not None and (not isinstance(project_id, int) or project_id <= 0):
            raise ValidationException(f"Invalid project ID: {project_id}")
        # --- End Validation ---

        # Default checked_out_date if not provided/processed
        checked_out_date_obj = processed_data.get("checked_out_date", datetime.now())
        if not isinstance(checked_out_date_obj, datetime):
             logger.warning(f"Processed checked_out_date is not datetime: {type(checked_out_date_obj)}. Defaulting to now.")
             checked_out_date_obj = datetime.now()

        # Ensure due date is not in the past
        if due_date_obj < checked_out_date_obj.date():
            raise ValidationException("Due date cannot be before checkout date.")

        with self.transaction():
            tool = self.repository.get_by_id(tool_id)
            if not tool: raise ToolNotFoundException(tool_id=tool_id)
            if tool.status != "IN_STOCK":
                raise ToolNotAvailableException(tool_id=tool.id, current_status=tool.status)

            project_name = self._validate_and_get_project_name(project_id)

            # Prepare checkout data with Python objects for repository using processed data
            checkout_data_to_create = {
                "tool_id": tool_id,
                "tool_name": tool.name, # Denormalize name
                "checked_out_by": checked_out_by,
                "checked_out_date": checked_out_date_obj, # Use datetime object
                "due_date": due_date_obj, # Use date object
                "project_id": project_id,
                "project_name": project_name, # Denormalized project name
                "notes": processed_data.get("notes"),
                "status": "CHECKED_OUT",
                "condition_before": processed_data.get("condition_before", "Good"), # Default condition
                "created_at": processed_data.get("created_at", checked_out_date_obj), # Use processed or current
                "updated_at": processed_data.get("updated_at", checked_out_date_obj)  # Use processed or current
            }
            # Remove None values if repo create expects only provided fields
            checkout_data_to_create = {k: v for k, v in checkout_data_to_create.items() if v is not None}

            logger.debug(f"checkout_tool: Data being passed to checkout_repository.create: {checkout_data_to_create}")
            checkout = self._create_checkout_record_in_repo(checkout_data_to_create)

            # Update tool using Python objects
            tool_update_data = {
                 "status": "CHECKED_OUT",
                 "checked_out_to": checked_out_by,
                 "checked_out_date": checked_out_date_obj, # datetime object
                 "due_date": due_date_obj, # date object
                 "updated_at": processed_data.get("updated_at", checked_out_date_obj) # Ensure tool update time matches
            }
            logger.debug(f"checkout_tool: Data being passed to repository.update for tool {tool_id}: {tool_update_data}")
            self._update_tool_record_in_repo(tool_id, tool_update_data)

            self._publish_tool_checked_out_event(checkout, user_id)
            self._invalidate_checkout_caches(tool_id=tool_id, list_too=True)
            self._invalidate_tool_caches(tool_id=tool_id, list_too=True)
            logger.info(f"Tool {tool_id} checked out to {checked_out_by} (Checkout ID: {checkout.id})")
            return checkout

    def return_tool(self, checkout_id: int, data: Dict[str, Any], user_id: Optional[int] = None) -> ToolCheckout:
        """ Return a checked out tool. """
        if not isinstance(checkout_id, int) or checkout_id <= 0:
            raise ValidationException(f"Invalid checkout ID: {checkout_id}")
        if not data: data = {} # Allow empty data, defaults will be used
        logger.info(f"User {user_id} returning checkout {checkout_id} with data: {data}")

        # Preprocess data (handles date/time keys and values)
        try:
            processed_data = self._preprocess_data_dates(data, self._checkout_date_fields_map, is_update=True)
        except ValidationException as e:
            logger.error(f"Validation error during return data preprocessing: {e}")
            raise

        # Default returned_date if not provided/processed
        returned_date_obj = processed_data.get("returned_date", datetime.now())
        if not isinstance(returned_date_obj, datetime):
             logger.warning(f"Processed returned_date is not datetime: {type(returned_date_obj)}. Defaulting to now.")
             returned_date_obj = datetime.now()

        # Get condition and issues from processed data (now snake_case)
        condition_after = processed_data.get("condition_after", "Good") # Default condition
        issue_description = processed_data.get("issue_description")
        has_issues = bool(issue_description)

        # Update timestamp
        updated_at_obj = processed_data.get("updated_at", returned_date_obj) # Use processed or return time


        with self.transaction():
            checkout = self.checkout_repository.get_by_id(checkout_id)
            if not checkout: raise CheckoutNotFoundException(checkout_id=checkout_id)
            if checkout.status != "CHECKED_OUT":
                 raise BusinessRuleException(f"Checkout {checkout_id} has status '{checkout.status}', cannot return.")

            # Prepare checkout update data with Python objects
            checkout_update = {
                "returned_date": returned_date_obj, # datetime object
                "status": "RETURNED_WITH_ISSUES" if has_issues else "RETURNED",
                "condition_after": condition_after,
                "issue_description": issue_description, # Will be None if no issues
                "updated_at": updated_at_obj # datetime object
            }
            # Remove None values before repo update
            checkout_update = {k: v for k, v in checkout_update.items() if v is not None}

            logger.debug(f"return_tool: Data being passed to checkout_repository.update for checkout {checkout_id}: {checkout_update}")
            updated_checkout = self._update_checkout_record_in_repo(checkout_id, checkout_update)

            # Update tool status using Python objects
            tool_status = "MAINTENANCE" if has_issues else "IN_STOCK"
            tool_update_data = {
                "status": tool_status,
                "checked_out_to": None, # Clear checkout info
                "checked_out_date": None,
                "due_date": None,
                "updated_at": updated_at_obj # Match update time
            }
            logger.debug(f"return_tool: Data being passed to repository.update for tool {updated_checkout.tool_id}: {tool_update_data}")
            self._update_tool_record_in_repo(updated_checkout.tool_id, tool_update_data)

            if has_issues:
                logger.info(f"Tool {updated_checkout.tool_id} returned with issues, scheduling maintenance.")
                self._schedule_maintenance_after_return(updated_checkout, condition_after, issue_description, user_id)

            self._publish_tool_returned_event(updated_checkout, condition_after, has_issues, user_id)
            self._invalidate_checkout_caches(checkout_id=checkout_id, tool_id=updated_checkout.tool_id, list_too=True)
            self._invalidate_tool_caches(tool_id=updated_checkout.tool_id, list_too=True)
            logger.info(f"Checkout {checkout_id} (Tool: {updated_checkout.tool_id}) returned successfully.")
            return updated_checkout

    # --- Maintenance Operations ---
    def get_maintenance_records(self, status: Optional[str] = None, tool_id: Optional[int] = None,
                                upcoming_only: bool = False, skip: int = 0, limit: int = 100) -> List[ToolMaintenance]:
        """ Get tool maintenance records. """
        filters = {}
        if status: filters["status"] = status
        if tool_id is not None:
             if not isinstance(tool_id, int) or tool_id <= 0: raise ValidationException(f"Invalid tool ID: {tool_id}")
             filters["tool_id"] = tool_id # Match repo/model key

        logger.debug(f"Fetching maintenance: filters={filters}, upcoming={upcoming_only}, skip={skip}, limit={limit}")

        try:
             if upcoming_only:
                 today = date.today()
                 thirty_days_later = today + timedelta(days=30)
                 # Use the specific repository method if it handles date comparison efficiently
                 logger.debug(f"Fetching upcoming maintenance between {today} and {thirty_days_later}")
                 records = self.maintenance_repository.get_maintenance_by_date_range(
                      start_date=today,
                      end_date=thirty_days_later,
                      status="SCHEDULED", # Only scheduled upcoming
                      skip=skip, limit=limit
                 )
                 logger.debug(f"Retrieved {len(records)} upcoming maint records via repo filter.")
             else:
                 records = self.maintenance_repository.list(skip=skip, limit=limit, **filters)
                 logger.debug(f"Retrieved {len(records)} maintenance records.")
             return records
        except Exception as e:
             logger.error(f"Error retrieving maintenance from repository: {e}", exc_info=True)
             raise HideSyncException("Failed to retrieve maintenance records.") from e

    def get_maintenance_schedule(self, start_date_str: Optional[str] = None,
                                 end_date_str: Optional[str] = None) -> MaintenanceSchedule:
        """ Get tool maintenance schedule (uses date objects internally). """
        logger.debug(f"Generating maintenance schedule: start={start_date_str}, end={end_date_str}")

        # Parse date strings to date objects robustly
        try:
            start_date_obj = _parse_date_or_datetime(start_date_str, "start_date") or date.today()
            end_date_obj = _parse_date_or_datetime(end_date_str, "end_date") or (start_date_obj + timedelta(days=30))
        except ValidationException as e:
             raise e # Re-raise parsing error

        if start_date_obj > end_date_obj:
            raise ValidationException("Start date cannot be after end date.")

        logger.debug(f"Fetching scheduled maintenance between {start_date_obj} and {end_date_obj}")
        # Fetch scheduled records in range (using date objects)
        scheduled_records = self.maintenance_repository.get_maintenance_by_date_range(
            start_date=start_date_obj,
            end_date=end_date_obj,
            status="SCHEDULED"
        )
        logger.debug(f"Fetched {len(scheduled_records)} scheduled maintenance records.")

        # Fetch needed tools efficiently
        tool_ids = {r.tool_id for r in scheduled_records if r.tool_id}
        tools_dict = {t.id: t for t in self.repository.get_by_ids(list(tool_ids))} if tool_ids else {}

        schedule_items: List[MaintenanceScheduleItem] = []
        today = date.today()
        overdue_count = 0

        for record in scheduled_records:
            # Ensure record.date is a valid date object
            record_date_obj = record.date if isinstance(record.date, date) else None
            if not record_date_obj or not record.tool_id:
                 logger.warning(f"Skipping schedule item generation for record ID {record.id}: missing date or tool_id")
                 continue # Skip if no date or tool ID

            tool = tools_dict.get(record.tool_id)
            if not tool:
                logger.warning(f"Tool ID {record.tool_id} not found for maintenance record {record.id}, skipping schedule item.")
                continue # Skip if tool not found

            is_overdue = record_date_obj < today
            days_until = (record_date_obj - today).days if record_date_obj >= today else None

            # Ensure category is string value for the schema
            category_str = tool.category.value if isinstance(tool.category, ToolCategory) else str(tool.category)

            item = MaintenanceScheduleItem(
                tool_id=tool.id,
                tool_name=tool.name,
                maintenance_type=record.maintenance_type, # Use correct attribute name
                scheduled_date=record_date_obj, # Keep as date object for Pydantic conversion
                category=category_str, # Pass string value
                status=record.status,
                location=tool.location,
                is_overdue=is_overdue,
                days_until_due=days_until
            )
            schedule_items.append(item)
            if is_overdue: overdue_count += 1

        schedule_items.sort(key=lambda x: x.scheduled_date)
        response = MaintenanceSchedule(
            schedule=schedule_items,
            total_items=len(schedule_items),
            overdue_items=overdue_count,
            upcoming_items=len(schedule_items) - overdue_count,
            start_date=start_date_obj, # Keep as date object for Pydantic conversion
            end_date=end_date_obj     # Keep as date object for Pydantic conversion
        )
        logger.debug("Maintenance schedule generated.")
        return response # Pydantic will handle converting date objects to strings in response


    def create_maintenance(self, data: Dict[str, Any], user_id: Optional[int] = None) -> ToolMaintenance:
        """ Create (schedule) a maintenance record. """
        if not data: raise ValidationException("No data provided for maintenance creation")
        logger.info(f"User {user_id} creating maintenance with data: {data}")

        # Preprocess data (handles dates and key cases)
        try:
            processed_data = self._preprocess_data_dates(data, self._maintenance_date_fields_map, is_update=False)
        except ValidationException as e:
            logger.error(f"Validation error during maintenance data preprocessing: {e}")
            raise

        # --- Validation on processed data ---
        tool_id = processed_data.get("tool_id")
        maint_type = processed_data.get("maintenance_type")
        maint_date_obj = processed_data.get("date")
        status = processed_data.get("status", "SCHEDULED")
        cost = processed_data.get("cost", 0.0) # Default cost

        if not tool_id: raise ValidationException("Tool ID required.")
        if not isinstance(tool_id, int) or tool_id <= 0: raise ValidationException(f"Invalid tool ID: {tool_id}")
        if not maint_type: raise ValidationException("Maintenance type required.")
        if not maint_date_obj: raise ValidationException("Maintenance date required.")
        if not isinstance(maint_date_obj, date): raise ValidationException("Maintenance date must be a valid date.")
        if status not in ["SCHEDULED", "IN_PROGRESS", "COMPLETED", "WAITING_PARTS"]:
             raise ValidationException(f"Invalid status: {status}")

        try: cost_float = float(cost)
        except (ValueError, TypeError): raise ValidationException("Invalid cost format.")
        if cost_float < 0: raise ValidationException("Cost cannot be negative.")
        processed_data["cost"] = cost_float # Ensure float type
        # --- End Validation ---

        with self.transaction():
            tool = self.repository.get_by_id(tool_id)
            if not tool: raise ToolNotFoundException(tool_id=tool_id)

            # Prepare maintenance data with Python objects for repository
            # Use processed_data which has snake_case keys and parsed dates
            maint_data_create = {
                "tool_id": tool_id,
                "tool_name": tool.name, # Denormalize
                "maintenance_type": maint_type,
                "date": maint_date_obj, # date object
                "performed_by": processed_data.get("performed_by"),
                "cost": processed_data["cost"], # Already validated float
                "internal_service": processed_data.get("internal_service", True), # Default true
                "details": processed_data.get("details"),
                "parts": processed_data.get("parts"),
                "condition_before": processed_data.get("condition_before", tool.status), # Default to current tool status
                "condition_after": processed_data.get("condition_after"),
                "status": status,
                "next_date": processed_data.get("next_date"), # date object or None
                "created_at": processed_data.get("created_at", datetime.now()), # Use processed or now
                "updated_at": processed_data.get("updated_at", datetime.now())  # Use processed or now
            }
            # Remove None values if repo create expects only provided fields
            maint_data_create = {k: v for k, v in maint_data_create.items() if v is not None}

            logger.debug(f"create_maintenance: Data being passed to maintenance_repository.create: {maint_data_create}")
            maintenance = self._create_maintenance_record_in_repo(maint_data_create)

            # Update tool's next maintenance date if this is a scheduled maintenance
            self._update_tool_after_maint_schedule(tool, maintenance, user_id)
            self._publish_maintenance_scheduled_event(maintenance, user_id)
            self._invalidate_maintenance_caches(tool_id=tool_id, list_too=True) # Invalidate list too
            logger.info(f"Maintenance record {maintenance.id} created for tool {tool_id}.")
            return maintenance

    def update_maintenance(self, maintenance_id: int, data: Dict[str, Any],
                           user_id: Optional[int] = None) -> ToolMaintenance:
        """ Update maintenance record. """
        if not isinstance(maintenance_id, int) or maintenance_id <= 0:
             raise ValidationException(f"Invalid maintenance ID: {maintenance_id}")
        if not data: raise ValidationException("No update data provided.")
        logger.info(f"User {user_id} updating maintenance {maintenance_id} with data: {data}")

        # Preprocess data (handles dates and key cases)
        try:
            processed_data = self._preprocess_data_dates(data, self._maintenance_date_fields_map, is_update=True)
        except ValidationException as e:
            logger.error(f"Validation error during maintenance update data preprocessing: {e}")
            raise

        # --- Validation on processed data ---
        if "status" in processed_data and processed_data["status"] not in ["SCHEDULED", "IN_PROGRESS", "COMPLETED", "WAITING_PARTS"]:
            raise ValidationException(f"Invalid status: {processed_data['status']}")
        if processed_data.get("cost") is not None:
             try: cost_float = float(processed_data["cost"])
             except (ValueError, TypeError): raise ValidationException("Invalid cost format.")
             if cost_float < 0: raise ValidationException("Cost cannot be negative.")
             processed_data["cost"] = cost_float # Ensure float type
        if "date" in processed_data and not isinstance(processed_data["date"], date):
            raise ValidationException("Maintenance date must be a valid date.")
        if "next_date" in processed_data and processed_data["next_date"] is not None and not isinstance(processed_data["next_date"], date):
            raise ValidationException("Next maintenance date must be a valid date or null.")
        # --- End Validation ---

        if not processed_data:
             logger.warning(f"No valid data remaining after preprocessing for maintenance {maintenance_id} update.")
             raise ValidationException("No valid update data provided after processing.")


        with self.transaction():
            maintenance = self.maintenance_repository.get_by_id(maintenance_id)
            if not maintenance: raise MaintenanceNotFoundException(maintenance_id=maintenance_id)

            # Prevent certain updates if already completed
            allowed_updates_on_completed = {"details", "cost", "parts", "updated_at"} # Only allow these on completed
            if maintenance.status == "COMPLETED" and not set(processed_data.keys()).issubset(allowed_updates_on_completed):
                disallowed_fields = set(processed_data.keys()) - allowed_updates_on_completed
                logger.warning(f"Attempt to update disallowed fields on completed maintenance {maintenance_id}: {disallowed_fields}")
                raise BusinessRuleException(f"Cannot modify completed maintenance {maintenance_id} with fields: {disallowed_fields}")

            # Pass dict with Python date/datetime objects to repository
            logger.debug(f"update_maintenance: Data being passed to maintenance_repository.update for maint {maintenance_id}: {processed_data}")
            updated_maintenance = self._update_maintenance_record_in_repo(maintenance_id, processed_data)
            self._invalidate_maintenance_caches(maintenance_id=maintenance_id, tool_id=maintenance.tool_id, list_too=True) # Invalidate list too

            # If status changed to completed, update tool potentially
            new_status = processed_data.get("status")
            if new_status == "COMPLETED":
                 logger.info(f"Maintenance {maintenance_id} marked completed, updating tool {updated_maintenance.tool_id}.")
                 tool = self.repository.get_by_id(updated_maintenance.tool_id)
                 if tool:
                      # Use Python date object for comparison/update
                      # Use the date from the updated maintenance record, default to today if missing (shouldn't happen)
                      completion_date_obj = updated_maintenance.date if isinstance(updated_maintenance.date, date) else date.today()
                      # Reschedule next maintenance if needed
                      next_maint_date_obj = self._schedule_next_maintenance_if_needed(
                            tool, completion_date_obj, updated_maintenance.condition_after or "Good", user_id
                      )
                      # Update tool's last_maintenance and next_maintenance fields
                      completion_dt_obj = datetime.combine(completion_date_obj, datetime.min.time()) # Convert completion date to datetime
                      self._update_tool_after_maint_completion(
                           tool, completion_dt_obj, next_maint_date_obj, user_id
                      )
                      self._publish_maintenance_completed_event(updated_maintenance, next_maint_date_obj, user_id)
                 else:
                      logger.error(f"Tool {updated_maintenance.tool_id} not found when trying to update after maintenance {maintenance_id} completion.")


            logger.info(f"Maintenance record {maintenance_id} updated.")
            return updated_maintenance


    def complete_maintenance(self, maintenance_id: int, data: Dict[str, Any],
                             user_id: Optional[int] = None) -> ToolMaintenance:
        """ Mark maintenance as completed. Expects snake_case keys like 'details', 'cost'. """
        if not isinstance(maintenance_id, int) or maintenance_id <= 0:
            raise ValidationException(f"Invalid maintenance ID: {maintenance_id}")
        if not data: data = {}
        logger.info(f"User {user_id} completing maintenance {maintenance_id} with data: {data}")

        # --- Validation on incoming data ---
        cost = data.get("cost")
        if cost is not None:
            try: cost_float = float(cost)
            except (ValueError, TypeError): raise ValidationException("Invalid cost format.")
            if cost_float < 0: raise ValidationException("Cost cannot be negative.")
            data["cost"] = cost_float # Ensure float type
        # --- End Validation ---

        now_dt = datetime.now()
        completion_date_obj = now_dt.date() # Use today's date as completion date

        # Get condition after and notes
        condition_after = data.get("condition_after", "Good") # Default condition if not provided
        notes = data.get("details", '') # Allow empty notes, use 'details' key to match create/update
        parts_used = data.get("parts") # Get parts if provided

        # Timestamp for update
        updated_at_obj = now_dt

        with self.transaction():
            maintenance = self.maintenance_repository.get_by_id(maintenance_id)
            if not maintenance: raise MaintenanceNotFoundException(maintenance_id=maintenance_id)
            if maintenance.status == "COMPLETED": raise BusinessRuleException(f"Maintenance {maintenance_id} already completed.")

            tool = self.repository.get_by_id(maintenance.tool_id)
            if not tool: raise ToolNotFoundException(maintenance.tool_id) # Use specific exception

            # Prepare maintenance update data with Python objects
            maint_update = {
                "status": "COMPLETED",
                "date": completion_date_obj, # date object for completion date
                "performed_by": maintenance.performed_by or f"User {user_id}", # Default performer
                "condition_after": condition_after,
                "details": (maintenance.details or "") + f"\n\nCompleted by User {user_id} on {completion_date_obj.isoformat()}. Notes: {notes}",
                "updated_at": updated_at_obj # datetime object
            }
            if cost is not None: maint_update["cost"] = data["cost"] # Use validated float
            if parts_used is not None: maint_update["parts"] = parts_used

            logger.debug(f"complete_maintenance: Data being passed to maintenance_repository.update for maint {maintenance_id}: {maint_update}")
            completed_maint = self._update_maintenance_record_in_repo(maintenance_id, maint_update)

            # Schedule next maintenance if needed (uses date objects)
            logger.debug(f"complete_maintenance: Scheduling next maintenance for tool {tool.id} if needed.")
            next_maint_date_obj = self._schedule_next_maintenance_if_needed(tool, completion_date_obj, condition_after, user_id)

            # Update tool (uses date/datetime objects)
            logger.debug(f"complete_maintenance: Updating tool record {tool.id} after completion.")
            self._update_tool_after_maint_completion(tool, now_dt, next_maint_date_obj, user_id)

            # Publish event (needs strings)
            self._publish_maintenance_completed_event(completed_maint, next_maint_date_obj, user_id)
            self._invalidate_maintenance_caches(maintenance_id=maintenance_id, tool_id=tool.id, list_too=True)
            self._invalidate_tool_caches(tool_id=tool.id, list_too=True)

            logger.info(f"Maintenance record {maintenance_id} completed for tool {tool.id}.")
            return completed_maint

    # --- Private Helper Methods ---

    def _validate_status_transition(self, current_status: str, new_status: str) -> None:
        """ Validate tool status transitions. """
        allowed = {
            "IN_STOCK": ["CHECKED_OUT", "MAINTENANCE", "DAMAGED", "LOST", "RETIRED"],
            "CHECKED_OUT": ["IN_STOCK", "DAMAGED", "LOST", "MAINTENANCE"], # Allow direct transition on return w/ issues
            "MAINTENANCE": ["IN_STOCK", "DAMAGED", "RETIRED"],
            "DAMAGED": ["MAINTENANCE", "RETIRED", "IN_STOCK"], # Allow marking as usable again
            "LOST": ["IN_STOCK"], # Found
            "RETIRED": [],
            # Add any other statuses like ON_ORDER if needed
        }
        if current_status == new_status: return
        if new_status not in allowed.get(current_status, []):
            logger.warning(f"Invalid tool status transition: {current_status} -> {new_status}")
            raise InvalidStatusTransitionException(
                 f"Cannot transition tool from '{current_status}' to '{new_status}'",
                 allowed_status=allowed.get(current_status, [])
            )
        logger.debug(f"Valid tool status transition: {current_status} -> {new_status}")


    def _validate_and_get_project_name(self, project_id: Optional[int]) -> Optional[str]:
        """ Validate project ID and get project name (if service available). """
        if not project_id: return None
        if not isinstance(project_id, int) or project_id <= 0:
             logger.warning(f"Invalid project ID type or value: {project_id}, skipping name lookup.")
             return None

        if self.project_service and hasattr(self.project_service, 'get_project_name_by_id'): # Example method name
            try:
                project_name = self.project_service.get_project_name_by_id(project_id)
                if project_name:
                     logger.debug(f"Retrieved project name '{project_name}' for ID {project_id}")
                     return project_name
                else:
                     logger.warning(f"Project ID {project_id} not found by project_service.")
                     return None
            except EntityNotFoundException: # Catch specific exception if project service raises it
                logger.warning(f"Project ID {project_id} not found during validation.")
                return None
            except Exception as e:
                 logger.error(f"Error fetching project name for {project_id}: {e}", exc_info=True)
                 return None # Avoid blocking operation due to project service error
        else:
             logger.debug("Project service or required method not available for name lookup.")
             return None


    def _create_checkout_record_in_repo(self, data: Dict[str, Any]) -> ToolCheckout:
        """ Create checkout record using repository. """
        try:
            checkout = self.checkout_repository.create(data)
            logger.info(f"Checkout record {checkout.id} created for tool {data.get('tool_id')}.")
            return checkout
        except Exception as e:
            logger.error(f"Repository create checkout failed: {e}", exc_info=True)
            raise HideSyncException("DB error creating checkout record.") from e

    def _update_checkout_record_in_repo(self, checkout_id: int, data: Dict[str, Any]) -> ToolCheckout:
        """ Update checkout record using repository. """
        try:
            updated = self.checkout_repository.update(checkout_id, data)
            if not updated:
                 logger.error(f"Repository update checkout returned None for ID {checkout_id}.")
                 raise CheckoutNotFoundException(checkout_id=checkout_id) # Or other appropriate error
            logger.info(f"Checkout record {checkout_id} updated.")
            return updated
        except Exception as e:
            logger.error(f"Repository update checkout failed for ID {checkout_id}: {e}", exc_info=True)
            raise HideSyncException("DB error updating checkout record.") from e

    def _update_tool_record_in_repo(self, tool_id: int, data: Dict[str, Any]):
         """ Update tool record using repository. """
         try:
              updated_tool = self.repository.update(tool_id, data)
              if not updated_tool:
                  logger.error(f"Repository update tool returned None for ID {tool_id}.")
                  # Don't necessarily raise here, might just mean no change, but log it.
              else:
                  log_data = {k:v for k,v in data.items() if k != 'updated_at'} # Exclude timestamp from log noise
                  logger.info(f"Tool record {tool_id} updated in repo with data: {log_data}")
         except Exception as e:
              logger.error(f"Repository update tool failed for {tool_id}: {e}", exc_info=True)
              # Decide if this should rollback the transaction or just log
              raise HideSyncException(f"DB error updating tool {tool_id} after related operation.") from e

    def _schedule_maintenance_after_return(self, checkout: ToolCheckout, condition: str, issues: Optional[str],
                                           user_id: Optional[int]):
        """ Schedule maintenance if tool returned with issues. """
        if not checkout or not checkout.tool_id or not issues:
            logger.debug("_schedule_maintenance_after_return: No checkout, tool ID, or issues provided. Skipping.")
            return
        logger.info(f"Auto-scheduling repair for tool {checkout.tool_id} due to return issues.")
        try:
            now_dt = datetime.now()
            maint_data = {
                "tool_id": checkout.tool_id,
                "tool_name": checkout.tool_name, # Use name from checkout record
                "maintenance_type": "REPAIR",
                "date": now_dt.date(), # Schedule for today (as string YYYY-MM-DD)
                "status": "SCHEDULED", # Needs attention
                "details": f"Auto-scheduled after return (Checkout ID: {checkout.id}). Issues: {issues}",
                "condition_before": condition,
            }
            # Call the public create_maintenance method to handle full creation logic,
            # it will handle preprocessing including date conversion.
            self.create_maintenance(maint_data, user_id) # Pass dict with date string
            logger.info(f"Successfully auto-scheduled maintenance for tool {checkout.tool_id}.")
        except Exception as e:
            # Log error but don't necessarily fail the return operation
            logger.error(f"Failed to auto-schedule maintenance for tool {checkout.tool_id}: {e}", exc_info=True)


    def _create_maintenance_record_in_repo(self, data: Dict[str, Any]) -> ToolMaintenance:
        """ Create maintenance record using repository. """
        try:
            maintenance = self.maintenance_repository.create(data)
            logger.info(f"Maintenance record {maintenance.id} created for tool {data.get('tool_id')}.")
            return maintenance
        except Exception as e:
            logger.error(f"Repository create maintenance failed: {e}", exc_info=True)
            raise HideSyncException("DB error creating maintenance record.") from e

    def _update_maintenance_record_in_repo(self, maintenance_id: int, data: Dict[str, Any]) -> ToolMaintenance:
         """ Update maintenance record using repository. """
         try:
              updated = self.maintenance_repository.update(maintenance_id, data)
              if not updated:
                   logger.error(f"Repository update maintenance returned None for ID {maintenance_id}.")
                   raise MaintenanceNotFoundException(maintenance_id=maintenance_id) # Or other appropriate error
              logger.info(f"Maintenance record {maintenance_id} updated.")
              return updated
         except Exception as e:
              logger.error(f"Repository update maintenance failed for ID {maintenance_id}: {e}", exc_info=True)
              raise HideSyncException("DB error updating maintenance record.") from e


    def _update_tool_after_maint_schedule(self, tool: Tool, maintenance: ToolMaintenance, user_id: Optional[int]):
        """ Update tool's next maintenance date after scheduling, if applicable. """
        if not tool or not maintenance or maintenance.status != "SCHEDULED":
            logger.debug("_update_tool_after_maint_schedule: Conditions not met, skipping tool update.")
            return
        if not isinstance(maintenance.date, date):
            logger.warning(f"_update_tool_after_maint_schedule: Maintenance record {maintenance.id} has invalid date type: {type(maintenance.date)}. Skipping tool update.")
            return # Ensure it's a date object

        update_data = {}
        schedule_date_obj = maintenance.date # This is now a date object

        # Update next_maintenance if the new scheduled date is earlier or if none was set
        if tool.next_maintenance is None or schedule_date_obj < tool.next_maintenance:
            logger.debug(f"Updating tool {tool.id} next_maintenance from {tool.next_maintenance} to {schedule_date_obj}")
            update_data["next_maintenance"] = schedule_date_obj # date object

        # Optional: Change tool status if appropriate (e.g., DAMAGED -> MAINTENANCE)
        # if tool.status == "DAMAGED" and maintenance.maintenance_type == "REPAIR":
        #     update_data["status"] = "MAINTENANCE"

        if update_data:
            # Add timestamp for update
            update_data["updated_at"] = datetime.now()
            logger.debug(f"_update_tool_after_maint_schedule: Updating tool {tool.id} with data: {update_data}")
            self._update_tool_record_in_repo(tool.id, update_data)
        else:
             logger.debug(f"_update_tool_after_maint_schedule: No relevant updates needed for tool {tool.id}.")


    def _schedule_initial_maintenance_if_needed(self, tool: Tool, maintenance_interval: Optional[int], user_id: Optional[int]) -> None:
        """ Schedule initial maintenance based on interval after creation. """
        if not tool or not maintenance_interval or maintenance_interval <= 0:
            logger.debug("_schedule_initial_maintenance: Conditions not met (no tool, interval, or interval <= 0).")
            return

        # Use purchase date if available and valid, otherwise creation date
        base_date = None
        if isinstance(tool.purchase_date, date):
            base_date = tool.purchase_date
            logger.debug(f"_schedule_initial_maintenance: Using purchase_date {base_date} as base.")
        elif isinstance(tool.created_at, datetime):
             base_date = tool.created_at.date()
             logger.debug(f"_schedule_initial_maintenance: Using created_at {base_date} as base.")
        else:
            base_date = date.today() # Fallback to today if others are invalid/missing
            logger.warning(f"_schedule_initial_maintenance: Missing valid purchase_date or created_at for tool {tool.id}. Using today {base_date} as base.")


        try:
            initial_maint_date = base_date + timedelta(days=maintenance_interval)
            logger.info(f"Scheduling initial maintenance for tool {tool.id} on {initial_maint_date}")

            maint_data = {
                "tool_id": tool.id,
                "tool_name": tool.name, # Denormalize
                "maintenance_type": "ROUTINE",
                "date": initial_maint_date.isoformat(), # Pass as YYYY-MM-DD string
                "status": "SCHEDULED",
                "details": "Initial routine maintenance scheduled",
            }
            # Call public create method which handles preprocessing
            self.create_maintenance(maint_data, user_id)

            # Also update the tool's next_maintenance field directly IF it's earlier than existing
            # (create_maintenance might handle this via _update_tool_after_maint_schedule, but direct update is safer)
            if tool.next_maintenance is None or initial_maint_date < tool.next_maintenance:
                tool_update = {"next_maintenance": initial_maint_date, "updated_at": datetime.now()}
                logger.debug(f"_schedule_initial_maintenance: Directly updating tool {tool.id} next_maintenance to {initial_maint_date}")
                self._update_tool_record_in_repo(tool.id, tool_update)
            else:
                 logger.debug(f"_schedule_initial_maintenance: Tool {tool.id} already has earlier next_maintenance {tool.next_maintenance}, not overwriting.")

        except Exception as e:
            logger.error(f"Failed schedule initial maintenance for tool {tool.id}: {e}", exc_info=True)


    def _schedule_next_maintenance_if_needed(self, tool: Tool, completion_date: date, condition_after: str,
                                             user_id: Optional[int]) -> Optional[date]:
        """ Schedule next routine maintenance after completion, returns the next date object if scheduled. """
        if not tool or not tool.maintenance_interval or tool.maintenance_interval <= 0:
             logger.debug(f"_schedule_next_maintenance: Tool {tool.id} has no maintenance interval, skipping.")
             return None # No interval, nothing to schedule

        # Ensure completion_date is a date object
        if not isinstance(completion_date, date):
             logger.error(f"_schedule_next_maintenance: Invalid completion_date type for tool {tool.id}: {type(completion_date)}. Skipping.")
             return None

        next_maint_date_obj = completion_date + timedelta(days=tool.maintenance_interval)
        logger.info(f"Scheduling next routine maintenance for tool {tool.id} on {next_maint_date_obj} based on completion date {completion_date}")

        try:
            maint_data = {
                "tool_id": tool.id,
                "tool_name": tool.name, # Denormalize
                "maintenance_type": "ROUTINE",
                "date": next_maint_date_obj.isoformat(), # Pass as YYYY-MM-DD string
                "status": "SCHEDULED",
                "details": f"Routine maintenance scheduled after completion on {completion_date.isoformat()}",
                "condition_before": condition_after, # Condition after previous maint.
            }
            # Call public create method which handles preprocessing
            # We don't need the created object here, just need to ensure it's scheduled
            self.create_maintenance(maint_data, user_id)
            logger.info(f"Successfully scheduled next maintenance for tool {tool.id} on {next_maint_date_obj}.")
            return next_maint_date_obj # Return the scheduled date object
        except Exception as e:
            logger.error(f"Failed schedule next maintenance for tool {tool.id}: {e}", exc_info=True)
            return None # Failed to schedule


    def _update_tool_after_maint_completion(self, tool: Tool, completion_dt: datetime, next_maint_date: Optional[date],
                                            user_id: Optional[int]):
        """ Update tool record after maintenance completion. """
        if not tool:
             logger.error("_update_tool_after_maint_completion: Tool object is None.")
             return
        if not isinstance(completion_dt, datetime):
             logger.error(f"_update_tool_after_maint_completion: Invalid completion_dt type for tool {tool.id}: {type(completion_dt)}. Skipping.")
             return

        completion_date_obj = completion_dt.date() # Get date part for last_maintenance

        # Prepare update data using Python objects
        update_data = {
            "last_maintenance": completion_date_obj, # date object
            "next_maintenance": next_maint_date, # date object or None
            "updated_at": completion_dt # Use the full datetime for updated_at
        }
        # Only change status back if it was explicitly IN_MAINTENANCE or DAMAGED being repaired
        if tool.status in ["MAINTENANCE", "DAMAGED"]:
             update_data["status"] = "IN_STOCK"
             logger.debug(f"_update_tool_after_maint_completion: Setting tool {tool.id} status to IN_STOCK.")

        logger.debug(f"_update_tool_after_maint_completion: Updating tool {tool.id} with data: {update_data}")
        self._update_tool_record_in_repo(tool.id, update_data)


    # --- Cache Invalidation Helpers ---
    def _invalidate_tool_caches(self, tool_id: int, list_too: bool = False, detail_too: bool = True):
        """ Invalidate tool cache entries. """
        if not self.cache_service: return
        keys_invalidated = []
        if detail_too:
            key = f"Tool:detail:{tool_id}"
            self.cache_service.invalidate(key)
            keys_invalidated.append(key)
        if list_too:
            pattern = "Tool:list:*"
            self.cache_service.invalidate_pattern(pattern)
            keys_invalidated.append(pattern)
        if keys_invalidated:
             logger.debug(f"Invalidated cache keys/patterns: {keys_invalidated}")

    def _invalidate_maintenance_caches(self, maintenance_id: Optional[int] = None, tool_id: Optional[int] = None,
                                       list_too: bool = True):
        """ Invalidate maintenance cache entries. """
        if not self.cache_service: return
        keys_invalidated = []
        if maintenance_id:
            key = f"Maintenance:detail:{maintenance_id}"
            self.cache_service.invalidate(key)
            keys_invalidated.append(key)
        if list_too:
            pattern_list = "Maintenance:list:*"
            self.cache_service.invalidate_pattern(pattern_list)
            keys_invalidated.append(pattern_list)
            # Invalidate schedule cache if list is invalidated
            pattern_schedule = "Maintenance:schedule:*"
            self.cache_service.invalidate_pattern(pattern_schedule)
            keys_invalidated.append(pattern_schedule)
        if keys_invalidated:
             logger.debug(f"Invalidated cache keys/patterns: {keys_invalidated}")

        # Invalidate tool detail if maintenance affects it (e.g., next date changed)
        if tool_id: self._invalidate_tool_caches(tool_id, list_too=False, detail_too=True)


    def _invalidate_checkout_caches(self, checkout_id: Optional[int] = None, tool_id: Optional[int] = None,
                                    list_too: bool = True):
        """ Invalidate checkout cache entries. """
        if not self.cache_service: return
        keys_invalidated = []
        if checkout_id:
            key = f"Checkout:detail:{checkout_id}"
            self.cache_service.invalidate(key)
            keys_invalidated.append(key)
        if list_too:
            pattern = "Checkout:list:*"
            self.cache_service.invalidate_pattern(pattern)
            keys_invalidated.append(pattern)
        if keys_invalidated:
             logger.debug(f"Invalidated cache keys/patterns: {keys_invalidated}")

        # Invalidate tool detail if checkout affects it
        if tool_id: self._invalidate_tool_caches(tool_id, list_too=False, detail_too=True)


    # --- Other Service Interactions ---
    def _handle_inventory_adjustment(self, tool: Tool, quantity_change: int, adjustment_type: str, reason: str,
                                     user_id: Optional[int]):
        """ Adjust inventory if service is available. """
        if not tool:
             logger.warning("_handle_inventory_adjustment: Tool object is None.")
             return
        if not self.inventory_service or not hasattr(self.inventory_service, "adjust_inventory"):
            logger.debug("Inventory service not available, skipping adjustment.")
            return

        try:
            logger.info(f"Adjusting inventory for tool {tool.id} by {quantity_change} ({adjustment_type})")
            # Assuming adjust_inventory can handle location string or ID
            self.inventory_service.adjust_inventory(
                item_type="tool", item_id=tool.id,
                quantity_change=quantity_change,
                adjustment_type=adjustment_type, reason=reason,
                location_id=tool.location, # Pass location string/ID
                user_id=user_id
            )
            logger.debug(f"Inventory adjustment successful for tool {tool.id}.")
        except Exception as e:
            # Log error but don't fail the primary operation
            logger.error(f"Failed inventory adjustment for tool {tool.id}: {e}", exc_info=True)


    # --- Event Publishing Helpers (Ensure correct types - strings for events) ---
    def _publish_event(self, event: DomainEvent):
         """ Helper to publish event if bus exists. """
         if not self.event_bus or not hasattr(self.event_bus, 'publish'):
              logger.debug(f"Event bus not available, skipping publish of {type(event).__name__}")
              return
         try:
              logger.debug(f"Publishing event {type(event).__name__} ID {event.event_id}")
              self.event_bus.publish(event)
         except Exception as e:
              logger.error(f"Failed to publish event {type(event).__name__} ID {event.event_id}: {e}", exc_info=True)

    def _publish_tool_created_event(self, tool: Tool, user_id: Optional[int]):
        cat_value = tool.category.value if isinstance(tool.category, ToolCategory) else str(tool.category)
        self._publish_event(ToolCreated(
            tool_id=tool.id, name=tool.name, category=cat_value, user_id=user_id
        ))

    def _publish_tool_status_changed_event(self, tool_id: int, prev: str, new: str, reason: Optional[str], user_id: Optional[int]):
        self._publish_event(ToolStatusChanged(
            tool_id=tool_id, previous_status=prev, new_status=new,
            reason=reason or f"Status updated by user {user_id}", user_id=user_id
        ))

    def _publish_tool_checked_out_event(self, ck: ToolCheckout, user_id: Optional[int]):
        # Ensure dates are ISO strings for event payload
        due_date_str = ck.due_date.isoformat() if isinstance(ck.due_date, date) else str(ck.due_date)
        self._publish_event(ToolCheckedOut(
            checkout_id=ck.id, tool_id=ck.tool_id, checked_out_by=ck.checked_out_by,
            project_id=ck.project_id, due_date=due_date_str, user_id=user_id
        ))

    def _publish_tool_returned_event(self, ck: ToolCheckout, cond: str, issues: bool, user_id: Optional[int]):
        self._publish_event(ToolReturned(
            checkout_id=ck.id, tool_id=ck.tool_id, has_issues=issues,
            condition_after=cond, user_id=user_id
        ))

    def _publish_maintenance_scheduled_event(self, mt: ToolMaintenance, user_id: Optional[int]):
        if mt.status != "SCHEDULED":
             logger.debug(f"Maintenance {mt.id} status is {mt.status}, not publishing Scheduled event.")
             return
        # Ensure date is ISO string
        date_str = mt.date.isoformat() if isinstance(mt.date, date) else str(mt.date)
        self._publish_event(ToolMaintenanceScheduled(
            maintenance_id=mt.id, tool_id=mt.tool_id,
            maintenance_type=mt.maintenance_type, # Use correct attribute name
            date=date_str, user_id=user_id
        ))

    def _publish_maintenance_completed_event(self, mt: ToolMaintenance, next_dt: Optional[date], user_id: Optional[int]):
        if mt.status != "COMPLETED":
             logger.debug(f"Maintenance {mt.id} status is {mt.status}, not publishing Completed event.")
             return
        # Ensure dates are ISO strings or None
        completion_date_str = mt.date.isoformat() if isinstance(mt.date, date) else str(mt.date)
        next_date_str = next_dt.isoformat() if isinstance(next_dt, date) else None
        self._publish_event(ToolMaintenanceCompleted(
            maintenance_id=mt.id, tool_id=mt.tool_id,
            completion_date=completion_date_str,
            performed_by=mt.performed_by,
            next_date=next_date_str,
            user_id=user_id
        ))

# End of ToolService Class