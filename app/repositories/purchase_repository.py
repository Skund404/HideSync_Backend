# File: app/repositories/purchase_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func
from datetime import datetime, timedelta

from app.db.models.purchase import Purchase, PurchaseItem
from app.db.models.enums import PurchaseStatus, PaymentStatus
from app.repositories.base_repository import BaseRepository


class PurchaseRepository(BaseRepository[Purchase]):
    """
    Repository for Purchase entity operations.

    Handles data access operations for purchases from suppliers,
    including order tracking, receiving, and payment status.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the PurchaseRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Purchase

    def get_purchases_by_supplier(
        self, supplier_id: int, skip: int = 0, limit: int = 100
    ) -> List[Purchase]:
        """
        Get purchases from a specific supplier.

        Args:
            supplier_id (int): ID of the supplier
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Purchase]: List of purchases from the supplier
        """
        query = self.session.query(self.model).filter(
            self.model.supplierId == supplier_id
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_purchases_by_status(
        self, status: PurchaseStatus, skip: int = 0, limit: int = 100
    ) -> List[Purchase]:
        """
        Get purchases by status.

        Args:
            status (PurchaseStatus): The purchase status to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Purchase]: List of purchases with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_purchases_by_payment_status(
        self, payment_status: PaymentStatus, skip: int = 0, limit: int = 100
    ) -> List[Purchase]:
        """
        Get purchases by payment status.

        Args:
            payment_status (PaymentStatus): The payment status to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Purchase]: List of purchases with the specified payment status
        """
        query = self.session.query(self.model).filter(
            self.model.paymentStatus == payment_status
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_purchases_in_date_range(
        self, start_date: str, end_date: str, skip: int = 0, limit: int = 100
    ) -> List[Purchase]:
        """
        Get purchases within a specific date range.

        Args:
            start_date (str): Start of the date range
            end_date (str): End of the date range
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Purchase]: List of purchases within the date range
        """
        query = self.session.query(self.model).filter(
            and_(self.model.date >= start_date, self.model.date <= end_date)
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_pending_deliveries(self, skip: int = 0, limit: int = 100) -> List[Purchase]:
        """
        Get purchases with pending deliveries.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Purchase]: List of purchases with pending deliveries
        """
        query = self.session.query(self.model).filter(
            and_(
                self.model.status == PurchaseStatus.ORDERED,
                self.model.deliveryDate >= datetime.now().isoformat(),
            )
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_overdue_deliveries(self, skip: int = 0, limit: int = 100) -> List[Purchase]:
        """
        Get purchases with overdue deliveries.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Purchase]: List of purchases with overdue deliveries
        """
        query = self.session.query(self.model).filter(
            and_(
                self.model.status == PurchaseStatus.ORDERED,
                self.model.deliveryDate < datetime.now().isoformat(),
            )
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_purchase_status(
        self, purchase_id: str, status: PurchaseStatus
    ) -> Optional[Purchase]:
        """
        Update a purchase's status.

        Args:
            purchase_id (str): ID of the purchase
            status (PurchaseStatus): New status to set

        Returns:
            Optional[Purchase]: Updated purchase if found, None otherwise
        """
        purchase = self.get_by_id(purchase_id)
        if not purchase:
            return None

        purchase.status = status

        # Update timestamps based on status
        if status == PurchaseStatus.ORDERED:
            purchase.updatedAt = datetime.now()
        elif status == PurchaseStatus.RECEIVED:
            purchase.updatedAt = datetime.now()

        self.session.commit()
        self.session.refresh(purchase)
        return self._decrypt_sensitive_fields(purchase)

    def update_payment_status(
        self, purchase_id: str, payment_status: PaymentStatus
    ) -> Optional[Purchase]:
        """
        Update a purchase's payment status.

        Args:
            purchase_id (str): ID of the purchase
            payment_status (PaymentStatus): New payment status to set

        Returns:
            Optional[Purchase]: Updated purchase if found, None otherwise
        """
        purchase = self.get_by_id(purchase_id)
        if not purchase:
            return None

        purchase.paymentStatus = payment_status
        purchase.updatedAt = datetime.now()

        self.session.commit()
        self.session.refresh(purchase)
        return self._decrypt_sensitive_fields(purchase)

    def get_purchase_with_items(self, purchase_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a purchase with its items.

        Args:
            purchase_id (str): ID of the purchase

        Returns:
            Optional[Dict[str, Any]]: Dictionary with purchase and items if found, None otherwise
        """
        purchase = self.get_by_id(purchase_id)
        if not purchase:
            return None

        # Get purchase items
        items = (
            self.session.query(PurchaseItem)
            .filter(PurchaseItem.purchase_id == purchase_id)
            .all()
        )

        return {"purchase": self._decrypt_sensitive_fields(purchase), "items": items}

    def get_purchase_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about purchases.

        Returns:
            Dict[str, Any]: Dictionary with purchase statistics
        """
        # Total purchases
        total_count = self.session.query(func.count(self.model.id)).scalar()

        # Total amount spent
        total_amount = self.session.query(func.sum(self.model.total)).scalar() or 0

        # Count by status
        status_counts = (
            self.session.query(
                self.model.status, func.count(self.model.id).label("count")
            )
            .group_by(self.model.status)
            .all()
        )

        # Count by supplier
        supplier_counts = (
            self.session.query(
                self.model.supplier,
                func.count(self.model.id).label("count"),
                func.sum(self.model.total).label("total"),
            )
            .group_by(self.model.supplier)
            .all()
        )

        # Recent purchases
        recent_purchases = (
            self.session.query(self.model)
            .order_by(desc(self.model.date))
            .limit(5)
            .all()
        )

        return {
            "total_count": total_count,
            "total_amount": float(total_amount),
            "by_status": [
                {
                    "status": status.value if hasattr(status, "value") else status,
                    "count": count,
                }
                for status, count in status_counts
            ],
            "by_supplier": [
                {"supplier": supplier, "count": count, "total": float(total)}
                for supplier, count, total in supplier_counts
            ],
            "recent_purchases": [
                {
                    "id": purchase.id,
                    "supplier": purchase.supplier,
                    "date": purchase.date,
                    "total": float(purchase.total),
                    "status": (
                        purchase.status.value
                        if hasattr(purchase.status, "value")
                        else purchase.status
                    ),
                }
                for purchase in recent_purchases
            ],
        }


class PurchaseItemRepository(BaseRepository[PurchaseItem]):
    """
    Repository for PurchaseItem entity operations.

    Manages individual items in purchase orders, including quantities,
    pricing, and relationships to materials or supplies.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the PurchaseItemRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = PurchaseItem

    def get_items_by_purchase(self, purchase_id: int) -> List[PurchaseItem]:
        """
        Get items for a specific purchase.

        Args:
            purchase_id (int): ID of the purchase

        Returns:
            List[PurchaseItem]: List of items in the purchase
        """
        query = self.session.query(self.model).filter(
            self.model.purchase_id == purchase_id
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_items_by_material_type(self, material_type: str) -> List[PurchaseItem]:
        """
        Get purchase items for a specific material type.

        Args:
            material_type (str): The material type to filter by

        Returns:
            List[PurchaseItem]: List of purchase items for the material type
        """
        query = self.session.query(self.model).filter(
            self.model.materialType == material_type
        )

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_item_quantity(
        self, item_id: int, quantity: int
    ) -> Optional[PurchaseItem]:
        """
        Update a purchase item's quantity.

        Args:
            item_id (int): ID of the purchase item
            quantity (int): New quantity value

        Returns:
            Optional[PurchaseItem]: Updated purchase item if found, None otherwise
        """
        item = self.get_by_id(item_id)
        if not item:
            return None

        item.quantity = quantity
        item.total = item.price * quantity

        self.session.commit()
        self.session.refresh(item)
        return self._decrypt_sensitive_fields(item)

    def update_item_price(self, item_id: int, price: float) -> Optional[PurchaseItem]:
        """
        Update a purchase item's price.

        Args:
            item_id (int): ID of the purchase item
            price (float): New price value

        Returns:
            Optional[PurchaseItem]: Updated purchase item if found, None otherwise
        """
        item = self.get_by_id(item_id)
        if not item:
            return None

        item.price = price
        item.total = price * item.quantity

        self.session.commit()
        self.session.refresh(item)
        return self._decrypt_sensitive_fields(item)
