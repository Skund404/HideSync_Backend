# File: app/services/purchase_service.py

from typing import List, Optional, Dict, Any, Union, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from app.services.base_service import BaseService
from app.db.models.purchase import Purchase, PurchaseItem
from app.db.models.enums import PurchaseStatus, PaymentStatus
from app.repositories.purchase_repository import PurchaseRepository
from app.core.exceptions import (
    ValidationException,
    EntityNotFoundException,
    BusinessRuleError,
)
from app.core.events import DomainEvent
from app.core.validation import validate_input, validate_entity

logger = logging.getLogger(__name__)


# Domain events
class PurchaseCreated(DomainEvent):
    """Event emitted when a purchase is created."""

    def __init__(
        self,
        purchase_id: str,
        supplier_id: Optional[int],
        total: float,
        user_id: Optional[int] = None,
    ):
        """
        Initialize purchase created event.

        Args:
            purchase_id: ID of the created purchase
            supplier_id: ID of the supplier (if any)
            total: Total amount of the purchase
            user_id: Optional ID of the user who created the purchase
        """
        super().__init__()
        self.purchase_id = purchase_id
        self.supplier_id = supplier_id
        self.total = total
        self.user_id = user_id


class PurchaseStatusChanged(DomainEvent):
    """Event emitted when a purchase's status changes."""

    def __init__(
        self,
        purchase_id: str,
        previous_status: str,
        new_status: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize purchase status changed event.

        Args:
            purchase_id: ID of the purchase
            previous_status: Previous status
            new_status: New status
            user_id: Optional ID of the user who changed the status
        """
        super().__init__()
        self.purchase_id = purchase_id
        self.previous_status = previous_status
        self.new_status = new_status
        self.user_id = user_id


class PurchaseItemAdded(DomainEvent):
    """Event emitted when an item is added to a purchase."""

    def __init__(
        self,
        purchase_id: str,
        item_id: int,
        material_id: Optional[int],
        quantity: int,
        price: float,
        user_id: Optional[int] = None,
    ):
        """
        Initialize purchase item added event.

        Args:
            purchase_id: ID of the purchase
            item_id: ID of the added item
            material_id: Optional material ID
            quantity: Quantity of the item
            price: Price of the item
            user_id: Optional ID of the user who added the item
        """
        super().__init__()
        self.purchase_id = purchase_id
        self.item_id = item_id
        self.material_id = material_id
        self.quantity = quantity
        self.price = price
        self.user_id = user_id


class ItemsReceived(DomainEvent):
    """Event emitted when items are received for a purchase."""

    def __init__(
        self,
        purchase_id: str,
        received_items: List[Dict[str, Any]],
        partial: bool,
        user_id: Optional[int] = None,
    ):
        """
        Initialize items received event.

        Args:
            purchase_id: ID of the purchase
            received_items: List of received items with quantities
            partial: Whether this is a partial receipt
            user_id: Optional ID of the user who received the items
        """
        super().__init__()
        self.purchase_id = purchase_id
        self.received_items = received_items
        self.partial = partial
        self.user_id = user_id


# Validation functions
validate_purchase = validate_entity(Purchase)
validate_purchase_item = validate_entity(PurchaseItem)


class PurchaseService(BaseService[Purchase]):
    """
    Service for managing purchases in the HideSync system.

    Provides functionality for:
    - Purchase order creation and management
    - Supplier ordering
    - Inventory replenishment
    - Purchase tracking
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        supplier_service=None,
        material_service=None,
        inventory_service=None,
    ):
        """
        Initialize PurchaseService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository override
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            supplier_service: Optional supplier service for supplier validation
            material_service: Optional material service for material validation
            inventory_service: Optional inventory service for inventory updates
        """
        self.session = session
        self.repository = repository or PurchaseRepository(session)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.supplier_service = supplier_service
        self.material_service = material_service
        self.inventory_service = inventory_service

    @validate_input(validate_purchase)
    def create_purchase(self, data: Dict[str, Any]) -> Purchase:
        """
        Create a new purchase.

        Args:
            data: Purchase data with required fields

        Returns:
            Created purchase entity

        Raises:
            ValidationException: If data validation fails
            EntityNotFoundException: If referenced supplier not found
        """
        # Validate supplier if supplier_id is provided
        if "supplier_id" in data and data["supplier_id"] and self.supplier_service:
            supplier = self.supplier_service.get_by_id(data["supplier_id"])
            if not supplier:
                raise EntityNotFoundException("Supplier", data["supplier_id"])

        # Set default values if not provided
        if "status" not in data:
            data["status"] = PurchaseStatus.PLANNING.value

        if "payment_status" not in data:
            data["payment_status"] = PaymentStatus.PENDING.value

        if "date" not in data:
            data["date"] = datetime.now().date()

        # Initialize total if not provided
        if "total" not in data:
            data["total"] = 0.0

        with self.transaction():
            # Create purchase
            purchase = self.repository.create(data)

            # Create purchase items if provided
            if "items" in data and isinstance(data["items"], list):
                for item_data in data["items"]:
                    self.add_purchase_item(purchase.id, item_data)

                # Refresh purchase to get updated total
                purchase = self.repository.get_by_id(purchase.id)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PurchaseCreated(
                        purchase_id=purchase.id,
                        supplier_id=purchase.supplier_id,
                        total=purchase.total,
                        user_id=user_id,
                    )
                )

            return purchase

    def update_purchase(
        self, purchase_id: str, data: Dict[str, Any]
    ) -> Optional[Purchase]:
        """
        Update an existing purchase.

        Args:
            purchase_id: Purchase ID
            data: Updated purchase data

        Returns:
            Updated purchase entity or None if not found

        Raises:
            ValidationException: If data validation fails
            EntityNotFoundException: If referenced supplier not found
        """
        # Validate supplier if supplier_id is being updated
        if "supplier_id" in data and data["supplier_id"] and self.supplier_service:
            supplier = self.supplier_service.get_by_id(data["supplier_id"])
            if not supplier:
                raise EntityNotFoundException("Supplier", data["supplier_id"])

        with self.transaction():
            # Get the original purchase for event creation
            original_purchase = self.repository.get_by_id(purchase_id)
            if not original_purchase:
                return None

            # Check if status is being changed
            status_changed = (
                "status" in data and data["status"] != original_purchase.status
            )
            previous_status = original_purchase.status if status_changed else None

            # Update purchase
            updated_purchase = self.repository.update(purchase_id, data)
            if not updated_purchase:
                return None

            # Publish events if event bus exists
            if self.event_bus and status_changed:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PurchaseStatusChanged(
                        purchase_id=purchase_id,
                        previous_status=previous_status,
                        new_status=data["status"],
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Purchase:{purchase_id}")

            return updated_purchase

    def delete_purchase(self, purchase_id: str) -> bool:
        """
        Delete a purchase by ID.

        Args:
            purchase_id: Purchase ID

        Returns:
            True if deleted, False if not found
        """
        with self.transaction():
            # Get the purchase before deletion for event creation
            purchase = self.repository.get_by_id(purchase_id)
            if not purchase:
                return False

            # Check if purchase can be deleted (only certain statuses)
            if purchase.status not in [
                PurchaseStatus.PLANNING.value,
                PurchaseStatus.PENDING_APPROVAL.value,
                PurchaseStatus.DRAFT.value,
            ]:
                raise BusinessRuleError(
                    f"Cannot delete purchase in status {purchase.status}",
                    "PURCHASE_DELETE_001",
                    {"purchase_id": purchase_id, "status": purchase.status},
                )

            # Delete purchase items first
            items = self.get_purchase_items(purchase_id)
            for item in items:
                self.delete_purchase_item(item.id)

            # Delete purchase
            result = self.repository.delete(purchase_id)

            # Invalidate cache if cache service exists
            if result and self.cache_service:
                self.cache_service.invalidate(f"Purchase:{purchase_id}")

            return result

    def get_purchase_items(self, purchase_id: str) -> List[PurchaseItem]:
        """
        Get items for a purchase.

        Args:
            purchase_id: Purchase ID

        Returns:
            List of purchase items
        """
        return self.repository.get_purchase_items(purchase_id)

    @validate_input(validate_purchase_item)
    def add_purchase_item(
        self, purchase_id: str, item_data: Dict[str, Any]
    ) -> PurchaseItem:
        """
        Add an item to a purchase.

        Args:
            purchase_id: Purchase ID
            item_data: Item data

        Returns:
            Created purchase item

        Raises:
            EntityNotFoundException: If purchase not found
            ValidationException: If data validation fails
        """
        # Check if purchase exists
        purchase = self.repository.get_by_id(purchase_id)
        if not purchase:
            raise EntityNotFoundException("Purchase", purchase_id)

        # Add purchase_id to item data
        item_data["purchase_id"] = purchase_id

        # Validate material if material_id is provided
        if (
            "material_id" in item_data
            and item_data["material_id"]
            and self.material_service
        ):
            material = self.material_service.get_by_id(item_data["material_id"])
            if not material:
                raise EntityNotFoundException("Material", item_data["material_id"])

            # Set name from material if not provided
            if "name" not in item_data and hasattr(material, "name"):
                item_data["name"] = material.name

            # Set unit from material if not provided
            if "unit" not in item_data and hasattr(material, "unit"):
                item_data["unit"] = material.unit

        # Calculate total if price and quantity are provided
        if "price" in item_data and "quantity" in item_data:
            item_data["total"] = item_data["price"] * item_data["quantity"]

        with self.transaction():
            # Create purchase item
            item = self.repository.add_purchase_item(item_data)

            # Update purchase total
            self._update_purchase_total(purchase_id)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PurchaseItemAdded(
                        purchase_id=purchase_id,
                        item_id=item.id,
                        material_id=(
                            item.material_id if hasattr(item, "material_id") else None
                        ),
                        quantity=item.quantity,
                        price=item.price,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Purchase:{purchase_id}")

            return item

    def update_purchase_item(
        self, item_id: int, item_data: Dict[str, Any]
    ) -> Optional[PurchaseItem]:
        """
        Update a purchase item.

        Args:
            item_id: Item ID
            item_data: Updated item data

        Returns:
            Updated purchase item or None if not found

        Raises:
            ValidationException: If data validation fails
        """
        with self.transaction():
            # Get the original item
            original_item = self.repository.get_purchase_item_by_id(item_id)
            if not original_item:
                return None

            # Recalculate total if price or quantity is updated
            if (
                "price" in item_data or "quantity" in item_data
            ) and not "total" in item_data:
                price = item_data.get(
                    "price",
                    original_item.price if hasattr(original_item, "price") else 0,
                )
                quantity = item_data.get(
                    "quantity",
                    original_item.quantity if hasattr(original_item, "quantity") else 0,
                )
                item_data["total"] = price * quantity

            # Update purchase item
            updated_item = self.repository.update_purchase_item(item_id, item_data)
            if not updated_item:
                return None

            # Update purchase total
            self._update_purchase_total(original_item.purchase_id)

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Purchase:{original_item.purchase_id}")

            return updated_item

    def delete_purchase_item(self, item_id: int) -> bool:
        """
        Delete a purchase item.

        Args:
            item_id: Item ID

        Returns:
            True if deleted, False if not found
        """
        # Get the item before deletion to get purchase_id
        item = self.repository.get_purchase_item_by_id(item_id)
        if not item:
            return False

        purchase_id = item.purchase_id

        with self.transaction():
            # Delete item
            result = self.repository.delete_purchase_item(item_id)

            # Update purchase total
            if result:
                self._update_purchase_total(purchase_id)

                # Invalidate cache if cache service exists
                if self.cache_service:
                    self.cache_service.invalidate(f"Purchase:{purchase_id}")

            return result

    def update_purchase_status(
        self, purchase_id: str, new_status: str
    ) -> Optional[Purchase]:
        """
        Update a purchase's status.

        Args:
            purchase_id: Purchase ID
            new_status: New status

        Returns:
            Updated purchase or None if not found

        Raises:
            ValidationException: If status is invalid
            BusinessRuleError: If status transition is invalid
        """
        # Validate status
        if new_status not in [status.value for status in PurchaseStatus]:
            raise ValidationException(
                f"Invalid purchase status: {new_status}",
                {"status": [f"Invalid purchase status: {new_status}"]},
            )

        with self.transaction():
            # Get the purchase
            purchase = self.repository.get_by_id(purchase_id)
            if not purchase:
                return None

            # Check if status is changing
            if purchase.status == new_status:
                return purchase

            # Validate status transition
            if not self._is_valid_status_transition(purchase.status, new_status):
                raise BusinessRuleError(
                    f"Invalid status transition: {purchase.status} -> {new_status}",
                    "PURCHASE_STATUS_001",
                    {
                        "purchase_id": purchase_id,
                        "current_status": purchase.status,
                        "new_status": new_status,
                    },
                )

            # Store previous status for event
            previous_status = purchase.status

            # Update status
            updated_purchase = self.repository.update(
                purchase_id, {"status": new_status}
            )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PurchaseStatusChanged(
                        purchase_id=purchase_id,
                        previous_status=previous_status,
                        new_status=new_status,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Purchase:{purchase_id}")

            return updated_purchase

    def receive_items(
        self, purchase_id: str, receive_data: Dict[str, Any]
    ) -> Optional[Purchase]:
        """
        Record receipt of items for a purchase.

        Args:
            purchase_id: Purchase ID
            receive_data: Data about the received items (item_id + quantity)

        Returns:
            Updated purchase or None if not found

        Raises:
            BusinessRuleError: If purchase cannot receive items
            EntityNotFoundException: If purchase or item not found
        """
        with self.transaction():
            # Get the purchase
            purchase = self.repository.get_by_id(purchase_id)
            if not purchase:
                return None

            # Validate purchase status
            if purchase.status not in [
                PurchaseStatus.ORDERED.value,
                PurchaseStatus.PARTIAL_SHIPMENT.value,
                PurchaseStatus.SHIPPED.value,
                PurchaseStatus.IN_TRANSIT.value,
            ]:
                raise BusinessRuleError(
                    f"Cannot receive items for purchase in status {purchase.status}",
                    "PURCHASE_RECEIVE_001",
                    {"purchase_id": purchase_id, "status": purchase.status},
                )

            # Get items to be received
            if "items" not in receive_data or not isinstance(
                receive_data["items"], list
            ):
                raise ValidationException(
                    "Missing items data for receipt",
                    {"items": ["Items data is required for receipt"]},
                )

            # Process received items
            total_expected = 0
            total_received = 0
            processed_items = []

            # Get all purchase items
            purchase_items = self.get_purchase_items(purchase_id)
            purchase_items_by_id = {item.id: item for item in purchase_items}

            for receive_item in receive_data["items"]:
                if (
                    "item_id" not in receive_item
                    or "quantity_received" not in receive_item
                ):
                    raise ValidationException(
                        "Invalid receive item data",
                        {
                            "items": [
                                "Each item must have item_id and quantity_received"
                            ]
                        },
                    )

                item_id = receive_item["item_id"]
                quantity_received = receive_item["quantity_received"]

                # Check if item exists in this purchase
                if item_id not in purchase_items_by_id:
                    raise EntityNotFoundException("PurchaseItem", item_id)

                purchase_item = purchase_items_by_id[item_id]

                # Update received quantity for this item
                current_received = (
                    purchase_item.quantity_received
                    if hasattr(purchase_item, "quantity_received")
                    else 0
                )
                new_received = current_received + quantity_received

                # Ensure we don't receive more than ordered
                if new_received > purchase_item.quantity:
                    raise BusinessRuleError(
                        f"Cannot receive more than ordered for item {item_id}",
                        "PURCHASE_RECEIVE_002",
                        {
                            "item_id": item_id,
                            "ordered": purchase_item.quantity,
                            "already_received": current_received,
                            "attempting_to_receive": quantity_received,
                        },
                    )

                # Update the purchase item
                self.update_purchase_item(item_id, {"quantity_received": new_received})

                # Add to processed items for the event
                processed_items.append(
                    {
                        "item_id": item_id,
                        "material_id": (
                            purchase_item.material_id
                            if hasattr(purchase_item, "material_id")
                            else None
                        ),
                        "name": (
                            purchase_item.name
                            if hasattr(purchase_item, "name")
                            else f"Item {item_id}"
                        ),
                        "quantity_received": quantity_received,
                        "total_received": new_received,
                        "quantity_ordered": purchase_item.quantity,
                    }
                )

                # Update inventory if material_id is present
                if (
                    hasattr(purchase_item, "material_id")
                    and purchase_item.material_id
                    and self.inventory_service
                ):
                    try:
                        self.inventory_service.adjust_inventory(
                            item_id=purchase_item.material_id,
                            quantity_change=quantity_received,
                            reason=f"Purchase #{purchase_id}",
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to update inventory for material {purchase_item.material_id}: {str(e)}",
                            exc_info=True,
                        )

                # Track totals for status update
                total_expected += purchase_item.quantity
                total_received += new_received

            # Determine new status based on received quantities
            new_status = purchase.status
            if total_received >= total_expected:
                new_status = PurchaseStatus.RECEIVED.value
            elif total_received > 0:
                new_status = PurchaseStatus.PARTIALLY_RECEIVED.value

            # Update purchase status if changed
            if new_status != purchase.status:
                updated_purchase = self.update_purchase_status(purchase_id, new_status)
            else:
                updated_purchase = purchase

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ItemsReceived(
                        purchase_id=purchase_id,
                        received_items=processed_items,
                        partial=new_status == PurchaseStatus.PARTIALLY_RECEIVED.value,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Purchase:{purchase_id}")

            return updated_purchase

    def get_purchases_by_supplier(
        self, supplier_id: int, limit: int = 100
    ) -> List[Purchase]:
        """
        Get purchases for a specific supplier.

        Args:
            supplier_id: Supplier ID
            limit: Maximum number of purchases to return

        Returns:
            List of purchases for the supplier
        """
        return self.repository.get_by_supplier(supplier_id, limit=limit)

    def get_purchases_by_status(self, status: str, limit: int = 100) -> List[Purchase]:
        """
        Get purchases by status.

        Args:
            status: Purchase status
            limit: Maximum number of purchases to return

        Returns:
            List of purchases with the specified status
        """
        return self.repository.list(status=status, limit=limit)

    def get_recent_purchases(self, days: int = 30, limit: int = 100) -> List[Purchase]:
        """
        Get recent purchases.

        Args:
            days: Number of days to look back
            limit: Maximum number of purchases to return

        Returns:
            List of recent purchases
        """
        start_date = datetime.now() - timedelta(days=days)
        return self.repository.list(
            date_from=start_date, sort_by="date", sort_dir="desc", limit=limit
        )

    def get_purchases_by_date_range(
        self, start_date: datetime, end_date: datetime, limit: int = 100
    ) -> List[Purchase]:
        """
        Get purchases within a date range.

        Args:
            start_date: Start date
            end_date: End date
            limit: Maximum number of purchases to return

        Returns:
            List of purchases within the date range
        """
        return self.repository.list(
            date_from=start_date,
            date_to=end_date,
            sort_by="date",
            sort_dir="desc",
            limit=limit,
        )

    def get_purchases_stats(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get purchase statistics.

        Args:
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Dictionary of purchase statistics
        """
        # Set default date range if not provided
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()

        # Get purchases in date range
        purchases = self.repository.list(date_from=start_date, date_to=end_date)

        # Calculate statistics
        total_purchases = len(purchases)
        total_spent = sum(
            purchase.total for purchase in purchases if hasattr(purchase, "total")
        )
        avg_purchase_value = total_spent / total_purchases if total_purchases > 0 else 0

        # Count by status
        status_counts = {}
        for status in PurchaseStatus:
            status_counts[status.name] = len(
                [p for p in purchases if p.status == status.value]
            )

        # Calculate spending by day
        spending_by_day = {}
        for purchase in purchases:
            if not hasattr(purchase, "date") or not hasattr(purchase, "total"):
                continue

            day = (
                purchase.date.isoformat()
                if isinstance(purchase.date, datetime)
                else purchase.date
            )
            if day not in spending_by_day:
                spending_by_day[day] = 0
            spending_by_day[day] += purchase.total

        # Get supplies by category
        spending_by_category = {}
        for purchase in purchases:
            items = self.get_purchase_items(purchase.id)
            for item in items:
                if not hasattr(item, "material_type") or not hasattr(item, "total"):
                    continue

                material_type = getattr(item, "material_type", "Other")
                if material_type not in spending_by_category:
                    spending_by_category[material_type] = 0
                spending_by_category[material_type] += item.total

        return {
            "total_purchases": total_purchases,
            "total_spent": total_spent,
            "avg_purchase_value": avg_purchase_value,
            "status_counts": status_counts,
            "spending_by_day": spending_by_day,
            "spending_by_category": spending_by_category,
        }

    def get_pending_deliveries(self, days_ahead: int = 14) -> List[Dict[str, Any]]:
        """
        Get pending deliveries due within a number of days.

        Args:
            days_ahead: Number of days to look ahead

        Returns:
            List of pending deliveries
        """
        today = datetime.now().date()
        end_date = today + timedelta(days=days_ahead)

        # Get purchases with delivery dates in range
        purchases = self.repository.list(
            status_in=[
                PurchaseStatus.ORDERED.value,
                PurchaseStatus.ACKNOWLEDGED.value,
                PurchaseStatus.PROCESSING.value,
                PurchaseStatus.SHIPPED.value,
                PurchaseStatus.IN_TRANSIT.value,
                PurchaseStatus.PARTIAL_SHIPMENT.value,
            ],
            delivery_date_from=today,
            delivery_date_to=end_date,
            sort_by="delivery_date",
            sort_dir="asc",
        )

        # Format for display
        result = []
        for purchase in purchases:
            supplier_name = "Unknown Supplier"
            if (
                hasattr(purchase, "supplier_id")
                and purchase.supplier_id
                and self.supplier_service
            ):
                supplier = self.supplier_service.get_by_id(purchase.supplier_id)
                if supplier and hasattr(supplier, "name"):
                    supplier_name = supplier.name

            # Get items count
            items = self.get_purchase_items(purchase.id)

            result.append(
                {
                    "purchase_id": purchase.id,
                    "supplier": supplier_name,
                    "delivery_date": (
                        purchase.delivery_date.isoformat()
                        if hasattr(purchase, "delivery_date")
                        else None
                    ),
                    "status": purchase.status,
                    "items_count": len(items),
                    "total": purchase.total if hasattr(purchase, "total") else 0,
                }
            )

        return result

    def _update_purchase_total(self, purchase_id: str) -> None:
        """
        Update purchase total based on items.

        Args:
            purchase_id: Purchase ID
        """
        # Get purchase items
        items = self.get_purchase_items(purchase_id)

        # Calculate total
        total = sum(item.total for item in items if hasattr(item, "total"))

        # Update purchase
        self.repository.update(purchase_id, {"total": total})

    def _is_valid_status_transition(self, current_status: str, new_status: str) -> bool:
        """
        Check if a status transition is valid.

        Args:
            current_status: Current status
            new_status: New status

        Returns:
            True if valid, False otherwise
        """
        # Same status is always valid
        if current_status == new_status:
            return True

        # Define valid transitions
        valid_transitions = {
            PurchaseStatus.PLANNING.value: [
                PurchaseStatus.PENDING_APPROVAL.value,
                PurchaseStatus.DRAFT.value,
                PurchaseStatus.CANCELLED.value,
            ],
            PurchaseStatus.DRAFT.value: [
                PurchaseStatus.PENDING_APPROVAL.value,
                PurchaseStatus.APPROVED.value,
                PurchaseStatus.CANCELLED.value,
            ],
            PurchaseStatus.PENDING_APPROVAL.value: [
                PurchaseStatus.APPROVED.value,
                PurchaseStatus.PLANNING.value,
                PurchaseStatus.CANCELLED.value,
            ],
            PurchaseStatus.APPROVED.value: [
                PurchaseStatus.ORDERED.value,
                PurchaseStatus.CANCELLED.value,
            ],
            PurchaseStatus.ORDERED.value: [
                PurchaseStatus.ACKNOWLEDGED.value,
                PurchaseStatus.BACKORDERED.value,
                PurchaseStatus.PROCESSING.value,
                PurchaseStatus.SHIPPED.value,
                PurchaseStatus.CANCELLED.value,
            ],
            PurchaseStatus.ACKNOWLEDGED.value: [
                PurchaseStatus.PROCESSING.value,
                PurchaseStatus.BACKORDERED.value,
                PurchaseStatus.SHIPPED.value,
                PurchaseStatus.CANCELLED.value,
            ],
            PurchaseStatus.BACKORDERED.value: [
                PurchaseStatus.PROCESSING.value,
                PurchaseStatus.SHIPPED.value,
                PurchaseStatus.CANCELLED.value,
            ],
            PurchaseStatus.PROCESSING.value: [
                PurchaseStatus.SHIPPED.value,
                PurchaseStatus.PARTIAL_SHIPMENT.value,
                PurchaseStatus.CANCELLED.value,
            ],
            PurchaseStatus.SHIPPED.value: [
                PurchaseStatus.IN_TRANSIT.value,
                PurchaseStatus.PARTIALLY_RECEIVED.value,
                PurchaseStatus.RECEIVED.value,
            ],
            PurchaseStatus.IN_TRANSIT.value: [
                PurchaseStatus.PARTIALLY_RECEIVED.value,
                PurchaseStatus.RECEIVED.value,
            ],
            PurchaseStatus.PARTIAL_SHIPMENT.value: [
                PurchaseStatus.SHIPPED.value,
                PurchaseStatus.PARTIALLY_RECEIVED.value,
            ],
            PurchaseStatus.PARTIALLY_RECEIVED.value: [PurchaseStatus.RECEIVED.value],
            PurchaseStatus.RECEIVED.value: [
                PurchaseStatus.QUALITY_INSPECTION.value,
                PurchaseStatus.COMPLETE.value,
            ],
            PurchaseStatus.QUALITY_INSPECTION.value: [
                PurchaseStatus.COMPLETE.value,
                PurchaseStatus.DISPUTED.value,
            ],
            PurchaseStatus.DISPUTED.value: [
                PurchaseStatus.COMPLETE.value,
                PurchaseStatus.CANCELLED.value,
            ],
        }

        # Check if transition is valid
        return new_status in valid_transitions.get(current_status, [])

    def _create_created_event(self, entity: Purchase) -> DomainEvent:
        """
        Create event for purchase creation.

        Args:
            entity: Created purchase entity

        Returns:
            PurchaseCreated event
        """
        user_id = (
            self.security_context.current_user.id if self.security_context else None
        )
        return PurchaseCreated(
            purchase_id=entity.id,
            supplier_id=entity.supplier_id if hasattr(entity, "supplier_id") else None,
            total=entity.total if hasattr(entity, "total") else 0,
            user_id=user_id,
        )
