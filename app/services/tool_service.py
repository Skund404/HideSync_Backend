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
    ToolNotFoundException  # Use if defined, otherwise EntityNotFoundException
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
    if isinstance(value, datetime):  # Already a datetime object
        return value if expect_datetime else value.date()
    if isinstance(value, date):  # Already a date object
        return datetime.combine(value, datetime.min.time()) if expect_datetime else value
    if isinstance(value, str):
        try:
            # Try parsing as full ISO datetime first (more specific)
            # Handle potential fractional seconds and 'Z' timezone indicator
            dt_str = value.split('.')[0].replace('Z', '+00:00')
            dt_obj = datetime.fromisoformat(dt_str)
            return dt_obj if expect_datetime else dt_obj.date()
        except ValueError:
            # If datetime fails, try parsing just the date part
            try:
                date_obj = date.fromisoformat(value.split('T')[0])
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
    """
    Service for managing tools in the HideSync system.
    Handles CRUD, status, maintenance, checkouts, business logic, validation, events, caching.
    """

    # --- Field Type Mapping ---
    _tool_date_fields_map = {  # Field name -> expects datetime? (True/False)
        "purchase_date": False, "last_maintenance": False, "next_maintenance": False,
        "checked_out_date": True, "due_date": False, "created_at": True, "updated_at": True,
    }
    # Map Pydantic schema field names (camelCase) used in incoming 'data' dict
    _checkout_date_fields_map = {
        "checkedOutDate": True, "dueDate": False, "returnedDate": True,
        "createdAt": True, "updatedAt": True,
    }
    _maintenance_date_fields_map = {
        "date": False,  # Assumes ToolMaintenance model uses Date for 'date' column
        "nextDate": False,  # Assumes ToolMaintenance model uses Date for 'next_date'
        "createdAt": True, "updatedAt": True,
    }

    def __init__(
            self, session: Session, repository: Optional[ToolRepository] = None,
            maintenance_repository: Optional[ToolMaintenanceRepository] = None,
            checkout_repository: Optional[ToolCheckoutRepository] = None,
            event_bus=None, cache_service=None, inventory_service=None,
            project_service=None, supplier_service=None,
    ):
        """ Initialize ToolService with dependencies. """
        self.session = session
        self.repository = repository or ToolRepository(session)
        self.maintenance_repository = maintenance_repository or ToolMaintenanceRepository(session)
        self.checkout_repository = checkout_repository or ToolCheckoutRepository(session)
        self.event_bus = event_bus;
        self.cache_service = cache_service
        self.inventory_service = inventory_service;
        self.project_service = project_service
        self.supplier_service = supplier_service
        super().__init__(session=session, repository=self.repository, event_bus=event_bus, cache_service=cache_service)
        logger.info("ToolService initialized.")

    def _preprocess_data_dates(self, data: Dict[str, Any], field_map: Dict[str, bool]):
        """ Converts date/datetime fields in data dict based on map, adds timestamps. """
        if not data:
            return

        # Convert existing fields
        for field, expect_datetime in field_map.items():
            # Check for both potential schema names (camelCase) and model names (snake_case)
            # This handles data coming directly from API (camel) or internal calls (snake)
            schema_field_name = field  # Assume map uses schema names for incoming data
            model_field_name = field  # Assume map uses model names for internal calls? Adjust if needed.

            if schema_field_name in data:
                try:
                    parsed_value = _parse_date_or_datetime(data[schema_field_name], schema_field_name, expect_datetime)
                    data[schema_field_name] = parsed_value
                except ValidationException as e:
                    logger.error(f"Date preprocessing failed for field '{schema_field_name}': {e}")
                    raise  # Re-raise validation error

        # Add/update timestamps using datetime objects
        now_dt = datetime.now()
        if "createdAt" in field_map and field_map["createdAt"]:
            # Only set 'createdAt' if it's not already present (i.e., during creation)
            data.setdefault("createdAt", now_dt)
        if "updatedAt" in field_map and field_map["updatedAt"]:
            data["updatedAt"] = now_dt  # Always set/overwrite 'updatedAt'

    # --- Tool CRUD & Listing ---
    def get_tools(self, skip: int = 0, limit: int = 100, search_params: Optional[ToolSearchParams] = None) -> List[
        Tool]:
        """ Get tools with filtering and pagination. """
        logger.debug(f"Fetching tools: skip={skip}, limit={limit}, params={search_params}")
        filters = {};
        search_term = None
        if search_params:
            search_term = search_params.search
            if search_params.category:
                try:
                    filters["category"] = ToolCategory[search_params.category.upper()]
                except KeyError:
                    raise ValidationException(f"Invalid category: {search_params.category}")
            if search_params.status: filters["status"] = search_params.status
            if search_params.location: filters["location"] = search_params.location
        if search_term:
            tools = self.repository.search_tools(search_term, skip=skip, limit=limit, **filters)
        else:
            tools = self.repository.list(skip=skip, limit=limit, **filters)
        logger.debug(f"Retrieved {len(tools)} tools.");
        return tools

    def get_tool(self, tool_id: int) -> Tool:
        """ Get a tool by ID using base service method (handles cache). """
        if not tool_id or not isinstance(tool_id, int) or tool_id <= 0:
            raise ValidationException(f"Invalid tool ID: {tool_id}")

        logger.debug(f"Getting tool ID: {tool_id}")
        tool = self.get_by_id(tool_id)
        if not tool:
            logger.warning(f"Tool {tool_id} not found.")
            raise ToolNotFoundException(
                tool_id=tool_id) if 'ToolNotFoundException' in globals() else EntityNotFoundException("Tool", tool_id)
        logger.debug(f"Retrieved tool {tool_id}")
        return tool

    def create_tool(self, data: Dict[str, Any], user_id: Optional[int] = None) -> Tool:
        """ Create a new tool, converting date strings to objects. """
        if not data:
            raise ValidationException("No data provided for tool creation")

        logger.info(f"User {user_id} creating tool: {data.get('name')}")
        # Basic Validation
        if not data.get("name"): raise ValidationException("Tool name required.")
        if not data.get("category"): raise ValidationException("Tool category required.")
        if not isinstance(data.get("category"), ToolCategory): raise ValidationException(
            "Invalid internal category type.")
        data.setdefault("status", "IN_STOCK")
        if data.get("purchase_price") is not None and data["purchase_price"] < 0: raise ValidationException(
            "Price cannot be negative.")
        if data.get("maintenance_interval") is not None and data[
            "maintenance_interval"] <= 0: raise ValidationException("Interval must be positive.")

        # Preprocess Dates (includes created_at/updated_at)
        self._preprocess_data_dates(data, self._tool_date_fields_map)

        with self.transaction():
            try:
                tool = self.repository.create(data)  # Pass dict with date/datetime objects
            except Exception as repo_e:
                logger.error(f"Repo create tool failed: {repo_e}", exc_info=True); raise HideSyncException(
                    f"DB error creating tool.")
            logger.info(f"Tool {tool.id} ({tool.name}) created by user {user_id}.")
            self._handle_inventory_adjustment(tool, 1, "INITIAL_STOCK", f"New tool '{tool.name}' added", user_id)
            self._publish_tool_created_event(tool, user_id)
            self._schedule_initial_maintenance_if_needed(tool, data.get("maintenance_interval"), user_id)
            self._invalidate_tool_caches(tool.id, list_too=True)
            return tool

    def update_tool(self, tool_id: int, data: Dict[str, Any], user_id: Optional[int] = None) -> Tool:
        """ Update an existing tool, converting date strings to objects. """
        if not tool_id or not isinstance(tool_id, int) or tool_id <= 0:
            raise ValidationException(f"Invalid tool ID: {tool_id}")
        if not data:
            raise ValidationException("No data provided for tool update")

        logger.info(
            f"User {user_id} updating tool {tool_id}: { {k: v for k, v in data.items() if k not in ['specifications', 'image']} }")
        # Basic Validation
        if "category" in data and data.get("category") is not None and not isinstance(data.get("category"),
                                                                                      ToolCategory): raise ValidationException(
            "Invalid internal category type.")
        if data.get("purchase_price") is not None and data["purchase_price"] < 0: raise ValidationException(
            "Price cannot be negative.")
        if data.get("maintenance_interval") is not None and data[
            "maintenance_interval"] <= 0: raise ValidationException("Interval must be positive.")

        # Preprocess Dates (includes updated_at)
        self._preprocess_data_dates(data, self._tool_date_fields_map)

        with self.transaction():
            tool = self.repository.get_by_id(tool_id)
            if not tool: raise ToolNotFoundException(
                tool_id=tool_id) if 'ToolNotFoundException' in globals() else EntityNotFoundException("Tool", tool_id)
            previous_status = tool.status;
            new_status = data.get("status", previous_status)
            if new_status != previous_status: self._validate_status_transition(previous_status, new_status)

            try:
                updated_tool = self.repository.update(tool_id, data)  # Pass dict with date/datetime objects
            except Exception as repo_e:
                logger.error(f"Repo update failed for tool {tool_id}: {repo_e}",
                             exc_info=True); raise HideSyncException(f"DB error updating tool {tool_id}")
            logger.info(f"Tool {tool_id} updated by user {user_id}.")
            if new_status != previous_status: self._publish_tool_status_changed_event(tool_id, previous_status,
                                                                                      new_status,
                                                                                      data.get("status_change_reason"),
                                                                                      user_id)
            self._invalidate_tool_caches(tool_id, list_too=True)
            return updated_tool

    def delete_tool(self, tool_id: int, user_id: Optional[int] = None) -> None:
        """ Delete a tool. """
        if not tool_id or not isinstance(tool_id, int) or tool_id <= 0:
            raise ValidationException(f"Invalid tool ID: {tool_id}")

        logger.info(f"User {user_id} attempting to delete tool {tool_id}")
        with self.transaction():
            tool = self.repository.get_by_id(tool_id);
            if not tool: raise ToolNotFoundException(
                tool_id=tool_id) if 'ToolNotFoundException' in globals() else EntityNotFoundException("Tool", tool_id)
            if tool.status == "CHECKED_OUT": raise BusinessRuleException(f"Cannot delete checked out tool {tool_id}.")
            try:
                self.repository.delete(tool_id)
            except Exception as repo_e:
                logger.error(f"Repo delete failed for tool {tool_id}: {repo_e}",
                             exc_info=True); raise HideSyncException(f"DB error deleting tool {tool_id}")
            logger.info(f"Tool {tool_id} deleted by user {user_id}.")
            self._handle_inventory_adjustment(tool, -1, "DISPOSAL", f"Tool '{tool.name}' deleted", user_id)
            self._invalidate_tool_caches(tool_id, list_too=True, detail_too=True)

    # --- Checkout Operations ---
    def get_checkouts(self, status: Optional[str] = None, tool_id: Optional[int] = None,
                      project_id: Optional[int] = None, user_id: Optional[int] = None,
                      skip: int = 0, limit: int = 100) -> List[ToolCheckout]:
        """ Get tool checkouts with filtering. """
        filters = {}
        if status:
            filters["status"] = status
        if tool_id:
            if not isinstance(tool_id, int) or tool_id <= 0:
                raise ValidationException(f"Invalid tool ID: {tool_id}")
            filters["toolId"] = tool_id
        if project_id:
            if not isinstance(project_id, int) or project_id <= 0:
                raise ValidationException(f"Invalid project ID: {project_id}")
            filters["projectId"] = project_id
        if user_id:
            filters["checked_out_by_user_id"] = user_id

        logger.debug(f"Fetching checkouts: filters={filters}, skip={skip}, limit={limit}")
        checkouts = self.checkout_repository.list(skip=skip, limit=limit, **filters)
        logger.debug(f"Retrieved {len(checkouts)} checkouts.")
        return checkouts

    def checkout_tool(self, data: Dict[str, Any], user_id: Optional[int] = None) -> ToolCheckout:
        """ Check out a tool, converting date strings to objects. """
        if not data:
            raise ValidationException("No data provided for checkout")

        # Handle both snake_case and camelCase keys for flexibility
        tool_id = data.get("tool_id") or data.get("toolId")
        checked_out_by = data.get("checked_out_by") or data.get("checkedOutBy")
        due_date = data.get("due_date") or data.get("dueDate")

        logger.info(f"User {user_id} checking out tool {tool_id} to '{checked_out_by}'")

        if not tool_id:
            raise ValidationException("Tool ID required.")
        if not isinstance(tool_id, int) or tool_id <= 0:
            raise ValidationException(f"Invalid tool ID: {tool_id}")
        if not checked_out_by:
            raise ValidationException("'checked_out_by' required.")
        if not due_date:
            raise ValidationException("Due date required.")

        # Preprocess Dates (includes createdAt/updatedAt)
        # Support both naming conventions in input data
        date_fields_to_process = {}
        # Add camelCase fields from original map
        date_fields_to_process.update(self._checkout_date_fields_map)
        # Add snake_case equivalents
        date_fields_to_process.update({
            "checked_out_date": self._checkout_date_fields_map.get("checkedOutDate", True),
            "due_date": self._checkout_date_fields_map.get("dueDate", False),
            "returned_date": self._checkout_date_fields_map.get("returnedDate", True),
            "created_at": self._checkout_date_fields_map.get("createdAt", True),
            "updated_at": self._checkout_date_fields_map.get("updatedAt", True),
        })

        # Preprocess all date fields
        for field, expect_datetime in date_fields_to_process.items():
            if field in data and data[field] is not None:
                data[field] = _parse_date_or_datetime(data[field], field, expect_datetime)

        # Ensure we have timestamps
        now_dt = datetime.now()
        # Handle both naming conventions
        data.setdefault("created_at", now_dt)
        data.setdefault("createdAt", now_dt)
        data["updated_at"] = now_dt
        data["updatedAt"] = now_dt

        with self.transaction():
            tool = self.repository.get_by_id(tool_id)
            if not tool:
                raise ToolNotFoundException(tool_id=tool_id)
            if tool.status != "IN_STOCK":
                raise ToolNotAvailableException(
                    f"Tool {tool_id} unavailable (Status: {tool.status})",
                    tool_id=tool_id,
                    current_status=tool.status
                )

            project_id = data.get("project_id") or data.get("projectId")
            project_name = self._validate_and_get_project_name(project_id)

            # Prepare checkout data with standardized keys for repository
            checked_out_date = data.get("checked_out_date") or data.get("checkedOutDate") or now_dt
            checkout_data_to_create = {
                "toolId": tool_id,
                "toolName": tool.name,
                "checkedOutBy": checked_out_by,
                "checkedOutDate": checked_out_date,
                "dueDate": data.get("due_date") or data.get("dueDate"),
                "projectId": project_id,
                "projectName": project_name,
                "notes": data.get("notes"),
                "status": "CHECKED_OUT",
                "conditionBefore": data.get("condition_before") or data.get("conditionBefore", "Good"),
                "createdAt": data.get("created_at") or data.get("createdAt"),
                "updatedAt": data.get("updated_at") or data.get("updatedAt")
            }
            checkout_data_to_create = {k: v for k, v in checkout_data_to_create.items() if v is not None}

            checkout = self._create_checkout_record_in_repo(checkout_data_to_create)
            self._update_tool_after_checkout(tool_id, checkout, user_id)
            self._publish_tool_checked_out_event(checkout, user_id)
            return checkout

    def return_tool(self, checkout_id: int, data: Dict[str, Any], user_id: Optional[int] = None) -> ToolCheckout:
        """ Return a checked out tool, converting date strings to objects. """
        if not checkout_id or not isinstance(checkout_id, int) or checkout_id <= 0:
            raise ValidationException(f"Invalid checkout ID: {checkout_id}")
        if not data:
            data = {}  # Use empty dict with defaults

        logger.info(f"User {user_id} returning checkout {checkout_id} with data: {data}")

        # Set default return date if not provided
        now_dt = datetime.now()
        data.setdefault("returned_date", now_dt)  # Default as datetime object
        data.setdefault("returnedDate", now_dt)  # Support both naming conventions

        # Preprocess Dates (includes updatedAt and returnedDate)
        # Support both naming conventions in input data
        date_fields_to_process = {}
        # Add camelCase fields from original map
        date_fields_to_process.update(self._checkout_date_fields_map)
        # Add snake_case equivalents
        date_fields_to_process.update({
            "checked_out_date": self._checkout_date_fields_map.get("checkedOutDate", True),
            "due_date": self._checkout_date_fields_map.get("dueDate", False),
            "returned_date": self._checkout_date_fields_map.get("returnedDate", True),
            "created_at": self._checkout_date_fields_map.get("createdAt", True),
            "updated_at": self._checkout_date_fields_map.get("updatedAt", True),
        })

        # Preprocess all date fields
        for field, expect_datetime in date_fields_to_process.items():
            if field in data and data[field] is not None:
                data[field] = _parse_date_or_datetime(data[field], field, expect_datetime)

        # Ensure we have timestamps
        data["updated_at"] = now_dt
        data["updatedAt"] = now_dt

        with self.transaction():
            checkout = self.checkout_repository.get_by_id(checkout_id)
            if not checkout:
                raise CheckoutNotFoundException(checkout_id=checkout_id)
            if checkout.status != "CHECKED_OUT":
                raise BusinessRuleException(f"Checkout {checkout_id} not CHECKED_OUT.")

            # Support both naming conventions for condition and issues
            condition_after = data.get("condition_after") or data.get("conditionAfter", "Good")
            issue_description = data.get("issue_description") or data.get("issueDescription")
            has_issues = bool(issue_description)

            # Prepare update data with standardized keys
            checkout_update = {
                "returnedDate": data.get("returned_date") or data.get("returnedDate"),
                "status": "RETURNED_WITH_ISSUES" if has_issues else "RETURNED",
                "conditionAfter": condition_after,
                "issueDescription": issue_description,
                "updatedAt": data.get("updated_at") or data.get("updatedAt")
            }
            checkout_update = {k: v for k, v in checkout_update.items() if v is not None}

            updated_checkout = self._update_checkout_record_in_repo(checkout_id, checkout_update)
            self._update_tool_after_return(updated_checkout.toolId, has_issues, user_id)
            if has_issues:
                self._schedule_maintenance_after_return(updated_checkout, condition_after, issue_description, user_id)
            self._publish_tool_returned_event(updated_checkout, condition_after, has_issues, user_id)
            return updated_checkout

    # --- Maintenance Operations ---
    def get_maintenance_records(self, status: Optional[str] = None, tool_id: Optional[int] = None,
                                upcoming_only: bool = False, skip: int = 0, limit: int = 100) -> List[ToolMaintenance]:
        """ Get tool maintenance records. """
        filters = {}
        if status:
            filters["status"] = status
        if tool_id:
            if not isinstance(tool_id, int) or tool_id <= 0:
                raise ValidationException(f"Invalid tool ID: {tool_id}")
            filters["toolId"] = tool_id

        logger.debug(f"Fetching maintenance: filters={filters}, upcoming={upcoming_only}, skip={skip}, limit={limit}")

        if upcoming_only:
            today = date.today()
            filters["status"] = "SCHEDULED"
            # Attempt efficient query if repo supports date comparison
            try:
                records = self.maintenance_repository.list(date_gte=today, skip=skip, limit=limit, **filters)
                logger.debug(f"Retrieved {len(records)} upcoming maint records via repo filter.")
            except TypeError:  # If repo doesn't support date_gte
                logger.warning("Repo doesn't support date_gte filter, filtering upcoming maint in memory.")
                all_scheduled = self.maintenance_repository.list(**filters)
                records = [r for r in all_scheduled if r.date and isinstance(r.date, date) and r.date >= today]
                records = records[skip: skip + limit]
                logger.debug(f"Retrieved {len(records)} upcoming maint records via memory filter.")
        else:
            records = self.maintenance_repository.list(skip=skip, limit=limit, **filters)
            logger.debug(f"Retrieved {len(records)} maintenance records.")
        return records

    def get_maintenance_schedule(self, start_date_str: Optional[str] = None,
                                 end_date_str: Optional[str] = None) -> MaintenanceSchedule:
        """ Get tool maintenance schedule. """
        logger.debug(f"Generating maintenance schedule: start={start_date_str}, end={end_date_str}")

        # Parse date strings to date objects
        try:
            start_date = date.fromisoformat(start_date_str) if start_date_str else date.today()
            end_date = date.fromisoformat(end_date_str) if end_date_str else start_date + timedelta(days=30)
        except ValueError as e:
            raise ValidationException(f"Invalid date format: {e}. Use YYYY-MM-DD.")

        if start_date > end_date:
            raise ValidationException("Start date cannot be after end date.")

        # Fetch scheduled records in range (using date objects)
        scheduled_records = self.maintenance_repository.get_maintenance_by_date_range(
            start_date=start_date,
            end_date=end_date,
            status="SCHEDULED"
        )
        logger.debug(f"Fetched {len(scheduled_records)} scheduled maintenance records.")

        schedule_items: List[MaintenanceScheduleItem] = []
        today = date.today()
        overdue_count = 0

        # Get all required tools in one query
        tool_ids = {r.tool_id for r in scheduled_records}
        tools_dict = {t.id: t for t in self.repository.get_by_ids(list(tool_ids))} if tool_ids else {}

        # Process each maintenance record
        for record in scheduled_records:
            # Ensure we have a valid date object
            record_date = record.date if isinstance(record.date, date) else None
            if not record_date:
                continue

            tool = tools_dict.get(record.toolId)
            if not tool:
                continue

            is_overdue = record_date < today
            days_until = (record_date - today).days if record_date >= today else None

            item = MaintenanceScheduleItem(
                tool_id=tool.id,
                tool_name=tool.name,
                maintenance_type=record.maintenanceType,
                scheduled_date=record_date,
                category=tool.category,
                status=record.status,
                location=tool.location,
                is_overdue=is_overdue,
                days_until_due=days_until
            )
            schedule_items.append(item)

            if is_overdue:
                overdue_count += 1

        # Sort by scheduled date and create response
        schedule_items.sort(key=lambda x: x.scheduled_date)
        response = MaintenanceSchedule(
            schedule=schedule_items,
            total_items=len(schedule_items),
            overdue_items=overdue_count,
            upcoming_items=len(schedule_items) - overdue_count,
            start_date=start_date,
            end_date=end_date
        )

        logger.debug("Maintenance schedule generated.")
        return response

    def create_maintenance(self, data: Dict[str, Any], user_id: Optional[int] = None) -> ToolMaintenance:
        """ Create (schedule) a maintenance record, converting date strings. """
        if not data:
            raise ValidationException("No data provided for maintenance creation")

        # Support both naming conventions
        tool_id = data.get("tool_id") or data.get("toolId")
        maint_type = data.get("maintenance_type") or data.get("maintenanceType")
        maint_date = data.get("date")

        logger.info(f"User {user_id} creating maintenance for tool {tool_id}: Type='{maint_type}', Date='{maint_date}'")

        if not tool_id:
            raise ValidationException("Tool ID required.")
        if not isinstance(tool_id, int) or tool_id <= 0:
            raise ValidationException(f"Invalid tool ID: {tool_id}")
        if not maint_type:
            raise ValidationException("Maintenance type required.")
        if not maint_date:
            raise ValidationException("Maintenance date required.")

        # Preprocess Dates (includes createdAt/updatedAt)
        # Support both naming conventions in input data
        date_fields_to_process = {}
        # Add fields from original map
        date_fields_to_process.update(self._maintenance_date_fields_map)
        # Add snake_case equivalents if using camelCase in map
        date_fields_to_process.update({
            "next_date": self._maintenance_date_fields_map.get("nextDate", False),
            "created_at": self._maintenance_date_fields_map.get("createdAt", True),
            "updated_at": self._maintenance_date_fields_map.get("updatedAt", True),
        })

        # Preprocess all date fields
        for field, expect_datetime in date_fields_to_process.items():
            if field in data and data[field] is not None:
                data[field] = _parse_date_or_datetime(data[field], field, expect_datetime)

        # Ensure we have timestamps
        now_dt = datetime.now()
        data.setdefault("created_at", now_dt)
        data.setdefault("createdAt", now_dt)
        data["updated_at"] = now_dt
        data["updatedAt"] = now_dt

        with self.transaction():
            tool = self.repository.get_by_id(tool_id)
            if not tool:
                raise ToolNotFoundException(tool_id=tool_id)

            # Prepare maintenance data with standardized keys
            performed_by = data.get("performed_by") or data.get("performedBy")
            condition_before = data.get("condition_before") or data.get("conditionBefore", tool.status)
            condition_after = data.get("condition_after") or data.get("conditionAfter")
            internal_service = data.get("internal_service") or data.get("internalService", True)

            maint_data_create = {
                "toolId": tool_id,
                "toolName": tool.name,
                "maintenanceType": maint_type,
                "date": data.get("date"),
                "performedBy": performed_by,
                "cost": data.get("cost", 0.0),
                "internalService": internal_service,
                "details": data.get("details"),
                "parts": data.get("parts"),
                "conditionBefore": condition_before,
                "conditionAfter": condition_after,
                "status": data.get("status", "SCHEDULED"),
                "nextDate": data.get("next_date") or data.get("nextDate"),
                "createdAt": data.get("created_at") or data.get("createdAt"),
                "updatedAt": data.get("updated_at") or data.get("updatedAt")
            }

            if maint_data_create["status"] not in ["SCHEDULED", "IN_PROGRESS", "COMPLETED", "WAITING_PARTS"]:
                raise ValidationException(f"Invalid status: {maint_data_create['status']}")

            maint_data_create = {k: v for k, v in maint_data_create.items() if v is not None}

            maintenance = self._create_maintenance_record_in_repo(maint_data_create)
            self._update_tool_after_maint_schedule(tool, maintenance, user_id)
            self._publish_maintenance_scheduled_event(maintenance, user_id)
            self._invalidate_maintenance_caches(tool_id=tool_id)
            return maintenance

    def update_maintenance(self, maintenance_id: int, data: Dict[str, Any],
                           user_id: Optional[int] = None) -> ToolMaintenance:
        """ Update maintenance record, converting date strings. """
        if not maintenance_id or not isinstance(maintenance_id, int) or maintenance_id <= 0:
            raise ValidationException(f"Invalid maintenance ID: {maintenance_id}")
        if not data:
            raise ValidationException("No update data provided.")

        logger.info(f"User {user_id} updating maintenance {maintenance_id}: {data}")

        if "status" in data and data["status"] not in ["SCHEDULED", "IN_PROGRESS", "COMPLETED", "WAITING_PARTS"]:
            raise ValidationException(f"Invalid status: {data['status']}")
        if data.get("cost") is not None and data["cost"] < 0:
            raise ValidationException("Cost cannot be negative.")

        # Preprocess Dates (includes updatedAt)
        # Support both naming conventions in input data
        date_fields_to_process = {}
        # Add fields from original map
        date_fields_to_process.update(self._maintenance_date_fields_map)
        # Add snake_case equivalents if using camelCase in map
        date_fields_to_process.update({
            "next_date": self._maintenance_date_fields_map.get("nextDate", False),
            "created_at": self._maintenance_date_fields_map.get("createdAt", True),
            "updated_at": self._maintenance_date_fields_map.get("updatedAt", True),
        })

        # Preprocess all date fields
        for field, expect_datetime in date_fields_to_process.items():
            if field in data and data[field] is not None:
                data[field] = _parse_date_or_datetime(data[field], field, expect_datetime)

        # Ensure we have timestamp for update
        now_dt = datetime.now()
        data["updated_at"] = now_dt
        data["updatedAt"] = now_dt

        with self.transaction():
            maintenance = self.maintenance_repository.get_by_id(maintenance_id)
            if not maintenance:
                raise MaintenanceNotFoundException(maintenance_id=maintenance_id)

            allowed_updates_on_completed = {"details", "cost", "parts", "updatedAt", "updated_at"}
            if maintenance.status == "COMPLETED" and not set(data.keys()).issubset(allowed_updates_on_completed):
                raise BusinessRuleException(f"Cannot modify completed maintenance {maintenance_id}.")

            # Clean None values before repo update
            update_data_repo = {k: v for k, v in data.items() if v is not None}

            updated_maintenance = self._update_maintenance_record_in_repo(maintenance_id, update_data_repo)
            self._invalidate_maintenance_caches(maintenance_id=maintenance_id, tool_id=maintenance.toolId)
            return updated_maintenance

    def complete_maintenance(self, maintenance_id: int, data: Dict[str, Any],
                             user_id: Optional[int] = None) -> ToolMaintenance:
        """ Mark maintenance as completed, converting date strings. """
        if not maintenance_id or not isinstance(maintenance_id, int) or maintenance_id <= 0:
            raise ValidationException(f"Invalid maintenance ID: {maintenance_id}")
        if not data:
            data = {}  # Use empty dict with defaults

        logger.info(f"User {user_id} completing maintenance {maintenance_id}: {data}")

        if data.get("cost") is not None and data["cost"] < 0:
            raise ValidationException("Cost cannot be negative.")

        # Preprocess Dates
        # Support both naming conventions in input data
        date_fields_to_process = {}
        # Add fields from original map
        date_fields_to_process.update(self._maintenance_date_fields_map)
        # Add snake_case equivalents if using camelCase in map
        date_fields_to_process.update({
            "next_date": self._maintenance_date_fields_map.get("nextDate", False),
            "created_at": self._maintenance_date_fields_map.get("createdAt", True),
            "updated_at": self._maintenance_date_fields_map.get("updatedAt", True),
        })

        # Preprocess all date fields
        for field, expect_datetime in date_fields_to_process.items():
            if field in data and data[field] is not None:
                data[field] = _parse_date_or_datetime(data[field], field, expect_datetime)

        # Ensure we have timestamp for update
        now_dt = datetime.now()
        data["updated_at"] = now_dt
        data["updatedAt"] = now_dt

        with self.transaction():
            maintenance = self.maintenance_repository.get_by_id(maintenance_id)
            if not maintenance:
                raise MaintenanceNotFoundException(maintenance_id=maintenance_id)
            if maintenance.status == "COMPLETED":
                raise BusinessRuleException(f"Maintenance {maintenance_id} already completed.")

            tool = self.repository.get_by_id(maintenance.toolId)
            if not tool:
                raise EntityNotFoundException("Tool", maintenance.toolId)

            # Get condition after and notes, supporting both naming conventions
            condition_after = data.get("condition_after") or data.get("conditionAfter", "Good")
            notes = data.get("details") or data.get("notes", 'N/A')

            # Prepare maintenance update
            completion_date_obj = now_dt

            # Determine date field type based on map
            date_field_value = completion_date_obj.date() if self._maintenance_date_fields_map.get(
                "date") is False else completion_date_obj

            maint_update = {
                "status": "COMPLETED",
                "date": date_field_value,  # Use correct date/datetime type
                "performedBy": maintenance.performedBy or f"User {user_id}",
                "cost": data.get("cost", maintenance.cost),
                "details": (
                                       maintenance.details or "") + f"\n\nCompleted by User {user_id} on {now_dt.strftime('%Y-%m-%d %H:%M')}.\nNotes: {notes}",
                "conditionAfter": condition_after,
                "updatedAt": now_dt,
            }

            # Add parts if provided
            if "parts" in data:
                maint_update["parts"] = data["parts"]

            maint_update = {k: v for k, v in maint_update.items() if v is not None}

            completed_maint = self._update_maintenance_record_in_repo(maintenance_id, maint_update)

            # Schedule next maintenance if needed, using date object
            next_maint_date_obj = self._schedule_next_maintenance_if_needed(tool, completion_date_obj.date(),
                                                                            condition_after, user_id)

            # Update tool with maintenance information
            self._update_tool_after_maint_completion(tool, completion_date_obj, next_maint_date_obj, user_id)

            # Publish event and invalidate caches
            self._publish_maintenance_completed_event(completed_maint, next_maint_date_obj, user_id)
            self._invalidate_maintenance_caches(maintenance_id=maintenance_id, tool_id=tool.id, list_too=True)

            return completed_maint

    # --- Private Helper Methods ---
    def _validate_status_transition(self, current_status: str, new_status: str) -> None:
        """Validate that a status transition is allowed."""
        if not current_status or not new_status:
            logger.warning(f"Empty status in transition: '{current_status}'->{new_status}'")
            raise ValidationException("Status cannot be empty")

        allowed = {
            "IN_STOCK": ["CHECKED_OUT", "MAINTENANCE", "DAMAGED", "LOST", "RETIRED"],
            "CHECKED_OUT": ["IN_STOCK", "DAMAGED", "LOST"],
            "MAINTENANCE": ["IN_STOCK", "DAMAGED", "RETIRED"],
            "DAMAGED": ["MAINTENANCE", "IN_STOCK", "RETIRED"],
            "LOST": ["IN_STOCK"],
            "RETIRED": [],
            "ON_ORDER": ["IN_STOCK", "DAMAGED"]
        }

        if current_status == new_status:
            return

        if new_status not in allowed.get(current_status, []):
            logger.warning(f"Invalid transition: {current_status}->{new_status}")
            raise InvalidStatusTransitionException(
                f"Cannot transition from '{current_status}' to '{new_status}'",
                allowed.get(current_status, [])
            )

        logger.debug(f"Valid transition: {current_status}->{new_status}")

    def _validate_and_get_project_name(self, project_id: Optional[int]) -> Optional[str]:
        """Validate project ID and get project name."""
        if not project_id:
            return None

        if not isinstance(project_id, int) or project_id <= 0:
            logger.warning(f"Invalid project ID: {project_id}")
            return None

        if self.project_service:
            try:
                return self.project_service.get_by_id(project_id).name
            except EntityNotFoundException:
                logger.warning(f"Project ID {project_id} not found.")
                return None
        return None

    def _create_checkout_record_in_repo(self, data: Dict[str, Any]) -> ToolCheckout:
        """Create a checkout record in the repository."""
        try:
            checkout = self.checkout_repository.create(data)
            logger.info(f"Checkout {checkout.id} created.")
            return checkout
        except Exception as e:
            logger.error(f"Repo create checkout fail: {e}", exc_info=True)
            raise HideSyncException("DB error creating checkout.")

    def _update_tool_after_checkout(self, tool_id: int, checkout: ToolCheckout, user_id: Optional[int]):
        """Update tool record after checkout."""
        if not tool_id or not isinstance(tool_id, int) or tool_id <= 0:
            logger.error(f"Invalid tool_id in _update_tool_after_checkout: {tool_id}")
            return

        update_data = {
            "status": "CHECKED_OUT",
            "checked_out_to": checkout.checkedOutBy,
            "checked_out_date": checkout.checkedOutDate,
            "due_date": checkout.dueDate
        }

        self.update_tool(tool_id, update_data, user_id)

    def _update_checkout_record_in_repo(self, checkout_id: int, data: Dict[str, Any]) -> ToolCheckout:
        """Update a checkout record in the repository."""
        try:
            updated = self.checkout_repository.update(checkout_id, data)
            logger.info(f"Checkout {checkout_id} updated.")
            return updated
        except Exception as e:
            logger.error(f"Repo update checkout fail: {e}", exc_info=True)
            raise HideSyncException("DB error updating checkout.")

    def _update_tool_after_return(self, tool_id: int, has_issues: bool, user_id: Optional[int]):
        """Update tool record after return."""
        if tool_id is None or not isinstance(tool_id, int) or tool_id <= 0:
            logger.error(f"Invalid tool_id in _update_tool_after_return: {tool_id}")
            return

        status = "MAINTENANCE" if has_issues else "IN_STOCK"
        update_data = {
            "status": status,
            "checked_out_to": None,
            "checked_out_date": None,
            "due_date": None
        }

        try:
            self.update_tool(tool_id, update_data, user_id)
            logger.info(f"Tool {tool_id} status->{status} after return.")
        except Exception as e:
            logger.error(f"Failed tool update after return {tool_id}: {e}", exc_info=True)

    def _schedule_maintenance_after_return(self, checkout: ToolCheckout, condition: str, issues: Optional[str],
                                           user_id: Optional[int]):
        """Schedule maintenance for a tool after it's returned with issues."""
        if not checkout or not checkout.toolId:
            logger.error("Invalid checkout in _schedule_maintenance_after_return")
            return

        logger.info(f"Scheduling maint for tool {checkout.toolId} from return issues.")

        try:
            now_dt = datetime.now()
            now_date = now_dt.date()

            maintenance_data = {
                "tool_id": checkout.toolId,
                "tool_name": checkout.toolName,
                "maintenance_type": "REPAIR",
                "date": now_date,  # Use date object directly
                "status": "SCHEDULED",
                "details": f"Issues on return (CK{checkout.id}): {issues}",
                "condition_before": condition,
                "created_at": now_dt,
                "updated_at": now_dt
            }

            self.create_maintenance(maintenance_data, user_id)
        except Exception as e:
            logger.error(f"Failed auto-schedule maint for tool {checkout.toolId}: {e}", exc_info=True)

    def _create_maintenance_record_in_repo(self, data: Dict[str, Any]) -> ToolMaintenance:
        """Create a maintenance record in the repository."""
        try:
            maintenance = self.maintenance_repository.create(data)
            logger.info(f"Maint {maintenance.id} created.")
            return maintenance
        except Exception as e:
            logger.error(f"Repo create maint fail: {e}", exc_info=True)
            raise HideSyncException("DB error creating maint.")

    def _update_tool_after_maint_schedule(self, tool: Tool, maintenance: ToolMaintenance, user_id: Optional[int]):
        """Update tool record after maintenance is scheduled."""
        if not tool or not maintenance:
            logger.error("Invalid tool or maintenance in _update_tool_after_maint_schedule")
            return

        if maintenance.status == "SCHEDULED":
            # Only update if status is SCHEDULED
            update_data = {"next_maintenance": maintenance.date}  # Use date object

            # Change tool status if appropriate
            if tool.status == "DAMAGED" and maintenance.maintenanceType == "REPAIR":
                update_data["status"] = "MAINTENANCE"

            # Only update tool if something has changed
            current_next = tool.next_maintenance  # Already a date object
            new_next = maintenance.date  # Already a date object

            if current_next != new_next or update_data.get("status", tool.status) != tool.status:
                self.update_tool(tool.id, update_data, user_id)

    def _update_maintenance_record_in_repo(self, maintenance_id: int, data: Dict[str, Any]) -> ToolMaintenance:
        """Update a maintenance record in the repository."""
        try:
            updated = self.maintenance_repository.update(maintenance_id, data)
            logger.info(f"Maint {maintenance_id} updated.")
            return updated
        except Exception as e:
            logger.error(f"Repo update maint fail: {e}", exc_info=True)
            raise HideSyncException("DB error updating maint.")

    def _schedule_next_maintenance_if_needed(self, tool: Tool, completion_date: date, condition_after: str,
                                             user_id: Optional[int]) -> Optional[date]:
        """Schedule next maintenance for a tool if needed."""
        if not tool:
            logger.error("Invalid tool in _schedule_next_maintenance_if_needed")
            return None

        next_dt = None
        if tool.maintenance_interval and tool.maintenance_interval > 0:
            next_dt = completion_date + timedelta(days=tool.maintenance_interval)
            logger.info(f"Scheduling next maint for tool {tool.id} on {next_dt}")

            try:
                now = datetime.now()
                maintenance_data = {
                    "tool_id": tool.id,
                    "tool_name": tool.name,
                    "maintenance_type": "ROUTINE",
                    "date": next_dt,  # Pass date object directly
                    "status": "SCHEDULED",
                    "details": f"Routine maint after completion on {completion_date}",
                    "condition_before": condition_after,
                    "created_at": now,
                    "updated_at": now
                }
                self.create_maintenance(maintenance_data, user_id)
            except Exception as e:
                logger.error(f"Failed schedule next maint for tool {tool.id}: {e}", exc_info=True)
                next_dt = None

        return next_dt

    def _update_tool_after_maint_completion(self, tool: Tool, completion_dt: datetime, next_maint_date: Optional[date],
                                            user_id: Optional[int]):
        """Update tool record after maintenance is completed."""
        if not tool:
            logger.error("Invalid tool in _update_tool_after_maint_completion")
            return

        # Determine correct field types based on mapping
        last_maint_val = completion_dt if self._tool_date_fields_map.get(
            "last_maintenance") is True else completion_dt.date()

        # Prepare update data
        update_data = {
            "last_maintenance": last_maint_val,
            "status": "IN_STOCK" if tool.status == "MAINTENANCE" else tool.status,
            "next_maintenance": next_maint_date  # Already a date object or None
        }

        # Allow explicit None for next_maintenance to clear the field
        update_data = {k: v for k, v in update_data.items() if v is not None or k == "next_maintenance"}

        # Perform update if we have data
        if update_data:
            try:
                self.update_tool(tool.id, update_data, user_id)
                logger.info(f"Tool {tool.id} updated after maint completion.")
            except Exception as e:
                logger.error(f"Failed tool update post-maint {tool.id}: {e}", exc_info=True)

    def _invalidate_tool_caches(self, tool_id: int, list_too: bool = False, detail_too: bool = True):
        """Invalidate tool-related cache entries."""
        if not self.cache_service:
            return

        if detail_too:
            key = f"Tool:detail:{tool_id}"
            logger.debug(f"Invalidating cache: {key}")
            self.cache_service.invalidate(key)

        if list_too:
            pattern = "Tool:list:*"
            logger.debug(f"Invalidating cache pattern: {pattern}")
            self.cache_service.invalidate_pattern(pattern)

    def _invalidate_maintenance_caches(self, maintenance_id: Optional[int] = None, tool_id: Optional[int] = None,
                                       list_too: bool = True):
        """Invalidate maintenance-related cache entries."""
        if not self.cache_service:
            return

        if maintenance_id:
            key = f"Maintenance:detail:{maintenance_id}"
            logger.debug(f"Invalidating cache: {key}")
            self.cache_service.invalidate(key)

        if list_too:
            pattern = "Maintenance:list:*"
            logger.debug(f"Invalidating cache pattern: {pattern}")
            self.cache_service.invalidate_pattern(pattern)

        if tool_id:
            self._invalidate_tool_caches(tool_id, list_too=False, detail_too=True)

    def _handle_inventory_adjustment(self, tool: Tool, quantity_change: int, adjustment_type: str, reason: str,
                                     user_id: Optional[int]):
        """Handle inventory adjustment for a tool."""
        if not tool:
            logger.error("Invalid tool in _handle_inventory_adjustment")
            return

        if self.inventory_service and hasattr(self.inventory_service, "adjust_inventory"):
            try:
                logger.debug(f"Adjust inventory tool {tool.id} by {quantity_change}")
                self.inventory_service.adjust_inventory(
                    item_type="tool",
                    item_id=tool.id,
                    quantity_change=quantity_change,
                    adjustment_type=adjustment_type,
                    reason=reason,
                    location_id=tool.location,
                    user_id=user_id
                )
            except Exception as e:
                logger.error(f"Failed inventory adjust tool {tool.id}: {e}", exc_info=True)

    def _schedule_initial_maintenance_if_needed(self, tool: Tool, maintenance_interval: Optional[int],
                                                user_id: Optional[int]) -> None:
        """Schedule initial maintenance for a new tool if needed."""
        if not tool or not maintenance_interval or maintenance_interval <= 0:
            return

        try:
            # Calculate initial maintenance date
            now = datetime.now()
            initial_maint_date = now.date() + timedelta(days=maintenance_interval)

            # Prepare maintenance data
            maintenance_data = {
                "tool_id": tool.id,
                "tool_name": tool.name,
                "maintenance_type": "ROUTINE",
                "date": initial_maint_date,  # Use date object
                "status": "SCHEDULED",
                "details": "Initial routine maintenance",
                "condition_before": "Good",
                "created_at": now,
                "updated_at": now
            }

            # Create maintenance record
            self.create_maintenance(maintenance_data, user_id)
            logger.info(f"Initial maintenance scheduled for tool {tool.id} on {initial_maint_date}")
        except Exception as e:
            logger.error(f"Failed to schedule initial maintenance for tool {tool.id}: {e}", exc_info=True)

    # --- Event Publishing Helpers ---
    def _publish_tool_created_event(self, tool: Tool, user_id: Optional[int]):
        """Publish tool created event."""
        if not self.event_bus:
            return

        logger.debug(f"Pub ToolCreated tool {tool.id}")
        try:
            self.event_bus.publish(ToolCreated(
                tool_id=tool.id,
                name=tool.name,
                category=str(tool.category.value),
                user_id=user_id
            ))
        except Exception as e:
            logger.error(f"Fail pub ToolCreated: {e}", exc_info=True)

    def _publish_tool_status_changed_event(self, tool_id: int, prev: str, new: str, reason: Optional[str],
                                           user_id: Optional[int]):
        """Publish tool status changed event."""
        if not self.event_bus:
            return

        logger.debug(f"Pub ToolStatusChanged tool {tool_id}")
        try:
            self.event_bus.publish(ToolStatusChanged(
                tool_id=tool_id,
                previous_status=prev,
                new_status=new,
                reason=reason or f"User {user_id}",
                user_id=user_id
            ))
        except Exception as e:
            logger.error(f"Fail pub ToolStatusChanged: {e}", exc_info=True)

    def _publish_tool_checked_out_event(self, ck: ToolCheckout, user_id: Optional[int]):
        """Publish tool checked out event."""
        if not self.event_bus:
            return

        logger.debug(f"Pub ToolCheckedOut ck {ck.id}")
        try:
            # Use isoformat() which already returns a string
            ck_dt = ck.checkedOutDate.isoformat() if isinstance(ck.checkedOutDate, datetime) else str(ck.checkedOutDate)
            due_dt = ck.dueDate.isoformat() if isinstance(ck.dueDate, date) else str(ck.dueDate)

            self.event_bus.publish(ToolCheckedOut(
                checkout_id=ck.id,
                tool_id=ck.toolId,
                checked_out_by=ck.checkedOutBy,
                project_id=ck.projectId,
                due_date=due_dt,
                user_id=user_id
            ))
        except Exception as e:
            logger.error(f"Fail pub ToolCheckedOut: {e}", exc_info=True)

    def _publish_tool_returned_event(self, ck: ToolCheckout, cond: str, issues: bool, user_id: Optional[int]):
        """Publish tool returned event."""
        if not self.event_bus:
            return

        logger.debug(f"Pub ToolReturned ck {ck.id}")
        try:
            self.event_bus.publish(ToolReturned(
                checkout_id=ck.id,
                tool_id=ck.toolId,
                has_issues=issues,
                condition_after=cond,
                user_id=user_id
            ))
        except Exception as e:
            logger.error(f"Fail pub ToolReturned: {e}", exc_info=True)

    def _publish_maintenance_scheduled_event(self, mt: ToolMaintenance, user_id: Optional[int]):
        """Publish maintenance scheduled event."""
        if not self.event_bus or mt.status != "SCHEDULED":
            return

        logger.debug(f"Pub ToolMaintScheduled mt {mt.id}")
        try:
            # Use isoformat() which already returns a string
            dt_str = mt.date.isoformat() if isinstance(mt.date, date) else str(mt.date)

            self.event_bus.publish(ToolMaintenanceScheduled(
                maintenance_id=mt.id,
                tool_id=mt.toolId,
                maintenance_type=mt.maintenanceType,
                date=dt_str,
                user_id=user_id
            ))
        except Exception as e:
            logger.error(f"Fail pub ToolMaintScheduled: {e}", exc_info=True)

    def _publish_maintenance_completed_event(self, mt: ToolMaintenance, next_dt: Optional[date],
                                             user_id: Optional[int]):
        """Publish maintenance completed event."""
        if not self.event_bus:
            return

        logger.debug(f"Pub ToolMaintCompleted mt {mt.id}")
        try:
            # Use isoformat() which already returns a string
            comp_dt = mt.date.isoformat() if isinstance(mt.date, (datetime, date)) else str(mt.date)
            next_dt_str = next_dt.isoformat() if next_dt else None

            self.event_bus.publish(ToolMaintenanceCompleted(
                maintenance_id=mt.id,
                tool_id=mt.toolId,
                completion_date=comp_dt,
                performed_by=mt.performedBy,
                next_date=next_dt_str,
                user_id=user_id
            ))
        except Exception as e:
            logger.error(f"Fail pub ToolMaintCompleted: {e}", exc_info=True)