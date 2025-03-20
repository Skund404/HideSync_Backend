# File: app/repositories/shipment_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func
from datetime import datetime, timedelta

from app.db.models.shipment import Shipment
from app.repositories.base_repository import BaseRepository


class ShipmentRepository(BaseRepository[Shipment]):
    """
    Repository for Shipment entity operations.

    Handles data access for shipments, tracking shipping information,
    status, and relationships to sales orders.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the ShipmentRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Shipment

    def get_shipments_by_sale(self, sale_id: int) -> List[Shipment]:
        """
        Get shipments for a specific sale.

        Args:
            sale_id (int): ID of the sale

        Returns:
            List[Shipment]: List of shipments for the sale
        """
        query = self.session.query(self.model).filter(self.model.sale_id == sale_id)

        entities = query.all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_shipments_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[Shipment]:
        """
        Get shipments by status.

        Args:
            status (str): The status to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Shipment]: List of shipments with the specified status
        """
        query = self.session.query(self.model).filter(self.model.status == status)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_shipments_by_tracking_number(
        self, tracking_number: str
    ) -> Optional[Shipment]:
        """
        Get a shipment by tracking number.

        Args:
            tracking_number (str): The tracking number to search for

        Returns:
            Optional[Shipment]: The shipment if found, None otherwise
        """
        entity = (
            self.session.query(self.model)
            .filter(self.model.tracking_number == tracking_number)
            .first()
        )
        return self._decrypt_sensitive_fields(entity) if entity else None

    def get_shipments_by_date_range(
        self, start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100
    ) -> List[Shipment]:
        """
        Get shipments within a specific date range.

        Args:
            start_date (datetime): Start of the date range
            end_date (datetime): End of the date range
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Shipment]: List of shipments within the date range
        """
        query = self.session.query(self.model).filter(
            and_(self.model.ship_date >= start_date, self.model.ship_date <= end_date)
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_shipments_by_shipping_method(
        self, shipping_method: str, skip: int = 0, limit: int = 100
    ) -> List[Shipment]:
        """
        Get shipments by shipping method.

        Args:
            shipping_method (str): The shipping method to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Shipment]: List of shipments with the specified shipping method
        """
        query = self.session.query(self.model).filter(
            self.model.shipping_method == shipping_method
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_recent_shipments(
        self, days: int = 30, skip: int = 0, limit: int = 100
    ) -> List[Shipment]:
        """
        Get shipments from the last specified number of days.

        Args:
            days (int): Number of days to look back
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Shipment]: List of recent shipments
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        query = (
            self.session.query(self.model)
            .filter(self.model.ship_date >= cutoff_date)
            .order_by(desc(self.model.ship_date))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def update_shipment_status(
        self, shipment_id: int, status: str
    ) -> Optional[Shipment]:
        """
        Update a shipment's status.

        Args:
            shipment_id (int): ID of the shipment
            status (str): New status to set

        Returns:
            Optional[Shipment]: Updated shipment if found, None otherwise
        """
        shipment = self.get_by_id(shipment_id)
        if not shipment:
            return None

        shipment.status = status

        self.session.commit()
        self.session.refresh(shipment)
        return self._decrypt_sensitive_fields(shipment)

    def update_tracking_information(
        self, shipment_id: int, tracking_number: str, shipping_method: str
    ) -> Optional[Shipment]:
        """
        Update a shipment's tracking information.

        Args:
            shipment_id (int): ID of the shipment
            tracking_number (str): New tracking number
            shipping_method (str): New shipping method

        Returns:
            Optional[Shipment]: Updated shipment if found, None otherwise
        """
        shipment = self.get_by_id(shipment_id)
        if not shipment:
            return None

        shipment.tracking_number = tracking_number
        shipment.shipping_method = shipping_method

        self.session.commit()
        self.session.refresh(shipment)
        return self._decrypt_sensitive_fields(shipment)

    def get_shipment_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about shipments.

        Returns:
            Dict[str, Any]: Dictionary with shipment statistics
        """
        # Total shipments
        total_count = self.session.query(func.count(self.model.id)).scalar()

        # Average shipping cost
        avg_cost = self.session.query(func.avg(self.model.shipping_cost)).scalar() or 0

        # Shipments by status
        status_counts = (
            self.session.query(
                self.model.status, func.count(self.model.id).label("count")
            )
            .group_by(self.model.status)
            .all()
        )

        # Shipments by shipping method
        method_counts = (
            self.session.query(
                self.model.shipping_method,
                func.count(self.model.id).label("count"),
                func.avg(self.model.shipping_cost).label("avg_cost"),
            )
            .group_by(self.model.shipping_method)
            .all()
        )

        # Monthly shipment counts
        monthly_counts = (
            self.session.query(
                func.date_trunc("month", self.model.ship_date).label("month"),
                func.count(self.model.id).label("count"),
            )
            .group_by("month")
            .order_by("month")
            .all()
        )

        return {
            "total_count": total_count,
            "average_shipping_cost": float(avg_cost),
            "by_status": [
                {"status": status, "count": count} for status, count in status_counts
            ],
            "by_shipping_method": [
                {"method": method, "count": count, "average_cost": float(avg_cost)}
                for method, count, avg_cost in method_counts
            ],
            "monthly_trends": [
                {
                    "month": (
                        month.strftime("%Y-%m") if hasattr(month, "strftime") else month
                    ),
                    "count": count,
                }
                for month, count in monthly_counts
            ],
        }
