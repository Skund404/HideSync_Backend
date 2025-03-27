# File: app/repositories/shipment_repository.py
"""
Repository for Shipment entity operations.

This module provides data access functionality for shipments, including
creating, retrieving, and updating shipment records.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from app.db.models.shipment import Shipment
from app.repositories.base_repository import BaseRepository


class ShipmentRepository(BaseRepository[Shipment]):
    """
    Repository for Shipment entity operations.

    Provides methods for retrieving, creating and updating shipment records.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the ShipmentRepository.

        Args:
            session: SQLAlchemy database session
            encryption_service: Optional service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Shipment

    def get_shipment_by_sale(self, sale_id: int) -> Optional[Shipment]:
        """
        Get the shipment for a specific sale.

        Args:
            sale_id: ID of the sale

        Returns:
            Shipment for the specified sale, or None if not found
        """
        query = self.session.query(self.model).filter(self.model.sale_id == sale_id)
        entity = query.first()
        if entity:
            return self._decrypt_sensitive_fields(entity)
        return None

    def get_shipments_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[Shipment]:
        """
        Get shipments with a specific status.

        Args:
            status: Status to filter by
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of shipments with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)
        entities = query.offset(skip).limit(limit).all()
        return self._decrypt_sensitive_fields_in_list(entities)

    def get_recent_shipments(
        self, days: int = 7, skip: int = 0, limit: int = 100
    ) -> List[Shipment]:
        """
        Get shipments created within the specified number of days.

        Args:
            days: Number of days to look back
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List of recent shipments
        """
        cutoff_date = datetime.now() - datetime.timedelta(days=days)
        query = (
            self.session.query(self.model)
            .filter(self.model.created_at >= cutoff_date)
            .order_by(desc(self.model.created_at))
        )

        entities = query.offset(skip).limit(limit).all()
        return self._decrypt_sensitive_fields_in_list(entities)

    def update_shipment_status(
        self, shipment_id: int, status: str
    ) -> Optional[Shipment]:
        """
        Update a shipment's status.

        Args:
            shipment_id: ID of the shipment
            status: New status to set

        Returns:
            Updated shipment if found, None otherwise
        """
        shipment = self.get_by_id(shipment_id)
        if not shipment:
            return None

        shipment.status = status
        self.session.commit()
        self.session.refresh(shipment)
        return self._decrypt_sensitive_fields(shipment)

    def mark_shipped(
        self,
        shipment_id: int,
        tracking_number: str,
        method: str,
        cost: float,
        date: Optional[datetime] = None,
    ) -> Optional[Shipment]:
        """
        Mark a shipment as shipped with tracking details.

        Args:
            shipment_id: ID of the shipment
            tracking_number: Carrier tracking number
            method: Shipping method used
            cost: Shipping cost
            date: Ship date (defaults to now)

        Returns:
            Updated shipment if found, None otherwise
        """
        shipment = self.get_by_id(shipment_id)
        if not shipment:
            return None

        shipment.mark_shipped(
            tracking_number=tracking_number,
            method=method,
            cost=cost,
            date=date,
        )

        self.session.commit()
        self.session.refresh(shipment)
        return self._decrypt_sensitive_fields(shipment)

    def update_tracking(
        self, shipment_id: int, tracking_number: str, shipping_provider: str
    ) -> Optional[Shipment]:
        """
        Update tracking information for a shipment.

        Args:
            shipment_id: ID of the shipment
            tracking_number: New tracking number
            shipping_provider: Shipping provider/carrier

        Returns:
            Updated shipment if found, None otherwise
        """
        shipment = self.get_by_id(shipment_id)
        if not shipment:
            return None

        shipment.tracking_number = tracking_number
        shipment.shipping_method = shipping_provider

        self.session.commit()
        self.session.refresh(shipment)
        return self._decrypt_sensitive_fields(shipment)
