# File: services/inventory_service.py

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

# --- Application Imports ---
# Adjust paths as per your project structure
from app.core.events import DomainEvent
from app.core.exceptions import (
    BusinessRuleException,
    EntityNotFoundException,
    HideSyncException,
    InsufficientInventoryException,
    StorageLocationNotFoundException, # Assuming this exists
    ValidationException,
)
from app.core.validation import validate_input, validate_entity # Assuming these helpers exist
from app.db.models.enums import (
    InventoryAdjustmentType,
    InventoryStatus,
    TransactionType,
)
from app.db.models.inventory import Inventory, InventoryTransaction
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.inventory_transaction_repository import (
    InventoryTransactionRepository,
)
# Import schemas used for input/output structuring if needed by public methods
from app.schemas.inventory import (
    InventoryAdjustment, # Use specific schema for adjustment input if defined
    InventorySearchParams,
    InventoryTransactionCreate, # Use specific schema for transaction input if defined
)
from app.services.base_service import BaseService
# Import other services needed for item details (ensure they are injected)
# from app.services.product_service import ProductService
# from app.services.material_service import MaterialService
# from app.services.tool_service import ToolService
# from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


# --- Domain Events (Keep as previously defined or adjust as needed) ---
class InventoryAdjusted(DomainEvent):
    def __init__(self, inventory_id: int, item_id: int, item_type: str, previous_quantity: float, new_quantity: float, adjustment_type: InventoryAdjustmentType, reason: str, user_id: Optional[int] = None):
        super().__init__()
        self.inventory_id = inventory_id; self.item_id = item_id; self.item_type = item_type; self.previous_quantity = previous_quantity; self.new_quantity = new_quantity; self.adjustment_type = adjustment_type.name; self.reason = reason; self.user_id = user_id

class LowStockAlert(DomainEvent):
    def __init__(self, inventory_id: int, item_id: int, item_type: str, current_quantity: float, reorder_point: float):
        super().__init__()
        self.inventory_id = inventory_id; self.item_id = item_id; self.item_type = item_type; self.current_quantity = current_quantity; self.reorder_point = reorder_point

class InventoryTransferred(DomainEvent):
     def __init__(self, item_id: int, item_type: str, from_location: str, to_location: str, quantity: float, user_id: Optional[int] = None):
        super().__init__()
        self.item_id = item_id; self.item_type = item_type; self.from_location = from_location; self.to_location = to_location; self.quantity = quantity; self.user_id = user_id

class InventoryReconciled(DomainEvent):
     def __init__(self, inventory_id: int, item_id: int, item_type: str, previous_quantity: float, new_quantity: float, adjustment: float, count_id: Optional[str] = None, user_id: Optional[int] = None):
        super().__init__()
        self.inventory_id = inventory_id; self.item_id = item_id; self.item_type = item_type; self.previous_quantity = previous_quantity; self.new_quantity = new_quantity; self.adjustment = adjustment; self.count_id = count_id; self.user_id = user_id
# --- End Domain Events ---


class InventoryService(BaseService[Inventory]):
    """
    Service for managing inventory across all item types (Products, Materials, Tools).
    Acts as the central authority for stock levels and movements.
    """

    def __init__(
        self,
        session: Session,
        repository: Optional[InventoryRepository] = None,
        transaction_repository: Optional[InventoryTransactionRepository] = None,
        # << REMOVE product_service from constructor signature >>
        security_context=None,
        event_bus=None,
        cache_service=None,
        # Inject other needed services like MaterialService, ToolService here if needed
        material_service = None,
        tool_service = None,
        storage_service = None,
        supplier_service = None,
    ):
        self.session = session
        self.repository = repository or InventoryRepository(session)
        self.transaction_repository = transaction_repository or InventoryTransactionRepository(session)

        # Store other potentially injected services
        self.material_service = material_service
        self.tool_service = tool_service
        self.storage_service = storage_service
        self.supplier_service = supplier_service

        # Core services
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service

        # Lazy load ProductService if needed
        self._product_service_instance = None



    def _get_current_user_id(self) -> Optional[int]:
        """Helper to safely get current user ID."""
        # Implement based on your security context structure
        if self.security_context and hasattr(self.security_context, 'current_user') and self.security_context.current_user:
            return getattr(self.security_context.current_user, 'id', None)
        return None

    # --- Core Inventory Management ---

    def create_inventory(
        self,
        item_type: str,
        item_id: int,
        quantity: float = 0.0,
        status: Optional[InventoryStatus] = None,
        storage_location: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Inventory:
        """
        Creates an initial inventory record for a new item (Product, Material, Tool).
        Should typically be called by the respective item's service (e.g., ProductService).

        Args:
            item_type: 'product', 'material', or 'tool'.
            item_id: The ID of the product, material, or tool.
            quantity: Initial quantity (defaults to 0).
            status: Initial status (defaults based on quantity).
            storage_location: Optional initial storage location.
            user_id: Optional ID of the user performing the action.

        Returns:
            The created Inventory record.

        Raises:
            BusinessRuleException: If an inventory record already exists for this item.
            ValidationException: For invalid item_type.
        """
        logger.info(f"Attempting to create inventory record for {item_type} ID: {item_id}")
        user_id = user_id or self._get_current_user_id()
        item_type = item_type.lower()

        if item_type not in ["product", "material", "tool"]:
            raise ValidationException(f"Invalid item_type: {item_type}", {"item_type": "Must be 'product', 'material', or 'tool'."})

        with self.transaction():
            # Check if record already exists
            existing = self.repository.get_inventory_by_item_id(item_type, item_id)
            if existing:
                logger.warning(f"Inventory record already exists for {item_type} ID {item_id}.")
                raise BusinessRuleException(f"Inventory record already exists for {item_type} {item_id}.", "INVENTORY_ALREADY_EXISTS")

            # Determine initial status if not provided
            if status is None:
                status = InventoryStatus.OUT_OF_STOCK if quantity <= 0 else InventoryStatus.IN_STOCK

            inventory_data = {
                "item_type": item_type,
                "item_id": item_id,
                "quantity": max(0.0, quantity), # Ensure quantity isn't negative
                "status": status,
                "storage_location": storage_location,
            }

            inventory = self.repository.create(inventory_data)
            logger.info(f"Inventory record created with ID: {inventory.id} for {item_type} ID {item_id}")

            # Optional: Log initial creation as a transaction?
            # Depends on requirements, often the first *adjustment* logs the initial stock.

            # No cache invalidation needed for creates

            return inventory

    def delete_inventory(self, item_type: str, item_id: int, user_id: Optional[int] = None) -> bool:
        """
        Deletes the inventory record associated with an item.
        Should be called when the corresponding item (Product, Material, Tool) is deleted.

        Args:
            item_type: 'product', 'material', or 'tool'.
            item_id: The ID of the item whose inventory record should be deleted.
            user_id: Optional ID of the user performing the action.

        Returns:
            True if deletion occurred, False otherwise.

        Raises:
            ValidationException: For invalid item_type.
            BusinessRuleException: Potentially if there are outstanding transactions or stock? (Decide rules)
        """
        logger.info(f"Attempting to delete inventory record for {item_type} ID: {item_id}")
        user_id = user_id or self._get_current_user_id()
        item_type = item_type.lower()

        if item_type not in ["product", "material", "tool"]:
            raise ValidationException(f"Invalid item_type: {item_type}", {"item_type": "Must be 'product', 'material', or 'tool'."})

        with self.transaction():
            inventory = self.repository.get_inventory_by_item_id(item_type, item_id)
            if not inventory:
                logger.warning(f"Inventory record not found for {item_type} ID {item_id} during deletion attempt.")
                return False # Item not found, effectively deleted state

            # Optional: Add business rule checks here (e.g., cannot delete if quantity > 0?)
            # if inventory.quantity > 0:
            #    raise BusinessRuleException("Cannot delete inventory with positive stock.", "INVENTORY_HAS_STOCK")

            inventory_id = inventory.id # Store ID before deletion

            # Delete associated transactions? Or rely on FK constraints? Depends on design.
            # logger.info(f"Deleting transactions for inventory ID {inventory_id}...")
            # self.transaction_repository.delete_by_inventory_id(inventory_id) # Requires this method in repo

            # Delete the inventory record
            deleted = self.repository.delete(inventory_id)

            if deleted:
                logger.info(f"Inventory record ID {inventory_id} deleted for {item_type} ID {item_id}")
                # Invalidate cache
                if self.cache_service:
                    cache_key = self._get_cache_key(item_type, item_id)
                    self.cache_service.invalidate(cache_key)
                    self.cache_service.invalidate(f"{cache_key}:status")
                # Optional: Publish an InventoryDeleted event if needed
            else:
                 logger.error(f"Deletion failed for inventory record ID {inventory_id} after finding it.")
                 # Should not happen if get succeeded, raise an internal error?
                 raise HideSyncException(f"Inventory deletion failed unexpectedly for {item_type} {item_id}")

            return deleted

    # Use a specific schema or individual args for adjust_inventory
    # Using individual args here for clarity based on previous calls
    def adjust_inventory(
        self,
        item_type: str,
        item_id: int,
        quantity_change: float,
        adjustment_type: InventoryAdjustmentType,
        reason: str,
        reference_id: Optional[str] = None, # Can be SaleID, ProjectID, CountID etc.
        reference_type: Optional[str] = None, # Type of reference ('sale', 'project', 'count')
        from_location: Optional[str] = None, # Relevant for some adjustments
        to_location: Optional[str] = None, # Relevant for some adjustments
        notes: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Inventory:
        """
        Adjusts the inventory quantity for a specific item and logs the transaction.
        This is the central method for changing stock levels.

        Args:
            item_type: 'product', 'material', or 'tool'.
            item_id: The ID of the item.
            quantity_change: The amount to change (+ for increase, - for decrease).
            adjustment_type: The type of adjustment (Enum member).
            reason: A required reason for the adjustment.
            reference_id: Optional ID related to the adjustment.
            reference_type: Optional type of the reference ID.
            from_location: Optional source location (used in transaction log).
            to_location: Optional destination location (used in transaction log/updates inventory).
            notes: Optional additional notes for the transaction.
            user_id: Optional ID of the user performing the action.

        Returns:
            The updated Inventory record.

        Raises:
            ValidationException: For invalid inputs.
            EntityNotFoundException: If the base item (product/material/tool) doesn't exist (via _get_item_details).
            InsufficientInventoryException: If quantity would go below zero.
            HideSyncException: For internal errors.
        """
        logger.info(f"Adjusting inventory for {item_type} ID {item_id}: change={quantity_change}, type={adjustment_type.name}, reason='{reason}'")
        user_id = user_id or self._get_current_user_id()
        item_type = item_type.lower()

        if item_type not in ["product", "material", "tool"]:
            raise ValidationException(f"Invalid item_type: {item_type}", {"item_type": "Must be 'product', 'material', or 'tool'."})
        if not reason:
             raise ValidationException("Reason is required for inventory adjustment.", {"reason": "Cannot be empty."})
        if not isinstance(adjustment_type, InventoryAdjustmentType):
             raise ValidationException("Invalid adjustment_type provided.", {"adjustment_type": "Must be InventoryAdjustmentType enum member."})

        with self.transaction():
            # 1. Get or Create Inventory Record
            inventory = self.repository.get_inventory_by_item_id(item_type, item_id)
            created_inventory = False
            if not inventory:
                # If adjusting positively, allow creation. If negative, it's an error.
                if quantity_change > 0:
                    logger.warning(f"Inventory record not found for {item_type} ID {item_id}. Creating one due to positive adjustment.")
                    # Use the to_location if provided, otherwise null
                    inventory = self.create_inventory(
                        item_type=item_type,
                        item_id=item_id,
                        quantity=0.0, # Start at 0 before applying change
                        storage_location=to_location,
                        user_id=user_id
                    )
                    created_inventory = True
                else:
                    logger.error(f"Cannot apply negative adjustment: Inventory record not found for {item_type} ID {item_id}.")
                    raise InsufficientInventoryException(f"No inventory record found for {item_type} {item_id} to decrease quantity.", "INVENTORY_NOT_FOUND_FOR_DECREASE")

            # 2. Calculate New Quantity and Validate
            previous_quantity = inventory.quantity
            new_quantity = previous_quantity + quantity_change

            if new_quantity < 0:
                logger.warning(f"Insufficient inventory for {item_type} {item_id}. Available: {previous_quantity}, Requested change: {quantity_change}")
                raise InsufficientInventoryException(
                    f"Insufficient inventory for {item_type} {item_id}. Available: {previous_quantity}, Requested change: {quantity_change}",
                    "INVENTORY_INSUFFICIENT",
                    {"item": f"{item_type}:{item_id}", "available": previous_quantity, "change": quantity_change}
                )

            # 3. Determine New Status (requires reorder point)
            item_details = self._get_item_details(item_type, item_id)
            if not item_details and not created_inventory:
                 # Should not happen if inventory exists unless item was deleted?
                 logger.error(f"Could not retrieve details for existing {item_type} ID {item_id} during adjustment.")
                 raise EntityNotFoundException(f"{item_type.capitalize()}", item_id) # Or handle differently

            reorder_point = item_details.get('reorder_point', 0.0) if item_details else 0.0
            new_status = self._determine_inventory_status(quantity=new_quantity, reorder_point=reorder_point)

            # 4. Prepare Inventory Update Data
            inventory_update_data = {
                "quantity": new_quantity,
                "status": new_status,
            }
            # Update location if 'to_location' is specified and different
            if to_location and inventory.storage_location != to_location:
                 inventory_update_data["storage_location"] = to_location
                 logger.info(f"Updating storage location for {item_type} {item_id} to '{to_location}' during adjustment.")

            # 5. Update Inventory Record
            updated_inventory = self.repository.update(inventory.id, inventory_update_data)
            if not updated_inventory: # Should not happen
                 logger.error(f"Failed to update inventory record ID {inventory.id} after validation.")
                 raise HideSyncException(f"Inventory update failed unexpectedly for {item_type} {item_id}")

            # 6. Create Transaction Log
            transaction_data = {
                "item_type": item_type,
                "item_id": item_id,
                "quantity_change": quantity_change, # Log the change amount
                "transaction_type": TransactionType.ADJUSTMENT, # Or derive from adjustment_type? Usually ADJUSTMENT is generic here.
                "adjustment_type": adjustment_type, # Specific reason
                "reference_id": reference_id,
                "reference_type": reference_type,
                "from_location": from_location,
                "to_location": to_location, # Log where it ended up
                "notes": f"{reason}{f' | {notes}' if notes else ''}", # Combine reason and notes
                "performed_by": str(user_id) if user_id else None, # Store user ID as string? Or FK?
                "transaction_date": datetime.now(),
            }
            # Use the specific transaction creation method
            self.transaction_repository.create_inventory_transaction(**transaction_data)
            logger.info(f"Inventory transaction logged for {item_type} ID {item_id}")

            # 7. Publish Event
            if self.event_bus:
                self.event_bus.publish(
                    InventoryAdjusted(
                        inventory_id=updated_inventory.id,
                        item_id=item_id,
                        item_type=item_type,
                        previous_quantity=previous_quantity,
                        new_quantity=updated_inventory.quantity,
                        adjustment_type=adjustment_type,
                        reason=reason,
                        user_id=user_id,
                    )
                )

            # 8. Check for Low Stock Alert
            # Pass reorder_point to avoid fetching details again
            self._check_low_stock(updated_inventory, reorder_point)

            # 9. Invalidate Cache
            if self.cache_service:
                cache_key = self._get_cache_key(item_type, item_id)
                self.cache_service.invalidate(cache_key)
                self.cache_service.invalidate(f"{cache_key}:status") # Invalidate status cache too

            self.session.refresh(updated_inventory) # Refresh state
            return updated_inventory

    def transfer_inventory(
        self,
        item_type: str,
        item_id: int,
        quantity: float,
        from_location: str,
        to_location: str,
        notes: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Transfers a specified quantity of an item from one location to another.

        Args:
            item_type: 'product', 'material', or 'tool'.
            item_id: The ID of the item.
            quantity: The positive quantity to transfer.
            from_location: The source storage location ID.
            to_location: The destination storage location ID.
            notes: Optional notes for the transfer transaction.
            user_id: Optional ID of the user performing the action.

        Returns:
            A dictionary confirming the transfer details.

        Raises:
            ValidationException: If quantity is not positive or locations are the same.
            EntityNotFoundException: If source/destination locations or source inventory don't exist.
            InsufficientInventoryException: If source location has less than the requested quantity.
            HideSyncException: For internal errors.
        """
        logger.info(f"Attempting inventory transfer: {quantity} of {item_type} ID {item_id} from '{from_location}' to '{to_location}'")
        user_id = user_id or self._get_current_user_id()
        item_type = item_type.lower()

        if item_type not in ["product", "material", "tool"]:
            raise ValidationException(f"Invalid item_type: {item_type}", {"item_type": "Must be 'product', 'material', or 'tool'."})
        if quantity <= 0:
            raise ValidationException("Transfer quantity must be positive.", {"quantity": "Must be > 0"})
        if from_location == to_location:
            raise ValidationException("Source and destination locations cannot be the same.", {"to_location": "Must differ from from_location"})

        # Validate locations if storage service exists
        if self.storage_service:
            if not self.storage_service.location_exists(from_location):
                 logger.warning(f"Source location '{from_location}' not found during transfer.")
                 raise StorageLocationNotFoundException(from_location)
            if not self.storage_service.location_exists(to_location):
                 logger.warning(f"Destination location '{to_location}' not found during transfer.")
                 raise StorageLocationNotFoundException(to_location)

        with self.transaction():
            # 1. Get Source Inventory & Check Quantity
            # Assuming repository method exists to get by item *and* location
            source_inventory = self.repository.get_inventory_by_item_and_location(item_type, item_id, from_location)
            if not source_inventory:
                logger.warning(f"No inventory found for {item_type} ID {item_id} at source location '{from_location}'.")
                raise EntityNotFoundException(f"Inventory for {item_type} {item_id} at location '{from_location}'")
            if source_inventory.quantity < quantity:
                logger.warning(f"Insufficient quantity for transfer: {item_type} {item_id} at '{from_location}'. Available: {source_inventory.quantity}, Requested: {quantity}")
                raise InsufficientInventoryException(
                    f"Insufficient quantity at source '{from_location}'. Available: {source_inventory.quantity}, Requested: {quantity}",
                    "INVENTORY_INSUFFICIENT_TRANSFER",
                    {"item": f"{item_type}:{item_id}", "location": from_location, "available": source_inventory.quantity, "requested": quantity}
                )

            # 2. Get or Create Destination Inventory
            dest_inventory = self.repository.get_inventory_by_item_and_location(item_type, item_id, to_location)
            if not dest_inventory:
                logger.info(f"No inventory record exists for {item_type} {item_id} at destination '{to_location}'. Creating one.")
                # Determine status based on item details (reorder point)
                item_details = self._get_item_details(item_type, item_id)
                reorder_point = item_details.get('reorder_point', 0.0) if item_details else 0.0
                dest_status = self._determine_inventory_status(quantity=quantity, reorder_point=reorder_point)

                dest_inventory = self.repository.create({
                    "item_type": item_type,
                    "item_id": item_id,
                    "quantity": quantity,
                    "status": dest_status,
                    "storage_location": to_location,
                })
                logger.info(f"Created destination inventory record ID {dest_inventory.id}")
            else:
                # Add quantity to existing destination inventory
                dest_new_quantity = dest_inventory.quantity + quantity
                item_details = self._get_item_details(item_type, item_id) # Need details for status
                reorder_point = item_details.get('reorder_point', 0.0) if item_details else 0.0
                dest_new_status = self._determine_inventory_status(quantity=dest_new_quantity, reorder_point=reorder_point)
                dest_inventory = self.repository.update(dest_inventory.id, {"quantity": dest_new_quantity, "status": dest_new_status})
                logger.info(f"Updated destination inventory record ID {dest_inventory.id} to quantity {dest_new_quantity}")

            # 3. Decrease Source Inventory Quantity
            source_new_quantity = source_inventory.quantity - quantity
            item_details = self._get_item_details(item_type, item_id) # Need details for status
            reorder_point = item_details.get('reorder_point', 0.0) if item_details else 0.0
            source_new_status = self._determine_inventory_status(quantity=source_new_quantity, reorder_point=reorder_point)

            # Decide whether to update or delete source inventory record if quantity becomes zero
            if source_new_quantity <= 0:
                logger.info(f"Source inventory quantity reached zero for {item_type} {item_id} at '{from_location}'. Deleting record.")
                self.repository.delete(source_inventory.id)
            else:
                source_inventory = self.repository.update(source_inventory.id, {"quantity": source_new_quantity, "status": source_new_status})
                logger.info(f"Updated source inventory record ID {source_inventory.id} to quantity {source_new_quantity}")

            # 4. Create ONE Transfer Transaction Log
            transaction_data = {
                "item_type": item_type,
                "item_id": item_id,
                "quantity_change": quantity, # Log the positive quantity moved
                "transaction_type": TransactionType.LOCATION_TRANSFER,
                "adjustment_type": None, # Not an adjustment in the typical sense
                "from_location": from_location,
                "to_location": to_location,
                "notes": notes,
                "performed_by": str(user_id) if user_id else None,
                "transaction_date": datetime.now(),
            }
            self.transaction_repository.create_inventory_transaction(**transaction_data)
            logger.info(f"Transfer transaction logged for {item_type} ID {item_id} from '{from_location}' to '{to_location}'")

            # 5. Publish Event
            if self.event_bus:
                 self.event_bus.publish(
                    InventoryTransferred(
                        item_id=item_id, item_type=item_type, from_location=from_location,
                        to_location=to_location, quantity=quantity, user_id=user_id
                    )
                )

            # 6. Invalidate Caches for both source and destination items
            if self.cache_service:
                cache_key_from = self._get_cache_key(item_type, item_id, from_location)
                cache_key_to = self._get_cache_key(item_type, item_id, to_location)
                self.cache_service.invalidate(cache_key_from)
                self.cache_service.invalidate(f"{cache_key_from}:status")
                self.cache_service.invalidate(cache_key_to)
                self.cache_service.invalidate(f"{cache_key_to}:status")
                # Also invalidate the general item cache key if used
                general_key = self._get_cache_key(item_type, item_id)
                self.cache_service.invalidate(general_key)
                self.cache_service.invalidate(f"{general_key}:status")


            return {
                "message": "Transfer completed successfully",
                "item_type": item_type,
                "item_id": item_id,
                "quantity": quantity,
                "from_location": from_location,
                "to_location": to_location,
                "timestamp": datetime.now().isoformat(),
            }

    # --- Read/Query Methods ---

    def get_inventory_status(self, item_type: str, item_id: int) -> Optional[Dict[str, Any]]:
        """
        Gets the inventory status for a specific item, enriching with details.
        """
        logger.debug(f"Getting inventory status for {item_type} ID: {item_id}")
        cache_key = self._get_cache_key(item_type, item_id, suffix=":status")
        if self.cache_service:
            cached = self.cache_service.get(cache_key)
            if cached:
                logger.debug(f"Returning cached status for {item_type} ID: {item_id}")
                return cached

        inventory = self.repository.get_inventory_by_item_id(item_type.lower(), item_id)
        if not inventory:
            logger.debug(f"No inventory record found for {item_type} ID {item_id}.")
            # Return a default 'not tracked' status? Or None? Depends on desired behavior.
            # Returning None here indicates no record exists.
            return None

        # Enrich with item details (name, reorder point, unit, etc.)
        item_details = self._get_item_details(item_type.lower(), item_id)

        result = {
            "inventory_id": inventory.id,
            "item_type": inventory.item_type,
            "item_id": inventory.item_id,
            "item_name": item_details.get("name", f"Unknown {inventory.item_type}") if item_details else f"Unknown {inventory.item_type}",
            "quantity": inventory.quantity,
            "status": inventory.status.name if inventory.status else None, # Use name for readability
            "reorder_point": item_details.get("reorder_point", 0.0) if item_details else 0.0,
            "unit": item_details.get("unit", "unit") if item_details else "unit",
            "storage_location": inventory.storage_location,
            "last_updated": inventory.updatedAt.isoformat() if hasattr(inventory, 'updatedAt') and inventory.updatedAt else None,
            # Add more relevant details?
        }

        if self.cache_service:
            logger.debug(f"Caching status for {item_type} ID: {item_id}")
            self.cache_service.set(cache_key, result, ttl=600) # Cache for 10 minutes

        return result

    def list_inventory_items(
        self, skip: int, limit: int, search_params: InventorySearchParams
    ) -> List[Inventory]:
        """
        Retrieves a list of inventory items using the repository's filtering.
        (This method now directly uses the schema for params)
        """
        logger.info(f"Listing inventory items: skip={skip}, limit={limit}, params={search_params.model_dump()}")
        # Assuming InventoryRepository has list_with_filters method accepting these params
        items = self.repository.list_with_filters(
            skip=skip,
            limit=limit,
            status=search_params.status,
            location=search_params.location,
            item_type=search_params.item_type,
            search_term=search_params.search # Pass the search term
        )
        logger.info(f"Found {len(items)} inventory items matching criteria.")
        # Consider enriching these results with item names if needed by the caller
        # enrich = enrich_results or False # Example flag
        # if enrich:
        #     return [self._enrich_inventory_item(item) for item in items]
        return items

    def get_inventory_transactions(
        self,
        skip: int = 0,
        limit: int = 100,
        item_id: Optional[int] = None,
        item_type: Optional[str] = None,
        transaction_type: Optional[str] = None,
        start_date: Optional[str] = None, # Expect ISO date strings
        end_date: Optional[str] = None, # Expect ISO date strings
    ) -> List[InventoryTransaction]:
        """
        Retrieves inventory transaction logs with filtering.
        """
        logger.info(f"Listing inventory transactions: skip={skip}, limit={limit}, item={item_type}:{item_id}, type={transaction_type}, date={start_date}-{end_date}")
        # Convert string dates to datetime objects if provided
        dt_start = datetime.fromisoformat(start_date) if start_date else None
        dt_end = datetime.fromisoformat(f"{end_date}T23:59:59.999999") if end_date else None # Include end day

        # Call repository method (assuming it exists and handles these filters)
        # You might need to build the filter logic here or enhance the repository method
        transactions = self.transaction_repository.get_filtered_transactions(
             skip=skip, limit=limit, item_id=item_id, item_type=item_type,
             transaction_type=transaction_type, start_date=dt_start, end_date=dt_end
        )
        logger.info(f"Found {len(transactions)} inventory transactions.")
        return transactions

    def get_low_stock_items(
        self, threshold_percentage: float = 100.0, item_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Gets items low in stock (at or below reorder point * threshold %).
        """
        logger.info(f"Fetching low stock items: threshold={threshold_percentage}%, type={item_type or 'All'}")
        # Repository method should handle the core query joining Inventory and Product/Material/Tool
        # to compare Inventory.quantity with Item.reorder_point
        low_stock_inventories = self.repository.get_low_stock_inventory_detailed(
            threshold_percentage=threshold_percentage,
            item_type=item_type.lower() if item_type else None,
            limit=500 # Add a reasonable limit
        ) # Assuming repo has this method

        results = []
        for inventory, item_details in low_stock_inventories: # Assuming repo returns tuples
            if not item_details: # Should ideally not happen if query is correct
                 logger.warning(f"Missing item details for low stock inventory ID {inventory.id} ({inventory.item_type} {inventory.item_id})")
                 continue

            reorder_point = item_details.get('reorder_point', 0.0)
            quantity = inventory.quantity

            # Format output
            results.append({
                "inventory_id": inventory.id,
                "item_type": inventory.item_type,
                "item_id": inventory.item_id,
                "item_name": item_details.get("name", f"Unknown {inventory.item_type}"),
                "quantity": quantity,
                "status": inventory.status.name if inventory.status else None,
                "reorder_point": reorder_point,
                "storage_location": inventory.storage_location,
                "percent_of_reorder": round((quantity / reorder_point * 100) if reorder_point > 0 else 0, 1),
                "units_below_reorder": max(0, reorder_point - quantity),
                "unit": item_details.get("unit", "unit"),
                # Add other useful details like supplier?
            })

        logger.info(f"Found {len(results)} low stock items.")
        # Sort results (e.g., by severity - lowest percentage first)
        return sorted(results, key=lambda x: x["percent_of_reorder"])


    # --- Reporting & Calculation Methods ---
    # (Keep calculate_inventory_value, generate_inventory_report, reconcile_inventory, perform_inventory_audit
    #  as defined previously, ensuring they use _get_item_details correctly)

    def calculate_inventory_value(self, as_of_date: Optional[datetime] = None) -> Dict[str, Any]:
        # ... (Implementation as before, relies on _get_item_details for costs) ...
        logger.info(f"Calculating inventory value as of {as_of_date or 'now'}")
        if not as_of_date: as_of_date = datetime.now()
        inventories = self.repository.list()
        total_value = 0.0
        by_type = {"product": {"count": 0, "value": 0.0}, "material": {"count": 0, "value": 0.0}, "tool": {"count": 0, "value": 0.0}}
        items_detail = []

        for inventory in inventories:
            if inventory.quantity <= 0: continue
            item_details = self._get_item_details(inventory.item_type, inventory.item_id)
            if not item_details: continue
            unit_cost = item_details.get("cost", 0.0)
            item_value = inventory.quantity * unit_cost
            total_value += item_value
            if inventory.item_type in by_type:
                 by_type[inventory.item_type]["count"] += 1
                 by_type[inventory.item_type]["value"] += item_value
            items_detail.append({
                "inventory_id": inventory.id, "item_type": inventory.item_type, "item_id": inventory.item_id,
                "name": item_details.get("name", f"Unknown {inventory.item_type}"),
                "quantity": inventory.quantity, "unit": item_details.get("unit"),
                "unit_cost": unit_cost, "total_value": item_value, "location": inventory.storage_location,
            })
        logger.info(f"Calculated total inventory value: {total_value:.2f}")
        return {
            "as_of_date": as_of_date.isoformat(), "total_value": round(total_value, 2),
            "item_count": sum(t["count"] for t in by_type.values()), "by_type": by_type,
            "items": sorted(items_detail, key=lambda x: x["total_value"], reverse=True),
        }

    def generate_inventory_report(self, report_type: str, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # ... (Implementation as before, dispatcher calling specific report methods) ...
         logger.info(f"Generating inventory report: type='{report_type}', filters={filters}")
         # Validate report type...
         # Dispatch to _generate_summary_report, _generate_detail_report, etc.
         pass # Placeholder for brevity

    def reconcile_inventory(self, item_type: str, item_id: int, actual_quantity: float, count_id: Optional[str] = None, notes: Optional[str] = None, user_id: Optional[int]=None) -> Dict[str, Any]:
        # ... (Implementation as before, using adjust_inventory) ...
         logger.info(f"Reconciling inventory for {item_type} ID {item_id}: actual quantity={actual_quantity}")
         user_id = user_id or self._get_current_user_id()
         inventory = self.repository.get_inventory_by_item_id(item_type.lower(), item_id)
         if not inventory: raise EntityNotFoundException(f"Inventory record for {item_type} {item_id}")

         previous_quantity = inventory.quantity
         adjustment = actual_quantity - previous_quantity
         adjustment_result = {}

         if adjustment != 0:
             updated_inventory = self.adjust_inventory(
                 item_type=item_type, item_id=item_id, quantity_change=adjustment,
                 adjustment_type=InventoryAdjustmentType.PHYSICAL_COUNT, # Or INVENTORY_CORRECTION
                 reason=f"Physical Count Reconciliation ({count_id or 'Manual'})",
                 reference_id=count_id, reference_type='count', notes=notes, user_id=user_id,
                 to_location=inventory.storage_location # Ensure location persists
             )
             new_quantity = updated_inventory.quantity
             adjustment_result["inventory_id"] = updated_inventory.id
         else:
              logger.info(f"No adjustment needed for {item_type} ID {item_id} (system quantity matches actual).")
              new_quantity = previous_quantity
              adjustment_result["inventory_id"] = inventory.id

         # Publish event
         if self.event_bus:
              self.event_bus.publish(InventoryReconciled(
                  inventory_id=inventory.id, item_id=item_id, item_type=item_type,
                  previous_quantity=previous_quantity, new_quantity=new_quantity,
                  adjustment=adjustment, count_id=count_id, user_id=user_id
              ))

         adjustment_result.update({
             "item_type": item_type, "item_id": item_id, "previous_quantity": previous_quantity,
             "actual_quantity": actual_quantity, "adjustment": adjustment, "count_id": count_id,
             "timestamp": datetime.now().isoformat(), "notes": notes,
         })
         return adjustment_result

    def perform_inventory_audit(self, location_id: Optional[str] = None, item_type: Optional[str] = None) -> Dict[str, Any]:
         # ... (Implementation as before, relying on _get_item_details) ...
         logger.info(f"Performing inventory audit prep: location={location_id}, type={item_type}")
         # Fetch inventory, group by location, get item details...
         pass # Placeholder for brevity


    # --- Helper Methods ---

    def _get_cache_key(self, item_type: str, item_id: int, suffix: Optional[str] = None, location: Optional[str] = None) -> str:
        """Generates a consistent cache key."""
        key = f"Inventory:{item_type.lower()}:{item_id}"
        if location:
             key += f":loc:{location}"
        if suffix:
            key += suffix
        return key

    def _get_item_details(self, item_type: str, item_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetches essential details (name, cost, reorder point, unit) for an item
        by delegating to the appropriate injected service.
        """
        item_type = item_type.lower()
        details = None
        logger.debug(f"Getting item details for {item_type} ID: {item_id}")

        try:
            if item_type == "product" and self.product_service:
                # Assume product service returns a dict or has a to_dict method
                item = self.product_service.get_product_by_id(item_id) # Fetch the object
                if item:
                     details = {
                         "name": getattr(item, 'name', None),
                         "cost": getattr(item, 'total_cost', 0.0), # Use total_cost for products
                         "reorder_point": getattr(item, 'reorder_point', 0.0),
                         "unit": "piece", # Products usually units/pieces
                         # Add other relevant fields like SKU?
                         "sku": getattr(item, 'sku', None),
                     }
            elif item_type == "material" and self.material_service:
                item = self.material_service.get_by_id(item_id) # Fetch the object
                if item:
                     details = {
                         "name": getattr(item, 'name', None),
                         "cost": getattr(item, 'cost', 0.0),
                         "reorder_point": getattr(item, 'reorder_point', 0.0),
                         "unit": getattr(item, 'unit', 'unit').name if hasattr(getattr(item, 'unit', None),'name') else getattr(item, 'unit', 'unit'), # Handle enum or string unit
                         "supplier_id": getattr(item, 'supplier_id', None),
                     }
            elif item_type == "tool" and self.tool_service:
                 item = self.tool_service.get_by_id(item_id) # Fetch the object
                 if item:
                     details = {
                         "name": getattr(item, 'name', None),
                         "cost": getattr(item, 'purchase_price', 0.0), # Tools have purchase_price
                         "reorder_point": 0.0, # Tools typically don't have a reorder point
                         "unit": "piece",
                         "category": getattr(item, 'category', None),
                     }
            else:
                 logger.warning(f"No appropriate service configured or found for item_type: {item_type}")

        except EntityNotFoundException:
             logger.warning(f"Item not found via its service: {item_type} ID {item_id}")
             return None # Item doesn't exist
        except Exception as e:
             logger.error(f"Error fetching details for {item_type} {item_id}: {e}", exc_info=True)
             # Decide if this should halt operation or just return None
             return None # Return None on error to avoid breaking caller

        if details:
             logger.debug(f"Successfully retrieved details for {item_type} ID {item_id}")
        else:
             logger.warning(f"Could not retrieve details for {item_type} ID {item_id}")

        return details

    def _determine_inventory_status(self, quantity: float, reorder_point: float) -> InventoryStatus:
        """Determines inventory status based on quantity and reorder point."""
        if quantity <= 0:
            return InventoryStatus.OUT_OF_STOCK
        elif reorder_point > 0 and quantity <= reorder_point:
            return InventoryStatus.LOW_STOCK
        else:
            return InventoryStatus.IN_STOCK

    def _check_low_stock(self, inventory: Inventory, reorder_point: Optional[float] = None) -> None:
        """Checks if inventory is low stock and emits an event if needed."""
        if not self.event_bus:
            return

        # Get reorder point if not provided
        if reorder_point is None:
            item_details = self._get_item_details(inventory.item_type, inventory.item_id)
            reorder_point = item_details.get('reorder_point', 0.0) if item_details else 0.0

        # Check status directly or compare quantity
        if reorder_point > 0 and inventory.quantity <= reorder_point:
             # Check if status *actually changed* to LOW_STOCK or OUT_OF_STOCK to avoid redundant alerts?
             # Or just alert whenever it's low. Alerting whenever low is simpler.
            logger.info(f"Low stock detected for {inventory.item_type} ID {inventory.item_id}. Qty: {inventory.quantity}, Reorder: {reorder_point}")
            self.event_bus.publish(
                LowStockAlert(
                    inventory_id=inventory.id, item_id=inventory.item_id, item_type=inventory.item_type,
                    current_quantity=inventory.quantity, reorder_point=reorder_point
                )
            )
        # else: No alert needed

        # Add these methods inside the InventoryService class
        # File: services/inventory_service.py (Continued)

        # --- Reporting Helper Methods ---

    def _generate_summary_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a summary inventory report based on filters.

        Args:
            filters: Dictionary of filters (e.g., item_type, status, location).

        Returns:
            Dictionary containing the summary report.
        """
        logger.info(f"Generating summary report with filters: {filters}")
        now = datetime.now()

        # Prepare search parameters for the repository
        search_params = InventorySearchParams(
            item_type=filters.get("item_type"),
            status=filters.get("status"),
            location=filters.get("location"),
            search=filters.get("search")  # Include search if provided in filters
        )

        # Fetch inventory items using the repository's filtered list method
        # Assuming list_with_filters fetches all matching items if limit isn't constrained significantly
        # For very large datasets, aggregation might need to happen in the DB query itself.
        inventories = self.repository.list_with_filters(
            skip=0, limit=10000,  # Fetch a large number for summary - adjust as needed
            status=search_params.status,
            location=search_params.location,
            item_type=search_params.item_type,
            search_term=search_params.search
        )

        # Initialize summary data structures
        summary = {
            "report_type": "summary",
            "generated_at": now.isoformat(),
            "filters_applied": filters,
            "total_items_tracked": len(inventories),  # Total distinct inventory records matching filters
            "total_quantity_on_hand": 0.0,
            "estimated_total_value": 0.0,  # Will calculate below
            "summary_by_type": {},  # e.g., {'product': {'count': 10, 'quantity': 50, 'value': 1000.0}, ...}
            "summary_by_status": {},  # e.g., {'IN_STOCK': {'count': 8, 'quantity': 45, 'value': 900.0}, ...}
            "summary_by_location": {},  # e.g., {'Shelf A': {'count': 5, 'quantity': 20, 'value': 400.0}, ...}
        }

        # Iterate and aggregate
        for inv in inventories:
            item_type = inv.item_type
            status_name = inv.status.name if inv.status else "UNKNOWN"
            location = inv.storage_location or "Unassigned"
            quantity = inv.quantity or 0.0

            # Get item details for cost calculation
            item_details = self._get_item_details(item_type, inv.item_id)
            unit_cost = item_details.get("cost", 0.0) if item_details else 0.0
            item_value = quantity * unit_cost

            # --- Aggregate Totals ---
            summary["total_quantity_on_hand"] += quantity
            summary["estimated_total_value"] += item_value

            # --- Aggregate By Type ---
            if item_type not in summary["summary_by_type"]:
                summary["summary_by_type"][item_type] = {"count": 0, "quantity": 0.0, "value": 0.0}
            summary["summary_by_type"][item_type]["count"] += 1
            summary["summary_by_type"][item_type]["quantity"] += quantity
            summary["summary_by_type"][item_type]["value"] += item_value

            # --- Aggregate By Status ---
            if status_name not in summary["summary_by_status"]:
                summary["summary_by_status"][status_name] = {"count": 0, "quantity": 0.0, "value": 0.0}
            summary["summary_by_status"][status_name]["count"] += 1
            summary["summary_by_status"][status_name]["quantity"] += quantity
            summary["summary_by_status"][status_name]["value"] += item_value

            # --- Aggregate By Location ---
            if location not in summary["summary_by_location"]:
                summary["summary_by_location"][location] = {"count": 0, "quantity": 0.0, "value": 0.0}
            summary["summary_by_location"][location]["count"] += 1
            summary["summary_by_location"][location]["quantity"] += quantity
            summary["summary_by_location"][location]["value"] += item_value

        # Round final values
        summary["total_quantity_on_hand"] = round(summary["total_quantity_on_hand"],
                                                  4)  # Adjust precision as needed
        summary["estimated_total_value"] = round(summary["estimated_total_value"], 2)
        for type_key in summary["summary_by_type"]:
            summary["summary_by_type"][type_key]["quantity"] = round(
                summary["summary_by_type"][type_key]["quantity"], 4)
            summary["summary_by_type"][type_key]["value"] = round(summary["summary_by_type"][type_key]["value"], 2)
        for status_key in summary["summary_by_status"]:
            summary["summary_by_status"][status_key]["quantity"] = round(
                summary["summary_by_status"][status_key]["quantity"], 4)
            summary["summary_by_status"][status_key]["value"] = round(
                summary["summary_by_status"][status_key]["value"], 2)
        for loc_key in summary["summary_by_location"]:
            summary["summary_by_location"][loc_key]["quantity"] = round(
                summary["summary_by_location"][loc_key]["quantity"], 4)
            summary["summary_by_location"][loc_key]["value"] = round(
                summary["summary_by_location"][loc_key]["value"], 2)

        logger.info(f"Summary report generated successfully. Total items: {summary['total_items_tracked']}")
        return summary

    def _generate_detail_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a detailed inventory report listing individual items based on filters.

        Args:
            filters: Dictionary of filters (e.g., item_type, status, location, search).

        Returns:
            Dictionary containing the detailed report.
        """
        logger.info(f"Generating detail report with filters: {filters}")
        now = datetime.now()

        # Prepare search parameters for the repository
        search_params = InventorySearchParams(
            item_type=filters.get("item_type"),
            status=filters.get("status"),
            location=filters.get("location"),
            search=filters.get("search")
        )

        # Fetch inventory items using the repository's filtered list method
        # Add pagination parameters from filters if provided, otherwise use defaults
        skip = filters.get("skip", 0)
        limit = filters.get("limit", 100)  # Default limit for detail report

        inventories = self.repository.list_with_filters(
            skip=skip,
            limit=limit,
            status=search_params.status,
            location=search_params.location,
            item_type=search_params.item_type,
            search_term=search_params.search
        )
        # Fetch total count for pagination info (might require separate count query in repo)
        total_count = self.repository.count_with_filters(  # Assuming repo has this method
            status=search_params.status,
            location=search_params.location,
            item_type=search_params.item_type,
            search_term=search_params.search
        )

        # Initialize detail report structure
        report = {
            "report_type": "detail",
            "generated_at": now.isoformat(),
            "filters_applied": filters,
            "pagination": {
                "total_items": total_count,
                "limit": limit,
                "skip": skip,
                "current_page": (skip // limit) + 1,
                "total_pages": (total_count + limit - 1) // limit if limit > 0 else 1,
            },
            "items": [],
        }

        # Process each inventory item
        for inv in inventories:
            item_details = self._get_item_details(inv.item_type, inv.item_id)
            if not item_details:
                logger.warning(
                    f"Skipping inventory ID {inv.id}: Could not retrieve details for {inv.item_type} {inv.item_id}")
                continue

            quantity = inv.quantity or 0.0
            unit_cost = item_details.get("cost", 0.0)
            item_value = quantity * unit_cost
            reorder_point = item_details.get("reorder_point", 0.0)

            report["items"].append({
                "inventory_id": inv.id,
                "item_type": inv.item_type,
                "item_id": inv.item_id,
                "item_name": item_details.get("name", f"Unknown {inv.item_type}"),
                "sku": item_details.get("sku"),  # Add SKU if available
                "status": inv.status.name if inv.status else "UNKNOWN",
                "quantity": quantity,
                "unit": item_details.get("unit", "unit"),
                "reorder_point": reorder_point,
                "location": inv.storage_location or "Unassigned",
                "unit_cost": round(unit_cost, 2),
                "total_value": round(item_value, 2),
                "last_updated": inv.updatedAt.isoformat() if hasattr(inv, 'updatedAt') and inv.updatedAt else None,
                # Optional: Add more details like last movement date?
            })

        logger.info(f"Detail report generated. Displaying {len(report['items'])} of {total_count} items.")
        # Optionally sort the items list, e.g., by name or value
        # report["items"] = sorted(report["items"], key=lambda x: x["item_name"])

        return report

    def _generate_movement_report(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates an inventory movement report showing transactions over a period.

        Args:
            filters: Dictionary of filters (e.g., date_range, item_type, transaction_type, location).

        Returns:
            Dictionary containing the movement report.
        """
        logger.info(f"Generating movement report with filters: {filters}")
        now = datetime.now()

        # --- Parse Filters ---
        # Date Range (default to last 30 days if not provided)
        default_start = now - timedelta(days=30)
        start_date_str = filters.get("start_date", default_start.isoformat())
        end_date_str = filters.get("end_date", now.isoformat())
        try:
            start_date = datetime.fromisoformat(start_date_str)
            # Include the whole end day
            end_date = datetime.fromisoformat(f"{end_date_str.split('T')[0]}T23:59:59.999999")
        except ValueError:
            logger.warning("Invalid date format in movement report filters. Using default range.")
            start_date = default_start
            end_date = now

        item_type_filter = filters.get("item_type")
        item_id_filter = filters.get("item_id")  # Allow filtering by specific item ID
        transaction_type_filter = filters.get("transaction_type")
        location_filter = filters.get("location")  # Filter by EITHER from_ or to_location matching this

        # Pagination
        skip = filters.get("skip", 0)
        limit = filters.get("limit", 100)

        # --- Fetch Transactions ---
        # Assuming transaction repo method handles these filters
        paginated_transactions = self.transaction_repository.get_filtered_transactions_paginated(
            skip=skip, limit=limit,
            item_id=item_id_filter, item_type=item_type_filter,
            transaction_type=transaction_type_filter,
            start_date=start_date, end_date=end_date,
            location=location_filter  # Repo needs to implement OR filter on from/to location
        )
        transactions = paginated_transactions.get("items", [])
        total_count = paginated_transactions.get("total", 0)

        # Initialize report structure
        report = {
            "report_type": "movement",
            "generated_at": now.isoformat(),
            "filters_applied": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "item_type": item_type_filter,
                "item_id": item_id_filter,
                "transaction_type": transaction_type_filter,
                "location": location_filter,
            },
            "pagination": {
                "total_items": total_count,
                "limit": limit,
                "skip": skip,
                "current_page": (skip // limit) + 1,
                "total_pages": (total_count + limit - 1) // limit if limit > 0 else 1,
            },
            "summary": {  # Add a summary section
                "total_transactions": total_count,
                "total_quantity_in": 0.0,
                "total_quantity_out": 0.0,
                "net_quantity_change": 0.0,
            },
            "transactions": [],
        }

        # Process transactions
        for tx in transactions:
            item_details = self._get_item_details(tx.item_type, tx.item_id)
            quantity_change = tx.quantity_change or 0.0  # Use the correct field name

            # Update summary totals
            if quantity_change > 0:
                report["summary"]["total_quantity_in"] += quantity_change
            else:
                report["summary"]["total_quantity_out"] += abs(quantity_change)

            report["transactions"].append({
                "transaction_id": tx.id,
                "date": tx.transaction_date.isoformat() if tx.transaction_date else None,
                "item_type": tx.item_type,
                "item_id": tx.item_id,
                "item_name": item_details.get("name",
                                              f"Unknown {tx.item_type}") if item_details else f"Unknown {tx.item_type}",
                "transaction_type": tx.transaction_type.name if tx.transaction_type else "UNKNOWN",
                "adjustment_type": tx.adjustment_type.name if tx.adjustment_type else None,
                "quantity_change": quantity_change,
                "from_location": tx.from_location,
                "to_location": tx.to_location,
                "reference_id": getattr(tx, 'reference_id', None),  # Get reference if exists
                "reference_type": getattr(tx, 'reference_type', None),
                "notes": tx.notes,
                "performed_by": tx.performed_by,
            })

        # Calculate net change for summary
        report["summary"]["net_quantity_change"] = report["summary"]["total_quantity_in"] - report["summary"][
            "total_quantity_out"]

        # Round summary values
        report["summary"]["total_quantity_in"] = round(report["summary"]["total_quantity_in"], 4)
        report["summary"]["total_quantity_out"] = round(report["summary"]["total_quantity_out"], 4)
        report["summary"]["net_quantity_change"] = round(report["summary"]["net_quantity_change"], 4)

        logger.info(
            f"Movement report generated. Displaying {len(report['transactions'])} of {total_count} transactions.")
        # Transactions are typically sorted descending by date by the repository

        return report

    # Make sure the generate_inventory_report dispatcher calls these correctly
    def generate_inventory_report(self, report_type: str, filters: Optional[Dict[str, Any]] = None) -> Dict[
        str, Any]:
        """
        Generate an inventory report based on specified type and filters.
        (Dispatcher Implementation)
        """
        logger.info(f"Dispatching inventory report generation: type='{report_type}'")
        filters = filters or {}
        report_type_lower = report_type.lower()

        valid_report_types = ["summary", "detail", "valuation", "movement", "low_stock"]
        if report_type_lower not in valid_report_types:
            raise ValidationException(
                f"Invalid report type: {report_type}",
                {"report_type": [f"Must be one of: {', '.join(valid_report_types)}"]},
            )

        if report_type_lower == "summary":
            return self._generate_summary_report(filters)
        elif report_type_lower == "detail":
            return self._generate_detail_report(filters)
        elif report_type_lower == "valuation":
            # Valuation might not need many filters other than date
            as_of_date = filters.get("as_of_date")
            dt_as_of = datetime.fromisoformat(as_of_date) if isinstance(as_of_date, str) else None
            return self.calculate_inventory_value(as_of_date=dt_as_of)
        elif report_type_lower == "movement":
            return self._generate_movement_report(filters)
        elif report_type_lower == "low_stock":
            threshold = filters.get("threshold_percentage", 100.0)  # Default to at/below reorder point
            item_type = filters.get("item_type")
            low_stock_items = self.get_low_stock_items(threshold, item_type)  # Calls updated service method
            return {
                "report_type": "low_stock",
                "generated_at": datetime.now().isoformat(),
                "filters_applied": filters,
                "item_count": len(low_stock_items),
                "items": low_stock_items,  # Already formatted by get_low_stock_items
            }
        else:
            # Should be caught by initial validation, but as a fallback
            raise NotImplementedError(f"Report type '{report_type}' is not implemented.")


