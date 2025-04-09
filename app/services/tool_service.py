# File: app/services/tool_service.py

from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime, timedelta, date
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

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

logger = logging.getLogger(__name__)


# --- Helper Function for Robust Date/Datetime Parsing ---
def _parse_date_or_datetime(value: Any, field_name: str, expect_datetime: bool = False) -> Optional[
    Union[date, datetime]]:
    """ Safely parses input into a date or datetime object. Handles None, existing objects, and ISO strings. """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if expect_datetime else value.date()
    if isinstance(value, date):
        # If a date object is received and datetime is expected, convert to datetime at start of day
        return datetime.combine(value, datetime.min.time()) if expect_datetime else value
    if isinstance(value, str):
        try:
            # Try parsing as full ISO datetime first (more specific)
            dt_str = value.split('.')[0] # Remove potential fractional seconds
            if 'Z' in dt_str: # Handle Z timezone indicator (treat as UTC)
                 dt_str = dt_str.replace('Z', '+00:00')
                 # Note: fromisoformat supports +00:00 directly
                 dt_obj = datetime.fromisoformat(dt_str)
            elif 'T' in dt_str: # Assume it's a datetime string
                 dt_obj = datetime.fromisoformat(dt_str)
            else: # Assume it's just a date string (YYYY-MM-DD)
                 date_obj = date.fromisoformat(dt_str)
                 dt_obj = datetime.combine(date_obj, datetime.min.time()) # Convert to datetime

            return dt_obj if expect_datetime else dt_obj.date()
        except ValueError:
            # Try parsing just the date part if full datetime parse fails
            try:
                date_obj = date.fromisoformat(value.split('T')[0])
                # Convert to datetime if expected, otherwise return date
                return datetime.combine(date_obj, datetime.min.time()) if expect_datetime else date_obj
            except ValueError:
                logger.warning(f"Failed to parse string '{value}' for field '{field_name}'.")
                raise ValidationException(
                    f"Invalid date/datetime format for {field_name}. Expected ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).")
    # If it's not None, date, datetime, or string, it's an invalid type
    logger.error(f"Invalid type provided for {field_name}: {type(value)}")
    raise ValidationException(
        f"Invalid type for {field_name}: {type(value)}. Expected date/datetime object or ISO string.")


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

    def _preprocess_data_dates(self, data: Dict[str, Any], field_map: Dict[str, bool], is_update: bool = False):
        """ Converts date/datetime fields in data dict based on map, adds timestamps. """
        if not data: return

        processed_data = {}
        now_dt = datetime.now()

        # Convert incoming fields (can be string or Python object)
        for field_key in list(data.keys()): # Iterate over keys copy
            # Check if the field (or its camelCase variant if from API) needs date processing
            model_field_name = field_key # Assume data keys match model fields internally
            api_field_name = field_key # Assume data keys match API fields initially

            # Find the corresponding map entry (try both snake and camel if needed, but map uses model names)
            field_info = field_map.get(model_field_name)
            if field_info is None:
                 # Try converting camelCase API key to snake_case model key
                 possible_model_key = ''.join(['_'+c.lower() if c.isupper() else c for c in field_key]).lstrip('_')
                 field_info = field_map.get(possible_model_key)
                 if field_info is not None:
                      model_field_name = possible_model_key # Use the correct model key
                 else:
                      processed_data[api_field_name] = data[field_key] # Keep non-date field as is
                      continue # Skip date processing if not in map

            expect_datetime = field_info
            try:
                parsed_value = _parse_date_or_datetime(data[field_key], model_field_name, expect_datetime)
                processed_data[model_field_name] = parsed_value # Store with model key
            except ValidationException as e:
                logger.error(f"Date preprocessing failed for field '{field_key}' mapped to '{model_field_name}': {e}")
                raise # Re-raise validation error

        # Add/update timestamps using datetime objects
        if not is_update and "created_at" in field_map and field_map["created_at"]:
            processed_data.setdefault("created_at", now_dt) # Only set on create

        if "updated_at" in field_map and field_map["updated_at"]:
            processed_data["updated_at"] = now_dt # Always set on create/update

        # Replace original data with processed data
        data.clear()
        data.update(processed_data)


    # --- Tool CRUD & Listing ---
    def get_tools(self, skip: int = 0, limit: int = 100, search_params: Optional[ToolSearchParams] = None) -> List[Tool]:
        """ Get tools with filtering and pagination. """
        logger.debug(f"Fetching tools: skip={skip}, limit={limit}, params={search_params}")
        filters = {}
        search_term = None
        if search_params:
            search_term = search_params.search
            if search_params.category:
                try:
                    # Convert category string to Enum for repository filter
                    filters["category"] = ToolCategory(search_params.category.upper())
                except ValueError: # Handle invalid enum value
                    raise ValidationException(f"Invalid category: {search_params.category}")
            if search_params.status: filters["status"] = search_params.status
            if search_params.location: filters["location"] = search_params.location
            # TODO: Handle search_params.maintenance_due / checked_out if needed via repo methods

        try:
             if search_term:
                 tools = self.repository.search_tools(search_term, skip=skip, limit=limit, **filters)
             else:
                 tools = self.repository.list(skip=skip, limit=limit, **filters)
             logger.debug(f"Retrieved {len(tools)} tools.")
             return tools
        except Exception as e:
             # Catching the TypeError during read and re-raising helps diagnose
             if isinstance(e, TypeError) and "fromisoformat" in str(e):
                  logger.error(f"SQLAlchemy TypeError during tool retrieval (likely Date/Time processing): {e}", exc_info=True)
                  raise HideSyncException("Database error processing date/time fields.") from e
             logger.error(f"Error retrieving tools from repository: {e}", exc_info=True)
             raise HideSyncException("Failed to retrieve tools.") from e

    def get_tool(self, tool_id: int) -> Tool:
        """ Get a tool by ID using base service method (handles cache). """
        if not isinstance(tool_id, int) or tool_id <= 0:
            raise ValidationException(f"Invalid tool ID: {tool_id}")

        logger.debug(f"Getting tool ID: {tool_id}")
        try:
             tool = self.get_by_id(tool_id) # BaseService method
             if not tool:
                 logger.warning(f"Tool {tool_id} not found.")
                 raise ToolNotFoundException(tool_id=tool_id)
             logger.debug(f"Retrieved tool {tool_id}")
             # The tool object here *should* have Python date/datetime objects
             return tool
        except Exception as e:
             if isinstance(e, TypeError) and "fromisoformat" in str(e):
                  logger.error(f"SQLAlchemy TypeError retrieving tool {tool_id}: {e}", exc_info=True)
                  raise HideSyncException("Database error processing date/time fields.") from e
             logger.error(f"Error retrieving tool {tool_id}: {e}", exc_info=True)
             raise HideSyncException(f"Failed to retrieve tool {tool_id}.") from e


    def create_tool(self, data: Dict[str, Any], user_id: Optional[int] = None) -> Tool:
        """ Create a new tool, converting date strings to objects. """
        if not data: raise ValidationException("No data provided for tool creation")
        logger.info(f"User {user_id} creating tool: {data.get('name')}")

        # --- Validation ---
        if not data.get("name"): raise ValidationException("Tool name required.")
        if not data.get("category"): raise ValidationException("Tool category required.")
        # Ensure category is the Enum type or convert string
        if isinstance(data.get("category"), str):
            try: data["category"] = ToolCategory(data["category"].upper())
            except ValueError: raise ValidationException(f"Invalid category: {data['category']}")
        elif not isinstance(data.get("category"), ToolCategory):
            raise ValidationException("Invalid category type provided.")

        data.setdefault("status", "IN_STOCK") # Ensure status default
        if data.get("purchase_price") is not None and float(data["purchase_price"]) < 0:
             raise ValidationException("Purchase price cannot be negative.")
        if data.get("maintenance_interval") is not None and int(data["maintenance_interval"]) <= 0:
             raise ValidationException("Maintenance interval must be positive.")
        # --- End Validation ---

        # Preprocess Dates (converts strings in `data` to Python objects)
        self._preprocess_data_dates(data, self._tool_date_fields_map, is_update=False)

        # Ensure numeric types are correct after parsing
        if data.get("purchase_price") is not None: data["purchase_price"] = float(data["purchase_price"])
        if data.get("maintenance_interval") is not None: data["maintenance_interval"] = int(data["maintenance_interval"])
        if data.get("supplier_id") is not None: data["supplier_id"] = int(data["supplier_id"])


        with self.transaction():
            try:
                # Pass dict with Python date/datetime objects to repository
                tool = self.repository.create(data)
            except Exception as repo_e:
                logger.error(f"Repository create tool failed: {repo_e}", exc_info=True)
                raise HideSyncException("Database error creating tool.") from repo_e

            logger.info(f"Tool {tool.id} ({tool.name}) created by user {user_id}.")
            self._handle_inventory_adjustment(tool, 1, "INITIAL_STOCK", f"New tool '{tool.name}' added", user_id)
            self._publish_tool_created_event(tool, user_id)
            # Use Python date object if available
            next_maint_date = tool.next_maintenance if isinstance(tool.next_maintenance, date) else None
            if not next_maint_date and tool.maintenance_interval: # If next not set but interval is
                 self._schedule_initial_maintenance_if_needed(tool, tool.maintenance_interval, user_id)

            self._invalidate_tool_caches(tool.id, list_too=True)
            return tool

    def update_tool(self, tool_id: int, data: Dict[str, Any], user_id: Optional[int] = None) -> Tool:
        """ Update an existing tool, converting date strings to objects. """
        if not isinstance(tool_id, int) or tool_id <= 0: raise ValidationException(f"Invalid tool ID: {tool_id}")
        if not data: raise ValidationException("No data provided for tool update")
        logger.info(f"User {user_id} updating tool {tool_id}")

        # --- Validation ---
        if "category" in data and data.get("category"):
            if isinstance(data["category"], str):
                try: data["category"] = ToolCategory(data["category"].upper())
                except ValueError: raise ValidationException(f"Invalid category: {data['category']}")
            elif not isinstance(data["category"], ToolCategory):
                raise ValidationException("Invalid category type provided.")
        if data.get("purchase_price") is not None and float(data["purchase_price"]) < 0:
             raise ValidationException("Purchase price cannot be negative.")
        if data.get("maintenance_interval") is not None and int(data["maintenance_interval"]) <= 0:
             raise ValidationException("Maintenance interval must be positive.")
        # --- End Validation ---

        # Preprocess Dates (converts strings in `data` to Python objects)
        self._preprocess_data_dates(data, self._tool_date_fields_map, is_update=True)

        # Ensure numeric types are correct after parsing
        if data.get("purchase_price") is not None: data["purchase_price"] = float(data["purchase_price"])
        if data.get("maintenance_interval") is not None: data["maintenance_interval"] = int(data["maintenance_interval"])
        if data.get("supplier_id") is not None: data["supplier_id"] = int(data["supplier_id"])


        with self.transaction():
            tool = self.repository.get_by_id(tool_id)
            if not tool: raise ToolNotFoundException(tool_id=tool_id)

            previous_status = tool.status
            new_status = data.get("status", previous_status)
            if new_status != previous_status:
                self._validate_status_transition(previous_status, new_status)

            try:
                # Pass dict with Python date/datetime objects to repository
                updated_tool = self.repository.update(tool_id, data)
            except Exception as repo_e:
                logger.error(f"Repository update failed for tool {tool_id}: {repo_e}", exc_info=True)
                raise HideSyncException(f"Database error updating tool {tool_id}") from repo_e

            logger.info(f"Tool {tool_id} updated by user {user_id}.")
            if new_status != previous_status:
                self._publish_tool_status_changed_event(
                    tool_id, previous_status, new_status, data.get("status_change_reason"), user_id
                )
            self._invalidate_tool_caches(tool_id, list_too=True)
            return updated_tool

    def delete_tool(self, tool_id: int, user_id: Optional[int] = None) -> None:
        """ Delete a tool. """
        if not isinstance(tool_id, int) or tool_id <= 0: raise ValidationException(f"Invalid tool ID: {tool_id}")
        logger.info(f"User {user_id} attempting to delete tool {tool_id}")

        with self.transaction():
            tool = self.repository.get_by_id(tool_id)
            if not tool: raise ToolNotFoundException(tool_id=tool_id)
            if tool.status == "CHECKED_OUT": raise BusinessRuleException(f"Cannot delete checked out tool {tool_id}.")

            try:
                self.repository.delete(tool_id)
            except Exception as repo_e:
                logger.error(f"Repository delete failed for tool {tool_id}: {repo_e}", exc_info=True)
                raise HideSyncException(f"Database error deleting tool {tool_id}") from repo_e

            logger.info(f"Tool {tool_id} deleted by user {user_id}.")
            self._handle_inventory_adjustment(tool, -1, "DISPOSAL", f"Tool '{tool.name}' deleted", user_id)
            self._invalidate_tool_caches(tool_id, list_too=True, detail_too=True)
            # Also invalidate related caches
            self._invalidate_maintenance_caches(tool_id=tool_id, list_too=True)
            self._invalidate_checkout_caches(tool_id=tool_id, list_too=True)


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
        if user_id is not None: # Assuming user_id corresponds to checked_out_by potentially
             # This might need adjustment based on how users are stored/referenced
            filters["checked_out_by"] = str(user_id) # Example: if checked_out_by stores user ID as string

        logger.debug(f"Fetching checkouts: filters={filters}, skip={skip}, limit={limit}")
        try:
             checkouts = self.checkout_repository.list(skip=skip, limit=limit, **filters)
             logger.debug(f"Retrieved {len(checkouts)} checkouts.")
             return checkouts
        except Exception as e:
             if isinstance(e, TypeError) and "fromisoformat" in str(e):
                  logger.error(f"SQLAlchemy TypeError during checkout retrieval: {e}", exc_info=True)
                  raise HideSyncException("Database error processing date/time fields.") from e
             logger.error(f"Error retrieving checkouts from repository: {e}", exc_info=True)
             raise HideSyncException("Failed to retrieve checkouts.") from e


    def checkout_tool(self, data: Dict[str, Any], user_id: Optional[int] = None) -> ToolCheckout:
        """ Check out a tool, converting date strings to objects. """
        if not data: raise ValidationException("No data provided for checkout")

        # Prioritize model (snake_case) keys, fallback to API (camelCase) keys
        tool_id = data.get("tool_id") or data.get("toolId")
        checked_out_by = data.get("checked_out_by") or data.get("checkedOutBy")
        due_date_input = data.get("due_date") or data.get("dueDate") # Keep original input for parsing
        project_id = data.get("project_id") or data.get("projectId")
        notes = data.get("notes")
        condition_before = data.get("condition_before") or data.get("conditionBefore", "Good") # Default

        logger.info(f"User {user_id} checking out tool {tool_id} to '{checked_out_by}'")

        # --- Validation ---
        if not tool_id: raise ValidationException("Tool ID required.")
        if not isinstance(tool_id, int) or tool_id <= 0: raise ValidationException(f"Invalid tool ID: {tool_id}")
        if not checked_out_by: raise ValidationException("'checked_out_by' required.")
        if not due_date_input: raise ValidationException("Due date required.")
        if project_id is not None and (not isinstance(project_id, int) or project_id <= 0):
            raise ValidationException(f"Invalid project ID: {project_id}")
        # --- End Validation ---

        # Parse dates - expect datetime for checkout, date for due date
        try:
            # Checked out date defaults to now if not provided or unparseable
            checked_out_date_obj = _parse_date_or_datetime(
                 data.get("checked_out_date") or data.get("checkedOutDate"),
                 "checked_out_date", expect_datetime=True
            ) or datetime.now()
            due_date_obj = _parse_date_or_datetime(due_date_input, "due_date", expect_datetime=False)
            if not due_date_obj: raise ValidationException("Invalid due date format.") # Should not happen if Pydantic validated
        except ValidationException as e:
            logger.error(f"Date parsing failed during checkout: {e}")
            raise

        # Add Timestamps
        now_dt = datetime.now()
        created_at_obj = now_dt
        updated_at_obj = now_dt

        with self.transaction():
            tool = self.repository.get_by_id(tool_id)
            if not tool: raise ToolNotFoundException(tool_id=tool_id)
            if tool.status != "IN_STOCK":
                raise ToolNotAvailableException(tool_id=tool.id, current_status=tool.status)

            project_name = self._validate_and_get_project_name(project_id)

            # Prepare checkout data with Python objects for repository
            checkout_data_to_create = {
                "tool_id": tool_id,
                "tool_name": tool.name,
                "checked_out_by": checked_out_by,
                "checked_out_date": checked_out_date_obj, # Pass datetime object
                "due_date": due_date_obj, # Pass date object
                "project_id": project_id,
                "project_name": project_name,
                "notes": notes,
                "status": "CHECKED_OUT",
                "condition_before": condition_before,
                "created_at": created_at_obj, # Pass datetime object
                "updated_at": updated_at_obj  # Pass datetime object
            }
            # Remove None values if repo create expects only provided fields
            checkout_data_to_create = {k: v for k, v in checkout_data_to_create.items() if v is not None}

            checkout = self._create_checkout_record_in_repo(checkout_data_to_create)

            # Update tool using Python objects
            tool_update_data = {
                 "status": "CHECKED_OUT",
                 "checked_out_to": checked_out_by,
                 "checked_out_date": checked_out_date_obj, # datetime object
                 "due_date": due_date_obj, # date object
                 "updated_at": updated_at_obj
            }
            self._update_tool_record_in_repo(tool_id, tool_update_data)

            self._publish_tool_checked_out_event(checkout, user_id)
            self._invalidate_checkout_caches(tool_id=tool_id, list_too=True)
            self._invalidate_tool_caches(tool_id=tool_id, list_too=True)
            return checkout

    def return_tool(self, checkout_id: int, data: Dict[str, Any], user_id: Optional[int] = None) -> ToolCheckout:
        """ Return a checked out tool. """
        if not isinstance(checkout_id, int) or checkout_id <= 0: raise ValidationException(f"Invalid checkout ID: {checkout_id}")
        if not data: data = {}
        logger.info(f"User {user_id} returning checkout {checkout_id} with data: {data}")

        now_dt = datetime.now()

        # Parse returned_date if provided, otherwise default to now
        try:
            returned_date_obj = _parse_date_or_datetime(
                 data.get("returned_date") or data.get("returnedDate"),
                 "returned_date", expect_datetime=True
            ) or now_dt
        except ValidationException as e:
            logger.error(f"Date parsing failed during return: {e}")
            raise

        # Get condition and issues, supporting both naming conventions
        condition_after = data.get("condition_after") or data.get("conditionAfter", "Good")
        issue_description = data.get("issue_description") or data.get("issueDescription")
        has_issues = bool(issue_description)

        # Add Timestamps
        updated_at_obj = now_dt


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
                "issue_description": issue_description,
                "updated_at": updated_at_obj # datetime object
            }
            # Remove None values before repo update
            checkout_update = {k: v for k, v in checkout_update.items() if v is not None}

            updated_checkout = self._update_checkout_record_in_repo(checkout_id, checkout_update)

            # Update tool status using Python objects
            tool_status = "MAINTENANCE" if has_issues else "IN_STOCK"
            tool_update_data = {
                "status": tool_status,
                "checked_out_to": None,
                "checked_out_date": None, # Clear dates
                "due_date": None,
                "updated_at": updated_at_obj # datetime object
            }
            self._update_tool_record_in_repo(updated_checkout.tool_id, tool_update_data)

            if has_issues:
                self._schedule_maintenance_after_return(updated_checkout, condition_after, issue_description, user_id)

            self._publish_tool_returned_event(updated_checkout, condition_after, has_issues, user_id)
            self._invalidate_checkout_caches(checkout_id=checkout_id, tool_id=updated_checkout.tool_id, list_too=True)
            self._invalidate_tool_caches(tool_id=updated_checkout.tool_id, list_too=True)
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
                 # Use the specific repository method if it handles date comparison efficiently
                 records = self.maintenance_repository.get_maintenance_by_date_range(
                      start_date=today,
                      end_date=today + timedelta(days=30*12), # Large range to catch all future
                      status="SCHEDULED", # Only scheduled upcoming
                      skip=skip, limit=limit
                 )
                 logger.debug(f"Retrieved {len(records)} upcoming maint records via repo filter.")
             else:
                 records = self.maintenance_repository.list(skip=skip, limit=limit, **filters)
                 logger.debug(f"Retrieved {len(records)} maintenance records.")
             return records
        except Exception as e:
             if isinstance(e, TypeError) and "fromisoformat" in str(e):
                  logger.error(f"SQLAlchemy TypeError during maintenance retrieval: {e}", exc_info=True)
                  raise HideSyncException("Database error processing date/time fields.") from e
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
            if not record_date_obj or not record.tool_id: continue # Skip if no date or tool ID

            tool = tools_dict.get(record.tool_id)
            if not tool: continue # Skip if tool not found

            is_overdue = record_date_obj < today
            days_until = (record_date_obj - today).days if record_date_obj >= today else None

            item = MaintenanceScheduleItem(
                tool_id=tool.id,
                tool_name=tool.name,
                maintenance_type=record.maintenanceType,
                scheduled_date=record_date_obj, # Keep as date object for Pydantic conversion
                category=tool.category,
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

        # Prioritize model keys, fallback to API keys
        tool_id = data.get("tool_id") or data.get("toolId")
        maint_type = data.get("maintenance_type") or data.get("maintenanceType")
        maint_date_input = data.get("date")
        performed_by = data.get("performed_by") or data.get("performedBy")
        cost = data.get("cost", 0.0)
        status = data.get("status", "SCHEDULED")
        details = data.get("details")
        # ... other fields ...

        logger.info(f"User {user_id} creating maintenance for tool {tool_id}: Type='{maint_type}', Date='{maint_date_input}'")

        # --- Validation ---
        if not tool_id: raise ValidationException("Tool ID required.")
        if not isinstance(tool_id, int) or tool_id <= 0: raise ValidationException(f"Invalid tool ID: {tool_id}")
        if not maint_type: raise ValidationException("Maintenance type required.")
        if not maint_date_input: raise ValidationException("Maintenance date required.")
        if status not in ["SCHEDULED", "IN_PROGRESS", "COMPLETED", "WAITING_PARTS"]:
             raise ValidationException(f"Invalid status: {status}")
        if float(cost) < 0: raise ValidationException("Cost cannot be negative.")
        # --- End Validation ---

        # Parse date (expecting date only for 'date' field based on map)
        try:
            maint_date_obj = _parse_date_or_datetime(maint_date_input, "date", expect_datetime=False)
            if not maint_date_obj: raise ValidationException("Invalid maintenance date format.")
            next_date_obj = _parse_date_or_datetime(data.get("next_date") or data.get("nextDate"), "next_date", expect_datetime=False)
        except ValidationException as e:
             logger.error(f"Date parsing failed during maintenance creation: {e}")
             raise

        # Add Timestamps
        now_dt = datetime.now()
        created_at_obj = now_dt
        updated_at_obj = now_dt

        with self.transaction():
            tool = self.repository.get_by_id(tool_id)
            if not tool: raise ToolNotFoundException(tool_id=tool_id)

            # Prepare maintenance data with Python objects for repository
            maint_data_create = {
                "tool_id": tool_id,
                "tool_name": tool.name,
                "maintenance_type": maint_type,
                "date": maint_date_obj, # date object
                "performed_by": performed_by,
                "cost": float(cost),
                "internal_service": data.get("internal_service", data.get("internalService", True)),
                "details": details,
                "parts": data.get("parts"),
                "condition_before": data.get("condition_before", data.get("conditionBefore", tool.status)),
                "condition_after": data.get("condition_after", data.get("conditionAfter")),
                "status": status,
                "next_date": next_date_obj, # date object or None
                "created_at": created_at_obj, # datetime object
                "updated_at": updated_at_obj  # datetime object
            }
            maint_data_create = {k: v for k, v in maint_data_create.items() if v is not None}

            maintenance = self._create_maintenance_record_in_repo(maint_data_create)
            self._update_tool_after_maint_schedule(tool, maintenance, user_id) # Pass objects
            self._publish_maintenance_scheduled_event(maintenance, user_id) # Event needs strings
            self._invalidate_maintenance_caches(tool_id=tool_id)
            return maintenance

    def update_maintenance(self, maintenance_id: int, data: Dict[str, Any],
                           user_id: Optional[int] = None) -> ToolMaintenance:
        """ Update maintenance record. """
        if not isinstance(maintenance_id, int) or maintenance_id <= 0: raise ValidationException(f"Invalid maintenance ID: {maintenance_id}")
        if not data: raise ValidationException("No update data provided.")
        logger.info(f"User {user_id} updating maintenance {maintenance_id}: {data}")

        # --- Validation ---
        if "status" in data and data["status"] not in ["SCHEDULED", "IN_PROGRESS", "COMPLETED", "WAITING_PARTS"]:
            raise ValidationException(f"Invalid status: {data['status']}")
        if data.get("cost") is not None and float(data["cost"]) < 0:
            raise ValidationException("Cost cannot be negative.")
        # --- End Validation ---

        # Preprocess Dates (handles parsing strings if present)
        self._preprocess_data_dates(data, self._maintenance_date_fields_map, is_update=True)

        # Ensure numeric types are correct after parsing
        if data.get("cost") is not None: data["cost"] = float(data["cost"])

        with self.transaction():
            maintenance = self.maintenance_repository.get_by_id(maintenance_id)
            if not maintenance: raise MaintenanceNotFoundException(maintenance_id=maintenance_id)

            allowed_updates_on_completed = {"details", "cost", "parts", "updated_at"} # Only allow these on completed
            if maintenance.status == "COMPLETED" and not set(data.keys()).issubset(allowed_updates_on_completed):
                raise BusinessRuleException(f"Cannot modify completed maintenance {maintenance_id} with fields: {set(data.keys()) - allowed_updates_on_completed}")

            # Pass dict with Python date/datetime objects to repository
            updated_maintenance = self._update_maintenance_record_in_repo(maintenance_id, data)
            self._invalidate_maintenance_caches(maintenance_id=maintenance_id, tool_id=maintenance.tool_id)

            # If status changed to completed, update tool potentially
            if data.get("status") == "COMPLETED":
                 tool = self.repository.get_by_id(updated_maintenance.tool_id)
                 if tool:
                      # Use Python date object for comparison/update
                      completion_date_obj = updated_maintenance.date if isinstance(updated_maintenance.date, date) else date.today()
                      next_maint_date_obj = self._schedule_next_maintenance_if_needed(
                            tool, completion_date_obj, updated_maintenance.condition_after or "Good", user_id
                      )
                      self._update_tool_after_maint_completion(
                           tool, datetime.combine(completion_date_obj, datetime.min.time()), next_maint_date_obj, user_id
                      )
                      self._publish_maintenance_completed_event(updated_maintenance, next_maint_date_obj, user_id)

            return updated_maintenance


    def complete_maintenance(self, maintenance_id: int, data: Dict[str, Any],
                             user_id: Optional[int] = None) -> ToolMaintenance:
        """ Mark maintenance as completed. """
        if not isinstance(maintenance_id, int) or maintenance_id <= 0: raise ValidationException(f"Invalid maintenance ID: {maintenance_id}")
        if not data: data = {}
        logger.info(f"User {user_id} completing maintenance {maintenance_id}: {data}")

        # --- Validation ---
        if data.get("cost") is not None and float(data["cost"]) < 0:
            raise ValidationException("Cost cannot be negative.")
        # --- End Validation ---

        now_dt = datetime.now()
        completion_date_obj = now_dt.date() # Use today's date as completion date

        # Get condition after and notes, supporting both naming conventions
        condition_after = data.get("condition_after") or data.get("conditionAfter", "Good")
        notes = data.get("details") or data.get("notes", '') # Allow empty notes
        cost = data.get("cost")

        # Update timestamp
        updated_at_obj = now_dt

        with self.transaction():
            maintenance = self.maintenance_repository.get_by_id(maintenance_id)
            if not maintenance: raise MaintenanceNotFoundException(maintenance_id=maintenance_id)
            if maintenance.status == "COMPLETED": raise BusinessRuleException(f"Maintenance {maintenance_id} already completed.")

            tool = self.repository.get_by_id(maintenance.tool_id)
            if not tool: raise EntityNotFoundException("Tool", maintenance.tool_id)

            # Prepare maintenance update data with Python objects
            maint_update = {
                "status": "COMPLETED",
                "date": completion_date_obj, # date object
                "performed_by": maintenance.performed_by or f"User {user_id}", # Default performer
                "condition_after": condition_after,
                "details": (maintenance.details or "") + f"\n\nCompleted by User {user_id} on {completion_date_obj.isoformat()}.\nNotes: {notes}",
                "updated_at": updated_at_obj # datetime object
            }
            if cost is not None: maint_update["cost"] = float(cost)
            if "parts" in data: maint_update["parts"] = data["parts"]

            completed_maint = self._update_maintenance_record_in_repo(maintenance_id, maint_update)

            # Schedule next maintenance if needed (uses date objects)
            next_maint_date_obj = self._schedule_next_maintenance_if_needed(tool, completion_date_obj, condition_after, user_id)

            # Update tool (uses date/datetime objects)
            self._update_tool_after_maint_completion(tool, now_dt, next_maint_date_obj, user_id)

            # Publish event (needs strings)
            self._publish_maintenance_completed_event(completed_maint, next_maint_date_obj, user_id)
            self._invalidate_maintenance_caches(maintenance_id=maintenance_id, tool_id=tool.id, list_too=True)
            self._invalidate_tool_caches(tool_id=tool.id, list_too=True)

            return completed_maint

    # --- Private Helper Methods ---

    def _validate_status_transition(self, current_status: str, new_status: str) -> None:
        """ Validate tool status transitions. """
        allowed = {
            "IN_STOCK": ["CHECKED_OUT", "MAINTENANCE", "DAMAGED", "LOST", "RETIRED"],
            "CHECKED_OUT": ["IN_STOCK", "DAMAGED", "LOST", "MAINTENANCE"], # Allow transition to Maintenance directly on return with issues
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
        if not isinstance(project_id, int) or project_id <= 0: return None # Silently ignore invalid ID

        if self.project_service and hasattr(self.project_service, 'get_by_id'):
            try:
                project = self.project_service.get_by_id(project_id)
                return project.name if project else None
            except EntityNotFoundException:
                logger.warning(f"Project ID {project_id} not found during validation.")
                return None
            except Exception as e:
                 logger.error(f"Error fetching project {project_id}: {e}", exc_info=True)
                 return None # Avoid blocking operation due to project service error
        return None # Return None if project service not available


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
            logger.info(f"Checkout record {checkout_id} updated.")
            return updated
        except Exception as e:
            logger.error(f"Repository update checkout failed: {e}", exc_info=True)
            raise HideSyncException("DB error updating checkout record.") from e

    def _update_tool_record_in_repo(self, tool_id: int, data: Dict[str, Any]):
         """ Update tool record using repository. """
         try:
              self.repository.update(tool_id, data)
              logger.info(f"Tool record {tool_id} updated with data: { {k:v for k,v in data.items() if k != 'updated_at'} }")
         except Exception as e:
              logger.error(f"Repository update tool failed for {tool_id}: {e}", exc_info=True)
              # Decide if this should rollback the transaction or just log
              # raise HideSyncException(f"DB error updating tool {tool_id} after related operation.") from e

    def _schedule_maintenance_after_return(self, checkout: ToolCheckout, condition: str, issues: Optional[str],
                                           user_id: Optional[int]):
        """ Schedule maintenance if tool returned with issues. """
        if not checkout or not checkout.tool_id or not issues: return
        logger.info(f"Auto-scheduling repair for tool {checkout.tool_id} due to return issues.")
        try:
            now_dt = datetime.now()
            maint_data = {
                "tool_id": checkout.tool_id,
                "tool_name": checkout.tool_name,
                "maintenance_type": "REPAIR",
                "date": now_dt.date(), # Schedule for today
                "status": "SCHEDULED", # Needs attention
                "details": f"Auto-scheduled after return (Checkout ID: {checkout.id}). Issues: {issues}",
                "condition_before": condition,
            }
            # Call the public create_maintenance method to handle full creation logic
            self.create_maintenance(maint_data, user_id)
        except Exception as e:
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
              logger.info(f"Maintenance record {maintenance_id} updated.")
              return updated
         except Exception as e:
              logger.error(f"Repository update maintenance failed: {e}", exc_info=True)
              raise HideSyncException("DB error updating maintenance record.") from e


    def _update_tool_after_maint_schedule(self, tool: Tool, maintenance: ToolMaintenance, user_id: Optional[int]):
        """ Update tool's next maintenance date after scheduling. """
        if not tool or not maintenance or maintenance.status != "SCHEDULED": return
        if not isinstance(maintenance.date, date): return # Ensure it's a date object

        update_data = {}
        # Update next_maintenance if the new scheduled date is earlier or if none was set
        if tool.next_maintenance is None or maintenance.date < tool.next_maintenance:
            update_data["next_maintenance"] = maintenance.date # date object

        # Optional: Change tool status if appropriate (e.g., DAMAGED -> MAINTENANCE)
        # if tool.status == "DAMAGED" and maintenance.maintenance_type == "REPAIR":
        #     update_data["status"] = "MAINTENANCE"

        if update_data:
            # Add timestamp for update
            update_data["updated_at"] = datetime.now()
            self._update_tool_record_in_repo(tool.id, update_data)


    def _schedule_initial_maintenance_if_needed(self, tool: Tool, maintenance_interval: Optional[int], user_id: Optional[int]) -> None:
        """ Schedule initial maintenance based on interval after creation. """
        if not tool or not maintenance_interval or maintenance_interval <= 0: return
        # Use purchase date if available, otherwise creation date
        base_date = tool.purchase_date if isinstance(tool.purchase_date, date) else (tool.created_at.date() if isinstance(tool.created_at, datetime) else date.today())

        try:
            initial_maint_date = base_date + timedelta(days=maintenance_interval)
            logger.info(f"Scheduling initial maintenance for tool {tool.id} on {initial_maint_date}")

            maint_data = {
                "tool_id": tool.id,
                "tool_name": tool.name,
                "maintenance_type": "ROUTINE",
                "date": initial_maint_date, # date object
                "status": "SCHEDULED",
                "details": "Initial routine maintenance",
            }
            # Call public create method
            self.create_maintenance(maint_data, user_id)

            # Also update the tool's next_maintenance field directly
            tool_update = {"next_maintenance": initial_maint_date, "updated_at": datetime.now()}
            self._update_tool_record_in_repo(tool.id, tool_update)

        except Exception as e:
            logger.error(f"Failed schedule initial maintenance for tool {tool.id}: {e}", exc_info=True)


    def _schedule_next_maintenance_if_needed(self, tool: Tool, completion_date: date, condition_after: str,
                                             user_id: Optional[int]) -> Optional[date]:
        """ Schedule next routine maintenance after completion, returns the next date object if scheduled. """
        if not tool or not tool.maintenance_interval or tool.maintenance_interval <= 0:
             return None # No interval, nothing to schedule

        next_maint_date_obj = completion_date + timedelta(days=tool.maintenance_interval)
        logger.info(f"Scheduling next routine maintenance for tool {tool.id} on {next_maint_date_obj}")

        try:
            maint_data = {
                "tool_id": tool.id,
                "tool_name": tool.name,
                "maintenance_type": "ROUTINE",
                "date": next_maint_date_obj, # date object
                "status": "SCHEDULED",
                "details": f"Routine maintenance scheduled after completion on {completion_date.isoformat()}",
                "condition_before": condition_after, # Condition after previous maint.
            }
            # Call public create method
            self.create_maintenance(maint_data, user_id)
            return next_maint_date_obj # Return the scheduled date
        except Exception as e:
            logger.error(f"Failed schedule next maintenance for tool {tool.id}: {e}", exc_info=True)
            return None # Failed to schedule


    def _update_tool_after_maint_completion(self, tool: Tool, completion_dt: datetime, next_maint_date: Optional[date],
                                            user_id: Optional[int]):
        """ Update tool record after maintenance completion. """
        if not tool: return

        completion_date_obj = completion_dt.date() # Get date part

        # Prepare update data using Python objects
        update_data = {
            "last_maintenance": completion_date_obj, # date object
            "next_maintenance": next_maint_date, # date object or None
            "updated_at": completion_dt # datetime object
        }
        # Only change status back if it was explicitly IN_MAINTENANCE or DAMAGED being repaired
        if tool.status in ["MAINTENANCE", "DAMAGED"]:
             update_data["status"] = "IN_STOCK"

        self._update_tool_record_in_repo(tool.id, update_data)


    def _invalidate_tool_caches(self, tool_id: int, list_too: bool = False, detail_too: bool = True):
        """ Invalidate tool cache entries. """
        if not self.cache_service: return
        if detail_too:
            self.cache_service.invalidate(f"Tool:detail:{tool_id}")
            logger.debug(f"Invalidated cache: Tool:detail:{tool_id}")
        if list_too:
            self.cache_service.invalidate_pattern("Tool:list:*")
            logger.debug("Invalidated cache pattern: Tool:list:*")

    def _invalidate_maintenance_caches(self, maintenance_id: Optional[int] = None, tool_id: Optional[int] = None,
                                       list_too: bool = True):
        """ Invalidate maintenance cache entries. """
        if not self.cache_service: return
        if maintenance_id:
            self.cache_service.invalidate(f"Maintenance:detail:{maintenance_id}")
            logger.debug(f"Invalidated cache: Maintenance:detail:{maintenance_id}")
        if list_too:
            self.cache_service.invalidate_pattern("Maintenance:list:*")
            logger.debug("Invalidated cache pattern: Maintenance:list:*")
            # Invalidate schedule cache if list is invalidated
            self.cache_service.invalidate_pattern("Maintenance:schedule:*")
            logger.debug("Invalidated cache pattern: Maintenance:schedule:*")

        # Invalidate tool detail if maintenance affects it
        if tool_id: self._invalidate_tool_caches(tool_id, list_too=False, detail_too=True)


    def _invalidate_checkout_caches(self, checkout_id: Optional[int] = None, tool_id: Optional[int] = None,
                                    list_too: bool = True):
        """ Invalidate checkout cache entries. """
        if not self.cache_service: return
        if checkout_id:
            self.cache_service.invalidate(f"Checkout:detail:{checkout_id}")
            logger.debug(f"Invalidated cache: Checkout:detail:{checkout_id}")
        if list_too:
            self.cache_service.invalidate_pattern("Checkout:list:*")
            logger.debug("Invalidated cache pattern: Checkout:list:*")

        # Invalidate tool detail if checkout affects it
        if tool_id: self._invalidate_tool_caches(tool_id, list_too=False, detail_too=True)


    def _handle_inventory_adjustment(self, tool: Tool, quantity_change: int, adjustment_type: str, reason: str,
                                     user_id: Optional[int]):
        """ Adjust inventory if service is available. """
        if not tool: return
        if self.inventory_service and hasattr(self.inventory_service, "adjust_inventory"):
            try:
                logger.debug(f"Adjusting inventory for tool {tool.id} by {quantity_change}")
                # Assuming adjust_inventory can handle location string or ID
                self.inventory_service.adjust_inventory(
                    item_type="tool", item_id=tool.id,
                    quantity_change=quantity_change,
                    adjustment_type=adjustment_type, reason=reason,
                    location_id=tool.location, # Pass location string/ID
                    user_id=user_id
                )
            except Exception as e:
                logger.error(f"Failed inventory adjustment for tool {tool.id}: {e}", exc_info=True)


    # --- Event Publishing Helpers (Ensure correct types - strings for events) ---
    def _publish_event(self, event: DomainEvent):
         """ Helper to publish event if bus exists. """
         if self.event_bus and hasattr(self.event_bus, 'publish'):
              try: self.event_bus.publish(event)
              except Exception as e: logger.error(f"Failed to publish event {type(event).__name__}: {e}", exc_info=True)

    def _publish_tool_created_event(self, tool: Tool, user_id: Optional[int]):
        logger.debug(f"Publishing ToolCreated event for tool {tool.id}")
        self._publish_event(ToolCreated(
            tool_id=tool.id, name=tool.name,
            category=tool.category.value if isinstance(tool.category, ToolCategory) else str(tool.category),
            user_id=user_id
        ))

    def _publish_tool_status_changed_event(self, tool_id: int, prev: str, new: str, reason: Optional[str], user_id: Optional[int]):
        logger.debug(f"Publishing ToolStatusChanged event for tool {tool_id}")
        self._publish_event(ToolStatusChanged(
            tool_id=tool_id, previous_status=prev, new_status=new,
            reason=reason or f"User {user_id} update", user_id=user_id
        ))

    def _publish_tool_checked_out_event(self, ck: ToolCheckout, user_id: Optional[int]):
        logger.debug(f"Publishing ToolCheckedOut event for checkout {ck.id}")
        self._publish_event(ToolCheckedOut(
            checkout_id=ck.id, tool_id=ck.tool_id, checked_out_by=ck.checked_out_by,
            project_id=ck.project_id,
            # Ensure dates are ISO strings for event payload
            due_date=ck.due_date.isoformat() if isinstance(ck.due_date, date) else str(ck.due_date),
            user_id=user_id
        ))

    def _publish_tool_returned_event(self, ck: ToolCheckout, cond: str, issues: bool, user_id: Optional[int]):
        logger.debug(f"Publishing ToolReturned event for checkout {ck.id}")
        self._publish_event(ToolReturned(
            checkout_id=ck.id, tool_id=ck.tool_id, has_issues=issues,
            condition_after=cond, user_id=user_id
        ))

    def _publish_maintenance_scheduled_event(self, mt: ToolMaintenance, user_id: Optional[int]):
        if mt.status != "SCHEDULED": return
        logger.debug(f"Publishing ToolMaintenanceScheduled event for maint {mt.id}")
        self._publish_event(ToolMaintenanceScheduled(
            maintenance_id=mt.id, tool_id=mt.tool_id, maintenance_type=mt.maintenanceType,
            date=mt.date.isoformat() if isinstance(mt.date, date) else str(mt.date), # ISO string
            user_id=user_id
        ))

    def _publish_maintenance_completed_event(self, mt: ToolMaintenance, next_dt: Optional[date], user_id: Optional[int]):
        if mt.status != "COMPLETED": return
        logger.debug(f"Publishing ToolMaintenanceCompleted event for maint {mt.id}")
        self._publish_event(ToolMaintenanceCompleted(
            maintenance_id=mt.id, tool_id=mt.tool_id,
            completion_date=mt.date.isoformat() if isinstance(mt.date, date) else str(mt.date), # ISO string
            performed_by=mt.performed_by,
            next_date=next_dt.isoformat() if next_dt else None, # ISO string or None
            user_id=user_id
        ))