# File: app/repositories/inventory_transaction_repository.py

from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func
from datetime import datetime, timedelta

from app.db.models.inventory import InventoryTransaction
from app.db.models.enums import TransactionType, InventoryAdjustmentType
from app.repositories.base_repository import BaseRepository


class InventoryTransactionRepository(BaseRepository[InventoryTransaction]):
    """
    Repository for InventoryTransaction entity operations.

    Handles data access for inventory transactions, providing methods for
    tracking material movements, usage, adjustments, and inventory history.
    This repository is essential for accurate inventory tracking and auditing.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the InventoryTransactionRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = InventoryTransaction

    def get_transactions_by_item(
        self, item_type: str, item_id: int, skip: int = 0, limit: int = 100
    ) -> List[InventoryTransaction]:
        """
        Get transactions for a specific inventory item.

        Args:
            item_type (str): Type of item ('material', 'product', 'tool')
            item_id (int): ID of the item
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[InventoryTransaction]: List of transactions for the item
        """
        query = (
            self.session.query(self.model)
            .filter(
                and_(self.model.item_type == item_type, self.model.item_id == item_id)
            )
            .order_by(desc(self.model.transaction_date))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_transactions_by_type(
        self, transaction_type: TransactionType, skip: int = 0, limit: int = 100
    ) -> List[InventoryTransaction]:
        """
        Get transactions by transaction type.

        Args:
            transaction_type (TransactionType): The transaction type to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[InventoryTransaction]: List of transactions of the specified type
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.transaction_type == transaction_type)
            .order_by(desc(self.model.transaction_date))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_transactions_by_adjustment_type(
        self, adjustment_type: InventoryAdjustmentType, skip: int = 0, limit: int = 100
    ) -> List[InventoryTransaction]:
        """
        Get transactions by adjustment type.

        Args:
            adjustment_type (InventoryAdjustmentType): The adjustment type to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[InventoryTransaction]: List of transactions with the specified adjustment type
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.adjustment_type == adjustment_type)
            .order_by(desc(self.model.transaction_date))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_transactions_by_date_range(
        self, start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100
    ) -> List[InventoryTransaction]:
        """
        Get transactions within a specific date range.

        Args:
            start_date (datetime): Start of the date range
            end_date (datetime): End of the date range
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[InventoryTransaction]: List of transactions within the date range
        """
        query = (
            self.session.query(self.model)
            .filter(
                and_(
                    self.model.transaction_date >= start_date,
                    self.model.transaction_date <= end_date,
                )
            )
            .order_by(desc(self.model.transaction_date))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_recent_transactions(
        self, days: int = 7, skip: int = 0, limit: int = 100
    ) -> List[InventoryTransaction]:
        """
        Get transactions from the last specified number of days.

        Args:
            days (int): Number of days to look back
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[InventoryTransaction]: List of recent transactions
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        query = (
            self.session.query(self.model)
            .filter(self.model.transaction_date >= cutoff_date)
            .order_by(desc(self.model.transaction_date))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_transactions_by_project(
        self, project_id: int, skip: int = 0, limit: int = 100
    ) -> List[InventoryTransaction]:
        """
        Get transactions related to a specific project.

        Args:
            project_id (int): ID of the project
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[InventoryTransaction]: List of transactions related to the project
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.project_id == project_id)
            .order_by(desc(self.model.transaction_date))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_transactions_by_sale(
        self, sale_id: int, skip: int = 0, limit: int = 100
    ) -> List[InventoryTransaction]:
        """
        Get transactions related to a specific sale.

        Args:
            sale_id (int): ID of the sale
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[InventoryTransaction]: List of transactions related to the sale
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.sale_id == sale_id)
            .order_by(desc(self.model.transaction_date))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_transactions_by_purchase(
        self, purchase_id: int, skip: int = 0, limit: int = 100
    ) -> List[InventoryTransaction]:
        """
        Get transactions related to a specific purchase.

        Args:
            purchase_id (int): ID of the purchase
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[InventoryTransaction]: List of transactions related to the purchase
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.purchase_id == purchase_id)
            .order_by(desc(self.model.transaction_date))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_transactions_by_location(
        self, location_id: str, skip: int = 0, limit: int = 100
    ) -> List[InventoryTransaction]:
        """
        Get transactions for a specific storage location.

        Args:
            location_id (str): ID of the storage location
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[InventoryTransaction]: List of transactions for the location
        """
        query = (
            self.session.query(self.model)
            .filter(
                or_(
                    self.model.from_location == location_id,
                    self.model.to_location == location_id,
                )
            )
            .order_by(desc(self.model.transaction_date))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def create_inventory_transaction(
        self,
        item_type: str,
        item_id: int,
        quantity: float,
        transaction_type: TransactionType,
        reference_id: Optional[int] = None,
        reference_type: Optional[str] = None,
        adjustment_type: Optional[InventoryAdjustmentType] = None,
        from_location: Optional[str] = None,
        to_location: Optional[str] = None,
        performed_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> InventoryTransaction:
        """
        Create a new inventory transaction.

        Args:
            item_type (str): Type of item ('material', 'product', 'tool')
            item_id (int): ID of the item
            quantity (float): Transaction quantity (positive for additions, negative for reductions)
            transaction_type (TransactionType): Type of transaction
            reference_id (Optional[int]): ID of the referenced entity (sale, purchase, project)
            reference_type (Optional[str]): Type of the referenced entity
            adjustment_type (Optional[InventoryAdjustmentType]): Type of adjustment (for adjustments)
            from_location (Optional[str]): Source location ID (for transfers)
            to_location (Optional[str]): Destination location ID (for transfers)
            performed_by (Optional[str]): User who performed the transaction
            notes (Optional[str]): Additional notes about the transaction

        Returns:
            InventoryTransaction: The created transaction record
        """
        # Set the appropriate reference field based on reference_type
        project_id = None
        sale_id = None
        purchase_id = None

        if reference_id and reference_type:
            if reference_type.lower() == "project":
                project_id = reference_id
            elif reference_type.lower() == "sale":
                sale_id = reference_id
            elif reference_type.lower() == "purchase":
                purchase_id = reference_id

        transaction_data = {
            "item_type": item_type,
            "item_id": item_id,
            "quantity": quantity,
            "transaction_type": transaction_type,
            "adjustment_type": adjustment_type,
            "project_id": project_id,
            "sale_id": sale_id,
            "purchase_id": purchase_id,
            "from_location": from_location,
            "to_location": to_location,
            "performed_by": performed_by,
            "notes": notes,
            "transaction_date": datetime.now(),
        }

        return self.create(transaction_data)

    def get_item_transaction_history(
        self, item_type: str, item_id: int
    ) -> Dict[str, Any]:
        """
        Get a summary of transaction history for a specific item.

        Args:
            item_type (str): Type of item ('material', 'product', 'tool')
            item_id (int): ID of the item

        Returns:
            Dict[str, Any]: Dictionary with transaction history summary
        """
        # Get all transactions for the item
        transactions = self.get_transactions_by_item(item_type, item_id, limit=1000)

        # Calculate total quantities by transaction type
        total_in = sum(t.quantity for t in transactions if t.quantity > 0)
        total_out = sum(abs(t.quantity) for t in transactions if t.quantity < 0)
        net_change = total_in - total_out

        # Count by transaction type
        transaction_type_counts = {}
        for transaction in transactions:
            type_key = (
                transaction.transaction_type.value
                if hasattr(transaction.transaction_type, "value")
                else str(transaction.transaction_type)
            )
            if type_key not in transaction_type_counts:
                transaction_type_counts[type_key] = 0
            transaction_type_counts[type_key] += 1

        # Get recent transactions
        recent_transactions = transactions[:5]

        # Get first and last transaction dates
        first_transaction_date = (
            transactions[-1].transaction_date if transactions else None
        )
        last_transaction_date = (
            transactions[0].transaction_date if transactions else None
        )

        return {
            "item_type": item_type,
            "item_id": item_id,
            "total_transactions": len(transactions),
            "total_in": total_in,
            "total_out": total_out,
            "net_change": net_change,
            "by_transaction_type": [
                {"type": type_key, "count": count}
                for type_key, count in transaction_type_counts.items()
            ],
            "first_transaction_date": first_transaction_date,
            "last_transaction_date": last_transaction_date,
            "recent_transactions": [
                {
                    "id": t.id,
                    "transaction_date": t.transaction_date,
                    "transaction_type": (
                        t.transaction_type.value
                        if hasattr(t.transaction_type, "value")
                        else str(t.transaction_type)
                    ),
                    "quantity": t.quantity,
                    "from_location": t.from_location,
                    "to_location": t.to_location,
                }
                for t in recent_transactions
            ],
        }

    def get_transaction_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about inventory transactions.

        Returns:
            Dict[str, Any]: Dictionary with transaction statistics
        """
        # Total transactions
        total_count = self.session.query(func.count(self.model.id)).scalar() or 0

        # Transactions by type
        type_counts = (
            self.session.query(
                self.model.transaction_type, func.count(self.model.id).label("count")
            )
            .group_by(self.model.transaction_type)
            .all()
        )

        # Transactions by adjustment type
        adjustment_counts = (
            self.session.query(
                self.model.adjustment_type, func.count(self.model.id).label("count")
            )
            .filter(self.model.adjustment_type.isnot(None))
            .group_by(self.model.adjustment_type)
            .all()
        )

        # Transactions by month (last 12 months)
        twelve_months_ago = datetime.now() - timedelta(days=365)
        monthly_counts = (
            self.session.query(
                func.strftime("%Y-%m", self.model.transaction_date).label("month"),
                func.count(self.model.id).label("count"),
            )
            .filter(self.model.transaction_date >= twelve_months_ago)
            .group_by("month")
            .order_by("month")
            .all()
        )

        # Total quantity movement
        quantity_sum = self.session.query(func.sum(self.model.quantity)).scalar() or 0

        # Average transaction quantity
        avg_quantity = (
            self.session.query(func.avg(func.abs(self.model.quantity))).scalar() or 0
        )

        return {
            "total_count": total_count,
            "total_quantity_movement": float(quantity_sum),
            "average_transaction_quantity": float(avg_quantity),
            "by_transaction_type": [
                {
                    "type": type_.value if hasattr(type_, "value") else str(type_),
                    "count": count,
                }
                for type_, count in type_counts
            ],
            "by_adjustment_type": [
                {
                    "type": (
                        adj_type.value if hasattr(adj_type, "value") else str(adj_type)
                    ),
                    "count": count,
                }
                for adj_type, count in adjustment_counts
            ],
            "monthly_trend": [
                {"month": month, "count": count} for month, count in monthly_counts
            ],
        }
