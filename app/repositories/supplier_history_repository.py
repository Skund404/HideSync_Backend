# File: app/repositories/supplier_history_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from datetime import datetime

from app.db.models.supplier_history import SupplierHistory
from app.repositories.base_repository import BaseRepository


class SupplierHistoryRepository(BaseRepository[SupplierHistory]):
    """
    Repository for SupplierHistory entity operations.

    Handles data access for supplier history records, providing methods for
    querying and analyzing supplier status changes and event history.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the SupplierHistoryRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = SupplierHistory

    def get_history_by_supplier(
            self,
            supplier_id: int,
            order_by: str = "change_date",
            order_dir: str = "desc",
            limit: int = 50
    ) -> List[SupplierHistory]:
        """
        Get history entries for a specific supplier.

        Args:
            supplier_id: ID of the supplier
            order_by: Field to order by
            order_dir: Direction of ordering ("asc" or "desc")
            limit: Maximum number of records to return

        Returns:
            List of supplier history entries
        """
        query = self.session.query(self.model).filter(self.model.supplier_id == supplier_id)

        # Apply ordering
        if order_dir.lower() == "desc":
            query = query.order_by(desc(getattr(self.model, order_by)))
        else:
            query = query.order_by(asc(getattr(self.model, order_by)))

        # Apply limit
        query = query.limit(limit)

        # Apply decryption if needed
        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_recent_history(
            self, cutoff_date: datetime, limit: int = 1000
    ) -> List[SupplierHistory]:
        """
        Get history entries after a cutoff date.

        Args:
            cutoff_date: Date after which to get entries
            limit: Maximum number of records to return

        Returns:
            List of recent supplier history entries
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.change_date >= cutoff_date)
            .order_by(desc(self.model.change_date))
            .limit(limit)
        )

        # Apply decryption if needed
        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_history_by_status(
            self, status: str, limit: int = 100
    ) -> List[SupplierHistory]:
        """
        Get history entries with a specific new status.

        Args:
            status: Status to filter by
            limit: Maximum number of records to return

        Returns:
            List of supplier history entries with the specified status
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.new_status == status)
            .order_by(desc(self.model.change_date))
            .limit(limit)
        )

        # Apply decryption if needed
        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_status_count_by_month(
            self, months: int = 12
    ) -> Dict[str, Dict[str, int]]:
        """
        Get status change counts grouped by month.

        Args:
            months: Number of months to look back

        Returns:
            Dictionary with month keys and status count values
        """
        # This is a simplified version - in a real implementation, you would use
        # SQLAlchemy's func.date_trunc or equivalent to group by month

        # Get recent history
        now = datetime.now()
        cutoff_date = datetime(now.year - (months // 12), now.month - (months % 12), 1)
        if cutoff_date.month < 1:
            cutoff_date = datetime(cutoff_date.year - 1, 12 + cutoff_date.month, 1)

        recent_history = self.get_recent_history(cutoff_date)

        # Group by month and status
        result = {}
        for entry in recent_history:
            month_key = entry.change_date.strftime("%Y-%m")
            if month_key not in result:
                result[month_key] = {}

            if entry.new_status not in result[month_key]:
                result[month_key][entry.new_status] = 0

            result[month_key][entry.new_status] += 1

        return result