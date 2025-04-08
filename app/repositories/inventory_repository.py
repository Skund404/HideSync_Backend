# File: app/repositories/inventory_repository.py

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from datetime import datetime

from app.db.models.inventory import Inventory
from app.db.models.enums import InventoryStatus
from app.repositories.base_repository import BaseRepository
import logging
logger = logging.getLogger(__name__)

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

    def count_by_status(self, status: InventoryStatus) -> int:
        """Counts inventory records matching a specific status."""
        logger.debug(f"Counting inventory items with status: {status.name}")
        count = (
            self.session.query(func.count(self.model.id))
            .filter(self.model.status == status)
            .scalar()
        )
        return count or 0

    def count_needs_reorder(self) -> int:
        """
        Counts inventory records where quantity is at or below the reorder point
        of the associated Product or Material. Requires JOINs.
        """
        logger.debug("Counting inventory items needing reorder.")
        # Import models needed for JOINs within the method if not globally imported
        from app.db.models.product import Product
        from app.db.models.material import Material
        # Add Tool if tools have reorder points

        # Query for products needing reorder
        product_reorder_query = (
            self.session.query(func.count(self.model.id))
            .join(Product, and_(self.model.item_type == 'product', self.model.item_id == Product.id))
            .filter(Product.reorder_point > 0)  # Ensure reorder point is set
            .filter(self.model.quantity <= Product.reorder_point)
        )

        # Query for materials needing reorder
        material_reorder_query = (
            self.session.query(func.count(self.model.id))
            .join(Material, and_(self.model.item_type == 'material', self.model.item_id == Material.id))
            .filter(Material.reorder_point > 0)  # Ensure reorder point is set
            .filter(self.model.quantity <= Material.reorder_point)
        )

        # Add query for tools if they have reorder points

        product_count = product_reorder_query.scalar() or 0
        material_count = material_reorder_query.scalar() or 0
        # tool_count = ...

        total_needs_reorder = product_count + material_count  # + tool_count
        logger.debug(
            f"Found {total_needs_reorder} items needing reorder ({product_count} products, {material_count} materials).")
        return total_needs_reorder

    def get_inventory_by_item_and_location(self, item_type: str, item_id: int, location: str) -> Optional[Inventory]:
        """
        Gets a specific inventory record for an item at a specific location.
        Needed for the transfer logic.
        """
        logger.debug(f"Fetching inventory for {item_type} ID {item_id} at location '{location}'")
        entity = (
            self.session.query(self.model)
            .filter(
                and_(
                    self.model.item_type == item_type.lower(),
                    self.model.item_id == item_id,
                    self.model.storage_location == location  # Filter by location too
                )
            )
            .first()
        )
        return self._decrypt_sensitive_fields(entity) if entity else None

    def get_low_stock_inventory_detailed(
            self,
            threshold_percentage: float = 100.0,
            item_type: Optional[str] = None,
            limit: int = 500
    ) -> List[Tuple[Inventory, Dict[str, Any]]]:
        """
        Fetches low stock inventory records along with essential item details.
        Returns tuples of (InventoryObject, ItemDetailsDict).
        """
        logger.debug(f"Fetching detailed low stock items: threshold={threshold_percentage}%, type={item_type or 'All'}")
        # This is complex because details come from different tables (Product, Material, Tool)
        # Option 1: Fetch low stock inventory IDs first, then fetch details individually (less efficient)
        # Option 2: Use UNION or complex JOINs (more efficient but harder to write/maintain)

        # --- Using Option 1 (Simpler to implement) ---
        low_stock_inventories = self.get_low_stock_inventory(  # Use the basic low stock method
            item_type=item_type,
            threshold_percentage=threshold_percentage,  # Pass threshold
            limit=limit
        )

        results = []
        # Requires _get_item_details helper in *this* repository OR access to the service layer
        # For simplicity, assuming InventoryService._get_item_details can be accessed or duplicated here
        # Ideally, this logic might live entirely in the service layer calling simpler repo methods.
        for inv in low_stock_inventories:
            # *** IMPORTANT: Requires access to _get_item_details logic ***
            # This is a dependency violation if called directly from service.
            # Better: Service calls repo.get_low_stock_inventory(), then service loops and calls _get_item_details()
            # For now, assume logic is available here:
            item_details = self._get_item_details_for_repo(inv.item_type, inv.item_id)  # Placeholder name
            if item_details:
                results.append((inv, item_details))
        logger.debug(f"Found {len(results)} detailed low stock items.")
        return results

    # Placeholder for the detail fetching logic needed by get_low_stock_inventory_detailed
    # This should ideally use injected services or be handled entirely in the service layer.
    def _get_item_details_for_repo(self, item_type: str, item_id: int) -> Optional[Dict[str, Any]]:
        # WARNING: This introduces service dependencies into the repository, which is not ideal.
        # Consider refactoring this logic into the service layer.
        from app.db.models.product import Product
        from app.db.models.material import Material
        # from app.db.models.tool import Tool # If needed

        logger.debug(f"Repo: Getting item details for {item_type} {item_id}")
        if item_type == 'product':
            item = self.session.query(Product).filter(Product.id == item_id).first()
            if item: return {"name": item.name, "cost": item.total_cost, "reorder_point": item.reorder_point,
                             "unit": "piece", "sku": item.sku}
        elif item_type == 'material':
            item = self.session.query(Material).filter(Material.id == item_id).first()
            if item: return {"name": item.name, "cost": item.cost, "reorder_point": item.reorder_point,
                             "unit": item.unit.name if item.unit else None, "supplier_id": item.supplier_id}
        # Add Tool logic if needed
        # elif item_type == 'tool': ...
        return None

    def get_low_stock_inventory(  # Basic version used by detailed one
            self, item_type: Optional[str] = None, threshold_percentage: float = 100.0, skip: int = 0, limit: int = 100
    ) -> List[Inventory]:
        """ Gets inventory items at or below reorder threshold """
        from app.db.models.product import Product
        from app.db.models.material import Material

        query = self.session.query(self.model)
        conditions = []

        # Product condition
        product_cond = and_(
            self.model.item_type == 'product',
            Product.reorder_point > 0,
            self.model.quantity <= (Product.reorder_point * (threshold_percentage / 100.0))
        )
        query_prod = query.join(Product, self.model.item_id == Product.id).filter(product_cond)

        # Material condition
        material_cond = and_(
            self.model.item_type == 'material',
            Material.reorder_point > 0,
            self.model.quantity <= (Material.reorder_point * (threshold_percentage / 100.0))
        )
        query_mat = query.join(Material, self.model.item_id == Material.id).filter(material_cond)

        # Combine queries using UNION if filtering by item_type is not done,
        # or select the appropriate query if item_type is specified.
        if item_type == 'product':
            final_query = query_prod
        elif item_type == 'material':
            final_query = query_mat
        elif item_type is None:
            # Combine results - UNION might be complex, fetching separately might be ok for moderate data
            # This simplified version fetches separately - consider UNION for performance
            prod_ids = [p.id for p in query_prod.all()]
            mat_ids = [m.id for m in query_mat.all()]
            all_ids = list(set(prod_ids + mat_ids))  # Combine unique inventory IDs
            if not all_ids: return []
            # Fetch final inventory objects - apply pagination here
            final_query = self.session.query(self.model).filter(self.model.id.in_(all_ids))
        else:  # Invalid item_type or tool not handled
            return []

        entities = final_query.order_by(self.model.id).offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    # Add count_with_filters if needed for pagination in _generate_detail_report
    def count_with_filters(self, status: Optional[str] = None, location: Optional[str] = None,
                           item_type: Optional[str] = None, search_term: Optional[str] = None) -> int:
        # Similar logic to list_with_filters but just does count()
        query = self.session.query(func.count(self.model.id))
        inventory_joined = False
        if status or location: query = query.join(self.model.inventory); inventory_joined = True
        if search_term:
            search_filter = f"%{search_term}%"
            # Add JOINs if searching item names
            query = query.filter(or_(self.model.storage_location.ilike(search_filter)))  # Simplified search
        if item_type: query = query.filter(self.model.item_type == item_type.lower())
        if status:
            try:
                enum_status = InventoryStatus(status); query = query.filter(Inventory.status == enum_status)
            except ValueError:
                pass  # Ignore invalid status
        if location: query = query.filter(Inventory.storage_location == location)
        count = query.scalar()
        return count or 0

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
                and_(self.model.item_type == item_type, self.model.item_id == item_id)
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
