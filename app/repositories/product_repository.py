# File: app/repositories/product_repository.py

import logging
from typing import List, Optional, Dict, Any, Tuple  # Added Tuple
from sqlalchemy.orm import Session, joinedload  # Added joinedload
from sqlalchemy import or_, and_, desc, func, case
from datetime import datetime

# --- Application Imports ---
# Adjust paths as per your project structure
from app.db.models.product import Product
from app.db.models.inventory import Inventory  # Import Inventory model
from app.db.models.enums import InventoryStatus, ProjectType  # Import necessary Enums
from app.repositories.base_repository import BaseRepository
from app.schemas.product import (
    ProductFilter,
)  # Import the filter schema used by the API/Service

logger = logging.getLogger(__name__)


class ProductRepository(BaseRepository[Product]):
    """
    Repository for Product entity operations.

    Provides methods for managing product data, including search,
    filtering by attributes, and retrieving information while considering
    related inventory status via JOINs.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the ProductRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Product

    def list_products_paginated(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[ProductFilter] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves a paginated list of products with filtering.
        Ensures Inventory is loaded for response serialization.
        """
        query = self.session.query(self.model)
        inventory_joined = False  # Track if we need to explicitly join

        # --- ALWAYS EAGER LOAD INVENTORY FOR RESPONSE ---
        # ProductResponse requires quantity, status, etc. from Inventory
        query = query.options(joinedload(self.model.inventory))
        # --- END EAGER LOAD ---

        if filters:
            # Determine if explicit JOIN is necessary for *filtering*
            if filters.status or filters.storageLocation:
                # Join only if not already implicitly joined by joinedload (SQLAlchemy might optimize)
                # Or simply join anyway if filtering requires it explicitly.
                # Using the relationship attribute directly often implies the join.
                # Let's check if direct filtering works first.
                # If filtering on Inventory fields fails without explicit .join(), add it back here.
                query = query.join(
                    self.model.inventory
                )  # Explicit join IF needed for filtering
                inventory_joined = True
                pass  # JOIN handled implicitly by joinedload option or added if needed below

            # Apply text search filter (on Product fields)
            if filters.searchQuery:
                # ... (search logic as before) ...
                search_term = f"%{filters.searchQuery}%"
                query = query.filter(
                    or_(
                        self.model.name.ilike(search_term),
                        self.model.sku.ilike(search_term),
                        self.model.description.ilike(search_term),
                    )
                )

            # Apply Product Type filter
            if filters.productType:
                # ... (type filter logic as before) ...
                try:
                    enum_types = [ProjectType(ptype) for ptype in filters.productType]
                    query = query.filter(self.model.product_type.in_(enum_types))
                except ValueError:
                    logger.warning(
                        f"Invalid product type filter received: {filters.productType}"
                    )

            # Apply Status filter (on Inventory field)
            if filters.status:
                # No need for explicit join check here if joinedload works for filtering
                # if not inventory_joined: query = query.join(self.model.inventory); inventory_joined = True
                try:
                    enum_statuses = [InventoryStatus(stat) for stat in filters.status]
                    # Filter using the relationship attribute
                    query = query.filter(
                        Product.inventory.has(Inventory.status.in_(enum_statuses))
                    )
                except ValueError:
                    logger.warning(f"Invalid status filter received: {filters.status}")

            # Apply Storage Location filter (on Inventory field)
            if filters.storageLocation:
                # if not inventory_joined: query = query.join(self.model.inventory); inventory_joined = True
                # Filter using the relationship attribute
                query = query.filter(
                    Product.inventory.has(
                        Inventory.storage_location == filters.storageLocation
                    )
                )

            # Apply Price Range filter
            if filters.priceRange:
                # ... (price filter logic as before) ...
                if filters.priceRange.min is not None:
                    query = query.filter(
                        self.model.selling_price >= filters.priceRange.min
                    )
                if filters.priceRange.max is not None:
                    query = query.filter(
                        self.model.selling_price <= filters.priceRange.max
                    )

            # Apply Date Added Range filter
            if filters.dateAddedRange:
                # ... (date filter logic as before) ...
                if filters.dateAddedRange.get("from"):
                    try:
                        from_date = datetime.fromisoformat(
                            filters.dateAddedRange["from"]
                        )
                        query = query.filter(self.model.createdAt >= from_date)
                    except (ValueError, TypeError):
                        logger.warning(
                            f"Invalid date_from filter: {filters.dateAddedRange['from']}"
                        )
                if filters.dateAddedRange.get("to"):
                    try:
                        to_date_str = filters.dateAddedRange["to"]
                        to_date = datetime.fromisoformat(
                            f"{to_date_str}T23:59:59.999999"
                        )
                        query = query.filter(self.model.createdAt <= to_date)
                    except (ValueError, TypeError):
                        logger.warning(
                            f"Invalid date_to filter: {filters.dateAddedRange['to']}"
                        )

        # Get the total count *before* pagination
        # Be careful: count() after joinedload might be inefficient or behave unexpectedly
        # depending on the relationship type. For one-to-one, it's usually fine.
        # Consider a separate count query if performance issues arise.
        # total_query = query.statement.with_only_columns([func.count()]).order_by(None)
        # total = self.session.execute(total_query).scalar()
        total = query.count()  # Try simple count first

        # Apply sorting
        query = query.order_by(self.model.name)

        # Apply pagination
        entities: List[Product] = query.offset(skip).limit(limit).all()

        # Decrypt if necessary
        items_list = [self._decrypt_sensitive_fields(entity) for entity in entities]

        # Log inventory loading status for debugging
        # for prod in items_list:
        #     logger.debug(f"Product ID {prod.id}, Inventory Loaded: {hasattr(prod, 'inventory') and prod.inventory is not None}")
        #     if hasattr(prod, 'inventory') and prod.inventory:
        #         logger.debug(f"  Inventory ID: {prod.inventory.id}, Qty: {prod.inventory.quantity}")

        return {"items": items_list, "total": total}

    def get_products_by_status(
        self, status: InventoryStatus, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """
        Get products by their inventory status by joining with Inventory.

        Args:
            status (InventoryStatus): The inventory status to filter by.
            skip (int): Number of records to skip (for pagination).
            limit (int): Maximum number of records to return.

        Returns:
            List[Product]: List of products with the specified inventory status.
        """
        logger.debug(
            f"Fetching products by status: {status.name}, skip: {skip}, limit: {limit}"
        )
        query = (
            self.session.query(self.model)
            .join(self.model.inventory)  # Join Product with Inventory
            .filter(Inventory.status == status)  # Filter on Inventory.status
            .order_by(self.model.name)  # Optional: order results
        )

        entities = query.offset(skip).limit(limit).all()
        logger.debug(f"Found {len(entities)} products with status {status.name}")
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_products_by_pattern(
        self, pattern_id: int, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """
        Get products based on a specific pattern. (No change needed here)
        """
        logger.debug(
            f"Fetching products by pattern ID: {pattern_id}, skip: {skip}, limit: {limit}"
        )
        query = (
            self.session.query(self.model)
            .filter(
                self.model.pattern_id == pattern_id  # Corrected attribute name from ERD
            )
            .order_by(self.model.name)
        )

        entities = query.offset(skip).limit(limit).all()
        logger.debug(f"Found {len(entities)} products for pattern ID {pattern_id}")
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_products_by_price_range(
        self, min_price: float, max_price: float, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """
        Get products within a specific price range. (No change needed here)
        """
        logger.debug(
            f"Fetching products by price range: {min_price}-{max_price}, skip: {skip}, limit: {limit}"
        )
        query = (
            self.session.query(self.model)
            .filter(
                and_(
                    self.model.selling_price >= min_price,
                    self.model.selling_price <= max_price,
                )
            )
            .order_by(self.model.selling_price)
        )

        entities = query.offset(skip).limit(limit).all()
        logger.debug(
            f"Found {len(entities)} products in price range {min_price}-{max_price}"
        )
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_best_selling_products(self, limit: int = 10) -> List[Product]:
        """
        Get best-selling products based on sales velocity. (No change needed here)
        """
        logger.debug(f"Fetching top {limit} best-selling products")
        query = (
            self.session.query(self.model)
            .filter(self.model.sales_velocity > 0)  # Corrected attribute name from ERD
            .order_by(desc(self.model.sales_velocity))
            .limit(limit)
        )

        entities = query.all()
        logger.debug(f"Found {len(entities)} best-selling products")
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_products_low_in_stock(
        self, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """
        Get products that are low in stock (quantity <= reorder point, but > 0).
        Queries via Inventory table JOIN.

        Args:
            skip (int): Number of records to skip (for pagination).
            limit (int): Maximum number of records to return.

        Returns:
            List[Product]: List of products low in stock.
        """
        logger.debug(f"Fetching low-in-stock products, skip: {skip}, limit: {limit}")
        query = (
            self.session.query(self.model)
            .join(self.model.inventory)  # Join Product with Inventory
            .filter(
                and_(
                    Inventory.quantity > 0,
                    # Compare Inventory quantity with Product reorder point
                    Inventory.quantity <= self.model.reorder_point,
                )
            )
            .order_by(self.model.name)  # Optional: order results
        )

        entities = query.offset(skip).limit(limit).all()
        logger.debug(f"Found {len(entities)} low-in-stock products")
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_products_out_of_stock(
        self, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """
        Get products that are out of stock (quantity <= 0).
        Queries via Inventory table JOIN.

        Args:
            skip (int): Number of records to skip (for pagination).
            limit (int): Maximum number of records to return.

        Returns:
            List[Product]: List of out-of-stock products.
        """
        logger.debug(f"Fetching out-of-stock products, skip: {skip}, limit: {limit}")
        query = (
            self.session.query(self.model)
            .join(self.model.inventory)  # Join Product with Inventory
            .filter(Inventory.quantity <= 0)  # Filter on Inventory quantity
            .order_by(self.model.name)  # Optional: order results
        )

        entities = query.offset(skip).limit(limit).all()
        logger.debug(f"Found {len(entities)} out-of-stock products")
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    # --- Method Removed ---
    # def update_product_inventory(...):
    # This method is removed. Inventory quantity updates MUST be handled
    # through the Inventory entity/service to maintain data integrity,
    # as Product no longer directly stores quantity or status.

    def update_product_pricing(
        self,
        product_id: int,
        total_cost: Optional[float] = None,
        selling_price: Optional[float] = None,
    ) -> Optional[Product]:
        """
        Update a product's pricing information. (No change needed here,
        but ensure lastUpdated is handled correctly by TimestampMixin or BaseRepository)
        """
        logger.debug(f"Updating pricing for product ID: {product_id}")
        product = self.get_by_id(product_id)
        if not product:
            logger.warning(f"Product not found for pricing update: {product_id}")
            return None

        update_data = {}
        if total_cost is not None:
            update_data["total_cost"] = total_cost
            logger.debug(f"Setting total_cost to {total_cost} for product {product_id}")
        if selling_price is not None:
            update_data["selling_price"] = selling_price
            logger.debug(
                f"Setting selling_price to {selling_price} for product {product_id}"
            )

        if not update_data:
            logger.debug(f"No pricing fields to update for product {product_id}")
            return product  # Return unchanged product if no data provided

        # Use the base update method
        updated_product = self.update(product_id, update_data)
        logger.info(f"Pricing updated for product ID: {product_id}")
        return updated_product  # self.update already decrypts

    def search_products(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """
        Search for products by name, description, or SKU.
        (No change needed here, as it searches Product fields)
        """
        logger.debug(
            f"Searching products for query: '{query}', skip: {skip}, limit: {limit}"
        )
        search_term = f"%{query}%"
        search_query = (
            self.session.query(self.model)
            .filter(
                or_(
                    self.model.name.ilike(search_term),
                    self.model.description.ilike(search_term),
                    self.model.sku.ilike(search_term),
                )
            )
            .order_by(self.model.name)
        )

        entities = search_query.offset(skip).limit(limit).all()
        logger.debug(f"Found {len(entities)} products matching search query '{query}'")
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_product_by_sku(self, sku: str) -> Optional[Product]:
        """
        Get a product by its SKU. (No change needed here)
        """
        logger.debug(f"Fetching product by SKU: {sku}")
        entity = self.session.query(self.model).filter(self.model.sku == sku).first()
        if entity:
            logger.debug(f"Product found for SKU {sku}: ID {entity.id}")
        else:
            logger.debug(f"No product found for SKU {sku}")
        return self._decrypt_sensitive_fields(entity) if entity else None

    # --- Overridden Base Methods (If needed for specific Product logic) ---

    def create(self, data: Dict[str, Any]) -> Product:
        """
        Overrides base create to potentially handle relationships or specific defaults.
        Ensure Inventory record is created via the service layer.
        """
        # Example: Default cost if not provided
        if "total_cost" not in data:
            data["total_cost"] = 0.0
        if "selling_price" not in data:
            data["selling_price"] = 0.0
        # DO NOT set quantity/status here - InventoryService should handle it.
        logger.info(f"Creating product with SKU: {data.get('sku', 'N/A')}")
        product = super().create(data)
        logger.info(f"Product created with ID: {product.id}")
        return product

    def update(self, id: int, data: Dict[str, Any]) -> Optional[Product]:
        """
        Overrides base update. Prevent direct updates to quantity/status.
        InventoryService should be used for stock changes.
        """
        if "quantity" in data:
            logger.warning(
                f"Attempted direct update of 'quantity' for product {id}. Ignoring. Use InventoryService."
            )
            del data["quantity"]
        if "status" in data:
            logger.warning(
                f"Attempted direct update of 'status' for product {id}. Ignoring. Use InventoryService."
            )
            del data["status"]
        if "storageLocation" in data:
            logger.warning(
                f"Attempted direct update of 'storageLocation' for product {id}. Ignoring. Use InventoryService."
            )
            del data["storageLocation"]

        if not data:  # If only invalid fields were passed
            logger.debug(
                f"No valid fields to update for product {id} after removing stock fields."
            )
            return self.get_by_id(id)  # Return existing

        logger.info(f"Updating product ID: {id} with data: {list(data.keys())}")
        product = super().update(id, data)
        if product:
            logger.info(f"Product ID {id} updated.")
        else:
            logger.warning(f"Product ID {id} not found for update.")
        return product

    def get_by_id(self, id: int, load_inventory: bool = True) -> Optional[Product]:
        """
        Overrides base get_by_id to optionally eager load the inventory record.

        Args:
            id: The ID of the product.
            load_inventory: Whether to eager load the associated inventory record.

        Returns:
            The Product object or None if not found.
        """
        logger.debug(f"Fetching product by ID: {id}, load_inventory: {load_inventory}")
        query = self.session.query(self.model)
        if load_inventory:
            # Eager load the inventory relationship
            query = query.options(joinedload(self.model.inventory))
        entity = query.filter(self.model.id == id).first()

        if entity:
            logger.debug(f"Product ID {id} found.")
            if load_inventory and hasattr(entity, "inventory") and entity.inventory:
                logger.debug(
                    f" Eager loaded inventory record ID: {entity.inventory.id}"
                )
            elif load_inventory:
                logger.debug(
                    f" Eager load requested, but no inventory record found or relationship not loaded for product {id}"
                )
        else:
            logger.debug(f"Product ID {id} not found.")

        return self._decrypt_sensitive_fields(entity) if entity else None
