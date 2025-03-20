# File: app/repositories/product_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func
from datetime import datetime

from app.db.models.inventory import Product
from app.db.models.enums import InventoryStatus
from app.repositories.base_repository import BaseRepository


class ProductRepository(BaseRepository[Product]):
    """
    Repository for Product entity operations.

    Provides methods for managing product data, including search,
    filtering by attributes, and calculating pricing information.
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

    def get_products_by_status(
        self, status: InventoryStatus, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """
        Get products by their inventory status.

        Args:
            status (InventoryStatus): The inventory status to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Product]: List of products with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_products_by_pattern(
        self, pattern_id: int, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """
        Get products based on a specific pattern.

        Args:
            pattern_id (int): ID of the pattern
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Product]: List of products using the specified pattern
        """
        query = self.session.query(self.model).filter(
            self.model.patternId == pattern_id
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_products_by_price_range(
        self, min_price: float, max_price: float, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """
        Get products within a specific price range.

        Args:
            min_price (float): Minimum price
            max_price (float): Maximum price
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Product]: List of products within the price range
        """
        query = self.session.query(self.model).filter(
            and_(
                self.model.sellingPrice >= min_price,
                self.model.sellingPrice <= max_price,
            )
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_best_selling_products(self, limit: int = 10) -> List[Product]:
        """
        Get best-selling products based on sales velocity.

        Args:
            limit (int): Maximum number of products to return

        Returns:
            List[Product]: List of best-selling products
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.salesVelocity > 0)
            .order_by(desc(self.model.salesVelocity))
            .limit(limit)
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_products_low_in_stock(
        self, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """
        Get products that are low in stock (below reorder point).

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Product]: List of products low in stock
        """
        query = self.session.query(self.model).filter(
            and_(
                self.model.quantity <= self.model.reorderPoint, self.model.quantity > 0
            )
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_products_out_of_stock(
        self, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """
        Get products that are out of stock.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Product]: List of out-of-stock products
        """
        query = self.session.query(self.model).filter(self.model.quantity <= 0)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_product_inventory(
        self, product_id: int, quantity_change: int
    ) -> Optional[Product]:
        """
        Update a product's inventory quantity.

        Args:
            product_id (int): ID of the product
            quantity_change (int): Amount to add (positive) or subtract (negative)

        Returns:
            Optional[Product]: Updated product if found, None otherwise
        """
        product = self.get_by_id(product_id)
        if not product:
            return None

        # Update quantity
        product.quantity = max(0, product.quantity + quantity_change)

        # Update status based on quantity
        if product.quantity <= 0:
            product.status = InventoryStatus.OUT_OF_STOCK
        elif product.quantity <= product.reorderPoint:
            product.status = InventoryStatus.LOW_STOCK
        else:
            product.status = InventoryStatus.IN_STOCK

        # Update the lastUpdated field
        product.lastUpdated = datetime.now()

        self.session.commit()
        self.session.refresh(product)
        return self._decrypt_sensitive_fields(product)

    def update_product_pricing(
        self,
        product_id: int,
        total_cost: Optional[float] = None,
        selling_price: Optional[float] = None,
    ) -> Optional[Product]:
        """
        Update a product's pricing information.

        Args:
            product_id (int): ID of the product
            total_cost (Optional[float]): New total cost value
            selling_price (Optional[float]): New selling price value

        Returns:
            Optional[Product]: Updated product if found, None otherwise
        """
        product = self.get_by_id(product_id)
        if not product:
            return None

        if total_cost is not None:
            product.totalCost = total_cost

        if selling_price is not None:
            product.sellingPrice = selling_price

        # Calculate profit margin
        if product.totalCost > 0 and product.sellingPrice > 0:
            product.profitMargin = (
                (product.sellingPrice - product.totalCost) / product.sellingPrice * 100
            )

        # Update the lastUpdated field
        product.lastUpdated = datetime.now()

        self.session.commit()
        self.session.refresh(product)
        return self._decrypt_sensitive_fields(product)

    def search_products(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """
        Search for products by name, description, or SKU.

        Args:
            query (str): The search query
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Product]: List of matching products
        """
        search_query = self.session.query(self.model).filter(
            or_(
                self.model.name.ilike(f"%{query}%"),
                self.model.description.ilike(f"%{query}%"),
                self.model.sku.ilike(f"%{query}%"),
            )
        )

        entities = search_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_product_by_sku(self, sku: str) -> Optional[Product]:
        """
        Get a product by its SKU.

        Args:
            sku (str): The SKU to search for

        Returns:
            Optional[Product]: The product if found, None otherwise
        """
        entity = self.session.query(self.model).filter(self.model.sku == sku).first()
        return self._decrypt_sensitive_fields(entity) if entity else None
