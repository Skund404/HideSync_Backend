# File: services/product_service.py

"""
Product management service for the HideSync system.

This module provides comprehensive functionality for managing leathercraft products,
which represent sellable items in the HideSync system. It handles product creation,
catalog management, pricing, inventory tracking, and the relationships between
products, patterns, and materials.

Products represent the final output of the leathercraft process - items that can be
sold to customers. They may be based on patterns and typically have associated
costs, prices, and inventory tracking.

Key features:
- Product creation and catalog management
- Pricing and cost calculation
- Inventory tracking and management
- Pattern and material association
- Product variants and customization options
- Product search and categorization
- Sales performance tracking

The service follows clean architecture principles with clear separation from
the data access layer through repository interfaces, and integrates with other
services like PatternService and InventoryService.
"""

from typing import List, Optional, Dict, Any, Union, Tuple
from datetime import datetime
import logging
import json
import uuid
from sqlalchemy.orm import Session

from app.core.events import DomainEvent
from app.core.exceptions import (
    HideSyncException,
    ValidationException,
    EntityNotFoundException,
    BusinessRuleException,
    ConcurrentOperationException,
)
from app.core.validation import validate_input, validate_entity
from app.db.models.enums import ProjectType, InventoryStatus
from app.db.models.inventory import Product
from app.repositories.product_repository import ProductRepository
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class ProductCreated(DomainEvent):
    """Event emitted when a product is created."""

    def __init__(
        self,
        product_id: int,
        name: str,
        product_type: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize product created event.

        Args:
            product_id: ID of the created product
            name: Name of the product
            product_type: Type of product
            user_id: Optional ID of the user who created the product
        """
        super().__init__()
        self.product_id = product_id
        self.name = name
        self.product_type = product_type
        self.user_id = user_id


class ProductUpdated(DomainEvent):
    """Event emitted when a product is updated."""

    def __init__(
        self,
        product_id: int,
        name: str,
        changes: List[str],
        user_id: Optional[int] = None,
    ):
        """
        Initialize product updated event.

        Args:
            product_id: ID of the updated product
            name: Name of the product
            changes: List of fields that were changed
            user_id: Optional ID of the user who updated the product
        """
        super().__init__()
        self.product_id = product_id
        self.name = name
        self.changes = changes
        self.user_id = user_id


class ProductDeleted(DomainEvent):
    """Event emitted when a product is deleted."""

    def __init__(self, product_id: int, name: str, user_id: Optional[int] = None):
        """
        Initialize product deleted event.

        Args:
            product_id: ID of the deleted product
            name: Name of the product
            user_id: Optional ID of the user who deleted the product
        """
        super().__init__()
        self.product_id = product_id
        self.name = name
        self.user_id = user_id


class ProductInventoryChanged(DomainEvent):
    """Event emitted when a product's inventory changes."""

    def __init__(
        self,
        product_id: int,
        name: str,
        previous_quantity: int,
        new_quantity: int,
        reason: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize inventory changed event.

        Args:
            product_id: ID of the product
            name: Name of the product
            previous_quantity: Previous inventory quantity
            new_quantity: New inventory quantity
            reason: Reason for the change
            user_id: Optional ID of the user who changed the inventory
        """
        super().__init__()
        self.product_id = product_id
        self.name = name
        self.previous_quantity = previous_quantity
        self.new_quantity = new_quantity
        self.change = new_quantity - previous_quantity
        self.reason = reason
        self.user_id = user_id


# Validation functions
validate_product = validate_entity(Product)


class ProductService(BaseService[Product]):
    """
    Service for managing products in the HideSync system.

    Provides functionality for:
    - Product creation and catalog management
    - Pricing and cost calculation
    - Inventory tracking and management
    - Pattern and material association
    - Product variants and customization options
    - Product search and categorization
    - Sales performance tracking
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        pattern_service=None,
        inventory_service=None,
        material_service=None,
        sale_service=None,
    ):
        """
        Initialize ProductService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository for products
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            pattern_service: Optional service for pattern operations
            inventory_service: Optional service for inventory operations
            material_service: Optional service for material operations
            sale_service: Optional service for sale operations
        """
        self.session = session
        self.repository = repository or ProductRepository(session)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.pattern_service = pattern_service
        self.inventory_service = inventory_service
        self.material_service = material_service
        self.sale_service = sale_service

    @validate_input(validate_product)
    def create_product(self, data: Dict[str, Any]) -> Product:
        """
        Create a new product.

        Args:
            data: Product data with required fields
                Required fields:
                - name: Product name
                - productType: Type of product
                Optional fields:
                - sku: Stock keeping unit
                - description: Product description
                - materials: List/string of materials used
                - color: Color description
                - dimensions: Dimensions description
                - patternId: ID of the pattern used
                - quantity: Initial inventory quantity
                - reorderPoint: Inventory level for reorder alert
                - sellingPrice: Selling price
                - totalCost: Total cost to produce
                - thumbnail: Thumbnail image path

        Returns:
            Created product entity

        Raises:
            ValidationException: If validation fails
            EntityNotFoundException: If referenced pattern not found
        """
        with self.transaction():
            # Check if pattern exists if pattern ID is provided
            pattern_id = data.get("patternId")
            if pattern_id and self.pattern_service:
                pattern = self.pattern_service.get_by_id(pattern_id)
                if not pattern:
                    from app.core.exceptions import EntityNotFoundException

                    raise EntityNotFoundException("Pattern", pattern_id)

            # Generate SKU if not provided
            if "sku" not in data or not data["sku"]:
                data["sku"] = self._generate_sku(data["name"], data.get("productType"))

            # Set default values if not provided
            if "quantity" not in data:
                data["quantity"] = 0

            if "reorderPoint" not in data:
                data["reorderPoint"] = 0

            if "status" not in data:
                if data.get("quantity", 0) > 0:
                    data["status"] = InventoryStatus.IN_STOCK.value
                else:
                    data["status"] = InventoryStatus.OUT_OF_STOCK.value

            if "dateAdded" not in data:
                data["dateAdded"] = datetime.now()

            if "lastUpdated" not in data:
                data["lastUpdated"] = datetime.now()

            # Convert materials to string if it's a list
            if "materials" in data and isinstance(data["materials"], list):
                data["materials"] = json.dumps(data["materials"])

            # Convert customizations to string if it's a list
            if "customizations" in data and isinstance(data["customizations"], list):
                data["customizations"] = json.dumps(data["customizations"])

            # Convert costBreakdown to string if it's a dict
            if "costBreakdown" in data and isinstance(data["costBreakdown"], dict):
                data["costBreakdown"] = json.dumps(data["costBreakdown"])

            # Create product
            product = self.repository.create(data)

            # Create inventory record if inventory service is available
            if self.inventory_service and hasattr(
                self.inventory_service, "create_inventory"
            ):
                self.inventory_service.create_inventory(
                    {
                        "itemType": "product",
                        "itemId": product.id,
                        "quantity": data.get("quantity", 0),
                        "status": data.get("status"),
                        "storageLocation": data.get("storageLocation"),
                    }
                )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ProductCreated(
                        product_id=product.id,
                        name=product.name,
                        product_type=product.productType,
                        user_id=user_id,
                    )
                )

            return product

    def update_product(self, product_id: int, data: Dict[str, Any]) -> Product:
        """
        Update an existing product.

        Args:
            product_id: ID of the product to update
            data: Updated product data

        Returns:
            Updated product entity

        Raises:
            EntityNotFoundException: If product not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if product exists
            product = self.get_by_id(product_id)
            if not product:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("Product", product_id)

            # Check if pattern exists if pattern ID is provided
            pattern_id = data.get("patternId")
            if pattern_id and self.pattern_service:
                pattern = self.pattern_service.get_by_id(pattern_id)
                if not pattern:
                    from app.core.exceptions import EntityNotFoundException

                    raise EntityNotFoundException("Pattern", pattern_id)

            # Update lastUpdated timestamp
            data["lastUpdated"] = datetime.now()

            # Track changed fields for event
            changes = list(data.keys())

            # Convert materials to string if it's a list
            if "materials" in data and isinstance(data["materials"], list):
                data["materials"] = json.dumps(data["materials"])

            # Convert customizations to string if it's a list
            if "customizations" in data and isinstance(data["customizations"], list):
                data["customizations"] = json.dumps(data["customizations"])

            # Convert costBreakdown to string if it's a dict
            if "costBreakdown" in data and isinstance(data["costBreakdown"], dict):
                data["costBreakdown"] = json.dumps(data["costBreakdown"])

            # Check if quantity is changing
            previous_quantity = product.quantity if hasattr(product, "quantity") else 0
            new_quantity = data.get("quantity")

            # Update product
            updated_product = self.repository.update(product_id, data)

            # Update inventory if quantity changed and inventory service is available
            if (
                new_quantity is not None
                and new_quantity != previous_quantity
                and self.inventory_service
            ):
                if hasattr(self.inventory_service, "adjust_inventory"):
                    self.inventory_service.adjust_inventory(
                        item_type="product",
                        item_id=product_id,
                        quantity_change=new_quantity - previous_quantity,
                        adjustment_type="INVENTORY_CORRECTION",
                        reason="Product updated",
                    )

                # Publish inventory changed event
                if self.event_bus:
                    user_id = (
                        self.security_context.current_user.id
                        if self.security_context
                        else None
                    )
                    self.event_bus.publish(
                        ProductInventoryChanged(
                            product_id=product_id,
                            name=updated_product.name,
                            previous_quantity=previous_quantity,
                            new_quantity=new_quantity,
                            reason="Product updated",
                            user_id=user_id,
                        )
                    )

            # Publish product updated event
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ProductUpdated(
                        product_id=product_id,
                        name=updated_product.name,
                        changes=changes,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Product:{product_id}")
                self.cache_service.invalidate(f"Product:detail:{product_id}")

            return updated_product

    def delete_product(self, product_id: int) -> bool:
        """
        Delete a product.

        Args:
            product_id: ID of the product to delete

        Returns:
            True if deletion was successful

        Raises:
            EntityNotFoundException: If product not found
            BusinessRuleException: If product has active sales
        """
        with self.transaction():
            # Check if product exists
            product = self.get_by_id(product_id)
            if not product:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("Product", product_id)

            # Check if product has active sales
            if self._has_active_sales(product_id):
                from app.core.exceptions import BusinessRuleException

                raise BusinessRuleException(
                    "Cannot delete product with active sales", "PRODUCT_001"
                )

            # Store product name for event
            product_name = product.name

            # Delete from inventory if inventory service is available
            if self.inventory_service and hasattr(
                self.inventory_service, "delete_inventory"
            ):
                self.inventory_service.delete_inventory(
                    item_type="product", item_id=product_id
                )

            # Delete product
            result = self.repository.delete(product_id)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ProductDeleted(
                        product_id=product_id, name=product_name, user_id=user_id
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Product:{product_id}")
                self.cache_service.invalidate(f"Product:detail:{product_id}")

            return result

    def get_product_with_details(self, product_id: int) -> Dict[str, Any]:
        """
        Get a product with comprehensive details.

        Args:
            product_id: ID of the product

        Returns:
            Product with detailed information

        Raises:
            EntityNotFoundException: If product not found
        """
        # Check cache first
        if self.cache_service:
            cache_key = f"Product:detail:{product_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get product
        product = self.get_by_id(product_id)
        if not product:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("Product", product_id)

        # Convert to dict
        result = product.to_dict()

        # Parse JSON fields
        if "materials" in result and result["materials"]:
            try:
                result["materials"] = json.loads(result["materials"])
            except (json.JSONDecodeError, TypeError):
                # If not valid JSON, convert to list if string with commas
                if isinstance(result["materials"], str) and "," in result["materials"]:
                    result["materials"] = [
                        m.strip() for m in result["materials"].split(",")
                    ]
                # Otherwise keep as is

        if "customizations" in result and result["customizations"]:
            try:
                result["customizations"] = json.loads(result["customizations"])
            except (json.JSONDecodeError, TypeError):
                # If not valid JSON, leave as is
                pass

        if "costBreakdown" in result and result["costBreakdown"]:
            try:
                result["costBreakdown"] = json.loads(result["costBreakdown"])
            except (json.JSONDecodeError, TypeError):
                # If not valid JSON, leave as is
                pass

        # Get pattern details if available
        pattern_id = result.get("patternId")
        if pattern_id and self.pattern_service:
            try:
                pattern = self.pattern_service.get_by_id(pattern_id)
                if pattern:
                    result["pattern"] = {
                        "id": pattern.id,
                        "name": pattern.name,
                        "projectType": (
                            pattern.projectType
                            if hasattr(pattern, "projectType")
                            else None
                        ),
                        "skillLevel": (
                            pattern.skillLevel
                            if hasattr(pattern, "skillLevel")
                            else None
                        ),
                        "thumbnail": (
                            pattern.thumbnail if hasattr(pattern, "thumbnail") else None
                        ),
                    }
            except Exception as e:
                logger.warning(f"Failed to get pattern for product: {str(e)}")

        # Get inventory status if inventory service is available
        if self.inventory_service and hasattr(
            self.inventory_service, "get_inventory_status"
        ):
            try:
                inventory = self.inventory_service.get_inventory_status(
                    item_type="product", item_id=product_id
                )
                if inventory:
                    result["inventory"] = inventory
            except Exception as e:
                logger.warning(f"Failed to get inventory for product: {str(e)}")

        # Get sales data if sale service is available
        if self.sale_service and hasattr(self.sale_service, "get_product_sales"):
            try:
                sales_data = self.sale_service.get_product_sales(product_id)
                result["sales_data"] = sales_data
            except Exception as e:
                logger.warning(f"Failed to get sales data for product: {str(e)}")

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, result, ttl=3600)  # 1 hour TTL

        return result

    def adjust_inventory(
        self,
        product_id: int,
        quantity_change: int,
        reason: str,
        reference_id: Optional[str] = None,
    ) -> Product:
        """
        Adjust product inventory.

        Args:
            product_id: ID of the product
            quantity_change: Quantity to add (positive) or subtract (negative)
            reason: Reason for adjustment
            reference_id: Optional reference ID (e.g., sale ID, project ID)

        Returns:
            Updated product entity

        Raises:
            EntityNotFoundException: If product not found
            ValidationException: If resulting quantity would be negative
        """
        with self.transaction():
            # Check if product exists
            product = self.get_by_id(product_id)
            if not product:
                from app.core.exceptions import EntityNotFoundException

                raise EntityNotFoundException("Product", product_id)

            # Get current quantity
            current_quantity = product.quantity if hasattr(product, "quantity") else 0

            # Calculate new quantity
            new_quantity = current_quantity + quantity_change

            # Validate new quantity
            if new_quantity < 0:
                raise ValidationException(
                    f"Cannot adjust inventory to negative quantity: {new_quantity}",
                    {"quantity": ["Cannot be negative"]},
                )

            # Determine new status
            new_status = None
            if new_quantity == 0:
                new_status = InventoryStatus.OUT_OF_STOCK.value
            elif (
                new_quantity <= product.reorderPoint
                if hasattr(product, "reorderPoint")
                else 0
            ):
                new_status = InventoryStatus.LOW_STOCK.value
            else:
                new_status = InventoryStatus.IN_STOCK.value

            # Update product
            updated_product = self.update_product(
                product_id,
                {
                    "quantity": new_quantity,
                    "status": new_status,
                    "lastUpdated": datetime.now(),
                },
            )

            # Update inventory if inventory service is available
            if self.inventory_service and hasattr(
                self.inventory_service, "adjust_inventory"
            ):
                adjustment_type = "SALE" if quantity_change < 0 else "RESTOCK"

                self.inventory_service.adjust_inventory(
                    item_type="product",
                    item_id=product_id,
                    quantity_change=quantity_change,
                    adjustment_type=adjustment_type,
                    reason=reason,
                    reference_id=reference_id,
                )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ProductInventoryChanged(
                        product_id=product_id,
                        name=product.name,
                        previous_quantity=current_quantity,
                        new_quantity=new_quantity,
                        reason=reason,
                        user_id=user_id,
                    )
                )

            return updated_product

    def get_products_by_type(
        self, product_type: Union[ProjectType, str]
    ) -> List[Product]:
        """
        Get products by type.

        Args:
            product_type: Type of product

        Returns:
            List of products of the specified type
        """
        # Convert string to enum if needed
        if isinstance(product_type, str):
            try:
                product_type = ProjectType[product_type.upper()]
                product_type = product_type.value
            except (KeyError, AttributeError):
                pass

        return self.repository.list(productType=product_type)

    def get_low_stock_products(
        self, threshold_percentage: float = 100.0
    ) -> List[Dict[str, Any]]:
        """
        Get products that are below their reorder point.

        Args:
            threshold_percentage: Percentage of reorder point to use as threshold
                                 (100% means at or below reorder point,
                                  50% means at or below half of reorder point)

        Returns:
            List of products with low stock
        """
        # Get all products
        products = self.repository.list()

        # Filter for low stock
        low_stock = []

        for product in products:
            reorder_point = (
                product.reorderPoint if hasattr(product, "reorderPoint") else 0
            )
            quantity = product.quantity if hasattr(product, "quantity") else 0

            # Skip products with no reorder point
            if reorder_point == 0:
                continue

            # Calculate threshold
            threshold = reorder_point * (threshold_percentage / 100.0)

            # Check if below threshold
            if quantity <= threshold:
                # Prepare result object
                product_dict = product.to_dict()

                # Add calculated fields
                product_dict["threshold"] = threshold
                product_dict["percent_of_reorder"] = (
                    (quantity / reorder_point * 100) if reorder_point > 0 else 0
                )
                product_dict["units_below_reorder"] = max(0, reorder_point - quantity)

                low_stock.append(product_dict)

        # Sort by percent of reorder (ascending)
        return sorted(low_stock, key=lambda x: x["percent_of_reorder"])

    def search_products(
        self,
        query: str,
        product_type: Optional[str] = None,
        in_stock_only: bool = False,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Search for products based on various criteria.

        Args:
            query: Search query for product name and description
            product_type: Optional product type filter
            in_stock_only: Whether to include only in-stock products
            min_price: Optional minimum price filter
            max_price: Optional maximum price filter
            limit: Maximum number of results
            offset: Result offset for pagination

        Returns:
            Dictionary with search results and total count
        """
        filters = {}

        # Add product type filter if specified
        if product_type:
            filters["productType"] = product_type

        # Add in-stock filter if specified
        if in_stock_only:
            filters["status"] = InventoryStatus.IN_STOCK.value

        # Repository would implement search functionality with price filtering
        # This is a simplified example
        if hasattr(self.repository, "search"):
            results, total = self.repository.search(
                query=query,
                min_price=min_price,
                max_price=max_price,
                limit=limit,
                offset=offset,
                **filters,
            )
        else:
            # Fallback to basic filter
            all_products = self.repository.list(**filters)

            # Filter by query
            if query:
                query = query.lower()
                filtered_products = [
                    p
                    for p in all_products
                    if (query in p.name.lower() if hasattr(p, "name") else False)
                    or (
                        query in p.description.lower()
                        if hasattr(p, "description")
                        else False
                    )
                    or (query in p.sku.lower() if hasattr(p, "sku") else False)
                ]
            else:
                filtered_products = all_products

            # Filter by price
            if min_price is not None:
                filtered_products = [
                    p
                    for p in filtered_products
                    if (
                        p.sellingPrice >= min_price
                        if hasattr(p, "sellingPrice")
                        else True
                    )
                ]

            if max_price is not None:
                filtered_products = [
                    p
                    for p in filtered_products
                    if (
                        p.sellingPrice <= max_price
                        if hasattr(p, "sellingPrice")
                        else True
                    )
                ]

            # Apply pagination
            total = len(filtered_products)
            results = filtered_products[offset : offset + limit]

        return {
            "items": [p.to_dict() for p in results],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_products_by_pattern(self, pattern_id: int) -> List[Product]:
        """
        Get products based on a specific pattern.

        Args:
            pattern_id: ID of the pattern

        Returns:
            List of products using the pattern
        """
        return self.repository.list(patternId=pattern_id)

    def calculate_cost_breakdown(self, product_id: int) -> Dict[str, Any]:
        """
        Calculate detailed cost breakdown for a product.

        Args:
            product_id: ID of the product

        Returns:
            Dictionary with cost breakdown details

        Raises:
            EntityNotFoundException: If product not found
        """
        # Check if product exists
        product = self.get_by_id(product_id)
        if not product:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("Product", product_id)

        # Initialize cost breakdown
        breakdown = {
            "material_costs": 0.0,
            "labor_costs": 0.0,
            "overhead_costs": 0.0,
            "total_cost": 0.0,
            "selling_price": (
                product.sellingPrice if hasattr(product, "sellingPrice") else 0.0
            ),
            "profit_margin": 0.0,
            "materials": [],
        }

        # Get pattern
        pattern_id = product.patternId if hasattr(product, "patternId") else None

        # If we have pattern and component services, calculate material costs
        if (
            pattern_id
            and self.pattern_service
            and hasattr(self.component_service, "calculate_material_requirements")
        ):
            try:
                # Get material requirements
                materials = self.component_service.calculate_material_requirements(
                    pattern_id
                )

                # Calculate cost for each material
                for material_id, material_data in materials.items():
                    # Get material cost
                    material_cost = 0.0
                    if self.material_service:
                        material = self.material_service.get_by_id(material_id)
                        if material and hasattr(material, "cost"):
                            material_cost = material.cost

                    # Calculate total cost for this material
                    quantity = material_data.get("quantity_required", 0)
                    total_material_cost = material_cost * quantity

                    # Add to total
                    breakdown["material_costs"] += total_material_cost

                    # Add to materials list
                    breakdown["materials"].append(
                        {
                            "id": material_id,
                            "name": material_data.get(
                                "name", f"Material {material_id}"
                            ),
                            "quantity": quantity,
                            "unit": material_data.get("unit", "UNIT"),
                            "cost_per_unit": material_cost,
                            "total_cost": total_material_cost,
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to calculate material costs: {str(e)}")

        # In a real implementation, labor and overhead would be calculated based on
        # time estimates, labor rates, and overhead allocation
        # For now, we'll use placeholder values
        breakdown["labor_costs"] = (
            product.laborCost if hasattr(product, "laborCost") else 0.0
        )
        breakdown["overhead_costs"] = (
            product.overheadCost if hasattr(product, "overheadCost") else 0.0
        )

        # Calculate total cost
        breakdown["total_cost"] = (
            breakdown["material_costs"]
            + breakdown["labor_costs"]
            + breakdown["overhead_costs"]
        )

        # Calculate profit margin
        if breakdown["total_cost"] > 0 and breakdown["selling_price"] > 0:
            profit = breakdown["selling_price"] - breakdown["total_cost"]
            breakdown["profit_margin"] = (profit / breakdown["selling_price"]) * 100

        # Update product with cost breakdown
        self.update_product(
            product_id,
            {"costBreakdown": breakdown, "totalCost": breakdown["total_cost"]},
        )

        return breakdown

    def _generate_sku(self, name: str, product_type: Optional[str] = None) -> str:
        """
        Generate a SKU for a product.

        Args:
            name: Product name
            product_type: Optional product type

        Returns:
            Generated SKU
        """
        # Clean name
        name_part = "".join(c for c in name.upper() if c.isalnum())[:4]

        # Get type prefix
        type_prefix = "PROD"
        if product_type:
            # Convert common product types to prefixes
            type_mapping = {
                "WALLET": "WAL",
                "BAG": "BAG",
                "BELT": "BLT",
                "ACCESSORY": "ACC",
            }
            type_prefix = type_mapping.get(
                product_type.upper(), product_type[:3].upper()
            )

        # Generate unique part
        unique_part = str(uuid.uuid4())[-8:].upper()

        return f"{type_prefix}-{name_part}-{unique_part}"

    def _has_active_sales(self, product_id: int) -> bool:
        """
        Check if a product has active sales.

        Args:
            product_id: ID of the product

        Returns:
            True if product has active sales
        """
        # In a real implementation, this would check the sale repository
        # for active orders containing this product
        # For now, return False as a placeholder
        if self.sale_service and hasattr(
            self.sale_service, "has_active_sales_for_product"
        ):
            return self.sale_service.has_active_sales_for_product(product_id)

        return False
