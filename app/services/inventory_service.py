# File: services/inventory_service.py

from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.core.events import DomainEvent
from app.core.exceptions import (
    HideSyncException,
    ValidationException,
    EntityNotFoundException,
    BusinessRuleException,
    InsufficientInventoryException,
)
from app.core.validation import validate_input, validate_entity
from app.db.models.enums import (
    InventoryStatus,
    InventoryAdjustmentType,
    TransactionType,
)
from app.db.models.inventory import Inventory, InventoryTransaction
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.inventory_transaction_repository import (
    InventoryTransactionRepository,
)
from app.services.base_service import BaseService
from app.schemas.inventory import InventorySearchParams
from app.db.models.inventory import Inventory

logger = logging.getLogger(__name__)


class InventoryAdjusted(DomainEvent):
    """Event emitted when inventory is adjusted."""

    def __init__(
        self,
        inventory_id: int,
        item_id: int,
        item_type: str,
        previous_quantity: float,
        new_quantity: float,
        adjustment_type: str,
        reason: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize inventory adjusted event.

        Args:
            inventory_id: ID of the inventory record
            item_id: ID of the inventory item
            item_type: Type of inventory item
            previous_quantity: Previous quantity
            new_quantity: New quantity
            adjustment_type: Type of adjustment
            reason: Reason for adjustment
            user_id: Optional ID of the user who made the adjustment
        """
        super().__init__()
        self.inventory_id = inventory_id
        self.item_id = item_id
        self.item_type = item_type
        self.previous_quantity = previous_quantity
        self.new_quantity = new_quantity
        self.adjustment_type = adjustment_type
        self.reason = reason
        self.user_id = user_id


class LowStockAlert(DomainEvent):
    """Event emitted when an item falls below its reorder point."""

    def __init__(
        self,
        inventory_id: int,
        item_id: int,
        item_type: str,
        current_quantity: float,
        reorder_point: float,
    ):
        """
        Initialize low stock alert event.

        Args:
            inventory_id: ID of the inventory record
            item_id: ID of the inventory item
            item_type: Type of inventory item
            current_quantity: Current quantity
            reorder_point: Reorder point threshold
        """
        super().__init__()
        self.inventory_id = inventory_id
        self.item_id = item_id
        self.item_type = item_type
        self.current_quantity = current_quantity
        self.reorder_point = reorder_point


class InventoryTransferred(DomainEvent):
    """Event emitted when inventory is transferred between locations."""

    def __init__(
        self,
        item_id: int,
        item_type: str,
        from_location: str,
        to_location: str,
        quantity: float,
        user_id: Optional[int] = None,
    ):
        """
        Initialize inventory transferred event.

        Args:
            item_id: ID of the inventory item
            item_type: Type of inventory item
            from_location: Source location
            to_location: Destination location
            quantity: Quantity transferred
            user_id: Optional ID of the user who made the transfer
        """
        super().__init__()
        self.item_id = item_id
        self.item_type = item_type
        self.from_location = from_location
        self.to_location = to_location
        self.quantity = quantity
        self.user_id = user_id


class InventoryReconciled(DomainEvent):
    """Event emitted when inventory is reconciled with physical count."""

    def __init__(
        self,
        inventory_id: int,
        item_id: int,
        item_type: str,
        previous_quantity: float,
        new_quantity: float,
        adjustment: float,
        count_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        """
        Initialize inventory reconciled event.

        Args:
            inventory_id: ID of the inventory record
            item_id: ID of the inventory item
            item_type: Type of inventory item
            previous_quantity: Previous quantity
            new_quantity: New quantity after reconciliation
            adjustment: Adjustment amount (positive or negative)
            count_id: Optional ID of the physical count record
            user_id: Optional ID of the user who performed reconciliation
        """
        super().__init__()
        self.inventory_id = inventory_id
        self.item_id = item_id
        self.item_type = item_type
        self.previous_quantity = previous_quantity
        self.new_quantity = new_quantity
        self.adjustment = adjustment
        self.count_id = count_id
        self.user_id = user_id


# Validation functions
validate_inventory = validate_entity(Inventory)
validate_inventory_transaction = validate_entity(InventoryTransaction)


class InventoryService(BaseService[Inventory]):
    """
    Service for managing inventory across all item types in the HideSync system.

    Provides functionality for:
    - Inventory tracking and adjustment
    - Stock level monitoring and alerting
    - Inventory transfers and movements
    - Inventory valuation and reporting
    - Reconciliation and auditing
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        transaction_repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        material_service=None,
        product_service=None,
        tool_service=None,
        storage_service=None,
        supplier_service=None,
    ):
        """
        Initialize InventoryService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository for inventory (defaults to InventoryRepository)
            transaction_repository: Optional repository for inventory transactions
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            material_service: Optional material service for material operations
            product_service: Optional product service for product operations
            tool_service: Optional tool service for tool operations
            storage_service: Optional storage service for location operations
            supplier_service: Optional supplier service for supplier operations
        """
        self.session = session
        self.repository = repository or InventoryRepository(session)
        self.transaction_repository = (
            transaction_repository or InventoryTransactionRepository(session)
        )
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.material_service = material_service
        self.product_service = product_service
        self.tool_service = tool_service
        self.storage_service = storage_service
        self.supplier_service = supplier_service

    def get_inventory_status(
        self, item_type: str, item_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get the current inventory status for an item.

        Args:
            item_type: Type of item (material, product, tool)
            item_id: ID of the item

        Returns:
            Inventory status with details, or None if not found

        Raises:
            ValidationException: If invalid item type
        """
        # Validate item type
        valid_item_types = ["material", "product", "tool"]
        if item_type.lower() not in valid_item_types:
            raise ValidationException(
                f"Invalid item type: {item_type}",
                {"item_type": [f"Must be one of: {', '.join(valid_item_types)}"]},
            )

        # Check cache first
        if self.cache_service:
            cache_key = f"Inventory:{item_type}:{item_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get inventory record
        inventory = self.repository.get_by_item(item_type.lower(), item_id)
        if not inventory:
            return None

        # Convert to dict
        result = inventory.to_dict()

        # Add item details
        result["item_details"] = self._get_item_details(item_type, item_id)

        # Add location details if available
        if inventory.storage_location and self.storage_service:
            location = self.storage_service.get_by_id(inventory.storage_location)
            if location:
                result["location_details"] = {
                    "id": location.id,
                    "name": location.name,
                    "type": location.type,
                    "section": location.section,
                }

        # Add inventory metrics
        result["metrics"] = self._calculate_inventory_metrics(inventory)

        # Add recent transactions
        result["recent_transactions"] = self._get_recent_transactions(
            item_type, item_id, limit=5
        )

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, result, ttl=1800)  # 30 minutes TTL

        return result

    def adjust_inventory(
        self,
        item_type: str,
        item_id: int,
        quantity_change: float,
        adjustment_type: Union[InventoryAdjustmentType, str],
        reason: str,
        reference_id: Optional[str] = None,
        location_id: Optional[str] = None,
    ) -> Inventory:
        """
        Adjust inventory level for an item with audit trail.

        Args:
            item_type: Type of item (material, product, tool)
            item_id: ID of the item
            quantity_change: Amount to change (positive or negative)
            adjustment_type: Type of adjustment
            reason: Reason for adjustment
            reference_id: Optional reference ID (e.g., sale ID, project ID)
            location_id: Optional storage location ID

        Returns:
            Updated inventory record

        Raises:
            ValidationException: If validation fails
            EntityNotFoundException: If inventory record not found
            InsufficientInventoryException: If adjustment would result in negative quantity
        """
        # Validate item type
        valid_item_types = ["material", "product", "tool"]
        if item_type.lower() not in valid_item_types:
            raise ValidationException(
                f"Invalid item type: {item_type}",
                {"item_type": [f"Must be one of: {', '.join(valid_item_types)}"]},
            )

        # Validate adjustment type
        if isinstance(adjustment_type, str):
            try:
                adjustment_type = InventoryAdjustmentType(adjustment_type)
            except ValueError:
                raise ValidationException(
                    f"Invalid adjustment type: {adjustment_type}",
                    {
                        "adjustment_type": [
                            f"Must be one of: {', '.join([a.value for a in InventoryAdjustmentType])}"
                        ]
                    },
                )

        # Begin transaction
        with self.transaction():
            # Get inventory record
            inventory = self.repository.get_by_item(item_type.lower(), item_id)

            # If no inventory record exists, create one
            if not inventory:
                inventory_data = {
                    "item_type": item_type.lower(),
                    "item_id": item_id,
                    "quantity": max(0, quantity_change),
                    "status": (
                        InventoryStatus.IN_STOCK.value
                        if quantity_change > 0
                        else InventoryStatus.OUT_OF_STOCK.value
                    ),
                    "storage_location": location_id,
                }

                inventory = self.repository.create(inventory_data)
                previous_quantity = 0
            else:
                # Store previous values
                previous_quantity = inventory.quantity or 0

                # Calculate new quantity
                new_quantity = previous_quantity + quantity_change

                # Check for negative quantity
                if new_quantity < 0:
                    raise InsufficientInventoryException(
                        f"Insufficient inventory for {item_type} {item_id}. Available: {previous_quantity}, Requested: {abs(quantity_change)}",
                        "INVENTORY_001",
                        {
                            "item_type": item_type,
                            "item_id": item_id,
                            "available": previous_quantity,
                            "requested": abs(quantity_change),
                        },
                    )

                # Determine new status
                new_status = self._determine_inventory_status(
                    item_type, item_id, new_quantity
                )

                # Update inventory
                update_data = {"quantity": new_quantity, "status": new_status}

                # Update location if provided
                if location_id:
                    update_data["storage_location"] = location_id

                inventory = self.repository.update(inventory.id, update_data)

            # Create transaction record
            transaction_data = {
                "item_type": item_type.lower(),
                "item_id": item_id,
                "quantity_change": quantity_change,
                "transaction_type": TransactionType.ADJUSTMENT.value,
                "adjustment_type": adjustment_type.value,
                "reason": reason,
                "reference_id": reference_id,
                "storage_location": location_id,
                "transaction_date": datetime.now(),
                "user_id": (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                ),
            }

            self.transaction_repository.create(transaction_data)

            # Publish inventory adjusted event
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    InventoryAdjusted(
                        inventory_id=inventory.id,
                        item_id=item_id,
                        item_type=item_type,
                        previous_quantity=previous_quantity,
                        new_quantity=inventory.quantity,
                        adjustment_type=adjustment_type.value,
                        reason=reason,
                        user_id=user_id,
                    )
                )

            # Check for low stock and emit alert if needed
            self._check_low_stock(inventory)

            # Update item in corresponding service if needed
            self._update_item_inventory(item_type, item_id, inventory.quantity)

            # Invalidate cache
            if self.cache_service:
                self.cache_service.invalidate(f"Inventory:{item_type}:{item_id}")

            return inventory

    def transfer_inventory(
        self,
        item_type: str,
        item_id: int,
        quantity: float,
        from_location: str,
        to_location: str,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Transfer inventory between storage locations.

        Args:
            item_type: Type of item (material, product, tool)
            item_id: ID of the item
            quantity: Quantity to transfer
            from_location: Source location ID
            to_location: Destination location ID
            reason: Reason for transfer

        Returns:
            Dictionary with transfer results

        Raises:
            ValidationException: If validation fails
            EntityNotFoundException: If inventory record or locations not found
            InsufficientInventoryException: If source has insufficient quantity
        """
        with self.transaction():
            # Check if inventory exists at source location
            inventory = self.repository.get_by_item_and_location(
                item_type.lower(), item_id, from_location
            )

            if not inventory or inventory.quantity < quantity:
                available = inventory.quantity if inventory else 0
                raise InsufficientInventoryException(
                    f"Insufficient inventory at source location. Available: {available}, Requested: {quantity}",
                    "INVENTORY_002",
                    {
                        "item_type": item_type,
                        "item_id": item_id,
                        "location": from_location,
                        "available": available,
                        "requested": quantity,
                    },
                )

            # Check if source and destination locations exist
            if self.storage_service:
                source_location = self.storage_service.get_by_id(from_location)
                destination_location = self.storage_service.get_by_id(to_location)

                if not source_location:
                    from app.core.exceptions import StorageLocationNotFoundException

                    raise StorageLocationNotFoundException(from_location)

                if not destination_location:
                    from app.core.exceptions import StorageLocationNotFoundException

                    raise StorageLocationNotFoundException(to_location)

            # Reduce inventory at source location
            self.adjust_inventory(
                item_type=item_type,
                item_id=item_id,
                quantity_change=-quantity,
                adjustment_type=InventoryAdjustmentType.TRANSFER,
                reason=f"Transfer to {to_location}: {reason}",
                location_id=from_location,
            )

            # Add inventory at destination location
            dest_inventory = self.repository.get_by_item_and_location(
                item_type.lower(), item_id, to_location
            )

            if dest_inventory:
                # Update existing inventory at destination
                self.adjust_inventory(
                    item_type=item_type,
                    item_id=item_id,
                    quantity_change=quantity,
                    adjustment_type=InventoryAdjustmentType.TRANSFER,
                    reason=f"Transfer from {from_location}: {reason}",
                    location_id=to_location,
                )
            else:
                # Create new inventory record at destination
                inventory_data = {
                    "item_type": item_type.lower(),
                    "item_id": item_id,
                    "quantity": quantity,
                    "status": InventoryStatus.IN_STOCK.value,
                    "storage_location": to_location,
                }

                self.repository.create(inventory_data)

                # Create transaction record
                transaction_data = {
                    "item_type": item_type.lower(),
                    "item_id": item_id,
                    "quantity_change": quantity,
                    "transaction_type": TransactionType.TRANSFER.value,
                    "adjustment_type": InventoryAdjustmentType.TRANSFER.value,
                    "reason": f"Transfer from {from_location}: {reason}",
                    "storage_location": to_location,
                    "transaction_date": datetime.now(),
                    "user_id": (
                        self.security_context.current_user.id
                        if self.security_context
                        else None
                    ),
                }

                self.transaction_repository.create(transaction_data)

            # Publish transfer event
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    InventoryTransferred(
                        item_id=item_id,
                        item_type=item_type,
                        from_location=from_location,
                        to_location=to_location,
                        quantity=quantity,
                        user_id=user_id,
                    )
                )

            # If storage service is available, use it to record the move
            if self.storage_service and hasattr(
                self.storage_service, "move_material_between_locations"
            ):
                self.storage_service.move_material_between_locations(
                    {
                        "material_id": item_id,
                        "material_type": item_type,
                        "from_storage_id": from_location,
                        "to_storage_id": to_location,
                        "quantity": quantity,
                        "reason": reason,
                    }
                )

            # Return transfer results
            return {
                "item_type": item_type,
                "item_id": item_id,
                "quantity": quantity,
                "from_location": from_location,
                "to_location": to_location,
                "timestamp": datetime.now().isoformat(),
                "status": "completed",
                "user_id": (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                ),
            }

    def get_low_stock_items(
        self, threshold_percentage: float = 20.0, item_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get items that are below their reorder threshold.

        Args:
            threshold_percentage: Percentage of reorder point to use as threshold
            item_type: Optional item type to filter by

        Returns:
            List of items below reorder threshold
        """
        # Use repository to get low stock items
        items = self.repository.get_low_stock_items(threshold_percentage, item_type)

        # Enrich with item details
        result = []
        for inventory in items:
            item_details = self._get_item_details(
                inventory.item_type, inventory.item_id
            )
            if not item_details:
                continue  # Skip if item details not found

            # Get reorder point based on item type
            reorder_point = item_details.get("reorder_point", 0)

            # Calculate days until stockout based on usage rate
            days_until_stockout = self._calculate_days_until_stockout(
                inventory.item_type, inventory.item_id, inventory.quantity
            )

            result.append(
                {
                    "inventory_id": inventory.id,
                    "item_type": inventory.item_type,
                    "item_id": inventory.item_id,
                    "name": item_details.get("name", f"Unknown {inventory.item_type}"),
                    "current_quantity": inventory.quantity,
                    "reorder_point": reorder_point,
                    "percentage_of_reorder": round(
                        (
                            (inventory.quantity / reorder_point * 100)
                            if reorder_point > 0
                            else 0
                        ),
                        1,
                    ),
                    "status": inventory.status,
                    "storage_location": inventory.storage_location,
                    "days_until_stockout": days_until_stockout,
                    "supplier_id": item_details.get("supplier_id"),
                    "supplier_name": item_details.get("supplier_name"),
                    "last_purchase_date": item_details.get("last_purchase_date"),
                    "unit": item_details.get("unit"),
                    "typical_lead_time": item_details.get("lead_time"),
                }
            )

        # Sort by percentage of reorder point (ascending)
        return sorted(result, key=lambda x: x["percentage_of_reorder"])

    def list_inventory_items(
            self, skip: int, limit: int, search_params: InventorySearchParams
    ) -> List[Inventory]:
        """
        Retrieve a list of inventory items with filtering and pagination.
        """
        logger.info(f"Listing inventory items: skip={skip}, limit={limit}, params={search_params}")
        # Assuming InventoryRepository has a method to handle this
        # You might need to adapt the repository method call based on its actual implementation
        items = self.repository.list_with_filters(
            skip=skip,
            limit=limit,
            # Pass filters - adjust based on repository method signature
            status=search_params.status,
            location=search_params.location,
            item_type=search_params.item_type,
            search_term=search_params.search
        )
        logger.info(f"Found {len(items)} inventory items.")
        return items


    def reconcile_inventory(
        self,
        item_type: str,
        item_id: int,
        actual_quantity: float,
        count_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Reconcile inventory based on physical count.

        Args:
            item_type: Type of item (material, product, tool)
            item_id: ID of the item
            actual_quantity: Actual quantity from physical count
            count_id: Optional ID of the physical count record
            notes: Optional notes about the reconciliation

        Returns:
            Dictionary with reconciliation results

        Raises:
            ValidationException: If validation fails
            EntityNotFoundException: If inventory record not found
        """
        with self.transaction():
            # Get inventory record
            inventory = self.repository.get_by_item(item_type.lower(), item_id)
            if not inventory:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException(
                    f"No inventory record found for {item_type} with ID {item_id}",
                    entity_type=item_type,
                )

            # Calculate adjustment
            previous_quantity = inventory.quantity or 0
            adjustment = actual_quantity - previous_quantity

            # Record the adjustment
            if adjustment != 0:
                adjustment_type = InventoryAdjustmentType.INVENTORY_CORRECTION
                reason = (
                    f"Inventory reconciliation: {notes}"
                    if notes
                    else "Inventory reconciliation"
                )

                inventory = self.adjust_inventory(
                    item_type=item_type,
                    item_id=item_id,
                    quantity_change=adjustment,
                    adjustment_type=adjustment_type,
                    reason=reason,
                    reference_id=count_id,
                    location_id=inventory.storage_location,
                )

            # Publish reconciliation event
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    InventoryReconciled(
                        inventory_id=inventory.id,
                        item_id=item_id,
                        item_type=item_type,
                        previous_quantity=previous_quantity,
                        new_quantity=actual_quantity,
                        adjustment=adjustment,
                        count_id=count_id,
                        user_id=user_id,
                    )
                )

            # Return reconciliation results
            return {
                "inventory_id": inventory.id,
                "item_type": item_type,
                "item_id": item_id,
                "previous_quantity": previous_quantity,
                "actual_quantity": actual_quantity,
                "adjustment": adjustment,
                "adjustment_percentage": round(
                    (
                        (adjustment / previous_quantity * 100)
                        if previous_quantity > 0
                        else 0
                    ),
                    1,
                ),
                "count_id": count_id,
                "timestamp": datetime.now().isoformat(),
                "user_id": (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                ),
                "notes": notes,
            }

    def calculate_inventory_value(
        self, as_of_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate the total value of inventory.

        Args:
            as_of_date: Optional date to calculate value as of

        Returns:
            Dictionary with inventory valuation results
        """
        if not as_of_date:
            as_of_date = datetime.now()

        # Get all inventory records
        inventories = self.repository.list()

        # Initialize valuation results
        total_value = 0.0
        by_type = {
            "material": {"count": 0, "value": 0.0},
            "product": {"count": 0, "value": 0.0},
            "tool": {"count": 0, "value": 0.0},
        }

        # Calculate value for each item
        items_detail = []
        for inventory in inventories:
            item_type = inventory.item_type
            item_id = inventory.item_id
            quantity = inventory.quantity or 0

            # Skip if no quantity
            if quantity <= 0:
                continue

            # Get item details
            item_details = self._get_item_details(item_type, item_id)
            if not item_details:
                continue  # Skip if item details not found

            # Get unit cost/value
            unit_cost = item_details.get("cost", 0)

            # Calculate item value
            item_value = quantity * unit_cost

            # Add to totals
            total_value += item_value

            if item_type in by_type:
                by_type[item_type]["count"] += 1
                by_type[item_type]["value"] += item_value

            # Add to items detail
            items_detail.append(
                {
                    "inventory_id": inventory.id,
                    "item_type": item_type,
                    "item_id": item_id,
                    "name": item_details.get("name", f"Unknown {item_type}"),
                    "quantity": quantity,
                    "unit": item_details.get("unit"),
                    "unit_cost": unit_cost,
                    "total_value": item_value,
                    "location": inventory.storage_location,
                }
            )

        # Return valuation results
        return {
            "as_of_date": as_of_date.isoformat(),
            "total_value": round(total_value, 2),
            "item_count": sum(t["count"] for t in by_type.values()),
            "by_type": by_type,
            "items": sorted(items_detail, key=lambda x: x["total_value"], reverse=True),
        }

    def generate_inventory_report(
        self, report_type: str, filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate an inventory report based on specified type and filters.

        Args:
            report_type: Type of report (summary, detail, valuation, movement)
            filters: Optional filters to apply to the report

        Returns:
            Dictionary with report results

        Raises:
            ValidationException: If invalid report type
        """
        # Validate report type
        valid_report_types = ["summary", "detail", "valuation", "movement", "low_stock"]
        if report_type.lower() not in valid_report_types:
            raise ValidationException(
                f"Invalid report type: {report_type}",
                {"report_type": [f"Must be one of: {', '.join(valid_report_types)}"]},
            )

        # Initialize filters
        if not filters:
            filters = {}

        # Get current date/time for report metadata
        now = datetime.now()

        # Generate report based on type
        if report_type.lower() == "summary":
            return self._generate_summary_report(filters)
        elif report_type.lower() == "detail":
            return self._generate_detail_report(filters)
        elif report_type.lower() == "valuation":
            return self.calculate_inventory_value(
                as_of_date=filters.get("as_of_date", now)
            )
        elif report_type.lower() == "movement":
            return self._generate_movement_report(filters)
        elif report_type.lower() == "low_stock":
            threshold = filters.get("threshold_percentage", 20.0)
            item_type = filters.get("item_type")
            low_stock_items = self.get_low_stock_items(threshold, item_type)

            return {
                "report_type": "low_stock",
                "generated_at": now.isoformat(),
                "threshold_percentage": threshold,
                "item_type": item_type,
                "item_count": len(low_stock_items),
                "items": low_stock_items,
            }

    def perform_inventory_audit(
        self, location_id: Optional[str] = None, item_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Prepare for an inventory audit by generating counting sheets.

        Args:
            location_id: Optional location ID to audit
            item_type: Optional item type to audit

        Returns:
            Dictionary with audit preparation results
        """
        # Get inventory records based on filters
        filters = {}
        if location_id:
            filters["storage_location"] = location_id
        if item_type:
            filters["item_type"] = item_type

        inventories = self.repository.list(**filters)

        # Group by location for more efficient counting
        by_location = {}
        for inventory in inventories:
            location = inventory.storage_location or "Unassigned"

            if location not in by_location:
                by_location[location] = []

            # Get item details
            item_details = self._get_item_details(
                inventory.item_type, inventory.item_id
            )

            by_location[location].append(
                {
                    "inventory_id": inventory.id,
                    "item_type": inventory.item_type,
                    "item_id": inventory.item_id,
                    "name": item_details.get("name", f"Unknown {inventory.item_type}"),
                    "system_quantity": inventory.quantity,
                    "unit": item_details.get("unit"),
                    "counted_quantity": None,  # To be filled during audit
                    "notes": None,  # To be filled during audit
                }
            )

        # Generate audit ID
        audit_id = f"AUDIT-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        # Return audit preparation results
        return {
            "audit_id": audit_id,
            "prepared_at": datetime.now().isoformat(),
            "location_id": location_id,
            "item_type": item_type,
            "total_items": len(inventories),
            "locations": len(by_location),
            "counting_sheets": by_location,
            "status": "prepared",
        }

    def _get_item_details(
        self, item_type: str, item_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get details for an inventory item based on type.

        Args:
            item_type: Type of item (material, product, tool)
            item_id: ID of the item

        Returns:
            Dictionary with item details, or None if not found
        """
        if item_type.lower() == "material" and self.material_service:
            material = self.material_service.get_by_id(item_id)
            if material:
                supplier_name = None
                if hasattr(material, "supplier") and material.supplier:
                    supplier_name = material.supplier
                elif (
                    hasattr(material, "supplier_id")
                    and material.supplier_id
                    and self.supplier_service
                ):
                    supplier = self.supplier_service.get_by_id(material.supplier_id)
                    if supplier:
                        supplier_name = supplier.name

                return {
                    "name": material.name,
                    "material_type": getattr(material, "material_type", None),
                    "unit": getattr(material, "unit", None),
                    "reorder_point": getattr(material, "reorder_point", 0),
                    "cost": getattr(material, "cost", 0),
                    "supplier_id": getattr(material, "supplier_id", None),
                    "supplier_name": supplier_name,
                    "last_purchase_date": getattr(material, "last_purchased", None),
                }

        elif item_type.lower() == "product" and self.product_service:
            product = self.product_service.get_by_id(item_id)
            if product:
                return {
                    "name": product.name,
                    "product_type": getattr(product, "product_type", None),
                    "sku": getattr(product, "sku", None),
                    "unit": "piece",  # Products are typically counted as pieces
                    "reorder_point": getattr(product, "reorder_point", 0),
                    "cost": getattr(product, "total_cost", 0),
                    "price": getattr(product, "selling_price", 0),
                }

        elif item_type.lower() == "tool" and self.tool_service:
            tool = self.tool_service.get_by_id(item_id)
            if tool:
                return {
                    "name": tool.name,
                    "category": getattr(tool, "category", None),
                    "unit": "piece",  # Tools are typically counted as pieces
                    "cost": getattr(tool, "purchase_price", 0),
                    "supplier_id": getattr(tool, "supplier_id", None),
                    "last_maintenance": getattr(tool, "last_maintenance", None),
                }

        return None

    def _determine_inventory_status(
        self, item_type: str, item_id: int, quantity: float
    ) -> str:
        """
        Determine inventory status based on quantity and item details.

        Args:
            item_type: Type of item (material, product, tool)
            item_id: ID of the item
            quantity: Current quantity

        Returns:
            Inventory status value
        """
        # If quantity is zero or negative, it's out of stock
        if quantity <= 0:
            return InventoryStatus.OUT_OF_STOCK.value

        # Get item details
        item_details = self._get_item_details(item_type, item_id)
        reorder_point = 0

        if item_details:
            reorder_point = item_details.get("reorder_point", 0)

        # Check if it's below reorder point (low stock)
        if reorder_point > 0 and quantity <= reorder_point:
            return InventoryStatus.LOW_STOCK.value

        # Default to in stock
        return InventoryStatus.IN_STOCK.value

    def _check_low_stock(self, inventory: Inventory) -> None:
        """
        Check if inventory is below reorder point and emit alert if needed.

        Args:
            inventory: Inventory record to check
        """
        if not self.event_bus:
            return

        # Get item details
        item_details = self._get_item_details(inventory.item_type, inventory.item_id)
        if not item_details:
            return

        reorder_point = item_details.get("reorder_point", 0)

        # No need to check if reorder point is not set
        if reorder_point <= 0:
            return

        # Check if below reorder point
        if inventory.quantity <= reorder_point:
            self.event_bus.publish(
                LowStockAlert(
                    inventory_id=inventory.id,
                    item_id=inventory.item_id,
                    item_type=inventory.item_type,
                    current_quantity=inventory.quantity,
                    reorder_point=reorder_point,
                )
            )

    def _update_item_inventory(
        self, item_type: str, item_id: int, quantity: float
    ) -> None:
        """
        Update inventory quantity in the corresponding item service.

        Args:
            item_type: Type of item (material, product, tool)
            item_id: ID of the item
            quantity: New quantity
        """
        # Update material quantity
        if item_type.lower() == "material" and self.material_service:
            if hasattr(self.material_service, "update_quantity"):
                self.material_service.update_quantity(
                    material_id=item_id, quantity=quantity
                )

        # Update product quantity
        elif item_type.lower() == "product" and self.product_service:
            if hasattr(self.product_service, "update_quantity"):
                self.product_service.update_quantity(
                    product_id=item_id, quantity=quantity
                )

        # Update tool status
        elif item_type.lower() == "tool" and self.tool_service:
            if hasattr(self.tool_service, "update_status"):
                status = "IN_STOCK" if quantity > 0 else "OUT_OF_STOCK"
                self.tool_service.update_status(tool_id=item_id, status=status)

    def _get_recent_transactions(
        self, item_type: str, item_id: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent transactions for an item.

        Args:
            item_type: Type of item (material, product, tool)
            item_id: ID of the item
            limit: Maximum number of transactions to return

        Returns:
            List of recent transactions
        """
        transactions = self.transaction_repository.get_by_item(
            item_type=item_type.lower(), item_id=item_id, limit=limit
        )

        return [
            {
                "id": transaction.id,
                "transaction_type": transaction.transaction_type,
                "adjustment_type": transaction.adjustment_type,
                "quantity_change": transaction.quantity_change,
                "reason": transaction.reason,
                "reference_id": transaction.reference_id,
                "storage_location": transaction.storage_location,
                "date": (
                    transaction.transaction_date.isoformat()
                    if transaction.transaction_date
                    else None
                ),
                "user_id": transaction.user_id,
            }
            for transaction in transactions
        ]

    def _calculate_inventory_metrics(self, inventory: Inventory) -> Dict[str, Any]:
        """
        Calculate metrics for an inventory item.

        Args:
            inventory: Inventory record

        Returns:
            Dictionary with inventory metrics
        """
        # Initialize metrics
        metrics = {
            "turnover_rate": 0,
            "days_on_hand": 0,
            "usage_trend": "stable",
            "last_movement": None,
            "days_since_last_movement": 0,
        }

        # Get recent transactions
        recent_transactions = self.transaction_repository.get_by_item(
            item_type=inventory.item_type, item_id=inventory.item_id, limit=100
        )

        if not recent_transactions:
            return metrics

        # Find last movement
        last_movement = max(
            (t for t in recent_transactions if t.transaction_date),
            key=lambda t: t.transaction_date,
            default=None,
        )

        if last_movement:
            metrics["last_movement"] = last_movement.transaction_date.isoformat()
            days_since = (datetime.now() - last_movement.transaction_date).days
            metrics["days_since_last_movement"] = days_since

        # Calculate usage over time
        usage_transactions = [
            t
            for t in recent_transactions
            if t.quantity_change < 0
            and t.transaction_type != TransactionType.INVENTORY_CORRECTION.value
        ]

        if usage_transactions:
            # Calculate average daily usage
            earliest_date = min(t.transaction_date for t in usage_transactions)
            days_span = max(1, (datetime.now() - earliest_date).days)

            total_usage = sum(abs(t.quantity_change) for t in usage_transactions)
            avg_daily_usage = total_usage / days_span

            if avg_daily_usage > 0 and inventory.quantity > 0:
                # Calculate days on hand
                days_on_hand = inventory.quantity / avg_daily_usage
                metrics["days_on_hand"] = round(days_on_hand)

                # Calculate turnover rate (annualized)
                annual_usage = avg_daily_usage * 365
                avg_inventory = inventory.quantity / 2  # Simplified average inventory
                if avg_inventory > 0:
                    turnover_rate = annual_usage / avg_inventory
                    metrics["turnover_rate"] = round(turnover_rate, 1)

            # Determine usage trend
            if len(usage_transactions) >= 4:
                # Split into two equal periods
                sorted_transactions = sorted(
                    usage_transactions, key=lambda t: t.transaction_date
                )
                mid_point = len(sorted_transactions) // 2

                early_usage = sum(
                    abs(t.quantity_change) for t in sorted_transactions[:mid_point]
                )
                late_usage = sum(
                    abs(t.quantity_change) for t in sorted_transactions[mid_point:]
                )

                # Compare usage between periods
                if late_usage > early_usage * 1.2:  # 20% increase
                    metrics["usage_trend"] = "increasing"
                elif late_usage < early_usage * 0.8:  # 20% decrease
                    metrics["usage_trend"] = "decreasing"

        return metrics

    def _calculate_days_until_stockout(
        self, item_type: str, item_id: int, current_quantity: float
    ) -> Optional[int]:
        """
        Calculate estimated days until stockout based on usage rate.

        Args:
            item_type: Type of item (material, product, tool)
            item_id: ID of the item
            current_quantity: Current quantity

        Returns:
            Estimated days until stockout, or None if cannot be calculated
        """
        # If no quantity, already stocked out
        if current_quantity <= 0:
            return 0

        # Get usage transactions for the last 90 days
        from_date = datetime.now() - timedelta(days=90)

        usage_transactions = self.transaction_repository.get_by_item_and_type(
            item_type=item_type,
            item_id=item_id,
            transaction_type=TransactionType.USAGE.value,
            from_date=from_date,
        )

        # Add other negative adjustments (except transfers and corrections)
        negative_adjustments = self.transaction_repository.get_negative_adjustments(
            item_type=item_type,
            item_id=item_id,
            from_date=from_date,
            exclude_types=[
                TransactionType.TRANSFER.value,
                TransactionType.INVENTORY_CORRECTION.value,
            ],
        )

        all_usage = usage_transactions + negative_adjustments

        if not all_usage:
            return None  # Cannot calculate without usage history

        # Calculate average daily usage
        total_usage = sum(abs(t.quantity_change) for t in all_usage)
        days_span = max(1, (datetime.now() - from_date).days)

        avg_daily_usage = total_usage / days_span

        if avg_daily_usage <= 0:
            return None  # No usage, cannot calculate

        # Calculate days until stockout
        days_until_stockout = current_quantity / avg_daily_usage

        return round(days_until_stockout)

    def _generate_summary_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate summary inventory report.

        Args:
            filters: Report filters

        Returns:
            Dictionary with summary report results
        """
        # Get all inventory records
        item_type = filters.get("item_type")
        status = filters.get("status")
        location = filters.get("location")

        query_filters = {}
        if item_type:
            query_filters["item_type"] = item_type
        if status:
            query_filters["status"] = status
        if location:
            query_filters["storage_location"] = location

        inventories = self.repository.list(**query_filters)

        # Initialize summary data
        summary = {
            "report_type": "summary",
            "generated_at": datetime.now().isoformat(),
            "filters": filters,
            "total_items": len(inventories),
            "total_quantity": sum(i.quantity or 0 for i in inventories),
            "by_type": {},
            "by_status": {},
            "by_location": {},
        }

        # Aggregate by type
        for inventory in inventories:
            item_type = inventory.item_type
            status = inventory.status
            location = inventory.storage_location or "Unassigned"
            quantity = inventory.quantity or 0

            # By type
            if item_type not in summary["by_type"]:
                summary["by_type"][item_type] = {"count": 0, "quantity": 0}
            summary["by_type"][item_type]["count"] += 1
            summary["by_type"][item_type]["quantity"] += quantity

            # By status
            if status not in summary["by_status"]:
                summary["by_status"][status] = {"count": 0, "quantity": 0}
            summary["by_status"][status]["count"] += 1
            summary["by_status"][status]["quantity"] += quantity

            # By location
            if location not in summary["by_location"]:
                summary["by_location"][location] = {"count": 0, "quantity": 0}
            summary["by_location"][location]["count"] += 1
            summary["by_location"][location]["quantity"] += quantity

        # Add value if we can calculate it
        try:
            valuation = self.calculate_inventory_value()
            summary["total_value"] = valuation["total_value"]
            summary["by_type_value"] = {
                t: details["value"] for t, details in valuation["by_type"].items()
            }
        except:
            # Skip valuation if it fails
            pass

        return summary

    def _generate_detail_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate detailed inventory report.

        Args:
            filters: Report filters

        Returns:
            Dictionary with detailed report results
        """
        # Get all inventory records
        item_type = filters.get("item_type")
        status = filters.get("status")
        location = filters.get("location")

        query_filters = {}
        if item_type:
            query_filters["item_type"] = item_type
        if status:
            query_filters["status"] = status
        if location:
            query_filters["storage_location"] = location

        inventories = self.repository.list(**query_filters)

        # Initialize detail report
        report = {
            "report_type": "detail",
            "generated_at": datetime.now().isoformat(),
            "filters": filters,
            "total_items": len(inventories),
            "items": [],
        }

        # Add detailed item information
        for inventory in inventories:
            item_type = inventory.item_type
            item_id = inventory.item_id

            # Get item details
            item_details = self._get_item_details(item_type, item_id)
            if not item_details:
                continue

            # Get metrics
            metrics = self._calculate_inventory_metrics(inventory)

            # Add to items list
            report["items"].append(
                {
                    "inventory_id": inventory.id,
                    "item_type": item_type,
                    "item_id": item_id,
                    "name": item_details.get("name", f"Unknown {item_type}"),
                    "status": inventory.status,
                    "quantity": inventory.quantity,
                    "unit": item_details.get("unit"),
                    "reorder_point": item_details.get("reorder_point", 0),
                    "location": inventory.storage_location,
                    "cost": item_details.get("cost", 0),
                    "value": (inventory.quantity or 0)
                    * (item_details.get("cost", 0) or 0),
                    "turnover_rate": metrics["turnover_rate"],
                    "days_on_hand": metrics["days_on_hand"],
                    "usage_trend": metrics["usage_trend"],
                    "last_movement": metrics["last_movement"],
                }
            )

        # Sort by value (descending)
        report["items"] = sorted(
            report["items"], key=lambda x: x["value"], reverse=True
        )

        return report

    def _generate_movement_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate inventory movement report.

        Args:
            filters: Report filters

        Returns:
            Dictionary with movement report results
        """
        # Get date range from filters
        from_date = filters.get("from_date")
        if isinstance(from_date, str):
            from_date = datetime.fromisoformat(from_date)
        elif not from_date:
            from_date = datetime.now() - timedelta(days=30)

        to_date = filters.get("to_date")
        if isinstance(to_date, str):
            to_date = datetime.fromisoformat(to_date)
        elif not to_date:
            to_date = datetime.now()

        # Get additional filters
        item_type = filters.get("item_type")
        transaction_type = filters.get("transaction_type")
        location = filters.get("location")

        # Get transactions
        query_filters = {"from_date": from_date, "to_date": to_date}

        if item_type:
            query_filters["item_type"] = item_type
        if transaction_type:
            query_filters["transaction_type"] = transaction_type
        if location:
            query_filters["storage_location"] = location

        transactions = self.transaction_repository.get_by_date_range(**query_filters)

        # Initialize movement report
        report = {
            "report_type": "movement",
            "generated_at": datetime.now().isoformat(),
            "filters": {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "item_type": item_type,
                "transaction_type": transaction_type,
                "location": location,
            },
            "total_transactions": len(transactions),
            "date_range_days": (to_date - from_date).days,
            "by_transaction_type": {},
            "by_item_type": {},
            "by_day": {},
            "transactions": [],
        }

        # Aggregate by transaction type and item type
        for transaction in transactions:
            trans_type = transaction.transaction_type
            item_type = transaction.item_type
            quantity_change = transaction.quantity_change
            transaction_date = transaction.transaction_date

            # Skip if no date
            if not transaction_date:
                continue

            day_key = transaction_date.strftime("%Y-%m-%d")

            # By transaction type
            if trans_type not in report["by_transaction_type"]:
                report["by_transaction_type"][trans_type] = {
                    "count": 0,
                    "total_quantity": 0,
                }
            report["by_transaction_type"][trans_type]["count"] += 1
            report["by_transaction_type"][trans_type][
                "total_quantity"
            ] += quantity_change

            # By item type
            if item_type not in report["by_item_type"]:
                report["by_item_type"][item_type] = {"count": 0, "total_quantity": 0}
            report["by_item_type"][item_type]["count"] += 1
            report["by_item_type"][item_type]["total_quantity"] += quantity_change

            # By day
            if day_key not in report["by_day"]:
                report["by_day"][day_key] = {"count": 0, "total_quantity": 0}
            report["by_day"][day_key]["count"] += 1
            report["by_day"][day_key]["total_quantity"] += quantity_change

            # Get item details
            item_details = self._get_item_details(
                transaction.item_type, transaction.item_id
            )

            # Add to transactions list
            report["transactions"].append(
                {
                    "id": transaction.id,
                    "item_type": transaction.item_type,
                    "item_id": transaction.item_id,
                    "item_name": (
                        item_details.get("name", f"Unknown {transaction.item_type}")
                        if item_details
                        else f"Unknown {transaction.item_type}"
                    ),
                    "transaction_type": transaction.transaction_type,
                    "adjustment_type": transaction.adjustment_type,
                    "quantity_change": transaction.quantity_change,
                    "reason": transaction.reason,
                    "reference_id": transaction.reference_id,
                    "location": transaction.storage_location,
                    "date": transaction_date.isoformat(),
                    "user_id": transaction.user_id,
                }
            )

        # Sort by date (newest first)
        report["transactions"] = sorted(
            report["transactions"], key=lambda x: x["date"], reverse=True
        )

        return report
