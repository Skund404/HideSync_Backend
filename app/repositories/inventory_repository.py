# File: app/repositories/inventory_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from datetime import datetime

from app.db.models.inventory import Inventory
from app.db.models.enums import InventoryStatus
from app.repositories.base_repository import BaseRepository


class InventoryRepository(BaseRepository[Inventory]):
    """
    Repository for Inventory entity operations.

    Provides methods for managing inventory records, including quantity tracking,
    location management, and inventory status updates.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the InventoryRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Inventory

    def list_with_filters(
            self,
            *,
            skip: int = 0,
            limit: int = 100,
            status: Optional[str] = None,
            location: Optional[str] = None,
            item_type: Optional[str] = None,
            search_term: Optional[str] = None,
    ) -> List[Inventory]:
        """
        Retrieves a list of inventory items with optional filtering and pagination.
        """
        query = self.session.query(self.model)

        if status:
            # Assuming status is passed as the string value of the enum
            query = query.filter(self.model.status == status)
        if location:
            # Use ilike for case-insensitive partial match for location
            query = query.filter(self.model.storageLocation.ilike(f'%{location}%'))
        if item_type:
            query = query.filter(self.model.itemType == item_type.lower())

        if search_term:
            # Basic search example: search within storageLocation or item_id (if text)
            # A more robust search on item name would require JOINs (see previous explanation)
            search_filter = or_(
                self.model.storageLocation.ilike(f'%{search_term}%'),
                # Add other searchable fields within Inventory model if applicable
                # self.model.itemId.ilike(f'%{search_term}%') # If item_id is text searchable
            )
            query = query.filter(search_filter)
            # NOTE: Searching item name requires joining with Material/Product/Tool tables,
            # which adds complexity not shown in this basic example.

        entities = query.order_by(self.model.id).offset(skip).limit(
            limit).all()  # Added order_by for consistent pagination

        # Apply decryption if necessary (assuming _decrypt_sensitive_fields exists)
        if hasattr(self, '_decrypt_sensitive_fields'):
            return [self._decrypt_sensitive_fields(entity) for entity in entities]
        else:
            # Handle case where decryption isn't needed or method doesn't exist
            return entities

    def get_inventory_by_item_id(
        self, item_type: str, item_id: int
    ) -> Optional[Inventory]:
        """
        Get inventory record for a specific item.

        Args:
            item_type (str): Type of item ('material', 'product', 'tool')
            item_id (int): ID of the item

        Returns:
            Optional[Inventory]: Inventory record if found, None otherwise
        """
        entity = (
            self.session.query(self.model)
            .filter(
                and_(self.model.itemType == item_type, self.model.itemId == item_id)
            )
            .first()
        )
        return self._decrypt_sensitive_fields(entity) if entity else None

    def get_inventory_by_status(
        self, status: InventoryStatus, skip: int = 0, limit: int = 100
    ) -> List[Inventory]:
        """
        Get inventory records by status.

        Args:
            status (InventoryStatus): Inventory status to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Inventory]: List of inventory records with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_inventory_by_location(
        self, location: str, skip: int = 0, limit: int = 100
    ) -> List[Inventory]:
        """
        Get inventory records by storage location.

        Args:
            location (str): Storage location to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Inventory]: List of inventory records in the specified location
        """
        query = self.session.query(self.model).filter(
            self.model.storageLocation == location
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_low_stock_inventory(
        self, skip: int = 0, limit: int = 100
    ) -> List[Inventory]:
        """
        Get inventory records that are low in stock.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Inventory]: List of low stock inventory records
        """
        query = self.session.query(self.model).filter(
            self.model.status == InventoryStatus.LOW_STOCK
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_inventory_quantity(
        self, inventory_id: int, quantity_change: float
    ) -> Optional[Inventory]:
        """
        Update inventory quantity.

        Args:
            inventory_id (int): ID of the inventory record
            quantity_change (float): Amount to add (positive) or subtract (negative)

        Returns:
            Optional[Inventory]: Updated inventory record if found, None otherwise
        """
        inventory = self.get_by_id(inventory_id)
        if not inventory:
            return None

        # Update quantity
        inventory.quantity = max(0, inventory.quantity + quantity_change)

        # Update status based on quantity
        if inventory.quantity <= 0:
            inventory.status = InventoryStatus.OUT_OF_STOCK
        elif (
            hasattr(inventory, "reorderPoint")
            and inventory.quantity <= inventory.reorderPoint
        ):
            inventory.status = InventoryStatus.LOW_STOCK
        else:
            inventory.status = InventoryStatus.IN_STOCK

        self.session.commit()
        self.session.refresh(inventory)
        return self._decrypt_sensitive_fields(inventory)

    def update_inventory_location(
        self, inventory_id: int, location: str
    ) -> Optional[Inventory]:
        """
        Update inventory storage location.

        Args:
            inventory_id (int): ID of the inventory record
            location (str): New storage location

        Returns:
            Optional[Inventory]: Updated inventory record if found, None otherwise
        """
        inventory = self.get_by_id(inventory_id)
        if not inventory:
            return None

        inventory.storageLocation = location

        self.session.commit()
        self.session.refresh(inventory)
        return self._decrypt_sensitive_fields(inventory)

    def get_inventory_statistics(self) -> Dict[str, Any]:
        """
        Get inventory statistics.

        Returns:
            Dict[str, Any]: Dictionary with inventory statistics
        """
        total_count = self.session.query(func.count(self.model.id)).scalar()

        in_stock_count = (
            self.session.query(func.count(self.model.id))
            .filter(self.model.status == InventoryStatus.IN_STOCK)
            .scalar()
        )

        low_stock_count = (
            self.session.query(func.count(self.model.id))
            .filter(self.model.status == InventoryStatus.LOW_STOCK)
            .scalar()
        )

        out_of_stock_count = (
            self.session.query(func.count(self.model.id))
            .filter(self.model.status == InventoryStatus.OUT_OF_STOCK)
            .scalar()
        )

        return {
            "total_count": total_count,
            "in_stock_count": in_stock_count,
            "low_stock_count": low_stock_count,
            "out_of_stock_count": out_of_stock_count,
            "in_stock_percentage": (
                (in_stock_count / total_count * 100) if total_count > 0 else 0
            ),
            "low_stock_percentage": (
                (low_stock_count / total_count * 100) if total_count > 0 else 0
            ),
            "out_of_stock_percentage": (
                (out_of_stock_count / total_count * 100) if total_count > 0 else 0
            ),
        }
