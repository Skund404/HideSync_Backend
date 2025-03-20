# File: app/repositories/sale_repository.py

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func
from datetime import datetime, timedelta

from app.db.models.sales import Sale, SaleItem
from app.db.models.enums import SaleStatus, PaymentStatus
from app.repositories.base_repository import BaseRepository


class SaleRepository(BaseRepository[Sale]):
    """
    Repository for Sale entity operations.

    Handles operations related to sales, orders, and revenue tracking.
    Provides methods for retrieving, creating and updating sales records.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the SaleRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Sale

    def get_sales_by_customer(
        self, customer_id: int, skip: int = 0, limit: int = 100
    ) -> List[Sale]:
        """
        Get sales for a specific customer.

        Args:
            customer_id (int): ID of the customer
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Sale]: List of sales for the specified customer
        """
        query = self.session.query(self.model).filter(
            self.model.customer_id == customer_id
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_sales_by_status(
        self, status: SaleStatus, skip: int = 0, limit: int = 100
    ) -> List[Sale]:
        """
        Get sales by their status.

        Args:
            status (SaleStatus): The sale status to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Sale]: List of sales with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_sales_by_payment_status(
        self, payment_status: PaymentStatus, skip: int = 0, limit: int = 100
    ) -> List[Sale]:
        """
        Get sales by their payment status.

        Args:
            payment_status (PaymentStatus): The payment status to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Sale]: List of sales with the specified payment status
        """
        query = self.session.query(self.model).filter(
            self.model.paymentStatus == payment_status
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_sales_in_date_range(
        self, start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100
    ) -> List[Sale]:
        """
        Get sales created within a specific date range.

        Args:
            start_date (datetime): Start of the date range
            end_date (datetime): End of the date range
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Sale]: List of sales within the date range
        """
        query = self.session.query(self.model).filter(
            and_(self.model.createdAt >= start_date, self.model.createdAt <= end_date)
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_recent_sales(
        self, days: int = 30, skip: int = 0, limit: int = 100
    ) -> List[Sale]:
        """
        Get sales created within the last specified number of days.

        Args:
            days (int): Number of days to look back
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Sale]: List of recent sales
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        query = (
            self.session.query(self.model)
            .filter(self.model.createdAt >= cutoff_date)
            .order_by(desc(self.model.createdAt))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_pending_shipments(self, skip: int = 0, limit: int = 100) -> List[Sale]:
        """
        Get sales that are ready for shipping.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Sale]: List of sales ready for shipping
        """
        query = self.session.query(self.model).filter(
            and_(
                self.model.status == SaleStatus.READY_FOR_PICKUP,
                self.model.paymentStatus == PaymentStatus.PAID,
            )
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_overdue_payments(self, skip: int = 0, limit: int = 100) -> List[Sale]:
        """
        Get sales with overdue payments.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Sale]: List of sales with overdue payments
        """
        query = self.session.query(self.model).filter(
            self.model.paymentStatus == PaymentStatus.OVERDUE
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_sale_status(self, sale_id: int, status: SaleStatus) -> Optional[Sale]:
        """
        Update a sale's status.

        Args:
            sale_id (int): ID of the sale
            status (SaleStatus): New status to set

        Returns:
            Optional[Sale]: Updated sale if found, None otherwise
        """
        sale = self.get_by_id(sale_id)
        if not sale:
            return None

        sale.status = status

        # If sale is completed, set the completion date
        if status == SaleStatus.COMPLETED and not sale.completedDate:
            sale.completedDate = datetime.now()

        self.session.commit()
        self.session.refresh(sale)
        return self._decrypt_sensitive_fields(sale)

    def update_payment_status(
        self, sale_id: int, payment_status: PaymentStatus
    ) -> Optional[Sale]:
        """
        Update a sale's payment status.

        Args:
            sale_id (int): ID of the sale
            payment_status (PaymentStatus): New payment status to set

        Returns:
            Optional[Sale]: Updated sale if found, None otherwise
        """
        sale = self.get_by_id(sale_id)
        if not sale:
            return None

        sale.paymentStatus = payment_status

        self.session.commit()
        self.session.refresh(sale)
        return self._decrypt_sensitive_fields(sale)

    def get_sale_with_items(self, sale_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a sale with its items.

        Args:
            sale_id (int): ID of the sale

        Returns:
            Optional[Dict[str, Any]]: Dictionary with sale and items if found, None otherwise
        """
        sale = self.get_by_id(sale_id)
        if not sale:
            return None

        # Get sale items
        items = self.session.query(SaleItem).filter(SaleItem.sale_id == sale_id).all()

        return {"sale": sale, "items": items}

    def get_revenue_by_period(
        self,
        period: str = "month",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get sales revenue aggregated by time period.

        Args:
            period (str): Aggregation period ('day', 'week', 'month', 'year')
            start_date (Optional[datetime]): Start of the date range
            end_date (Optional[datetime]): End of the date range

        Returns:
            List[Dict[str, Any]]: List of revenue data points by period
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=365)
        if not end_date:
            end_date = datetime.now()

        if period == "day":
            date_format = func.date(self.model.createdAt)
        elif period == "week":
            date_format = func.date_trunc("week", self.model.createdAt)
        elif period == "month":
            date_format = func.date_trunc("month", self.model.createdAt)
        else:  # year
            date_format = func.date_trunc("year", self.model.createdAt)

        query = (
            self.session.query(
                date_format.label("period"),
                func.sum(self.model.total_amount).label("revenue"),
                func.count(self.model.id).label("order_count"),
            )
            .filter(
                and_(
                    self.model.createdAt >= start_date, self.model.createdAt <= end_date
                )
            )
            .group_by("period")
            .order_by("period")
        )

        return [
            {
                "period": row.period,
                "revenue": float(row.revenue) if row.revenue else 0.0,
                "order_count": row.order_count,
            }
            for row in query.all()
        ]

    def search_sales(self, query: str, skip: int = 0, limit: int = 100) -> List[Sale]:
        """
        Search for sales by order ID, customer name, or notes.

        Args:
            query (str): The search query
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Sale]: List of matching sales
        """
        search_query = self.session.query(self.model).filter(
            or_(
                self.model.id.ilike(f"%{query}%"),
                self.model.platform_order_id.ilike(f"%{query}%"),
                self.model.notes.ilike(f"%{query}%"),
                self.model.customization.ilike(f"%{query}%"),
            )
        )

        entities = search_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]
