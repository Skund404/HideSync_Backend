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

from app.services.inventory_service import InventoryService
from app.services.pattern_service import PatternService
from app.services.material_service import MaterialService
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
    pattern_service: Optional[PatternService]
    # sale_service: Optional[SaleService]
    material_service: Optional[MaterialService]

    def __init__(
            self,
            session: Session,
            repository: Optional[ProductRepository] = None,
            # --- ACCEPT INJECTED SERVICES ---
            inventory_service: Optional[InventoryService] = None,
            pattern_service: Optional[PatternService] = None,
            material_service: Optional[MaterialService] = None,
            # --- END ACCEPT ---
            security_context=None,
            event_bus=None,
            cache_service=None,
            # --- Remove other services if not needed directly by __init__ ---
            # tool_service = None,
            # storage_service = None,
            # supplier_service = None,
    ):
        self.session = session
        self.repository = repository or ProductRepository(session)

        if not inventory_service:
            logger.error("CRITICAL: InventoryService was not provided to ProductService constructor!")
            raise ValueError("InventoryService is required for ProductService")
        self.inventory_service = inventory_service

        # --- STORE INJECTED SERVICES ---
        # Store them even if optional, methods will check for their existence
        self.pattern_service = pattern_service
        self.material_service = material_service
        # --- END STORE ---

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
        Generates SKU if not provided, validates uniqueness.
        Refreshes the product to load the inventory relationship before returning.
        """
        logger.info(
            f"Service: Creating product. User ID {user_id or 'Unknown'}. Provided SKU: '{product_in.sku or 'None'}'")
        user_id = user_id or self._get_current_user_id()

        with self.transaction():  # Ensures atomicity
            final_sku: str
            product_data = product_in.model_dump(
                exclude={'quantity', 'status', 'storage_location', 'sku'})  # Exclude SKU initially too

            # --- SKU Handling Logic ---
            if product_in.sku:
                # 1a. Validate Provided SKU
                provided_sku = product_in.sku.strip().upper()
                if not provided_sku:
                    raise ValidationException("Provided SKU cannot be empty.", {"sku": "Cannot be empty."})
                if self.repository.get_product_by_sku(provided_sku):
                    logger.warning(f"SKU conflict during creation: '{provided_sku}' already exists.")
                    raise BusinessRuleException(f"SKU '{provided_sku}' already exists.", "PRODUCT_SKU_CONFLICT")
                final_sku = provided_sku
                logger.info(f"Using provided valid SKU: {final_sku}")
            else:
                # 1b. Generate SKU if not provided
                max_retries = 3
                for attempt in range(max_retries):
                    # Make sure name is in product_data before generating
                    if 'name' not in product_data:
                        raise ValidationException("Product name is required to generate SKU.",
                                                  {"name": "Required field."})
                    generated_sku = self._generate_sku(product_data['name'], product_data.get('product_type'))
                    if not self.repository.get_product_by_sku(generated_sku):
                        final_sku = generated_sku
                        logger.info(f"Generated unique SKU: {final_sku} (attempt {attempt + 1})")
                        break
                    logger.warning(f"Generated SKU '{generated_sku}' collided (attempt {attempt + 1}). Retrying...")
                else:
                    logger.error(f"Failed to generate a unique SKU after {max_retries} attempts.")
                    raise HideSyncException("Failed to generate a unique SKU due to collisions.")
            # --- End SKU Handling ---

            # Add the final SKU to the data before creating
            product_data['sku'] = final_sku

            # 2. Create Product record
            product = self.repository.create(product_data)
            logger.info(f"Service: Product record created with ID: {product.id}")

            # 3. Create associated Inventory record via InventoryService
            try:
                initial_quantity = product_in.quantity if product_in.quantity is not None else 0.0
                self.inventory_service.create_inventory(
                    item_type="product",
                    item_id=product.id,
                    quantity=initial_quantity,
                    storage_location=product_in.storage_location,
                    user_id=user_id
                )
                logger.info(f"Service: Inventory record created via InventoryService for product ID: {product.id}")
            except Exception as e:
                logger.error(f"Service: Failed to create inventory record for product {product.id}: {e}", exc_info=True)
                # The transaction context manager will handle rollback
                raise HideSyncException(f"Failed to initialize inventory for product {product.id}") from e

            # --- REFRESH PRODUCT TO LOAD INVENTORY RELATIONSHIP ---
            try:
                self.session.flush()  # Ensure changes are sent to DB before refresh
                self.session.refresh(product, attribute_names=['inventory'])
                logger.debug(
                    f"Refreshed product {product.id}, inventory loaded: {hasattr(product, 'inventory') and product.inventory is not None}")
            except Exception as refresh_err:
                logger.error(f"Failed to refresh product {product.id} to load inventory: {refresh_err}", exc_info=True)
                # Raise an exception as the returned object might be incomplete
                raise HideSyncException(
                    f"Failed to load inventory details for newly created product {product.id}") from refresh_err
            # --- END REFRESH ---

            # 4. Publish Event (after successful creation and refresh)
            if self.event_bus:
                self.event_bus.publish(
                    ProductCreated(
                        product_id=product.id, name=product.name, sku=product.sku,
                        product_type=product.product_type, user_id=user_id
                    )
                )

            logger.info(f"Service: Product {product.id} '{product.name}' created successfully.")
            # The product object now has its .inventory relationship populated
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

    class ProductService(BaseService[Product]):
        # ... (__init__ and other methods as defined previously) ...

        def calculate_cost_breakdown(self, product_id: int) -> Dict[str, Any]:
            """
            Calculates (or recalculates) the detailed cost breakdown for a product
            based on its associated pattern's material requirements and potentially
            configured labor/overhead costs. Updates the product record.

            Requires PatternService and MaterialService to be injected during
            ProductService initialization.

            Args:
                product_id: The ID of the product.

            Returns:
                A dictionary representing the cost breakdown, including any errors encountered:
                {
                    "material_costs": float,
                    "labor_costs": float,         # Currently sourced from product or default 0.0
                    "overhead_costs": float,      # Currently sourced from product or default 0.0
                    "total_calculated_cost": float, # Sum of the above
                    "materials_detail": [         # Detailed list of material costs
                        { "material_id": int, "name": str, "type": str,
                          "quantity_required": float, "unit_required": str,
                          "cost_per_unit": float, "material_base_unit": str,
                          "total_cost": float }, ...
                    ],
                    "calculation_timestamp": str, # ISO format timestamp
                    "errors": List[str]           # List of errors encountered during calculation
                }

            Raises:
                EntityNotFoundException: If the product itself is not found.
                HideSyncException: If required services (PatternService, MaterialService)
                                   were not injected or if a critical error occurs.
                                   (Or returns breakdown dict with errors depending on preference)
            """
            logger.info(f"Service: Calculating cost breakdown for product ID: {product_id}")

            # 1. --- CHECK FOR DEPENDENCIES ---
            if not self.pattern_service or not self.material_service:
                error_msg = f"Cannot calculate cost for product {product_id}: PatternService or MaterialService not available/injected."
                logger.error(error_msg)
                # Option 1: Raise exception to halt immediately
                raise HideSyncException("Required services for cost calculation are not configured.")
                # Option 2: Return a dict indicating failure (less disruptive but caller needs to check)
                # return {
                #     "material_costs": 0.0, "labor_costs": 0.0, "overhead_costs": 0.0,
                #     "total_calculated_cost": 0.0, "materials_detail": [],
                #     "calculation_timestamp": datetime.now().isoformat(),
                #     "errors": ["Cost calculation services unavailable."]
                # }
            # --- END DEPENDENCY CHECK ---

            # 2. Get Product
            # Use the repository directly to ensure we get the latest DB state before calculation
            product = self.repository.get_by_id(product_id, load_inventory=False)  # Don't need inventory loaded here
            if not product:
                raise EntityNotFoundException("Product", product_id)

            # 3. Initialize Breakdown Structure
            breakdown = {
                "material_costs": 0.0,
                "labor_costs": getattr(product, 'labor_cost', 0.0),  # Get from product or default
                "overhead_costs": getattr(product, 'overhead_cost', 0.0),  # Get from product or default
                "total_calculated_cost": 0.0,  # Will sum at the end
                "materials_detail": [],
                "calculation_timestamp": datetime.now().isoformat(),
                "errors": []  # To log any issues during calculation
            }

            # 4. Calculate Material Costs (Requires Pattern & Material Services)
            pattern_id = product.pattern_id
            if not pattern_id:
                logger.warning(f"Product {product_id} has no associated pattern_id. Cannot calculate material costs.")
                breakdown["errors"].append("No pattern associated with product.")
            else:
                try:
                    # --- Use injected services ---
                    # Assume pattern service returns dict like: { "material_id": {"quantity_required": X, "unit": "Y", ...} }
                    if not hasattr(self.pattern_service, 'get_material_requirements_for_pattern'):
                        # This check might be overly defensive if types are hinted correctly
                        raise NotImplementedError("PatternService needs 'get_material_requirements_for_pattern'")

                    # Fetch requirements from PatternService
                    material_reqs = self.pattern_service.get_material_requirements_for_pattern(pattern_id)
                    logger.debug(f"Material requirements for pattern {pattern_id}: {material_reqs}")

                    if not material_reqs:
                        logger.warning(f"No material requirements found for pattern {pattern_id}.")
                        breakdown["errors"].append(f"No materials defined for pattern {pattern_id}.")
                    else:
                        # Iterate through required materials
                        for mat_id_str, req_data in material_reqs.items():
                            try:
                                mat_id = int(mat_id_str)  # Ensure ID is integer
                                quantity_needed = float(req_data.get('quantity_required', 0.0))
                                unit_needed = req_data.get('unit', 'unknown_unit')  # Unit required by the pattern

                                if quantity_needed <= 0:
                                    continue  # Skip if no quantity needed

                                # Fetch material details using MaterialService
                                material = self.material_service.get_by_id(mat_id)
                                if not material:
                                    error_msg = f"Material ID {mat_id} required by pattern {pattern_id} not found."
                                    logger.warning(error_msg)
                                    breakdown["errors"].append(error_msg)
                                    continue  # Skip this material

                                # Extract details from the material object
                                mat_cost_per_unit = getattr(material, 'cost', 0.0)  # Cost per material's base unit
                                mat_name = getattr(material, 'name', f"Material {mat_id}")
                                # Safely get enum names or string values
                                mat_type_obj = getattr(material, 'material_type', 'UNKNOWN')
                                mat_type = mat_type_obj.name if hasattr(mat_type_obj, 'name') else str(mat_type_obj)
                                mat_unit_obj = getattr(material, 'unit', 'unknown_unit')
                                mat_unit = mat_unit_obj.name if hasattr(mat_unit_obj, 'name') else str(mat_unit_obj)

                                # --- Unit Conversion Logic Placeholder ---
                                # TODO: Implement robust unit conversion if needed
                                cost_multiplier = 1.0
                                if unit_needed.lower() != mat_unit.lower():
                                    logger.warning(
                                        f"Unit mismatch for material {mat_id} ('{mat_name}'): Pattern requires '{unit_needed}', Material cost is per '{mat_unit}'. Cost calculation might be inaccurate without conversion logic.")
                                    breakdown["errors"].append(
                                        f"Unit mismatch for material {mat_id} ('{mat_name}'). Check pattern requirements vs material definition.")
                                    # Example: If conversion is impossible, maybe skip or use multiplier 1?
                                    # cost_multiplier = get_conversion_factor(mat_unit, unit_needed) # Hypothetical function

                                # Calculate total cost for this material
                                material_total_cost = quantity_needed * mat_cost_per_unit * cost_multiplier
                                breakdown["material_costs"] += material_total_cost

                                # Add detail to the breakdown
                                breakdown["materials_detail"].append({
                                    "material_id": mat_id,
                                    "name": mat_name,
                                    "type": mat_type,
                                    "quantity_required": round(quantity_needed, 4),
                                    "unit_required": unit_needed,
                                    "cost_per_unit": round(mat_cost_per_unit, 4),  # Cost per material's base unit
                                    "material_base_unit": mat_unit,
                                    "total_cost": round(material_total_cost, 2)
                                })

                            except ValueError:
                                logger.warning(
                                    f"Invalid material ID format '{mat_id_str}' in requirements for pattern {pattern_id}.")
                                breakdown["errors"].append(f"Invalid material ID format: {mat_id_str}")
                            except EntityNotFoundException as enf_mat:
                                # Catch if material_service.get_by_id raises this
                                logger.warning(f"Material referenced by pattern not found: {enf_mat}")
                                breakdown["errors"].append(f"Material ID {mat_id_str} not found.")
                            except Exception as mat_err:
                                logger.error(
                                    f"Error processing material {mat_id_str} for product {product_id}: {mat_err}",
                                    exc_info=True)
                                breakdown["errors"].append(
                                    f"Error processing material {mat_id_str}: {str(mat_err)[:100]}")  # Limit error message length

                except EntityNotFoundException as e:
                    # This catches if pattern_service.get_material_requirements... raises EntityNotFound for the pattern
                    logger.warning(f"Pattern {pattern_id} not found for product {product_id} cost calculation: {e}")
                    breakdown["errors"].append(f"Pattern {pattern_id} not found.")
                except NotImplementedError as e:
                    logger.error(f"Missing required service method for cost calculation: {e}")
                    breakdown["errors"].append(f"Service method missing: {e}")
                    # Optionally re-raise as HideSyncException if critical
                    # raise HideSyncException("Internal configuration error for cost calculation.") from e
                except Exception as e:
                    logger.error(f"Error calculating material costs for product {product_id}: {e}", exc_info=True)
                    breakdown["errors"].append(f"Unexpected error during material cost calculation: {str(e)}")
                    # Decide if this should be a critical failure

            # 5. --- Sum Total Calculated Cost ---
            breakdown["total_calculated_cost"] = round(
                breakdown["material_costs"] + breakdown["labor_costs"] + breakdown["overhead_costs"],
                2
            )

            # 6. --- Update Product Record in Database ---
            # Use a transaction to ensure atomicity if needed (though update is usually atomic)
            try:
                with self.transaction():  # Use the service's transaction context manager
                    # Prepare data for update, ensuring JSON serialization
                    # Store the detailed breakdown as JSON string
                    cost_update_data = {
                        "cost_breakdown": json.dumps(breakdown, default=str),
                        # Use default=str for non-serializable types like datetime
                        "total_cost": breakdown["total_calculated_cost"]
                    }
                    # Use the repository's update method
                    updated_product = self.repository.update(product_id, cost_update_data)
                    if not updated_product:
                        # This shouldn't happen if the product existed initially
                        logger.error(f"Failed to update product {product_id} in DB after cost calculation.")
                        breakdown["errors"].append("Failed to save calculated costs to product record.")
                        # Raise an exception here if saving is critical
                        raise HideSyncException(f"Failed to save calculated costs for product {product_id}")
                    else:
                        logger.info(
                            f"Successfully updated cost breakdown and total cost for product ID {product_id}. New total cost: {breakdown['total_calculated_cost']}")
                        # Invalidate cache only after successful update and commit
                        self._invalidate_product_cache(product_id)

            except Exception as update_err:
                # Catch errors during the update/commit phase
                logger.error(f"Failed to save updated costs for product {product_id}: {update_err}", exc_info=True)
                breakdown["errors"].append(f"Failed to save calculated costs to product record: {str(update_err)}")
                # Decide if this should raise an exception or just be logged in the result
                # raise HideSyncException(f"Failed to save calculated costs for product {product_id}") from update_err

            # 7. Return the detailed breakdown dictionary (including any errors)
            return breakdown