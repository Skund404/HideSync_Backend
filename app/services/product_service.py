# File: services/product_service.py

import logging
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

# --- Application Imports ---
# Adjust paths as per your project structure
from app.core.events import DomainEvent
from app.core.exceptions import (
    BusinessRuleException,
    ConcurrentOperationException,
    EntityNotFoundException,
    HideSyncException,
    InsufficientInventoryException, # Import if needed for adjust_inventory handling
    ValidationException,
)
# from app.core.validation import validate_input # Using Pydantic schemas in endpoints now
from app.db.models.enums import InventoryStatus, ProjectType, InventoryAdjustmentType # Added necessary enums
from app.db.models import Product


from app.repositories.product_repository import ProductRepository
from app.services.base_service import BaseService
# Import dependent services (ensure they are injected in __init__)
from app.services.inventory_service import InventoryService
# from app.services.pattern_service import PatternService
# from app.services.sale_service import SaleService
# from app.services.material_service import MaterialService # Only if calculating costs here
from app.schemas.product import ProductCreate, ProductUpdate, ProductFilter, ProductList, ProductResponse # Import necessary schemas

logger = logging.getLogger(__name__)


# --- Domain Events ---
class ProductCreated(DomainEvent):
    def __init__(self, product_id: int, name: str, sku: str, product_type: Optional[ProjectType], user_id: Optional[int] = None):
        super().__init__()
        self.product_id = product_id; self.name = name; self.sku = sku;
        self.product_type = product_type.name if product_type else None; self.user_id = user_id

class ProductUpdated(DomainEvent):
    def __init__(self, product_id: int, name: str, sku: str, changes: List[str], user_id: Optional[int] = None):
        super().__init__()
        self.product_id = product_id; self.name = name; self.sku = sku;
        self.changes = changes; self.user_id = user_id

class ProductDeleted(DomainEvent):
     def __init__(self, product_id: int, name: str, sku: str, user_id: Optional[int] = None):
        super().__init__()
        self.product_id = product_id; self.name = name; self.sku = sku;
        self.user_id = user_id

class ProductInventoryChanged(DomainEvent):
     def __init__(self, product_id: int, name: str, sku: str, previous_quantity: float, new_quantity: float, reason: str, user_id: Optional[int] = None):
        super().__init__()
        self.product_id = product_id; self.name = name; self.sku = sku;
        self.previous_quantity = previous_quantity; self.new_quantity = new_quantity;
        self.change = new_quantity - previous_quantity; self.reason = reason;
        self.user_id = user_id
# --- End Domain Events ---


class ProductService(BaseService[Product]):
    """
    Service layer for managing Product entities.
    Coordinates interactions between the Product API endpoints,
    the ProductRepository, InventoryService, and other related services.
    Handles business logic, validation, event publishing, and caching for Products.
    """

    # Type hint dependencies for clarity
    inventory_service: InventoryService
    # pattern_service: Optional[PatternService]
    # sale_service: Optional[SaleService]
    # material_service: Optional[MaterialService]

    def __init__(
        self,
        session: Session,
        repository: Optional[ProductRepository] = None, # Allow repo injection
        inventory_service: Optional[InventoryService] = None, # << ACCEPT inventory_service
        security_context=None,
        event_bus=None,
        cache_service=None,
        # ... other optional service args ...
    ):
        self.session = session
        self.repository = repository or ProductRepository(session) # Instantiate repo if not provided

        # --- Store Injected InventoryService ---
        if not inventory_service: # Check if it was actually passed
             logger.error("CRITICAL: InventoryService was not provided to ProductService constructor!")
             raise ValueError("InventoryService is required for ProductService")
        self.inventory_service = inventory_service # Store the injected instance

        # Core services
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service

    def _get_current_user_id(self) -> Optional[int]:
        """Helper to safely get current user ID."""
        if self.security_context and hasattr(self.security_context, 'current_user') and self.security_context.current_user:
            # Ensure the user object actually has an id and return it
            user_id = getattr(self.security_context.current_user, 'id', None)
            return int(user_id) if user_id is not None else None
        return None

    # --- CRUD Operations ---

    def create_product(self, product_in: ProductCreate, user_id: Optional[int] = None) -> Product:
        """
        Creates a new product and its associated inventory record.

        Args:
            product_in: Validated data for the new product (from endpoint).
            user_id: ID of the user performing the action.

        Returns:
            The created Product ORM instance.
        """
        logger.info(f"Service: Creating product with SKU '{product_in.sku}' by user ID {user_id or 'Unknown'}")
        user_id = user_id or self._get_current_user_id()

        with self.transaction():
            # 1. Validate SKU uniqueness
            if self.repository.get_product_by_sku(product_in.sku):
                logger.warning(f"SKU conflict during creation: '{product_in.sku}' already exists.")
                raise BusinessRuleException(f"SKU '{product_in.sku}' already exists.", "PRODUCT_SKU_CONFLICT")

            # 2. Prepare data for repository
            product_data = product_in.model_dump(exclude={'quantity', 'status', 'storage_location'}) # Exclude stock fields

            # Ensure SKU generation if needed (repository might also do this)
            if not product_data.get('sku'):
                 product_data['sku'] = self._generate_sku(product_data['name'], product_data.get('product_type'))
                 logger.info(f"Generated SKU '{product_data['sku']}' for new product.")

            # 3. Create Product record
            product = self.repository.create(product_data)
            logger.info(f"Service: Product record created with ID: {product.id}")

            # 4. Create associated Inventory record via InventoryService
            try:
                initial_quantity = product_in.quantity if product_in.quantity is not None else 0.0
                # Let Inventory Service determine initial status based on quantity & reorder point
                # initial_status = InventoryStatus.OUT_OF_STOCK if initial_quantity <= 0 else InventoryStatus.IN_STOCK
                # No - pass quantity and let inventory service handle status logic

                self.inventory_service.create_inventory(
                    item_type="product",
                    item_id=product.id,
                    quantity=initial_quantity,
                    # status=initial_status, # Let InventoryService determine status
                    storage_location=product_in.storage_location,
                    user_id=user_id
                )
                logger.info(f"Service: Inventory record created via InventoryService for product ID: {product.id}")
            except Exception as e:
                logger.error(f"Service: Failed to create inventory record for product {product.id}: {e}", exc_info=True)
                raise HideSyncException(f"Failed to initialize inventory for product {product.id}") from e # Rollback transaction

            # 5. Publish Event
            if self.event_bus:
                self.event_bus.publish(
                    ProductCreated(
                        product_id=product.id, name=product.name, sku=product.sku,
                        product_type=product.product_type, user_id=user_id
                    )
                )

            self.session.flush()
            self.session.refresh(product, attribute_names=['inventory'])

            logger.info(f"Service: Product {product.id} '{product.name}' created successfully.")
            return product

    def update_product(self, product_id: int, product_update: ProductUpdate, user_id: Optional[int] = None) -> Product:
        """
        Updates product details (non-stock related fields).

        Args:
            product_id: ID of the product to update.
            product_update: Validated update data.
            user_id: ID of the user performing the action.

        Returns:
            The updated Product ORM instance.
        """
        logger.info(f"Service: Updating product ID: {product_id} by user ID {user_id or 'Unknown'}")
        user_id = user_id or self._get_current_user_id()

        with self.transaction():
            # 1. Get existing product
            product = self.repository.get_by_id(product_id, load_inventory=False) # Don't need inventory loaded for this
            if not product:
                raise EntityNotFoundException("Product", product_id)

            # 2. Prepare update data
            update_data = product_update.model_dump(exclude_unset=True, exclude={'quantity', 'status', 'storage_location'})

            if not update_data:
                 logger.info(f"Service: No valid fields provided to update for product {product_id}.")
                 return product

            # 3. Validate SKU uniqueness if changed
            new_sku = update_data.get('sku')
            if new_sku and new_sku != product.sku:
                existing = self.repository.get_product_by_sku(new_sku)
                if existing and existing.id != product_id:
                    raise BusinessRuleException(f"SKU '{new_sku}' already exists.", "PRODUCT_SKU_CONFLICT")

            # 4. Update using repository (which guards stock fields)
            updated_product = self.repository.update(product_id, update_data)
            if not updated_product:
                 raise HideSyncException(f"Update failed unexpectedly for product {product_id}")

            # 5. Check if reorder_point changed - may need to update Inventory status via InventoryService
            if 'reorder_point' in update_data and self.inventory_service:
                try:
                    # Ask inventory service to re-evaluate status based on new reorder point
                    logger.info(f"Reorder point changed for {product_id}, triggering inventory status re-evaluation.")
                    # This requires InventoryService to have a method like this:
                    self.inventory_service.reevaluate_status(item_type="product", item_id=product_id)
                except Exception as e:
                    logger.error(f"Failed to trigger inventory status re-evaluation for product {product_id}: {e}", exc_info=True)
                    # Decide if this should be a critical failure

            # 6. Publish event
            if self.event_bus:
                self.event_bus.publish(
                    ProductUpdated(
                        product_id=updated_product.id, name=updated_product.name, sku=updated_product.sku,
                        changes=list(update_data.keys()), user_id=user_id
                    )
                )

            # 7. Invalidate Cache
            self._invalidate_product_cache(product_id)

            self.session.refresh(updated_product)
            logger.info(f"Service: Product {product_id} updated successfully.")
            return updated_product

    def delete_product(self, product_id: int, user_id: Optional[int] = None) -> bool:
        """
        Deletes a product and its associated inventory record.

        Args:
            product_id: ID of the product to delete.
            user_id: ID of the user performing the action.

        Returns:
            True if deletion was successful.
        """
        logger.info(f"Service: Deleting product ID: {product_id} by user ID {user_id or 'Unknown'}")
        user_id = user_id or self._get_current_user_id()

        with self.transaction():
            # 1. Get product
            product = self.repository.get_by_id(product_id, load_inventory=False)
            if not product:
                raise EntityNotFoundException("Product", product_id)

            product_name = product.name
            product_sku = product.sku

            # 2. Check business rules (e.g., active sales)
            if self._has_active_sales(product_id):
                 raise BusinessRuleException("Cannot delete product with active sales", "PRODUCT_ACTIVE_SALES")

            # 3. Delete associated Inventory record via InventoryService
            try:
                deleted_inv = self.inventory_service.delete_inventory(item_type="product", item_id=product_id)
                if not deleted_inv:
                     logger.warning(f"Service: Inventory record for product {product_id} was not found or delete failed.")
            except Exception as e:
                logger.error(f"Service: Error deleting inventory for product {product_id}: {e}", exc_info=True)
                raise HideSyncException(f"Failed to delete inventory for product {product_id}") from e

            # 4. Delete the Product record
            deleted_prod = self.repository.delete(product_id)
            if not deleted_prod:
                 raise HideSyncException(f"Product deletion failed unexpectedly for {product_id}")

            # 5. Publish event
            if self.event_bus:
                self.event_bus.publish(
                    ProductDeleted(product_id=product_id, name=product_name, sku=product_sku, user_id=user_id)
                )

            # 6. Invalidate cache
            self._invalidate_product_cache(product_id)

            logger.info(f"Service: Product {product_id} deleted successfully.")
            return True

    # --- Read Operations ---

    def get_product_by_id(self, product_id: int, load_inventory: bool = True) -> Optional[Product]:
        """Gets a product by ID, optionally loading inventory via relationship."""
        logger.debug(f"Service: Getting product by ID: {product_id}, load inventory: {load_inventory}")
        return self.repository.get_by_id(product_id, load_inventory=load_inventory)

    def get_product_by_sku(self, sku: str) -> Optional[Product]:
        """Gets a product by SKU."""
        logger.debug(f"Service: Getting product by SKU: {sku}")
        return self.repository.get_product_by_sku(sku)

    def list_products_paginated(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[ProductFilter] = None
    ) -> Dict[str, Any]:
        """
        Lists products with pagination and filtering using the repository.
        Repository handles JOINs with Inventory for status/location filters.

        Returns:
            Dict containing 'items': List[Product] and 'total': int.
        """
        logger.info(f"Service: Listing products paginated: skip={skip}, limit={limit}, filters={filters.model_dump(exclude_none=True) if filters else 'None'}")
        paginated_result = self.repository.list_products_paginated(
            skip=skip, limit=limit, filters=filters
        )
        logger.info(f"Service: Repository returned {len(paginated_result['items'])} items, total: {paginated_result['total']}")
        # Returns ORM objects, endpoint will serialize
        return paginated_result

    def get_product_with_details(self, product_id: int) -> Dict[str, Any]:
        """
        Gets detailed product view including related data (inventory, pattern, etc.).
        Uses the Product model's to_dict method which accesses inventory.
        """
        logger.debug(f"Service: Getting detailed view for product ID: {product_id}")
        cache_key = f"Product:detail:{product_id}"
        if self.cache_service:
            cached = self.cache_service.get(cache_key)
            if cached: return cached

        product = self.repository.get_by_id(product_id, load_inventory=True)
        if not product:
            raise EntityNotFoundException("Product", product_id)

        result = product.to_dict() # Uses inventory relationship for stock fields

        # Add other related details here if needed
        # if product.pattern_id and self.pattern_service: ...

        if self.cache_service:
            self.cache_service.set(cache_key, result, ttl=1800)

        return result

    # --- Inventory Specific Method (Delegation) ---

    def adjust_inventory(
            self,
            product_id: int,
            quantity_change: float,
            reason: str,
            # CHANGE THE DEFAULT VALUE HERE:
            adjustment_type: InventoryAdjustmentType = InventoryAdjustmentType.PHYSICAL_COUNT,
            # Or PHYSICAL_COUNT, etc.
            reference_id: Optional[str] = None,
            reference_type: Optional[str] = None,
            notes: Optional[str] = None,
            user_id: Optional[int] = None,
    ) -> Product:
        """
        Adjusts inventory for a specific product via InventoryService and returns the updated Product.
        """
        logger.info(f"Service: Delegating inventory adjustment for product ID {product_id}: change={quantity_change}, reason='{reason}'")
        user_id = user_id or self._get_current_user_id()

        # 1. Get product for event data and ensure it exists
        product = self.repository.get_by_id(product_id, load_inventory=True)
        if not product: raise EntityNotFoundException("Product", product_id)
        if not product.inventory: raise HideSyncException(f"Inventory record missing for product {product_id}")

        previous_quantity = product.inventory.quantity

        # 2. Call InventoryService (handles validation, update, transaction, events)
        try:
            updated_inventory = self.inventory_service.adjust_inventory(
                item_type="product", item_id=product_id, quantity_change=quantity_change,
                adjustment_type=adjustment_type, reason=reason,
                reference_id=reference_id, reference_type=reference_type, notes=notes, user_id=user_id,
                to_location=product.inventory.storage_location # Keep current location unless specified
            )
            new_quantity = updated_inventory.quantity
            logger.info(f"Service: InventoryService successful adjustment for product ID {product_id}. New quantity: {new_quantity}")

        except Exception as e: # Catch specific exceptions if needed (Insufficient, etc.)
            logger.error(f"Service: Inventory adjustment failed for product {product_id}: {e}", exc_info=True)
            raise # Re-raise the exception

        # 3. Publish Product-specific inventory change event
        if self.event_bus:
            self.event_bus.publish(
                ProductInventoryChanged(
                    product_id=product_id, name=product.name, sku=product.sku,
                    previous_quantity=previous_quantity, new_quantity=new_quantity,
                    reason=reason, user_id=user_id
                )
            )

        # 4. Invalidate Product cache (status might change via inventory relationship)
        self._invalidate_product_cache(product_id)

        # 5. Return the refreshed product instance
        # The inventory relationship on 'product' should be updated by the ORM if using the same session.
        # Fetching again guarantees latest state if sessions are complex.
        refreshed_product = self.repository.get_by_id(product_id, load_inventory=True)
        return refreshed_product if refreshed_product else product


    def get_low_stock_products(self) -> List[Dict[str, Any]]:
        """
        Gets products low in stock using the repository (which handles JOINs)
        and formats the output.
        """
        logger.info("Service: Fetching low stock products.")
        low_stock_products: List[Product] = self.repository.get_products_low_in_stock(limit=1000) # Use corrected repo method

        results = []
        for product in low_stock_products:
            if not product.inventory: continue

            # Format using product's to_dict and add extra calculated fields
            product_dict = product.to_dict() # Includes inventory data now
            reorder_point = product.reorder_point or 0
            quantity = product_dict.get('quantity', 0)

            product_dict["percent_of_reorder"] = round((quantity / reorder_point * 100) if reorder_point > 0 else 0, 1)
            product_dict["units_below_reorder"] = max(0, reorder_point - quantity)
            results.append(product_dict)

        logger.info(f"Service: Found {len(results)} low stock products.")
        return sorted(results, key=lambda x: x["percent_of_reorder"])

    # --- Methods needed for InventoryService Summary ---
    def count_all_products(self) -> int:
        """Counts all product records."""
        logger.debug("Service: Counting all products.")
        # Assuming BaseRepository has a count method or implement specific one
        if hasattr(self.repository, 'count'):
             return self.repository.count()
        else:
             # Fallback if base repo doesn't have count
             return len(self.repository.list(limit=100000)) # Less efficient

    def get_all_product_margins(self) -> List[Optional[float]]:
        """
        Retrieves the profit margin for all products.
        Optimized to fetch only necessary fields if possible.
        """
        logger.debug("Service: Getting margins for all products.")
        # This could be optimized in the repository to only select id, selling_price, total_cost
        all_products = self.repository.list(limit=100000) # Fetch all (potentially optimize)
        margins = [p.profit_margin for p in all_products] # Uses hybrid property
        return margins

    # --- Helper Methods ---
    def _invalidate_product_cache(self, product_id: int):
        """Invalidates cache entries for a specific product."""
        if self.cache_service:
            logger.debug(f"Invalidating cache for product ID: {product_id}")
            self.cache_service.invalidate(f"Product:{product_id}")
            self.cache_service.invalidate(f"Product:detail:{product_id}")
            self.cache_service.invalidate_by_pattern("Product:list:")

    def _has_active_sales(self, product_id: int) -> bool:
        """Placeholder: Check if product is in active sales orders."""
        # if self.sale_service and hasattr(self.sale_service, "has_active_sales_for_product"):
        #     return self.sale_service.has_active_sales_for_product(product_id)
        logger.warning(f"Placeholder check for active sales for product {product_id}. Returning False.")
        return False

    def _generate_sku(self, name: str, product_type: Optional[Union[ProjectType, str]] = None) -> str:
        """Generates a reasonably unique SKU."""
        name_part = "".join(c for c in name if c.isalnum()).upper()[:4]
        type_prefix = "PROD"
        if product_type:
            type_str = product_type.name if isinstance(product_type, ProjectType) else str(product_type)
            type_mapping = {"WALLET": "WAL", "BAG": "BAG", "BELT": "BLT", "ACCESSORY": "ACC", "CASE": "CSE", "CUSTOM": "CST", "OTHER": "OTH"}
            type_prefix = type_mapping.get(type_str.upper(), type_str[:3].upper())
        unique_part = uuid.uuid4().hex[:6].upper()
        sku = f"{type_prefix}-{name_part}-{unique_part}"
        return sku

    def calculate_cost_breakdown(self, product_id: int) -> Dict[str, Any]:
        """
        Calculates (or recalculates) the detailed cost breakdown for a product
        based on its associated pattern's material requirements and potentially
        configured labor/overhead costs. Updates the product record.

        Args:
            product_id: The ID of the product.

        Returns:
            A dictionary representing the cost breakdown:
            {
                "material_costs": float,
                "labor_costs": float,
                "overhead_costs": float,
                "total_calculated_cost": float, # Renamed for clarity
                "materials_detail": [ # Added more detail
                    { "material_id": int, "name": str, "type": str, "quantity": float, "unit": str, "cost_per_unit": float, "total_cost": float }, ...
                ]
            }

        Raises:
            EntityNotFoundException: If the product or required pattern/materials are not found.
            HideSyncException: If required services (PatternService, MaterialService) are not injected.
        """
        logger.info(f"Service: Calculating cost breakdown for product ID: {product_id}")

        # 1. Get Product
        product = self.repository.get_by_id(product_id, load_inventory=False)
        if not product:
            raise EntityNotFoundException("Product", product_id)

        # 2. Initialize Breakdown Structure
        breakdown = {
            "material_costs": 0.0,
            "labor_costs": getattr(product, 'labor_cost', 0.0), # Get from product or default
            "overhead_costs": getattr(product, 'overhead_cost', 0.0), # Get from product or default
            "total_calculated_cost": 0.0, # Will sum at the end
            "materials_detail": [],
            "calculation_timestamp": datetime.now().isoformat(),
            "errors": [] # To log any issues during calculation
        }

        # 3. Calculate Material Costs (Requires Pattern & Material Services)
        pattern_id = product.pattern_id
        if not pattern_id:
             logger.warning(f"Product {product_id} has no associated pattern_id. Cannot calculate material costs.")
             breakdown["errors"].append("No pattern associated with product.")
        elif not hasattr(self, 'pattern_service') or not self.pattern_service:
            logger.error("PatternService not available. Cannot calculate material costs.")
            breakdown["errors"].append("PatternService dependency missing.")
            # Optionally raise HideSyncException here if this is critical
        elif not hasattr(self, 'material_service') or not self.material_service:
             logger.error("MaterialService not available. Cannot calculate material costs.")
             breakdown["errors"].append("MaterialService dependency missing.")
             # Optionally raise HideSyncException here
        else:
            try:
                # Assume pattern service returns dict like: { "material_id": {"quantity_required": X, "unit": "Y", ...} }
                # This method might need adjustments based on actual PatternService implementation
                if not hasattr(self.pattern_service, 'get_material_requirements_for_pattern'):
                     raise NotImplementedError("PatternService needs 'get_material_requirements_for_pattern'")

                material_reqs = self.pattern_service.get_material_requirements_for_pattern(pattern_id)
                logger.debug(f"Material requirements for pattern {pattern_id}: {material_reqs}")

                if not material_reqs:
                     logger.warning(f"No material requirements found for pattern {pattern_id}.")
                     breakdown["errors"].append(f"No materials defined for pattern {pattern_id}.")

                for mat_id_str, req_data in material_reqs.items():
                    try:
                        mat_id = int(mat_id_str) # Ensure ID is integer
                        quantity_needed = float(req_data.get('quantity_required', 0.0))
                        unit_needed = req_data.get('unit', 'unknown_unit')

                        if quantity_needed <= 0:
                            continue

                        # Fetch material details for cost
                        material = self.material_service.get_by_id(mat_id)
                        if not material:
                            error_msg = f"Material ID {mat_id} required by pattern {pattern_id} not found."
                            logger.warning(error_msg)
                            breakdown["errors"].append(error_msg)
                            continue # Skip this material

                        mat_cost_per_unit = getattr(material, 'cost', 0.0)
                        mat_name = getattr(material, 'name', f"Material {mat_id}")
                        mat_type = getattr(material, 'material_type', 'UNKNOWN').name if hasattr(getattr(material, 'material_type', None), 'name') else getattr(material, 'material_type', 'UNKNOWN')
                        mat_unit = getattr(material, 'unit', 'unknown_unit').name if hasattr(getattr(material, 'unit', None), 'name') else getattr(material, 'unit', 'unknown_unit')


                        # Basic Unit Conversion (Example - NEEDS ROBUST IMPLEMENTATION)
                        # If required unit and material cost unit differ, attempt conversion
                        cost_multiplier = 1.0
                        if unit_needed.lower() != mat_unit.lower():
                             # Add specific conversion logic here based on your units (e.g., sqft to hide piece)
                             # This is complex and application specific!
                             logger.warning(f"Unit mismatch for material {mat_id}: Required '{unit_needed}', Material cost unit '{mat_unit}'. Cost calculation might be inaccurate without conversion logic.")
                             breakdown["errors"].append(f"Unit mismatch for material {mat_id} ('{mat_name}'). Check pattern requirements vs material definition.")
                             # Example placeholder: Assume cost is per primary unit listed on material
                             # cost_multiplier = get_conversion_factor(mat_unit, unit_needed)

                        material_total_cost = quantity_needed * mat_cost_per_unit * cost_multiplier
                        breakdown["material_costs"] += material_total_cost

                        breakdown["materials_detail"].append({
                            "material_id": mat_id,
                            "name": mat_name,
                            "type": mat_type,
                            "quantity_required": round(quantity_needed, 4),
                            "unit_required": unit_needed,
                            "cost_per_unit": round(mat_cost_per_unit, 4), # Cost per material's base unit
                            "material_base_unit": mat_unit,
                            "total_cost": round(material_total_cost, 2)
                        })

                    except ValueError:
                        logger.warning(f"Invalid material ID format '{mat_id_str}' in requirements for pattern {pattern_id}.")
                        breakdown["errors"].append(f"Invalid material ID format: {mat_id_str}")
                    except Exception as mat_err:
                         logger.error(f"Error processing material {mat_id_str} for product {product_id}: {mat_err}", exc_info=True)
                         breakdown["errors"].append(f"Error processing material {mat_id_str}: {str(mat_err)[:100]}") # Limit error message length

            except EntityNotFoundException as e:
                logger.warning(f"Pattern {pattern_id} not found for product {product_id} cost calculation: {e}")
                breakdown["errors"].append(f"Pattern {pattern_id} not found.")
            except NotImplementedError as e:
                 logger.error(f"Missing required service method for cost calculation: {e}")
                 breakdown["errors"].append(f"Service method missing: {e}")
            except Exception as e:
                 logger.error(f"Error calculating material costs for product {product_id}: {e}", exc_info=True)
                 breakdown["errors"].append(f"Unexpected error during material cost calculation.")

        # 4. Sum Total Calculated Cost
        breakdown["total_calculated_cost"] = round(
            breakdown["material_costs"] + breakdown["labor_costs"] + breakdown["overhead_costs"],
            2
        )

        # 5. Update Product Record (only update costs, not details list)
        # Use model_dump to serialize the breakdown dict correctly if needed by repo update
        try:
             cost_update_data = {
                  "cost_breakdown": json.dumps(breakdown), # Store full breakdown as JSON
                  "total_cost": breakdown["total_calculated_cost"]
             }
             self.repository.update(product_id, cost_update_data) # Use simple update
             logger.info(f"Updated cost breakdown and total cost for product ID {product_id}. New total cost: {breakdown['total_calculated_cost']}")
             # Invalidate cache after successful update
             self._invalidate_product_cache(product_id)
        except Exception as e:
             logger.error(f"Failed to update product {product_id} with calculated costs: {e}", exc_info=True)
             breakdown["errors"].append("Failed to save calculated costs to product record.")
             # Decide if this should raise an exception or just be logged in the result

        return breakdown # Return the detailed breakdown dictionary