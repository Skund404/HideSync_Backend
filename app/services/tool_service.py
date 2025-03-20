# File: services/tool_service.py

from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime, timedelta, date
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.core.events import DomainEvent
from app.core.exceptions import (
    HideSyncException,
    ValidationException,
    EntityNotFoundException,
    BusinessRuleException,
    ConcurrentOperationException,
)
from app.core.validation import validate_input, validate_entity
from app.db.models.enums import ToolCategory
from app.db.models.tool import Tool, ToolMaintenance, ToolCheckout
from app.repositories.tool_repository import (
    ToolRepository,
    ToolMaintenanceRepository,
    ToolCheckoutRepository,
)
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class ToolCreated(DomainEvent):
    """Event emitted when a tool is created."""

    def __init__(
        self, tool_id: int, name: str, category: str, user_id: Optional[int] = None
    ):
        """
        Initialize tool created event.

        Args:
            tool_id: ID of the created tool
            name: Name of the tool
            category: Category of the tool
            user_id: Optional ID of the user who created the tool
        """
        super().__init__()
        self.tool_id = tool_id
        self.name = name
        self.category = category
        self.user_id = user_id


class ToolStatusChanged(DomainEvent):
    """Event emitted when a tool's status changes."""

    def __init__(
        self,
        tool_id: int,
        previous_status: str,
        new_status: str,
        reason: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        """
        Initialize tool status changed event.

        Args:
            tool_id: ID of the tool
            previous_status: Previous status
            new_status: New status
            reason: Optional reason for the status change
            user_id: Optional ID of the user who changed the status
        """
        super().__init__()
        self.tool_id = tool_id
        self.previous_status = previous_status
        self.new_status = new_status
        self.reason = reason
        self.user_id = user_id


class ToolMaintenanceScheduled(DomainEvent):
    """Event emitted when tool maintenance is scheduled."""

    def __init__(
        self,
        maintenance_id: int,
        tool_id: int,
        maintenance_type: str,
        date: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize tool maintenance scheduled event.

        Args:
            maintenance_id: ID of the maintenance record
            tool_id: ID of the tool
            maintenance_type: Type of maintenance
            date: Scheduled date
            user_id: Optional ID of the user who scheduled maintenance
        """
        super().__init__()
        self.maintenance_id = maintenance_id
        self.tool_id = tool_id
        self.maintenance_type = maintenance_type
        self.date = date
        self.user_id = user_id


class ToolMaintenanceCompleted(DomainEvent):
    """Event emitted when tool maintenance is completed."""

    def __init__(
        self,
        maintenance_id: int,
        tool_id: int,
        performed_by: str,
        completion_date: str,
        next_date: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        """
        Initialize tool maintenance completed event.

        Args:
            maintenance_id: ID of the maintenance record
            tool_id: ID of the tool
            performed_by: Who performed the maintenance
            completion_date: Date completed
            next_date: Optional next scheduled maintenance date
            user_id: Optional ID of the user who recorded completion
        """
        super().__init__()
        self.maintenance_id = maintenance_id
        self.tool_id = tool_id
        self.performed_by = performed_by
        self.completion_date = completion_date
        self.next_date = next_date
        self.user_id = user_id


class ToolCheckedOut(DomainEvent):
    """Event emitted when a tool is checked out."""

    def __init__(
        self,
        checkout_id: int,
        tool_id: int,
        checked_out_by: str,
        project_id: Optional[int] = None,
        due_date: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        """
        Initialize tool checked out event.

        Args:
            checkout_id: ID of the checkout record
            tool_id: ID of the tool
            checked_out_by: Who checked out the tool
            project_id: Optional ID of the related project
            due_date: Optional due date for return
            user_id: Optional ID of the user who recorded the checkout
        """
        super().__init__()
        self.checkout_id = checkout_id
        self.tool_id = tool_id
        self.checked_out_by = checked_out_by
        self.project_id = project_id
        self.due_date = due_date
        self.user_id = user_id


class ToolReturned(DomainEvent):
    """Event emitted when a tool is returned."""

    def __init__(
        self,
        checkout_id: int,
        tool_id: int,
        condition_after: str,
        has_issues: bool,
        user_id: Optional[int] = None,
    ):
        """
        Initialize tool returned event.

        Args:
            checkout_id: ID of the checkout record
            tool_id: ID of the tool
            condition_after: Condition after return
            has_issues: Whether there are issues with the tool
            user_id: Optional ID of the user who recorded the return
        """
        super().__init__()
        self.checkout_id = checkout_id
        self.tool_id = tool_id
        self.condition_after = condition_after
        self.has_issues = has_issues
        self.user_id = user_id


# Validation functions
validate_tool = validate_entity(Tool)
validate_tool_maintenance = validate_entity(ToolMaintenance)
validate_tool_checkout = validate_entity(ToolCheckout)


class ToolService(BaseService[Tool]):
    """
    Service for managing tools in the HideSync system.

    Provides functionality for:
    - Tool creation and management
    - Tool status tracking
    - Maintenance scheduling and tracking
    - Tool checkout and return management
    - Tool condition monitoring
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        maintenance_repository=None,
        checkout_repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        inventory_service=None,
        project_service=None,
        supplier_service=None,
    ):
        """
        Initialize ToolService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository for tools (defaults to ToolRepository)
            maintenance_repository: Optional repository for tool maintenance
            checkout_repository: Optional repository for tool checkouts
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            inventory_service: Optional inventory service for inventory operations
            project_service: Optional project service for project validation
            supplier_service: Optional supplier service for supplier information
        """
        self.session = session
        self.repository = repository or ToolRepository(session)
        self.maintenance_repository = (
            maintenance_repository or ToolMaintenanceRepository(session)
        )
        self.checkout_repository = checkout_repository or ToolCheckoutRepository(
            session
        )
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.inventory_service = inventory_service
        self.project_service = project_service
        self.supplier_service = supplier_service

    @validate_input(validate_tool)
    def create_tool(self, data: Dict[str, Any]) -> Tool:
        """
        Create a new tool.

        Args:
            data: Tool data with name, category, and other details

        Returns:
            Created tool entity

        Raises:
            ValidationException: If validation fails
        """
        with self.transaction():
            # Set default values if not provided
            if "status" not in data:
                data["status"] = "IN_STOCK"

            if "purchase_date" not in data and "purchase_price" in data:
                data["purchase_date"] = datetime.now().date().isoformat()

            # Create tool
            tool = self.repository.create(data)

            # Update inventory if inventory service is available
            if self.inventory_service and hasattr(
                self.inventory_service, "adjust_inventory"
            ):
                self.inventory_service.adjust_inventory(
                    item_type="tool",
                    item_id=tool.id,
                    quantity_change=1,
                    adjustment_type="INITIAL_STOCK",
                    reason="New tool added to inventory",
                    location_id=data.get("location"),
                )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ToolCreated(
                        tool_id=tool.id,
                        name=tool.name,
                        category=tool.category,
                        user_id=user_id,
                    )
                )

            # Schedule initial maintenance if interval is specified
            if "maintenance_interval" in data and data["maintenance_interval"]:
                # Calculate next maintenance date
                next_date = datetime.now().date() + timedelta(
                    days=data["maintenance_interval"]
                )

                maintenance_data = {
                    "tool_id": tool.id,
                    "tool_name": tool.name,
                    "maintenance_type": "INITIAL_INSPECTION",
                    "date": next_date.isoformat(),
                    "status": "SCHEDULED",
                }

                self.schedule_maintenance(maintenance_data)

            return tool

    def update_tool(self, tool_id: int, data: Dict[str, Any]) -> Tool:
        """
        Update an existing tool.

        Args:
            tool_id: ID of the tool to update
            data: Updated tool data

        Returns:
            Updated tool entity

        Raises:
            ToolNotFoundException: If tool not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if tool exists
            tool = self.get_by_id(tool_id)
            if not tool:
                from app.core.exceptions import ToolNotFoundException

                raise ToolNotFoundException(tool_id)

            # Store previous status for event
            previous_status = tool.status

            # Update tool
            updated_tool = self.repository.update(tool_id, data)

            # Check if status changed and publish event
            if (
                "status" in data
                and data["status"] != previous_status
                and self.event_bus
            ):
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                reason = data.get("status_change_reason", "Status updated")

                self.event_bus.publish(
                    ToolStatusChanged(
                        tool_id=tool_id,
                        previous_status=previous_status,
                        new_status=data["status"],
                        reason=reason,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Tool:{tool_id}")
                self.cache_service.invalidate(f"Tool:detail:{tool_id}")

            return updated_tool

    def update_status(
        self, tool_id: int, status: str, reason: Optional[str] = None
    ) -> Tool:
        """
        Update the status of a tool.

        Args:
            tool_id: ID of the tool
            status: New status value
            reason: Optional reason for the status change

        Returns:
            Updated tool entity

        Raises:
            ToolNotFoundException: If tool not found
            ValidationException: If validation fails
        """
        # Validate status
        valid_statuses = [
            "IN_STOCK",
            "CHECKED_OUT",
            "MAINTENANCE",
            "DAMAGED",
            "LOST",
            "RETIRED",
            "ON_ORDER",
        ]

        if status not in valid_statuses:
            raise ValidationException(
                f"Invalid tool status: {status}",
                {"status": [f"Must be one of: {', '.join(valid_statuses)}"]},
            )

        with self.transaction():
            # Get tool
            tool = self.get_by_id(tool_id)
            if not tool:
                from app.core.exceptions import ToolNotFoundException

                raise ToolNotFoundException(tool_id)

            # Store previous status for event
            previous_status = tool.status

            # No change if status is the same
            if previous_status == status:
                return tool

            # Validate status transition
            self._validate_status_transition(previous_status, status)

            # Update tool
            updated_tool = self.repository.update(
                tool_id, {"status": status, "status_change_reason": reason}
            )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ToolStatusChanged(
                        tool_id=tool_id,
                        previous_status=previous_status,
                        new_status=status,
                        reason=reason,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Tool:{tool_id}")
                self.cache_service.invalidate(f"Tool:detail:{tool_id}")

            return updated_tool

    def get_tool_with_details(self, tool_id: int) -> Dict[str, Any]:
        """
        Get a tool with comprehensive details.

        Args:
            tool_id: ID of the tool

        Returns:
            Tool with details including maintenance history and checkout status

        Raises:
            ToolNotFoundException: If tool not found
        """
        # Check cache first
        if self.cache_service:
            cache_key = f"Tool:detail:{tool_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get tool
        tool = self.get_by_id(tool_id)
        if not tool:
            from app.core.exceptions import ToolNotFoundException

            raise ToolNotFoundException(tool_id)

        # Convert to dict and add related data
        result = tool.to_dict()

        # Add supplier details if available
        if tool.supplier_id and self.supplier_service:
            supplier = self.supplier_service.get_by_id(tool.supplier_id)
            if supplier:
                result["supplier"] = {
                    "id": supplier.id,
                    "name": supplier.name,
                    "contact_name": supplier.contact_name,
                    "phone": supplier.phone,
                    "email": supplier.email,
                    "website": supplier.website,
                }

        # Add current checkout if checked out
        if tool.status == "CHECKED_OUT":
            current_checkout = self._get_current_checkout(tool_id)
            if current_checkout:
                result["current_checkout"] = {
                    "id": current_checkout.id,
                    "checked_out_by": current_checkout.checked_out_by,
                    "checked_out_date": (
                        current_checkout.checked_out_date.isoformat()
                        if current_checkout.checked_out_date
                        else None
                    ),
                    "due_date": (
                        current_checkout.due_date.isoformat()
                        if current_checkout.due_date
                        else None
                    ),
                    "project_id": current_checkout.project_id,
                    "project_name": current_checkout.project_name,
                    "overdue": self._is_checkout_overdue(current_checkout),
                }

                # Add project details if available
                if current_checkout.project_id and self.project_service:
                    project = self.project_service.get_by_id(
                        current_checkout.project_id
                    )
                    if project:
                        result["current_checkout"]["project"] = {
                            "id": project.id,
                            "name": project.name,
                            "status": project.status,
                            "type": project.type,
                            "due_date": (
                                project.due_date.isoformat()
                                if project.due_date
                                else None
                            ),
                        }

        # Add maintenance history
        result["maintenance_history"] = self._get_maintenance_history(tool_id)

        # Add checkout history
        result["checkout_history"] = self._get_checkout_history(tool_id)

        # Add next scheduled maintenance
        next_maintenance = self._get_next_scheduled_maintenance(tool_id)
        if next_maintenance:
            result["next_maintenance"] = {
                "id": next_maintenance.id,
                "maintenance_type": next_maintenance.maintenance_type,
                "date": (
                    next_maintenance.date.isoformat() if next_maintenance.date else None
                ),
                "days_away": (
                    (next_maintenance.date - datetime.now().date()).days
                    if next_maintenance.date
                    else None
                ),
            }

        # Add usage statistics
        result["usage_statistics"] = self._calculate_usage_statistics(tool_id)

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, result, ttl=3600)  # 1 hour TTL

        return result

    def get_tools_by_category(self, category: Union[ToolCategory, str]) -> List[Tool]:
        """
        Get all tools in a specific category.

        Args:
            category: Category to filter by

        Returns:
            List of tools in the category
        """
        # Convert string category to enum value if needed
        if isinstance(category, ToolCategory):
            category = category.value

        return self.repository.list(category=category)

    def get_tools_by_status(self, status: str) -> List[Tool]:
        """
        Get all tools with a specific status.

        Args:
            status: Status to filter by

        Returns:
            List of tools with the status
        """
        return self.repository.list(status=status)

    def get_tools_due_for_maintenance(
        self, days_window: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get tools that are due for maintenance within a time window.

        Args:
            days_window: Number of days to look ahead

        Returns:
            List of tools with upcoming maintenance
        """
        # Calculate date range
        today = datetime.now().date()
        end_date = today + timedelta(days=days_window)

        # Get scheduled maintenance in date range
        maintenance_records = self.maintenance_repository.get_upcoming_maintenance(
            start_date=today, end_date=end_date
        )

        # Get tool details for each maintenance record
        result = []
        for maintenance in maintenance_records:
            tool = self.get_by_id(maintenance.tool_id)
            if not tool:
                continue

            # Add to result
            result.append(
                {
                    "maintenance_id": maintenance.id,
                    "tool_id": tool.id,
                    "tool_name": tool.name,
                    "category": tool.category,
                    "maintenance_type": maintenance.maintenance_type,
                    "scheduled_date": (
                        maintenance.date.isoformat() if maintenance.date else None
                    ),
                    "days_away": (
                        (maintenance.date - today).days if maintenance.date else None
                    ),
                    "status": maintenance.status,
                    "tool_status": tool.status,
                }
            )

        # Sort by scheduled date (ascending)
        return sorted(result, key=lambda x: x["scheduled_date"])

    def get_overdue_tools(self) -> List[Dict[str, Any]]:
        """
        Get tools that are overdue for return.

        Returns:
            List of overdue tool checkouts
        """
        # Get active checkouts
        checkouts = self.checkout_repository.list(status="CHECKED_OUT")

        # Filter for overdue
        today = datetime.now().date()
        overdue_checkouts = [c for c in checkouts if c.due_date and c.due_date < today]

        # Get tool details for each checkout
        result = []
        for checkout in overdue_checkouts:
            tool = self.get_by_id(checkout.tool_id)
            if not tool:
                continue

            # Add to result
            result.append(
                {
                    "checkout_id": checkout.id,
                    "tool_id": tool.id,
                    "tool_name": tool.name,
                    "category": tool.category,
                    "checked_out_by": checkout.checked_out_by,
                    "checked_out_date": (
                        checkout.checked_out_date.isoformat()
                        if checkout.checked_out_date
                        else None
                    ),
                    "due_date": (
                        checkout.due_date.isoformat() if checkout.due_date else None
                    ),
                    "days_overdue": (
                        (today - checkout.due_date).days if checkout.due_date else 0
                    ),
                    "project_id": checkout.project_id,
                    "project_name": checkout.project_name,
                }
            )

        # Sort by days overdue (descending)
        return sorted(result, key=lambda x: x["days_overdue"], reverse=True)

    @validate_input(validate_tool_maintenance)
    def schedule_maintenance(self, data: Dict[str, Any]) -> ToolMaintenance:
        """
        Schedule maintenance for a tool.

        Args:
            data: Maintenance data with tool_id, type, and date

        Returns:
            Created maintenance record

        Raises:
            ValidationException: If validation fails
            ToolNotFoundException: If tool not found
        """
        with self.transaction():
            # Check if tool exists
            tool_id = data.get("tool_id")
            tool = self.get_by_id(tool_id)
            if not tool:
                from app.core.exceptions import ToolNotFoundException

                raise ToolNotFoundException(tool_id)

            # Set default values if not provided
            if "status" not in data:
                data["status"] = "SCHEDULED"

            if "tool_name" not in data:
                data["tool_name"] = tool.name

            # Convert date string to date object if needed
            if "date" in data and isinstance(data["date"], str):
                try:
                    data["date"] = datetime.fromisoformat(
                        data["date"].replace("Z", "+00:00")
                    ).date()
                except ValueError:
                    try:
                        data["date"] = datetime.strptime(
                            data["date"], "%Y-%m-%d"
                        ).date()
                    except ValueError:
                        raise ValidationException(
                            "Invalid date format. Expected ISO format (YYYY-MM-DD).",
                            {"date": ["Invalid date format"]},
                        )

            # Create maintenance record
            maintenance = self.maintenance_repository.create(data)

            # Update tool's next maintenance date
            self.repository.update(
                tool_id,
                {
                    "next_maintenance": (
                        data["date"].isoformat()
                        if isinstance(data["date"], date)
                        else data["date"]
                    )
                },
            )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ToolMaintenanceScheduled(
                        maintenance_id=maintenance.id,
                        tool_id=tool_id,
                        maintenance_type=maintenance.maintenance_type,
                        date=maintenance.date.isoformat() if maintenance.date else None,
                        user_id=user_id,
                    )
                )

            # Invalidate cache
            if self.cache_service:
                self.cache_service.invalidate(f"Tool:detail:{tool_id}")

            return maintenance

    def complete_maintenance(
        self, maintenance_id: int, data: Dict[str, Any]
    ) -> ToolMaintenance:
        """
        Complete a scheduled maintenance.

        Args:
            maintenance_id: ID of the maintenance record
            data: Completion data with performed_by, date, and results

        Returns:
            Updated maintenance record

        Raises:
            MaintenanceNotFoundException: If maintenance record not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if maintenance record exists
            maintenance = self.maintenance_repository.get_by_id(maintenance_id)
            if not maintenance:
                from app.core.exceptions import MaintenanceNotFoundException

                raise MaintenanceNotFoundException(maintenance_id)

            # Check if already completed
            if maintenance.status == "COMPLETED":
                raise ValidationException(
                    "Maintenance has already been completed",
                    {"maintenance_id": ["Already completed"]},
                )

            # Set default values if not provided
            if "completion_date" not in data:
                data["completion_date"] = datetime.now().date().isoformat()

            # Convert to date object if needed
            if isinstance(data.get("completion_date"), str):
                try:
                    data["completion_date"] = datetime.fromisoformat(
                        data["completion_date"].replace("Z", "+00:00")
                    ).date()
                except ValueError:
                    try:
                        data["completion_date"] = datetime.strptime(
                            data["completion_date"], "%Y-%m-%d"
                        ).date()
                    except ValueError:
                        raise ValidationException(
                            "Invalid date format. Expected ISO format (YYYY-MM-DD).",
                            {"completion_date": ["Invalid date format"]},
                        )

            # Combine with status update
            completion_data = {**data, "status": "COMPLETED"}

            # Update maintenance record
            updated_maintenance = self.maintenance_repository.update(
                maintenance_id, completion_data
            )

            # Calculate next maintenance date if interval exists
            tool = self.get_by_id(maintenance.tool_id)
            next_date = None

            if tool and tool.maintenance_interval:
                # Calculate from completion date
                if isinstance(data.get("completion_date"), date):
                    next_date = data["completion_date"] + timedelta(
                        days=tool.maintenance_interval
                    )
                else:
                    next_date = datetime.now().date() + timedelta(
                        days=tool.maintenance_interval
                    )

                # Schedule next maintenance
                next_maintenance_data = {
                    "tool_id": tool.id,
                    "tool_name": tool.name,
                    "maintenance_type": "ROUTINE",
                    "date": next_date.isoformat(),
                    "status": "SCHEDULED",
                }

                self.schedule_maintenance(next_maintenance_data)

            # Update tool status and last maintenance date
            tool_update_data = {
                "last_maintenance": (
                    data.get("completion_date").isoformat()
                    if isinstance(data.get("completion_date"), date)
                    else data.get("completion_date")
                ),
                "status": "IN_STOCK" if tool.status == "MAINTENANCE" else tool.status,
            }

            if next_date:
                tool_update_data["next_maintenance"] = next_date.isoformat()

            self.repository.update(maintenance.tool_id, tool_update_data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ToolMaintenanceCompleted(
                        maintenance_id=maintenance_id,
                        tool_id=maintenance.tool_id,
                        performed_by=data.get("performed_by", "Unknown"),
                        completion_date=(
                            data.get("completion_date").isoformat()
                            if isinstance(data.get("completion_date"), date)
                            else data.get("completion_date")
                        ),
                        next_date=next_date.isoformat() if next_date else None,
                        user_id=user_id,
                    )
                )

            # Invalidate cache
            if self.cache_service:
                self.cache_service.invalidate(f"Tool:detail:{maintenance.tool_id}")

            return updated_maintenance

    @validate_input(validate_tool_checkout)
    def checkout_tool(self, data: Dict[str, Any]) -> ToolCheckout:
        """
        Check out a tool.

        Args:
            data: Checkout data with tool_id, checked_out_by, and optional project_id

        Returns:
            Created checkout record

        Raises:
            ValidationException: If validation fails
            ToolNotFoundException: If tool not found
            ToolNotAvailableException: If tool is not available for checkout
        """
        with self.transaction():
            # Check if tool exists
            tool_id = data.get("tool_id")
            tool = self.get_by_id(tool_id)
            if not tool:
                from app.core.exceptions import ToolNotFoundException

                raise ToolNotFoundException(tool_id)

            # Check if tool is available
            if tool.status != "IN_STOCK":
                from app.core.exceptions import ToolNotAvailableException

                raise ToolNotAvailableException(
                    f"Tool {tool_id} is not available for checkout (current status: {tool.status})",
                    current_status=tool.status,
                )

            # Set default values if not provided
            if "checked_out_date" not in data:
                data["checked_out_date"] = datetime.now().isoformat()

            if "status" not in data:
                data["status"] = "CHECKED_OUT"

            if "tool_name" not in data:
                data["tool_name"] = tool.name

            # Set condition_before if not provided
            if "condition_before" not in data:
                data["condition_before"] = "Good"

            # Check if project exists
            if "project_id" in data and data["project_id"] and self.project_service:
                project = self.project_service.get_by_id(data["project_id"])
                if project:
                    data["project_name"] = project.name

            # Create checkout record
            checkout = self.checkout_repository.create(data)

            # Update tool status
            self.update_status(
                tool_id=tool_id,
                status="CHECKED_OUT",
                reason=f"Checked out by {data.get('checked_out_by')}",
            )

            # Update tool checkout info
            self.repository.update(
                tool_id,
                {
                    "checked_out_to": data.get("checked_out_by"),
                    "checked_out_date": data.get("checked_out_date"),
                    "due_date": data.get("due_date"),
                },
            )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ToolCheckedOut(
                        checkout_id=checkout.id,
                        tool_id=tool_id,
                        checked_out_by=data.get("checked_out_by"),
                        project_id=data.get("project_id"),
                        due_date=data.get("due_date"),
                        user_id=user_id,
                    )
                )

            # Invalidate cache
            if self.cache_service:
                self.cache_service.invalidate(f"Tool:detail:{tool_id}")

            return checkout

    def return_tool(self, checkout_id: int, data: Dict[str, Any]) -> ToolCheckout:
        """
        Return a checked out tool.

        Args:
            checkout_id: ID of the checkout record
            data: Return data with condition_after and optional issues

        Returns:
            Updated checkout record

        Raises:
            CheckoutNotFoundException: If checkout record not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if checkout record exists
            checkout = self.checkout_repository.get_by_id(checkout_id)
            if not checkout:
                from app.core.exceptions import CheckoutNotFoundException

                raise CheckoutNotFoundException(checkout_id)

            # Check if already returned
            if checkout.status != "CHECKED_OUT":
                raise ValidationException(
                    f"Tool is not checked out (current status: {checkout.status})",
                    {"checkout_id": ["Not checked out"]},
                )

            # Set default values if not provided
            if "returned_date" not in data:
                data["returned_date"] = datetime.now().isoformat()

            if "status" not in data:
                # Determine status based on issues
                has_issues = (
                    data.get("issue_description") is not None
                    and data.get("issue_description") != ""
                )
                data["status"] = "RETURNED_WITH_ISSUES" if has_issues else "RETURNED"

            # Update checkout record
            updated_checkout = self.checkout_repository.update(checkout_id, data)

            # Determine tool status based on condition
            has_issues = (
                data.get("issue_description") is not None
                and data.get("issue_description") != ""
            )
            new_tool_status = "DAMAGED" if has_issues else "IN_STOCK"

            # Update tool status
            self.update_status(
                tool_id=checkout.tool_id,
                status=new_tool_status,
                reason=f"Returned by {checkout.checked_out_by}"
                + (
                    f" with issues: {data.get('issue_description')}"
                    if has_issues
                    else ""
                ),
            )

            # Clear checkout info from tool
            self.repository.update(
                checkout.tool_id,
                {"checked_out_to": None, "checked_out_date": None, "due_date": None},
            )

            # Schedule maintenance if issues reported
            if has_issues:
                maintenance_data = {
                    "tool_id": checkout.tool_id,
                    "tool_name": checkout.tool_name,
                    "maintenance_type": "REPAIR",
                    "date": datetime.now().date().isoformat(),
                    "status": "SCHEDULED",
                    "details": data.get("issue_description"),
                }

                self.schedule_maintenance(maintenance_data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ToolReturned(
                        checkout_id=checkout_id,
                        tool_id=checkout.tool_id,
                        condition_after=data.get("condition_after", "Unknown"),
                        has_issues=has_issues,
                        user_id=user_id,
                    )
                )

            # Invalidate cache
            if self.cache_service:
                self.cache_service.invalidate(f"Tool:detail:{checkout.tool_id}")

            return updated_checkout

    def get_tool_utilization(
        self, tool_id: int, date_range: Optional[Tuple[datetime, datetime]] = None
    ) -> Dict[str, Any]:
        """
        Get utilization statistics for a tool.

        Args:
            tool_id: ID of the tool
            date_range: Optional tuple of (start_date, end_date)

        Returns:
            Dictionary with utilization statistics

        Raises:
            ToolNotFoundException: If tool not found
        """
        # Check if tool exists
        tool = self.get_by_id(tool_id)
        if not tool:
            from app.core.exceptions import ToolNotFoundException

            raise ToolNotFoundException(tool_id)

        # Default date range to last 90 days if not provided
        if not date_range:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)
        else:
            start_date, end_date = date_range

        # Get checkouts in date range
        checkouts = self.checkout_repository.get_by_date_range(
            tool_id=tool_id, start_date=start_date, end_date=end_date
        )

        # Calculate total checked out days
        total_days = (end_date - start_date).days
        checked_out_days = 0

        for checkout in checkouts:
            if checkout.status not in [
                "CHECKED_OUT",
                "RETURNED",
                "RETURNED_WITH_ISSUES",
            ]:
                continue

            # Determine start date (max of checkout date and range start)
            checkout_start = max(
                (
                    checkout.checked_out_date.date()
                    if checkout.checked_out_date
                    else start_date.date()
                ),
                start_date.date(),
            )

            # Determine end date (min of return date and range end)
            if checkout.status == "CHECKED_OUT":
                # Still checked out
                checkout_end = end_date.date()
            else:
                # Returned
                checkout_end = min(
                    (
                        checkout.returned_date.date()
                        if checkout.returned_date
                        else end_date.date()
                    ),
                    end_date.date(),
                )

            # Add days
            checked_out_days += max(0, (checkout_end - checkout_start).days)

        # Calculate maintenance days
        maintenance_records = self.maintenance_repository.get_by_date_range(
            tool_id=tool_id, start_date=start_date, end_date=end_date
        )

        maintenance_days = 0
        for maintenance in maintenance_records:
            if maintenance.status == "COMPLETED":
                # Assume 1 day per maintenance for now
                maintenance_days += 1

        # Calculate utilization percentages
        utilization_percentage = (
            round((checked_out_days / total_days * 100), 1) if total_days > 0 else 0
        )
        availability_percentage = (
            round(
                ((total_days - checked_out_days - maintenance_days) / total_days * 100),
                1,
            )
            if total_days > 0
            else 0
        )
        maintenance_percentage = (
            round((maintenance_days / total_days * 100), 1) if total_days > 0 else 0
        )

        return {
            "tool_id": tool_id,
            "tool_name": tool.name,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": total_days,
            },
            "utilization": {
                "checked_out_days": checked_out_days,
                "maintenance_days": maintenance_days,
                "available_days": total_days - checked_out_days - maintenance_days,
                "utilization_percentage": utilization_percentage,
                "availability_percentage": availability_percentage,
                "maintenance_percentage": maintenance_percentage,
            },
            "checkout_count": len(checkouts),
            "maintenance_count": len(maintenance_records),
            "average_checkout_duration": (
                round(checked_out_days / len(checkouts), 1) if len(checkouts) > 0 else 0
            ),
        }

    def get_tools_needing_replacement(self) -> List[Dict[str, Any]]:
        """
        Get tools that may need replacement based on age, condition, or repair frequency.

        Returns:
            List of tools that may need replacement with reasons
        """
        # Get all tools
        tools = self.repository.list()

        # List to store tools needing replacement
        replacement_candidates = []

        for tool in tools:
            reasons = []

            # Check age if purchase date available
            if tool.purchase_date:
                age_years = (datetime.now().date() - tool.purchase_date).days / 365
                if age_years > 5:  # Arbitrary threshold
                    reasons.append(f"Tool is {round(age_years, 1)} years old")

            # Check maintenance frequency
            maintenance_records = self.maintenance_repository.list(tool_id=tool.id)
            repair_count = len(
                [
                    m
                    for m in maintenance_records
                    if m.maintenance_type == "REPAIR"
                    and m.date
                    and m.date > datetime.now().date() - timedelta(days=365)
                ]
            )

            if repair_count >= 3:  # Arbitrary threshold
                reasons.append(f"Required {repair_count} repairs in the past year")

            # Check status
            if tool.status == "DAMAGED":
                reasons.append("Currently damaged")

            # If any reasons, add to candidates
            if reasons:
                replacement_candidates.append(
                    {
                        "tool_id": tool.id,
                        "name": tool.name,
                        "category": tool.category,
                        "status": tool.status,
                        "purchase_date": (
                            tool.purchase_date.isoformat()
                            if tool.purchase_date
                            else None
                        ),
                        "age_years": (
                            round(
                                (datetime.now().date() - tool.purchase_date).days / 365,
                                1,
                            )
                            if tool.purchase_date
                            else None
                        ),
                        "repair_count_past_year": repair_count,
                        "replacement_reasons": reasons,
                    }
                )

        # Sort by number of reasons (descending)
        return sorted(
            replacement_candidates,
            key=lambda x: len(x["replacement_reasons"]),
            reverse=True,
        )

    def generate_tool_report(
        self, report_type: str, filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a tool report based on specified type and filters.

        Args:
            report_type: Type of report (inventory, maintenance, utilization)
            filters: Optional filters to apply to the report

        Returns:
            Dictionary with report results

        Raises:
            ValidationException: If invalid report type
        """
        # Validate report type
        valid_report_types = ["inventory", "maintenance", "utilization", "checkout"]
        if report_type.lower() not in valid_report_types:
            raise ValidationException(
                f"Invalid report type: {report_type}",
                {"report_type": [f"Must be one of: {', '.join(valid_report_types)}"]},
            )

        # Initialize filters
        if not filters:
            filters = {}

        # Generate report based on type
        if report_type.lower() == "inventory":
            return self._generate_inventory_report(filters)
        elif report_type.lower() == "maintenance":
            return self._generate_maintenance_report(filters)
        elif report_type.lower() == "utilization":
            return self._generate_utilization_report(filters)
        elif report_type.lower() == "checkout":
            return self._generate_checkout_report(filters)

    def _validate_status_transition(self, current_status: str, new_status: str) -> None:
        """
        Validate that a status transition is allowed based on business rules.

        Args:
            current_status: Current status
            new_status: Proposed new status

        Raises:
            InvalidStatusTransitionException: If transition is not allowed
        """
        # Define allowed transitions
        allowed_transitions = {
            "IN_STOCK": ["CHECKED_OUT", "MAINTENANCE", "DAMAGED", "LOST", "RETIRED"],
            "CHECKED_OUT": ["IN_STOCK", "DAMAGED", "LOST"],
            "MAINTENANCE": ["IN_STOCK", "DAMAGED", "RETIRED"],
            "DAMAGED": ["MAINTENANCE", "IN_STOCK", "RETIRED"],
            "LOST": ["IN_STOCK"],
            "RETIRED": [],
            "ON_ORDER": ["IN_STOCK", "DAMAGED"],
        }

        # Allow transition to same status
        if current_status == new_status:
            return

        # Check if transition is allowed
        if new_status not in allowed_transitions.get(current_status, []):
            from app.core.exceptions import InvalidStatusTransitionException

            raise InvalidStatusTransitionException(
                f"Cannot transition from {current_status} to {new_status}",
                allowed_transitions=allowed_transitions.get(current_status, []),
            )

    def _get_current_checkout(self, tool_id: int) -> Optional[ToolCheckout]:
        """
        Get the current checkout record for a tool.

        Args:
            tool_id: ID of the tool

        Returns:
            Current checkout record if found, None otherwise
        """
        checkouts = self.checkout_repository.list(tool_id=tool_id, status="CHECKED_OUT")

        return checkouts[0] if checkouts else None

    def _is_checkout_overdue(self, checkout: ToolCheckout) -> bool:
        """
        Check if a checkout is overdue.

        Args:
            checkout: Checkout record to check

        Returns:
            True if overdue, False otherwise
        """
        if not checkout.due_date:
            return False

        return checkout.due_date < datetime.now().date()

    def _get_maintenance_history(self, tool_id: int) -> List[Dict[str, Any]]:
        """
        Get maintenance history for a tool.

        Args:
            tool_id: ID of the tool

        Returns:
            List of maintenance records
        """
        maintenance_records = self.maintenance_repository.list(
            tool_id=tool_id, order_by="date", order_dir="desc"
        )

        return [
            {
                "id": record.id,
                "maintenance_type": record.maintenance_type,
                "status": record.status,
                "date": record.date.isoformat() if record.date else None,
                "completed_date": (
                    record.completion_date.isoformat()
                    if record.completion_date
                    else None
                ),
                "performed_by": record.performed_by,
                "cost": record.cost,
                "details": record.details,
                "parts": record.parts,
                "condition_before": record.condition_before,
                "condition_after": record.condition_after,
            }
            for record in maintenance_records
        ]

    def _get_checkout_history(self, tool_id: int) -> List[Dict[str, Any]]:
        """
        Get checkout history for a tool.

        Args:
            tool_id: ID of the tool

        Returns:
            List of checkout records
        """
        checkout_records = self.checkout_repository.list(
            tool_id=tool_id, order_by="checked_out_date", order_dir="desc"
        )

        return [
            {
                "id": record.id,
                "checked_out_by": record.checked_out_by,
                "status": record.status,
                "checked_out_date": (
                    record.checked_out_date.isoformat()
                    if record.checked_out_date
                    else None
                ),
                "due_date": record.due_date.isoformat() if record.due_date else None,
                "returned_date": (
                    record.returned_date.isoformat() if record.returned_date else None
                ),
                "project_id": record.project_id,
                "project_name": record.project_name,
                "condition_before": record.condition_before,
                "condition_after": record.condition_after,
                "issue_description": record.issue_description,
                "overdue": record.due_date
                and record.checked_out_date
                and (
                    (
                        record.status == "CHECKED_OUT"
                        and record.due_date < datetime.now().date()
                    )
                    or (
                        record.status in ["RETURNED", "RETURNED_WITH_ISSUES"]
                        and record.returned_date
                        and record.due_date < record.returned_date
                    )
                ),
            }
            for record in checkout_records
        ]

    def _get_next_scheduled_maintenance(
        self, tool_id: int
    ) -> Optional[ToolMaintenance]:
        """
        Get the next scheduled maintenance for a tool.

        Args:
            tool_id: ID of the tool

        Returns:
            Next maintenance record if found, None otherwise
        """
        maintenance_records = self.maintenance_repository.list(
            tool_id=tool_id, status="SCHEDULED", order_by="date", order_dir="asc"
        )

        # Filter for future dates
        future_maintenance = [
            m for m in maintenance_records if m.date and m.date >= datetime.now().date()
        ]

        return future_maintenance[0] if future_maintenance else None

    def _calculate_usage_statistics(self, tool_id: int) -> Dict[str, Any]:
        """
        Calculate usage statistics for a tool.

        Args:
            tool_id: ID of the tool

        Returns:
            Dictionary with usage statistics
        """
        # Get all checkouts for the tool
        checkouts = self.checkout_repository.list(tool_id=tool_id)

        if not checkouts:
            return {
                "total_checkouts": 0,
                "total_days_used": 0,
                "average_checkout_duration": 0,
                "utilization_last_90_days": 0,
                "most_frequent_user": None,
                "most_common_project": None,
            }

        # Calculate total days used
        total_days = 0
        for checkout in checkouts:
            if checkout.status == "CHECKED_OUT":
                # Still checked out
                days = (
                    (datetime.now().date() - checkout.checked_out_date.date()).days
                    if checkout.checked_out_date
                    else 0
                )
            else:
                # Returned
                if checkout.checked_out_date and checkout.returned_date:
                    days = (
                        checkout.returned_date.date() - checkout.checked_out_date.date()
                    ).days
                else:
                    days = 0

            total_days += max(0, days)

        # Calculate utilization in last 90 days
        ninety_days_ago = datetime.now().date() - timedelta(days=90)
        recent_checkouts = [
            c
            for c in checkouts
            if c.checked_out_date and c.checked_out_date.date() >= ninety_days_ago
        ]

        recent_days = 0
        for checkout in recent_checkouts:
            if checkout.status == "CHECKED_OUT":
                # Still checked out
                days = (datetime.now().date() - checkout.checked_out_date.date()).days
            else:
                # Returned
                if checkout.checked_out_date and checkout.returned_date:
                    days = (
                        checkout.returned_date.date() - checkout.checked_out_date.date()
                    ).days
                else:
                    days = 0

            recent_days += max(0, days)

        utilization_percentage = round((recent_days / 90 * 100), 1)

        # Find most frequent user
        user_counts = {}
        for checkout in checkouts:
            user = checkout.checked_out_by or "Unknown"
            if user not in user_counts:
                user_counts[user] = 0
            user_counts[user] += 1

        most_frequent_user = (
            max(user_counts.items(), key=lambda x: x[1]) if user_counts else None
        )

        # Find most common project
        project_counts = {}
        for checkout in checkouts:
            if not checkout.project_id:
                continue

            project = checkout.project_name or f"Project {checkout.project_id}"
            if project not in project_counts:
                project_counts[project] = 0
            project_counts[project] += 1

        most_common_project = (
            max(project_counts.items(), key=lambda x: x[1]) if project_counts else None
        )

        return {
            "total_checkouts": len(checkouts),
            "total_days_used": total_days,
            "average_checkout_duration": round(total_days / len(checkouts), 1),
            "utilization_last_90_days": utilization_percentage,
            "most_frequent_user": most_frequent_user[0] if most_frequent_user else None,
            "most_common_project": (
                most_common_project[0] if most_common_project else None
            ),
        }

    def _generate_inventory_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate inventory report for tools.

        Args:
            filters: Report filters

        Returns:
            Dictionary with inventory report results
        """
        # Apply filters
        category = filters.get("category")
        status = filters.get("status")

        query_filters = {}
        if category:
            query_filters["category"] = category
        if status:
            query_filters["status"] = status

        tools = self.repository.list(**query_filters)

        # Group by category and status
        by_category = {}
        by_status = {}

        for tool in tools:
            # By category
            category = tool.category
            if category not in by_category:
                by_category[category] = 0
            by_category[category] += 1

            # By status
            status = tool.status
            if status not in by_status:
                by_status[status] = 0
            by_status[status] += 1

        # Build report
        return {
            "report_type": "inventory",
            "generated_at": datetime.now().isoformat(),
            "filters": filters,
            "total_tools": len(tools),
            "by_category": by_category,
            "by_status": by_status,
            "tools": [
                {
                    "id": tool.id,
                    "name": tool.name,
                    "category": tool.category,
                    "status": tool.status,
                    "purchase_date": (
                        tool.purchase_date.isoformat() if tool.purchase_date else None
                    ),
                    "purchase_price": tool.purchase_price,
                    "location": tool.location,
                    "checked_out_to": tool.checked_out_to,
                    "last_maintenance": (
                        tool.last_maintenance.isoformat()
                        if tool.last_maintenance
                        else None
                    ),
                    "next_maintenance": (
                        tool.next_maintenance.isoformat()
                        if tool.next_maintenance
                        else None
                    ),
                }
                for tool in tools
            ],
        }

    def _generate_maintenance_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate maintenance report for tools.

        Args:
            filters: Report filters

        Returns:
            Dictionary with maintenance report results
        """
        # Get date range from filters
        from_date = filters.get("from_date")
        if isinstance(from_date, str):
            from_date = datetime.fromisoformat(from_date.replace("Z", "+00:00")).date()
        elif not from_date:
            from_date = datetime.now().date() - timedelta(days=90)

        to_date = filters.get("to_date")
        if isinstance(to_date, str):
            to_date = datetime.fromisoformat(to_date.replace("Z", "+00:00")).date()
        elif not to_date:
            to_date = datetime.now().date()

        # Apply filters
        category = filters.get("category")
        maintenance_type = filters.get("maintenance_type")
        status = filters.get("status")

        # Get maintenance records
        maintenance_records = self.maintenance_repository.get_by_date_range(
            start_date=from_date, end_date=to_date
        )

        # Filter by tool category if needed
        if category:
            filtered_records = []
            for record in maintenance_records:
                tool = self.get_by_id(record.tool_id)
                if tool and tool.category == category:
                    filtered_records.append(record)
            maintenance_records = filtered_records

        # Filter by maintenance type if needed
        if maintenance_type:
            maintenance_records = [
                r for r in maintenance_records if r.maintenance_type == maintenance_type
            ]

        # Filter by status if needed
        if status:
            maintenance_records = [r for r in maintenance_records if r.status == status]

        # Group by type and status
        by_type = {}
        by_status = {}

        for record in maintenance_records:
            # By type
            mtype = record.maintenance_type
            if mtype not in by_type:
                by_type[mtype] = 0
            by_type[mtype] += 1

            # By status
            mstatus = record.status
            if mstatus not in by_status:
                by_status[mstatus] = 0
            by_status[mstatus] += 1

        # Build report
        return {
            "report_type": "maintenance",
            "generated_at": datetime.now().isoformat(),
            "filters": {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "category": category,
                "maintenance_type": maintenance_type,
                "status": status,
            },
            "date_range_days": (to_date - from_date).days,
            "total_maintenance_records": len(maintenance_records),
            "by_type": by_type,
            "by_status": by_status,
            "maintenance_records": [
                {
                    "id": record.id,
                    "tool_id": record.tool_id,
                    "tool_name": record.tool_name,
                    "maintenance_type": record.maintenance_type,
                    "status": record.status,
                    "date": record.date.isoformat() if record.date else None,
                    "completion_date": (
                        record.completion_date.isoformat()
                        if record.completion_date
                        else None
                    ),
                    "performed_by": record.performed_by,
                    "cost": record.cost,
                    "details": record.details,
                }
                for record in maintenance_records
            ],
        }

    def _generate_utilization_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate utilization report for tools.

        Args:
            filters: Report filters

        Returns:
            Dictionary with utilization report results
        """
        # Get date range from filters
        from_date = filters.get("from_date")
        if isinstance(from_date, str):
            from_date = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
        elif not from_date:
            from_date = datetime.now() - timedelta(days=90)

        to_date = filters.get("to_date")
        if isinstance(to_date, str):
            to_date = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
        elif not to_date:
            to_date = datetime.now()

        # Apply filters
        category = filters.get("category")

        query_filters = {}
        if category:
            query_filters["category"] = category

        tools = self.repository.list(**query_filters)

        # Calculate utilization for each tool
        utilization_data = []
        for tool in tools:
            utilization = self.get_tool_utilization(
                tool_id=tool.id, date_range=(from_date, to_date)
            )
            utilization_data.append(utilization)

        # Calculate overall statistics
        total_days = sum(u["utilization"]["checked_out_days"] for u in utilization_data)
        maintenance_days = sum(
            u["utilization"]["maintenance_days"] for u in utilization_data
        )
        available_days = sum(
            u["utilization"]["available_days"] for u in utilization_data
        )
        total_period = (to_date - from_date).days * len(tools)

        overall_utilization = (
            round((total_days / total_period * 100), 1) if total_period > 0 else 0
        )
        overall_maintenance = (
            round((maintenance_days / total_period * 100), 1) if total_period > 0 else 0
        )
        overall_availability = (
            round((available_days / total_period * 100), 1) if total_period > 0 else 0
        )

        # Sort by utilization (descending)
        utilization_data.sort(
            key=lambda x: x["utilization"]["utilization_percentage"], reverse=True
        )

        # Build report
        return {
            "report_type": "utilization",
            "generated_at": datetime.now().isoformat(),
            "filters": {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "category": category,
            },
            "date_range_days": (to_date - from_date).days,
            "total_tools": len(tools),
            "overall_stats": {
                "total_days": total_period,
                "checked_out_days": total_days,
                "maintenance_days": maintenance_days,
                "available_days": available_days,
                "utilization_percentage": overall_utilization,
                "maintenance_percentage": overall_maintenance,
                "availability_percentage": overall_availability,
            },
            "utilization_by_tool": utilization_data,
            "most_utilized_tools": (
                utilization_data[:5] if len(utilization_data) > 5 else utilization_data
            ),
            "least_utilized_tools": (
                utilization_data[-5:][::-1]
                if len(utilization_data) > 5
                else utilization_data[::-1]
            ),
        }

    def _generate_checkout_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate checkout report for tools.

        Args:
            filters: Report filters

        Returns:
            Dictionary with checkout report results
        """
        # Get date range from filters
        from_date = filters.get("from_date")
        if isinstance(from_date, str):
            from_date = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
        elif not from_date:
            from_date = datetime.now() - timedelta(days=90)

        to_date = filters.get("to_date")
        if isinstance(to_date, str):
            to_date = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
        elif not to_date:
            to_date = datetime.now()

        # Apply filters
        status = filters.get("status")
        user = filters.get("user")
        project_id = filters.get("project_id")

        # Get checkouts
        checkouts = self.checkout_repository.get_by_date_range(
            start_date=from_date, end_date=to_date
        )

        # Apply additional filters
        if status:
            checkouts = [c for c in checkouts if c.status == status]

        if user:
            checkouts = [c for c in checkouts if c.checked_out_by == user]

        if project_id:
            checkouts = [c for c in checkouts if c.project_id == project_id]

        # Group by status and user
        by_status = {}
        by_user = {}
        by_project = {}

        for checkout in checkouts:
            # By status
            status = checkout.status
            if status not in by_status:
                by_status[status] = 0
            by_status[status] += 1

            # By user
            user = checkout.checked_out_by or "Unknown"
            if user not in by_user:
                by_user[user] = 0
            by_user[user] += 1

            # By project
            if checkout.project_id:
                project = checkout.project_name or f"Project {checkout.project_id}"
                if project not in by_project:
                    by_project[project] = 0
                by_project[project] += 1

        # Calculate overdue stats
        overdue_count = len(
            [
                c
                for c in checkouts
                if c.status == "CHECKED_OUT"
                and c.due_date
                and c.due_date < datetime.now().date()
            ]
        )

        returned_late_count = len(
            [
                c
                for c in checkouts
                if c.status in ["RETURNED", "RETURNED_WITH_ISSUES"]
                and c.due_date
                and c.returned_date
                and c.due_date < c.returned_date.date()
            ]
        )

        # Build report
        return {
            "report_type": "checkout",
            "generated_at": datetime.now().isoformat(),
            "filters": {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "status": status,
                "user": user,
                "project_id": project_id,
            },
            "date_range_days": (to_date - from_date).days,
            "total_checkouts": len(checkouts),
            "by_status": by_status,
            "by_user": by_user,
            "by_project": by_project,
            "overdue_stats": {
                "currently_overdue": overdue_count,
                "returned_late": returned_late_count,
                "overdue_percentage": (
                    round(
                        (overdue_count + returned_late_count) / len(checkouts) * 100, 1
                    )
                    if len(checkouts) > 0
                    else 0
                ),
            },
            "checkouts": [
                {
                    "id": checkout.id,
                    "tool_id": checkout.tool_id,
                    "tool_name": checkout.tool_name,
                    "checked_out_by": checkout.checked_out_by,
                    "status": checkout.status,
                    "checked_out_date": (
                        checkout.checked_out_date.isoformat()
                        if checkout.checked_out_date
                        else None
                    ),
                    "due_date": (
                        checkout.due_date.isoformat() if checkout.due_date else None
                    ),
                    "returned_date": (
                        checkout.returned_date.isoformat()
                        if checkout.returned_date
                        else None
                    ),
                    "project_id": checkout.project_id,
                    "project_name": checkout.project_name,
                    "overdue": (
                        checkout.status == "CHECKED_OUT"
                        and checkout.due_date
                        and checkout.due_date < datetime.now().date()
                    )
                    or (
                        checkout.status in ["RETURNED", "RETURNED_WITH_ISSUES"]
                        and checkout.due_date
                        and checkout.returned_date
                        and checkout.due_date < checkout.returned_date.date()
                    ),
                }
                for checkout in checkouts
            ],
        }
