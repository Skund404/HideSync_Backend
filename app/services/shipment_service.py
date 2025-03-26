# File: app/services/shipment_service.py
"""
Service for managing shipments in the HideSync system.

This module provides business logic for creating, tracking, and managing
shipments for customer orders, with integration to the sales system.
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import logging
from sqlalchemy.orm import Session

from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
    ValidationException,
)
from app.core.events import DomainEvent
from app.db.models.shipment import Shipment
from app.db.models.enums import SaleStatus, FulfillmentStatus
from app.repositories.shipment_repository import ShipmentRepository
from app.services.base_service import BaseService


logger = logging.getLogger(__name__)


class ShipmentCreated(DomainEvent):
    """Event emitted when a shipment is created."""

    def __init__(
        self,
        shipment_id: int,
        sale_id: int,
        user_id: Optional[int] = None,
    ):
        """
        Initialize shipment created event.

        Args:
            shipment_id: ID of the created shipment
            sale_id: ID of the associated sale
            user_id: Optional ID of the user who created the shipment
        """
        super().__init__()
        self.shipment_id = shipment_id
        self.sale_id = sale_id
        self.user_id = user_id


class ShipmentShipped(DomainEvent):
    """Event emitted when a shipment is marked as shipped."""

    def __init__(
        self,
        shipment_id: int,
        sale_id: int,
        tracking_number: str,
        shipping_method: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize shipment shipped event.

        Args:
            shipment_id: ID of the shipped shipment
            sale_id: ID of the associated sale
            tracking_number: Carrier tracking number
            shipping_method: Shipping method used
            user_id: Optional ID of the user who marked as shipped
        """
        super().__init__()
        self.shipment_id = shipment_id
        self.sale_id = sale_id
        self.tracking_number = tracking_number
        self.shipping_method = shipping_method
        self.user_id = user_id


class ShipmentStatusChanged(DomainEvent):
    """Event emitted when a shipment's status is changed."""

    def __init__(
        self,
        shipment_id: int,
        sale_id: int,
        previous_status: str,
        new_status: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize shipment status changed event.

        Args:
            shipment_id: ID of the shipment
            sale_id: ID of the associated sale
            previous_status: Previous status
            new_status: New status
            user_id: Optional ID of the user who changed the status
        """
        super().__init__()
        self.shipment_id = shipment_id
        self.sale_id = sale_id
        self.previous_status = previous_status
        self.new_status = new_status
        self.user_id = user_id


class ShipmentService(BaseService[Shipment]):
    """
    Service for managing shipments.

    Provides functionality for:
    - Creating and tracking shipments
    - Updating shipment statuses
    - Generating shipping labels and documentation
    - Integration with carrier APIs and sales system
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        sale_service=None,
    ):
        """
        Initialize ShipmentService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository for shipments (defaults to ShipmentRepository)
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            sale_service: Optional sale service for sale operations
        """
        self.session = session
        self.repository = repository or ShipmentRepository(session)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.sale_service = sale_service

    def create_shipment(self, data: Dict[str, Any]) -> Shipment:
        """
        Create a new shipment record.

        Args:
            data: Shipment data containing sale ID and shipping details

        Returns:
            Created shipment entity

        Raises:
            ValidationException: If validation fails
            SaleNotFoundException: If specified sale not found
            BusinessRuleException: If sale already has a shipment
        """
        with self.transaction():
            # Validate sale existence
            sale_id = data.get("sale_id")
            if not sale_id:
                raise ValidationException("Sale ID is required", {"sale_id": ["This field is required"]})

            if self.sale_service:
                sale = self.sale_service.get_by_id(sale_id)
                if not sale:
                    from app.core.exceptions import SaleNotFoundException
                    raise SaleNotFoundException(sale_id)

                # Check if sale already has a shipment
                existing_shipment = self.repository.get_shipment_by_sale(sale_id)
                if existing_shipment:
                    raise BusinessRuleException(
                        f"Sale with ID {sale_id} already has a shipment (ID: {existing_shipment.id})"
                    )

                # Validate sale status allows shipping
                if sale.status not in [
                    SaleStatus.FINAL_PAYMENT_RECEIVED.value,
                    SaleStatus.READY_FOR_PICKUP.value,
                ]:
                    raise BusinessRuleException(
                        f"Cannot create shipment for sale with status '{sale.status}'. "
                        f"Sale must be ready for pickup or have final payment received."
                    )

            # Set initial status if not provided
            if "status" not in data:
                data["status"] = "PENDING"

            # Set timestamp if not provided
            if "created_at" not in data:
                data["created_at"] = datetime.now()

            # Create shipment
            shipment = self.repository.create(data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ShipmentCreated(
                        shipment_id=shipment.id,
                        sale_id=shipment.sale_id,
                        user_id=user_id,
                    )
                )

            # Update sale if sale service exists
            if self.sale_service:
                # Update sale with shipment information
                self.sale_service.update_fulfillment_status(
                    sale_id=sale_id,
                    new_status=FulfillmentStatus.PENDING,
                    shipping_provider=data.get("shipping_method"),
                    tracking_number=data.get("tracking_number"),
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Sale:{sale_id}")
                self.cache_service.invalidate(f"Sale:detail:{sale_id}")

            return shipment

    def mark_as_shipped(
        self,
        shipment_id: int,
        tracking_number: str,
        shipping_method: str,
        shipping_cost: float,
        ship_date: Optional[datetime] = None,
    ) -> Shipment:
        """
        Mark a shipment as shipped with tracking details.

        Args:
            shipment_id: ID of the shipment
            tracking_number: Carrier tracking number
            shipping_method: Shipping method used
            shipping_cost: Cost of shipping
            ship_date: Date of shipment (defaults to now)

        Returns:
            Updated shipment

        Raises:
            EntityNotFoundException: If shipment not found
            BusinessRuleException: If shipment is not in pending status
        """
        with self.transaction():
            # Get shipment
            shipment = self.get_by_id(shipment_id)
            if not shipment:
                raise EntityNotFoundException(f"Shipment with ID {shipment_id} not found")

            # Validate shipment is pending
            if shipment.status != "PENDING":
                raise BusinessRuleException(
                    f"Cannot mark as shipped a shipment with status '{shipment.status}'. "
                    f"Shipment must be in PENDING status."
                )

            # Mark as shipped
            shipment = self.repository.mark_shipped(
                shipment_id=shipment_id,
                tracking_number=tracking_number,
                method=shipping_method,
                cost=shipping_cost,
                date=ship_date,
            )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ShipmentShipped(
                        shipment_id=shipment.id,
                        sale_id=shipment.sale_id,
                        tracking_number=tracking_number,
                        shipping_method=shipping_method,
                        user_id=user_id,
                    )
                )

            # Update sale if sale service exists
            if self.sale_service:
                # Update sale with shipping information
                self.sale_service.update_fulfillment_status(
                    sale_id=shipment.sale_id,
                    new_status=FulfillmentStatus.SHIPPED,
                    shipping_provider=shipping_method,
                    tracking_number=tracking_number,
                )

                # Update sale status to SHIPPED
                self.sale_service.update_sale_status(
                    sale_id=shipment.sale_id,
                    new_status=SaleStatus.SHIPPED,
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Shipment:{shipment_id}")
                self.cache_service.invalidate(f"Sale:{shipment.sale_id}")
                self.cache_service.invalidate(f"Sale:detail:{shipment.sale_id}")

            return shipment

    def update_shipment_status(self, shipment_id: int, status: str) -> Shipment:
        """
        Update a shipment's status.

        Args:
            shipment_id: ID of the shipment
            status: New status

        Returns:
            Updated shipment

        Raises:
            EntityNotFoundException: If shipment not found
        """
        with self.transaction():
            # Get shipment
            shipment = self.get_by_id(shipment_id)
            if not shipment:
                raise EntityNotFoundException(f"Shipment with ID {shipment_id} not found")

            # Store previous status for event
            previous_status = shipment.status

            # Update status
            shipment = self.repository.update_shipment_status(shipment_id, status)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    ShipmentStatusChanged(
                        shipment_id=shipment.id,
                        sale_id=shipment.sale_id,
                        previous_status=previous_status,
                        new_status=status,
                        user_id=user_id,
                    )
                )

            # Update sale status if status is DELIVERED and sale service exists
            if status == "DELIVERED" and self.sale_service:
                self.sale_service.update_fulfillment_status(
                    sale_id=shipment.sale_id,
                    new_status=FulfillmentStatus.DELIVERED,
                )
                self.sale_service.update_sale_status(
                    sale_id=shipment.sale_id,
                    new_status=SaleStatus.DELIVERED,
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Shipment:{shipment_id}")
                self.cache_service.invalidate(f"Sale:{shipment.sale_id}")
                self.cache_service.invalidate(f"Sale:detail:{shipment.sale_id}")

            return shipment

    def update_tracking_info(
        self, shipment_id: int, tracking_number: str, shipping_provider: str
    ) -> Shipment:
        """
        Update tracking information for a shipment.

        Args:
            shipment_id: ID of the shipment
            tracking_number: New tracking number
            shipping_provider: Shipping provider/carrier

        Returns:
            Updated shipment

        Raises:
            EntityNotFoundException: If shipment not found
        """
        with self.transaction():
            # Get shipment
            shipment = self.get_by_id(shipment_id)
            if not shipment:
                raise EntityNotFoundException(f"Shipment with ID {shipment_id} not found")

            # Update tracking information
            updated_shipment = self.repository.update_tracking(
                shipment_id=shipment_id,
                tracking_number=tracking_number,
                shipping_provider=shipping_provider,
            )

            # Update sale with new tracking information if sale service exists
            if self.sale_service:
                self.sale_service.update(
                    shipment.sale_id,
                    {
                        "tracking_number": tracking_number,
                        "shipping_provider": shipping_provider,
                    },
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Shipment:{shipment_id}")
                self.cache_service.invalidate(f"Sale:{shipment.sale_id}")
                self.cache_service.invalidate(f"Sale:detail:{shipment.sale_id}")

            return updated_shipment

    def get_shipment_by_sale(self, sale_id: int) -> Optional[Shipment]:
        """
        Get the shipment for a specific sale.

        Args:
            sale_id: ID of the sale

        Returns:
            Shipment for the sale, or None if not found
        """
        return self.repository.get_shipment_by_sale(sale_id)

    def get_pending_shipments(self) -> List[Shipment]:
        """
        Get all pending shipments.

        Returns:
            List of pending shipments
        """
        return self.repository.get_shipments_by_status("PENDING")

    def get_recent_shipments(self, days: int = 7) -> List[Shipment]:
        """
        Get shipments created within the specified number of days.

        Args:
            days: Number of days to look back

        Returns:
            List of recent shipments
        """
        return self.repository.get_recent_shipments(days)