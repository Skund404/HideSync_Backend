# File: app/services/refund_service.py
"""
Service for managing customer refunds in the HideSync system.

This module provides business logic for processing refunds, including
validation, status updates, and integration with sales and payment systems.
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
from app.db.models.refund import Refund
from app.db.models.enums import PaymentStatus, SaleStatus
from app.repositories.refund_repository import RefundRepository
from app.services.base_service import BaseService


logger = logging.getLogger(__name__)


class RefundCreated(DomainEvent):
    """Event emitted when a refund is created."""

    def __init__(
        self,
        refund_id: int,
        sale_id: int,
        amount: float,
        user_id: Optional[int] = None,
    ):
        """
        Initialize refund created event.

        Args:
            refund_id: ID of the created refund
            sale_id: ID of the associated sale
            amount: Refund amount
            user_id: Optional ID of the user who created the refund
        """
        super().__init__()
        self.refund_id = refund_id
        self.sale_id = sale_id
        self.amount = amount
        self.user_id = user_id


class RefundProcessed(DomainEvent):
    """Event emitted when a refund is processed."""

    def __init__(
        self,
        refund_id: int,
        sale_id: int,
        amount: float,
        transaction_id: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize refund processed event.

        Args:
            refund_id: ID of the processed refund
            sale_id: ID of the associated sale
            amount: Refund amount
            transaction_id: Transaction ID from payment processor
            user_id: Optional ID of the user who processed the refund
        """
        super().__init__()
        self.refund_id = refund_id
        self.sale_id = sale_id
        self.amount = amount
        self.transaction_id = transaction_id
        self.user_id = user_id


class RefundService(BaseService[Refund]):
    """
    Service for managing customer refunds.

    Provides functionality for:
    - Creating and processing refunds
    - Updating refund statuses
    - Validating refund requests
    - Integration with sales and payment systems
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        sale_service=None,
        payment_service=None,
    ):
        """
        Initialize RefundService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository for refunds (defaults to RefundRepository)
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            sale_service: Optional sale service for sale operations
            payment_service: Optional payment service for payment processing
        """
        self.session = session
        self.repository = repository or RefundRepository(session)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.sale_service = sale_service
        self.payment_service = payment_service

    def create_refund(self, data: Dict[str, Any]) -> Refund:
        """
        Create a new refund record.

        Args:
            data: Refund data containing sale ID, amount, reason, etc.

        Returns:
            Created refund entity

        Raises:
            ValidationException: If validation fails
            SaleNotFoundException: If specified sale not found
            BusinessRuleException: If refund amount exceeds sale amount
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

                # Validate refund amount
                refund_amount = data.get("refund_amount")
                if refund_amount > sale.total_amount:
                    raise BusinessRuleException(
                        f"Refund amount ({refund_amount}) cannot exceed sale amount ({sale.total_amount})"
                    )

                # Check if sale has already been refunded
                if sale.payment_status == PaymentStatus.REFUNDED:
                    raise BusinessRuleException("Sale has already been fully refunded")

                # Validate sale status allows refunds
                if sale.status not in [
                    SaleStatus.COMPLETED.value,
                    SaleStatus.DELIVERED.value,
                    SaleStatus.SHIPPED.value,
                    SaleStatus.CANCELLED.value,
                ]:
                    raise BusinessRuleException(
                        f"Cannot refund a sale with status '{sale.status}'. "
                        f"Sale must be completed, delivered, shipped, or cancelled."
                    )

            # Set refund date if not provided
            if "refund_date" not in data:
                data["refund_date"] = datetime.now()

            # Set initial status
            if "status" not in data:
                data["status"] = "PENDING"

            # Set processor ID if authenticated
            if self.security_context and self.security_context.current_user:
                data["processed_by"] = self.security_context.current_user.id

            # Create refund
            refund = self.repository.create(data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    RefundCreated(
                        refund_id=refund.id,
                        sale_id=refund.sale_id,
                        amount=refund.refund_amount,
                        user_id=user_id,
                    )
                )

            # Invalidate sale cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Sale:{sale_id}")
                self.cache_service.invalidate(f"Sale:detail:{sale_id}")

            return refund

    def process_refund(
        self,
        refund_id: int,
        transaction_id: str,
        payment_method: str,
        notes: Optional[str] = None,
    ) -> Refund:
        """
        Process a pending refund.

        Args:
            refund_id: ID of the refund to process
            transaction_id: Transaction ID from payment processor
            payment_method: Method used for the refund
            notes: Additional notes about the refund

        Returns:
            Updated refund

        Raises:
            EntityNotFoundException: If refund not found
            BusinessRuleException: If refund is not in pending status
        """
        with self.transaction():
            # Get refund
            refund = self.get_by_id(refund_id)
            if not refund:
                raise EntityNotFoundException(f"Refund with ID {refund_id} not found")

            # Validate refund is pending
            if refund.status != "PENDING":
                raise BusinessRuleException(
                    f"Cannot process refund with status '{refund.status}'. "
                    f"Refund must be in PENDING status."
                )

            # Set processor ID if authenticated
            processor_id = None
            if self.security_context and self.security_context.current_user:
                processor_id = self.security_context.current_user.id

            # Process refund
            refund = self.repository.process_refund(
                refund_id=refund_id,
                transaction_id=transaction_id,
                payment_method=payment_method,
                processor_id=processor_id,
                notes=notes,
            )

            # Update sale status if sale service exists
            if self.sale_service:
                sale = self.sale_service.get_by_id(refund.sale_id)
                if sale:
                    # Update sale payment status
                    if refund.refund_amount >= sale.total_amount * 0.99:  # Full refund
                        self.sale_service.update_payment_status(
                            sale_id=sale.id,
                            new_status=PaymentStatus.REFUNDED,
                            amount=refund.refund_amount,
                            transaction_id=transaction_id,
                            payment_method=payment_method,
                        )
                    else:  # Partial refund
                        self.sale_service.update_payment_status(
                            sale_id=sale.id,
                            new_status=PaymentStatus.PARTIALLY_REFUNDED,
                            amount=refund.refund_amount,
                            transaction_id=transaction_id,
                            payment_method=payment_method,
                        )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    RefundProcessed(
                        refund_id=refund.id,
                        sale_id=refund.sale_id,
                        amount=refund.refund_amount,
                        transaction_id=transaction_id,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Refund:{refund_id}")
                self.cache_service.invalidate(f"Sale:{refund.sale_id}")
                self.cache_service.invalidate(f"Sale:detail:{refund.sale_id}")

            return refund

    def get_refunds_by_sale(self, sale_id: int) -> List[Refund]:
        """
        Get all refunds for a specific sale.

        Args:
            sale_id: ID of the sale

        Returns:
            List of refunds for the sale
        """
        return self.repository.get_refunds_by_sale(sale_id)

    def get_pending_refunds(self) -> List[Refund]:
        """
        Get all pending refunds.

        Returns:
            List of pending refunds
        """
        return self.repository.get_pending_refunds()

    def cancel_refund(self, refund_id: int, reason: str) -> Refund:
        """
        Cancel a pending refund.

        Args:
            refund_id: ID of the refund to cancel
            reason: Reason for cancellation

        Returns:
            Updated refund

        Raises:
            EntityNotFoundException: If refund not found
            BusinessRuleException: If refund is not in pending status
        """
        with self.transaction():
            # Get refund
            refund = self.get_by_id(refund_id)
            if not refund:
                raise EntityNotFoundException(f"Refund with ID {refund_id} not found")

            # Validate refund is pending
            if refund.status != "PENDING":
                raise BusinessRuleException(
                    f"Cannot cancel refund with status '{refund.status}'. "
                    f"Refund must be in PENDING status."
                )

            # Update refund status and add cancellation reason to notes
            update_data = {
                "status": "CANCELLED",
                "notes": f"CANCELLED: {reason}"
                + (f"\n\nOriginal notes: {refund.notes}" if refund.notes else ""),
            }
            updated_refund = self.repository.update(refund_id, update_data)

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Refund:{refund_id}")
                self.cache_service.invalidate(f"Sale:{refund.sale_id}")
                self.cache_service.invalidate(f"Sale:detail:{refund.sale_id}")

            return updated_refund