# File: app/services/supplier_history_service.py
"""
Service for supplier history management in the HideSync system.

This module provides functionality for tracking supplier status changes,
interactions, and significant events over time.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.core.events import DomainEvent
from app.core.exceptions import EntityNotFoundException
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.supplier_history_repository import SupplierHistoryRepository
from app.db.models.supplier_history import SupplierHistory
from app.services.base_service import BaseService


class SupplierStatusChanged(DomainEvent):
    """Event emitted when a supplier's status is changed."""

    def __init__(
        self,
        supplier_id: int,
        previous_status: str,
        new_status: str,
        reason: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        """
        Initialize supplier status changed event.

        Args:
            supplier_id: ID of the supplier
            previous_status: Previous status of the supplier
            new_status: New status of the supplier
            reason: Optional reason for the status change
            user_id: Optional ID of the user who changed the status
        """
        super().__init__()
        self.supplier_id = supplier_id
        self.previous_status = previous_status
        self.new_status = new_status
        self.reason = reason
        self.user_id = user_id


class SupplierHistoryService(BaseService[SupplierHistory]):
    """
    Service for managing supplier history in the HideSync system.

    Provides functionality for:
    - Recording supplier status changes
    - Tracking supplier history
    - Analyzing historical data for trends
    """

    def __init__(
        self,
        session: Session,
        supplier_repository=None,
        supplier_history_repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
    ):
        """
        Initialize SupplierHistoryService with dependencies.

        Args:
            session: Database session for persistence operations
            supplier_repository: Optional repository for suppliers
            supplier_history_repository: Optional repository for supplier history
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
        """
        self.session = session
        self.supplier_repository = supplier_repository or SupplierRepository(session)
        self.repository = supplier_history_repository or SupplierHistoryRepository(
            session
        )
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service

    def record_status_change(
        self,
        supplier_id: int,
        previous_status: str,
        new_status: str,
        reason: Optional[str] = None,
    ) -> SupplierHistory:
        """
        Record a status change in the supplier history.

        Args:
            supplier_id: ID of the supplier
            previous_status: Previous status of the supplier
            new_status: New status of the supplier
            reason: Optional reason for the status change

        Returns:
            Created supplier history entry

        Raises:
            EntityNotFoundException: If supplier not found
        """
        with self.transaction():
            # Check if supplier exists
            supplier = self.supplier_repository.get_by_id(supplier_id)
            if not supplier:
                raise EntityNotFoundException(
                    f"Supplier with ID {supplier_id} not found"
                )

            # Get user ID from security context if available
            user_id = (
                self.security_context.current_user.id if self.security_context else None
            )

            # Create history record
            history_data = {
                "supplier_id": supplier_id,
                "previous_status": previous_status,
                "new_status": new_status,
                "reason": reason,
                "changed_by": user_id,
                "change_date": datetime.now(),
            }

            history_entry = self.repository.create(history_data)

            # Publish event if event bus exists
            if self.event_bus:
                self.event_bus.publish(
                    SupplierStatusChanged(
                        supplier_id=supplier_id,
                        previous_status=previous_status,
                        new_status=new_status,
                        reason=reason,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"SupplierHistory:{supplier_id}")

            return history_entry

    def get_history_by_supplier(
        self, supplier_id: int, limit: int = 50
    ) -> List[SupplierHistory]:
        """
        Get history entries for a specific supplier.

        Args:
            supplier_id: ID of the supplier
            limit: Maximum number of records to return

        Returns:
            List of supplier history entries ordered by change date (newest first)
        """
        # Check cache first
        if self.cache_service:
            cache_key = f"SupplierHistory:{supplier_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached[:limit]  # Return only requested number of records

        # Get history from repository
        history = self.repository.get_history_by_supplier(
            supplier_id, order_by="change_date", order_dir="desc", limit=limit
        )

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, history, ttl=3600)  # 1 hour TTL

        return history

    def get_recent_history(self, days: int = 90) -> List[SupplierHistory]:
        """
        Get recent history entries across all suppliers.

        Args:
            days: Number of days to look back

        Returns:
            List of recent supplier history entries
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        return self.repository.get_recent_history(cutoff_date)

    def get_status_change_trends(self) -> Dict[str, Any]:
        """
        Get trends in supplier status changes.

        Returns:
            Dictionary with status change trends by month and status
        """
        # Get recent status changes
        recent_changes = self.get_recent_history(days=90)

        # Count by new status and month
        status_by_month = {}
        month_format = "%Y-%m"

        for change in recent_changes:
            month = change.change_date.strftime(month_format)
            status = change.new_status

            if month not in status_by_month:
                status_by_month[month] = {}

            if status not in status_by_month[month]:
                status_by_month[month][status] = 0

            status_by_month[month][status] += 1

        return {
            "status_by_month": status_by_month,
            "total_changes": len(recent_changes),
        }

    def get_supplier_status_timeline(self, supplier_id: int) -> List[Dict[str, Any]]:
        """
        Get a timeline of status changes for a supplier.

        Args:
            supplier_id: ID of the supplier

        Returns:
            List of status changes with dates and reasons, ordered chronologically
        """
        # Check if supplier exists
        supplier = self.supplier_repository.get_by_id(supplier_id)
        if not supplier:
            raise EntityNotFoundException(f"Supplier with ID {supplier_id} not found")

        # Get all history entries for the supplier
        history = self.repository.get_history_by_supplier(
            supplier_id, order_by="change_date", order_dir="asc"
        )

        # Format as timeline entries
        timeline = []
        for entry in history:
            timeline.append(
                {
                    "date": (
                        entry.change_date.isoformat() if entry.change_date else None
                    ),
                    "previous_status": entry.previous_status,
                    "new_status": entry.new_status,
                    "reason": entry.reason,
                    "changed_by": entry.changed_by,
                }
            )

        return timeline
