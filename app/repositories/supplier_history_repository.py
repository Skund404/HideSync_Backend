# File: repositories/supplier_history_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.models.supplier_history import SupplierHistory
from app.repositories.base_repository import BaseRepository


class SupplierHistoryRepository(BaseRepository[SupplierHistory]):
    """
    Repository for managing supplier history records.

    This repository provides methods for creating and retrieving
    supplier status change history records.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the SupplierHistoryRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, SupplierHistory, encryption_service)

    def get_history_by_supplier(
        self, supplier_id: int, limit: int = 100
    ) -> List[SupplierHistory]:
        """
        Get status history records for a supplier.

        Args:
            supplier_id: ID of the supplier
            limit: Maximum number of records to return

        Returns:
            List of status history records in reverse chronological order
        """
        return (
            self.session.query(SupplierHistory)
            .filter(SupplierHistory.supplier_id == supplier_id)
            .order_by(desc(SupplierHistory.change_date))
            .limit(limit)
            .all()
        )

    def get_recent_history(
        self, days: int = 30, limit: int = 100
    ) -> List[SupplierHistory]:
        """
        Get recent status changes across all suppliers.

        Args:
            days: Number of days to look back
            limit: Maximum number of records to return

        Returns:
            List of recent status changes
        """
        from datetime import datetime, timedelta

        cutoff_date = datetime.now() - timedelta(days=days)

        return (
            self.session.query(SupplierHistory)
            .filter(SupplierHistory.change_date >= cutoff_date)
            .order_by(desc(SupplierHistory.change_date))
            .limit(limit)
            .all()
        )

    def get_status_changes_by_type(
        self, status: str, limit: int = 100
    ) -> List[SupplierHistory]:
        """
        Get history records for a specific status change.

        Args:
            status: Status to filter by (new_status)
            limit: Maximum number of records to return

        Returns:
            List of matching status changes
        """
        return (
            self.session.query(SupplierHistory)
            .filter(SupplierHistory.new_status == status)
            .order_by(desc(SupplierHistory.change_date))
            .limit(limit)
            .all()
        )
