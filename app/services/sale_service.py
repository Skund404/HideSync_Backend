# File: services/sale_service.py

from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session

from app.core.events import DomainEvent
from app.core.exceptions import (
    HideSyncException,
    ValidationException,
    EntityNotFoundException,
    BusinessRuleException,
    ConcurrentModificationException,
)
from app.core.validation import validate_input, validate_entity
from app.db.models.enums import SaleStatus, PaymentStatus, FulfillmentStatus
from app.db.models.sales import Sale, SaleItem
from app.repositories.sale_repository import SaleRepository
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class SaleCreated(DomainEvent):
    """Event emitted when a sale is created."""

    def __init__(
        self,
        sale_id: int,
        customer_id: Optional[int],
        total_amount: float,
        user_id: Optional[int] = None,
    ):
        """
        Initialize sale created event.

        Args:
            sale_id: ID of the created sale
            customer_id: ID of the customer who placed the order
            total_amount: Total amount of the sale
            user_id: Optional ID of the user who created the sale
        """
        super().__init__()
        self.sale_id = sale_id
        self.customer_id = customer_id
        self.total_amount = total_amount
        self.user_id = user_id


class SaleStatusChanged(DomainEvent):
    """Event emitted when a sale's status is changed."""

    def __init__(
        self,
        sale_id: int,
        previous_status: str,
        new_status: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize sale status changed event.

        Args:
            sale_id: ID of the updated sale
            previous_status: Previous status of the sale
            new_status: New status of the sale
            user_id: Optional ID of the user who updated the status
        """
        super().__init__()
        self.sale_id = sale_id
        self.previous_status = previous_status
        self.new_status = new_status
        self.user_id = user_id


class PaymentStatusChanged(DomainEvent):
    """Event emitted when a sale's payment status is changed."""

    def __init__(
        self,
        sale_id: int,
        previous_status: str,
        new_status: str,
        amount: Optional[float] = None,
        user_id: Optional[int] = None,
    ):
        """
        Initialize payment status changed event.

        Args:
            sale_id: ID of the updated sale
            previous_status: Previous payment status
            new_status: New payment status
            amount: Amount paid/refunded in this transaction
            user_id: Optional ID of the user who updated the payment status
        """
        super().__init__()
        self.sale_id = sale_id
        self.previous_status = previous_status
        self.new_status = new_status
        self.amount = amount
        self.user_id = user_id


class SaleItemAdded(DomainEvent):
    """Event emitted when an item is added to a sale."""

    def __init__(
        self,
        sale_id: int,
        item_id: int,
        quantity: int,
        price: float,
        user_id: Optional[int] = None,
    ):
        """
        Initialize sale item added event.

        Args:
            sale_id: ID of the sale
            item_id: ID of the added item
            quantity: Quantity of the item
            price: Price of the item
            user_id: Optional ID of the user who added the item
        """
        super().__init__()
        self.sale_id = sale_id
        self.item_id = item_id
        self.quantity = quantity
        self.price = price
        self.user_id = user_id


class FulfillmentStatusChanged(DomainEvent):
    """Event emitted when a sale's fulfillment status is changed."""

    def __init__(
        self,
        sale_id: int,
        previous_status: str,
        new_status: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize fulfillment status changed event.

        Args:
            sale_id: ID of the updated sale
            previous_status: Previous fulfillment status
            new_status: New fulfillment status
            user_id: Optional ID of the user who updated the fulfillment status
        """
        super().__init__()
        self.sale_id = sale_id
        self.previous_status = previous_status
        self.new_status = new_status
        self.user_id = user_id


# Validation functions
validate_sale = validate_entity(Sale)
validate_sale_item = validate_entity(SaleItem)


class SaleService(BaseService[Sale]):
    """
    Service for managing sales and orders in the HideSync system.

    Provides functionality for:
    - Order creation and management
    - Item management
    - Payment status tracking
    - Order fulfillment
    - Sales reporting and analytics
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        inventory_service=None,
        project_service=None,
        customer_service=None,
        shipment_service=None,
    ):
        """
        Initialize SaleService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository for sales (defaults to SaleRepository)
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            inventory_service: Optional inventory service for inventory operations
            project_service: Optional project service for project creation
            customer_service: Optional customer service for customer operations
            shipment_service: Optional shipment service for fulfillment operations
        """
        self.session = session
        self.repository = repository or SaleRepository(session)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.inventory_service = inventory_service
        self.project_service = project_service
        self.customer_service = customer_service
        self.shipment_service = shipment_service

    @validate_input(validate_sale)
    def create_sale(self, data: Dict[str, Any]) -> Sale:
        """
        Create a new sale.

        Args:
            data: Sale data containing customer, items, and other details

        Returns:
            Created sale entity

        Raises:
            ValidationException: If validation fails
            CustomerNotFoundException: If specified customer not found
        """
        # Process items if present in the data
        items_data = data.pop("items", []) if "items" in data else []

        with self.transaction():
            # Set initial status if not provided
            if "status" not in data:
                data["status"] = SaleStatus.DRAFT.value

            # Set initial payment status if not provided
            if "payment_status" not in data:
                data["payment_status"] = PaymentStatus.PENDING.value

            # Set initial fulfillment status if not provided
            if "fulfillment_status" not in data:
                data["fulfillment_status"] = FulfillmentStatus.PENDING.value

            # Set created date
            data["created_at"] = datetime.now()

            # Check if customer exists if customer_id is provided
            customer_id = data.get("customer_id")
            if customer_id and self.customer_service:
                customer = self.customer_service.get_by_id(customer_id)
                if not customer:
                    from app.core.exceptions import CustomerNotFoundException

                    raise CustomerNotFoundException(customer_id)

            # Calculate initial totals
            self._calculate_totals(data, items_data)

            # Create sale
            sale = self.repository.create(data)

            # Add items if provided
            for item_data in items_data:
                item_data["sale_id"] = sale.id
                self.add_sale_item(sale.id, item_data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    SaleCreated(
                        sale_id=sale.id,
                        customer_id=sale.customer_id,
                        total_amount=sale.total_amount,
                        user_id=user_id,
                    )
                )

            # Create associated project if needed
            if (
                "create_project" in data
                and data["create_project"]
                and self.project_service
            ):
                self._create_project_for_sale(sale)

            return sale

    def get_sales(self, skip: int = 0, limit: int = 100, search_params: dict = None):
        # TODO: Implement actual logic to query sales
        print(f"Placeholder: Fetching sales with skip={skip}, limit={limit}, params={search_params}")
        return {"items": [], "total": 0}

    # ... other methods ...

    def _calculate_totals(
        self, sale_data: Dict[str, Any], items_data: List[Dict[str, Any]]
    ) -> None:
        """
        Calculate totals for a sale based on items and other costs.

        Args:
            sale_data: Sale data to update with calculated totals
            items_data: List of item data with quantities and prices
        """
        subtotal = 0.0

        # Calculate subtotal from items
        for item in items_data:
            quantity = item.get("quantity", 0)
            price = item.get("price", 0.0)
            subtotal += quantity * price

        # Update sale data with calculated values
        sale_data["subtotal"] = subtotal

        # Calculate taxes if not directly provided
        if "taxes" not in sale_data:
            # Default tax calculation logic
            # In a real system, this would be more complex based on tax rules
            sale_data["taxes"] = round(
                subtotal * 0.0, 2
            )  # Assuming 0% tax rate by default

        # Calculate shipping if not provided
        if "shipping" not in sale_data:
            sale_data["shipping"] = 0.0

        # Calculate platform fees if not provided
        if "platform_fees" not in sale_data:
            sale_data["platform_fees"] = 0.0

        # Calculate total amount
        total_amount = (
            subtotal + sale_data.get("taxes", 0.0) + sale_data.get("shipping", 0.0)
        )
        sale_data["total_amount"] = round(total_amount, 2)

        # Calculate net revenue (total minus platform fees)
        net_revenue = total_amount - sale_data.get("platform_fees", 0.0)
        sale_data["net_revenue"] = round(net_revenue, 2)

        # Set deposit and balance due based on payment model
        # For this example, using a 50% deposit model
        if "deposit_amount" not in sale_data:
            sale_data["deposit_amount"] = round(total_amount * 0.5, 2)

        sale_data["balance_due"] = round(
            total_amount - sale_data.get("deposit_amount", 0.0), 2
        )

    @validate_input(validate_sale_item)
    def add_sale_item(self, sale_id: int, item_data: Dict[str, Any]) -> SaleItem:
        """
        Add an item to a sale.

        Args:
            sale_id: ID of the sale
            item_data: Item data with product information

        Returns:
            Created sale item

        Raises:
            SaleNotFoundException: If sale not found
            ValidationException: If validation fails
            ProductNotFoundException: If specified product not found
        """
        with self.transaction():
            # Check if sale exists
            sale = self.get_by_id(sale_id)
            if not sale:
                from app.core.exceptions import SaleNotFoundException

                raise SaleNotFoundException(sale_id)

            # Ensure sale_id is set in item data
            item_data["sale_id"] = sale_id

            # Check if product exists if product_id is provided
            product_id = item_data.get("product_id")
            if product_id and hasattr(self, "product_service") and self.product_service:
                product = self.product_service.get_by_id(product_id)
                if not product:
                    from app.core.exceptions import ProductNotFoundException

                    raise ProductNotFoundException(product_id)

            # Create sale item
            sale_item = self.repository.add_item(item_data)

            # Update sale totals
            self._update_sale_totals(sale_id)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    SaleItemAdded(
                        sale_id=sale_id,
                        item_id=sale_item.id,
                        quantity=sale_item.quantity,
                        price=sale_item.price,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Sale:{sale_id}")

            return sale_item

    def update_sale_status(
        self,
        sale_id: int,
        new_status: Union[SaleStatus, str],
        comments: Optional[str] = None,
    ) -> Sale:
        """
        Update the status of a sale.

        Args:
            sale_id: ID of the sale
            new_status: New status for the sale
            comments: Optional comments about the status change

        Returns:
            Updated sale

        Raises:
            SaleNotFoundException: If sale not found
            InvalidStatusTransitionException: If status transition is not allowed
        """
        with self.transaction():
            # Check if sale exists
            sale = self.get_by_id(sale_id)
            if not sale:
                from app.core.exceptions import SaleNotFoundException

                raise SaleNotFoundException(sale_id)

            # Convert string status to enum if needed
            if isinstance(new_status, str):
                try:
                    new_status = SaleStatus(new_status)
                except ValueError:
                    raise ValidationException(
                        f"Invalid sale status: {new_status}",
                        {
                            "status": [
                                f"Must be one of: {', '.join([s.value for s in SaleStatus])}"
                            ]
                        },
                    )

            # Store previous status for event
            previous_status = sale.status

            # Validate status transition
            self._validate_status_transition(previous_status, new_status.value)

            # Prepare update data
            update_data = {"status": new_status.value}

            # Update completed date if transitioning to completed
            if new_status == SaleStatus.COMPLETED:
                update_data["completed_date"] = datetime.now()

            # Update sale
            updated_sale = self.repository.update(sale_id, update_data)

            # Record status change in history
            self._record_status_change(
                sale_id=sale_id,
                previous_status=previous_status,
                new_status=new_status.value,
                comments=comments,
            )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    SaleStatusChanged(
                        sale_id=sale_id,
                        previous_status=previous_status,
                        new_status=new_status.value,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Sale:{sale_id}")

            return updated_sale

    def update_payment_status(
        self,
        sale_id: int,
        new_status: Union[PaymentStatus, str],
        amount: Optional[float] = None,
        transaction_id: Optional[str] = None,
        payment_method: Optional[str] = None,
    ) -> Sale:
        """
        Update the payment status of a sale.

        Args:
            sale_id: ID of the sale
            new_status: New payment status
            amount: Optional amount paid/refunded in this transaction
            transaction_id: Optional external transaction ID
            payment_method: Optional payment method used

        Returns:
            Updated sale

        Raises:
            SaleNotFoundException: If sale not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if sale exists
            sale = self.get_by_id(sale_id)
            if not sale:
                from app.core.exceptions import SaleNotFoundException

                raise SaleNotFoundException(sale_id)

            # Convert string status to enum if needed
            if isinstance(new_status, str):
                try:
                    new_status = PaymentStatus(new_status)
                except ValueError:
                    raise ValidationException(
                        f"Invalid payment status: {new_status}",
                        {
                            "payment_status": [
                                f"Must be one of: {', '.join([s.value for s in PaymentStatus])}"
                            ]
                        },
                    )

            # Store previous status for event
            previous_status = sale.payment_status

            # Prepare update data
            update_data = {"payment_status": new_status.value}

            # Update deposit paid and record transaction
            if new_status == PaymentStatus.DEPOSIT_PAID:
                # Record that the deposit has been paid
                self._record_payment_transaction(
                    sale_id=sale_id,
                    amount=amount or sale.deposit_amount,
                    transaction_id=transaction_id,
                    payment_method=payment_method,
                    payment_type="deposit",
                )

            # Update fully paid and record transaction
            elif new_status == PaymentStatus.PAID:
                # If coming directly from PENDING, record full payment
                if previous_status == PaymentStatus.PENDING.value:
                    self._record_payment_transaction(
                        sale_id=sale_id,
                        amount=amount or sale.total_amount,
                        transaction_id=transaction_id,
                        payment_method=payment_method,
                        payment_type="full",
                    )
                # If coming from DEPOSIT_PAID, record final payment
                elif previous_status == PaymentStatus.DEPOSIT_PAID.value:
                    self._record_payment_transaction(
                        sale_id=sale_id,
                        amount=amount or sale.balance_due,
                        transaction_id=transaction_id,
                        payment_method=payment_method,
                        payment_type="balance",
                    )

                # Update balance due to zero
                update_data["balance_due"] = 0.0

            # Handle refund status
            elif new_status == PaymentStatus.REFUNDED:
                self._record_payment_transaction(
                    sale_id=sale_id,
                    amount=-(amount or sale.total_amount),  # Negative amount for refund
                    transaction_id=transaction_id,
                    payment_method=payment_method,
                    payment_type="refund",
                )

            # Update sale
            updated_sale = self.repository.update(sale_id, update_data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    PaymentStatusChanged(
                        sale_id=sale_id,
                        previous_status=previous_status,
                        new_status=new_status.value,
                        amount=amount,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Sale:{sale_id}")

            return updated_sale

    def update_fulfillment_status(
        self,
        sale_id: int,
        new_status: Union[FulfillmentStatus, str],
        tracking_number: Optional[str] = None,
        shipping_provider: Optional[str] = None,
    ) -> Sale:
        """
        Update the fulfillment status of a sale.

        Args:
            sale_id: ID of the sale
            new_status: New fulfillment status
            tracking_number: Optional tracking number for shipment
            shipping_provider: Optional shipping provider

        Returns:
            Updated sale

        Raises:
            SaleNotFoundException: If sale not found
            ValidationException: If validation fails
        """
        with self.transaction():
            # Check if sale exists
            sale = self.get_by_id(sale_id)
            if not sale:
                from app.core.exceptions import SaleNotFoundException

                raise SaleNotFoundException(sale_id)

            # Convert string status to enum if needed
            if isinstance(new_status, str):
                try:
                    new_status = FulfillmentStatus(new_status)
                except ValueError:
                    raise ValidationException(
                        f"Invalid fulfillment status: {new_status}",
                        {
                            "fulfillment_status": [
                                f"Must be one of: {', '.join([s.value for s in FulfillmentStatus])}"
                            ]
                        },
                    )

            # Store previous status for event
            previous_status = sale.fulfillment_status

            # Prepare update data
            update_data = {"fulfillment_status": new_status.value}

            # Add shipping information if provided
            if tracking_number:
                update_data["tracking_number"] = tracking_number

            if shipping_provider:
                update_data["shipping_provider"] = shipping_provider

            # Create shipment record if transitioning to shipped
            if new_status == FulfillmentStatus.SHIPPED and self.shipment_service:
                # Create shipment with the shipping provider and tracking number
                shipment_data = {
                    "sale_id": sale_id,
                    "tracking_number": tracking_number,
                    "shipping_method": shipping_provider,
                    "ship_date": datetime.now(),
                    "status": "SHIPPED",
                }
                shipment = self.shipment_service.create_shipment(shipment_data)

                # Update sale with shipment ID if needed
                update_data["shipment_id"] = shipment.id

            # Allocate inventory if transitioning to IN_PRODUCTION
            if (
                new_status == FulfillmentStatus.IN_PRODUCTION
                and previous_status != FulfillmentStatus.IN_PRODUCTION.value
                and self.inventory_service
            ):
                self._allocate_inventory_for_sale(sale)

            # Update sale
            updated_sale = self.repository.update(sale_id, update_data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    FulfillmentStatusChanged(
                        sale_id=sale_id,
                        previous_status=previous_status,
                        new_status=new_status.value,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Sale:{sale_id}")

            return updated_sale

    def fulfill_sale(
        self,
        sale_id: int,
        tracking_number: Optional[str] = None,
        shipping_provider: Optional[str] = None,
    ) -> Sale:
        """
        Mark a sale as fulfilled, handling inventory and shipping.

        Args:
            sale_id: ID of the sale
            tracking_number: Optional tracking number for shipment
            shipping_provider: Optional shipping provider

        Returns:
            Updated sale

        Raises:
            SaleNotFoundException: If sale not found
            ValidationException: If validation fails
            InventoryException: If inventory allocation fails
        """
        # This is a convenience method that combines several operations
        with self.transaction():
            # Update fulfillment status to shipped
            sale = self.update_fulfillment_status(
                sale_id=sale_id,
                new_status=FulfillmentStatus.SHIPPED,
                tracking_number=tracking_number,
                shipping_provider=shipping_provider,
            )

            # If payment is complete, update sale status to completed
            if sale.payment_status == PaymentStatus.PAID.value:
                sale = self.update_sale_status(
                    sale_id=sale_id, new_status=SaleStatus.COMPLETED
                )

            return sale

    def get_sale_with_items(self, sale_id: int) -> Dict[str, Any]:
        """
        Get a sale with its items and details.

        Args:
            sale_id: ID of the sale

        Returns:
            Sale with items and related data

        Raises:
            SaleNotFoundException: If sale not found
        """
        # Check cache first
        if self.cache_service:
            cache_key = f"Sale:detail:{sale_id}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        # Get sale
        sale = self.get_by_id(sale_id)
        if not sale:
            from app.core.exceptions import SaleNotFoundException

            raise SaleNotFoundException(sale_id)

        # Convert to dict and add related data
        result = sale.to_dict()

        # Add items
        result["items"] = [
            item.to_dict() for item in self.repository.get_sale_items(sale_id)
        ]

        # Add customer details if available and customer service is provided
        if sale.customer_id and self.customer_service:
            customer = self.customer_service.get_by_id(sale.customer_id)
            if customer:
                result["customer"] = customer.to_dict()

        # Add payment history
        result["payment_history"] = self._get_payment_history(sale_id)

        # Add status history
        result["status_history"] = self._get_status_history(sale_id)

        # Store in cache if cache service exists
        if self.cache_service:
            self.cache_service.set(cache_key, result, ttl=3600)  # 1 hour TTL

        return result

    def get_sales_by_customer(self, customer_id: int) -> List[Sale]:
        """
        Get all sales for a specific customer.

        Args:
            customer_id: ID of the customer

        Returns:
            List of customer's sales
        """
        return self.repository.list(customer_id=customer_id)

    def get_sales_by_status(self, status: Union[SaleStatus, str]) -> List[Sale]:
        """
        Get all sales with a specific status.

        Args:
            status: Status to filter by

        Returns:
            List of sales with the specified status
        """
        # Convert string status to enum value if needed
        if isinstance(status, SaleStatus):
            status = status.value

        return self.repository.list(status=status)

    def get_sales_by_payment_status(
        self, payment_status: Union[PaymentStatus, str]
    ) -> List[Sale]:
        """
        Get all sales with a specific payment status.

        Args:
            payment_status: Payment status to filter by

        Returns:
            List of sales with the specified payment status
        """
        # Convert string status to enum value if needed
        if isinstance(payment_status, PaymentStatus):
            payment_status = payment_status.value

        return self.repository.list(payment_status=payment_status)

    def get_sales_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> List[Sale]:
        """
        Get all sales within a specific date range.

        Args:
            start_date: Start date for range
            end_date: End date for range

        Returns:
            List of sales within the date range
        """
        return self.repository.list(created_at_from=start_date, created_at_to=end_date)

    def get_sales_metrics(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get sales metrics for a date range.

        Args:
            start_date: Optional start date (defaults to 30 days ago)
            end_date: Optional end date (defaults to today)

        Returns:
            Dictionary with sales metrics
        """
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.now()

        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Get sales for the period
        sales = self.get_sales_by_date_range(start_date, end_date)

        # Calculate metrics
        total_revenue = sum(
            sale.total_amount
            for sale in sales
            if sale.status != SaleStatus.CANCELLED.value
        )
        net_revenue = sum(
            sale.net_revenue
            for sale in sales
            if sale.status != SaleStatus.CANCELLED.value
        )
        total_orders = len(
            [sale for sale in sales if sale.status != SaleStatus.CANCELLED.value]
        )
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

        # Count sales by status
        status_counts = {}
        for status in SaleStatus:
            status_counts[status.value] = len(
                [s for s in sales if s.status == status.value]
            )

        # Count sales by payment status
        payment_status_counts = {}
        for status in PaymentStatus:
            payment_status_counts[status.value] = len(
                [s for s in sales if s.payment_status == status.value]
            )

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": (end_date - start_date).days,
            },
            "metrics": {
                "total_revenue": round(total_revenue, 2),
                "net_revenue": round(net_revenue, 2),
                "total_orders": total_orders,
                "avg_order_value": round(avg_order_value, 2),
                "daily_avg_revenue": (
                    round(total_revenue / (end_date - start_date).days, 2)
                    if (end_date - start_date).days > 0
                    else 0
                ),
            },
            "status_counts": status_counts,
            "payment_status_counts": payment_status_counts,
        }

    def _update_sale_totals(self, sale_id: int) -> None:
        """
        Update the total amounts for a sale based on its current items.

        Args:
            sale_id: ID of the sale to update
        """
        # Get sale
        sale = self.get_by_id(sale_id)
        if not sale:
            return

        # Get items
        items = self.repository.get_sale_items(sale_id)

        # Calculate subtotal
        subtotal = sum(item.quantity * item.price for item in items)

        # Prepare update data
        update_data = {
            "subtotal": subtotal,
            "total_amount": subtotal + sale.taxes + sale.shipping,
            "net_revenue": subtotal + sale.taxes + sale.shipping - sale.platform_fees,
            # Update deposit amount based on payment model (e.g., 50% deposit)
            "deposit_amount": (subtotal + sale.taxes + sale.shipping) * 0.5,
        }

        # Update balance due based on payment status
        if sale.payment_status == PaymentStatus.PENDING.value:
            update_data["balance_due"] = update_data["total_amount"]
        elif sale.payment_status == PaymentStatus.DEPOSIT_PAID.value:
            update_data["balance_due"] = (
                update_data["total_amount"] - update_data["deposit_amount"]
            )
        elif sale.payment_status == PaymentStatus.PAID.value:
            update_data["balance_due"] = 0.0

        # Update sale
        self.repository.update(sale_id, update_data)

    def _validate_status_transition(self, current_status: str, new_status: str) -> None:
        """
        Validate that a status transition is allowed based on business rules.

        Args:
            current_status: Current status
            new_status: Proposed new status

        Raises:
            InvalidStatusTransitionException: If transition is not allowed
        """
        # Define allowed transitions
        allowed_transitions = {
            SaleStatus.DRAFT.value: [
                SaleStatus.INQUIRY.value,
                SaleStatus.QUOTE_REQUEST.value,
                SaleStatus.CONFIRMED.value,
                SaleStatus.CANCELLED.value,
            ],
            SaleStatus.INQUIRY.value: [
                SaleStatus.QUOTE_REQUEST.value,
                SaleStatus.DESIGN_CONSULTATION.value,
                SaleStatus.CONFIRMED.value,
                SaleStatus.CANCELLED.value,
            ],
            SaleStatus.QUOTE_REQUEST.value: [
                SaleStatus.DESIGN_CONSULTATION.value,
                SaleStatus.DESIGN_PROPOSAL.value,
                SaleStatus.CONFIRMED.value,
                SaleStatus.CANCELLED.value,
            ],
            SaleStatus.DESIGN_CONSULTATION.value: [
                SaleStatus.DESIGN_PROPOSAL.value,
                SaleStatus.DESIGN_APPROVAL.value,
                SaleStatus.CONFIRMED.value,
                SaleStatus.CANCELLED.value,
            ],
            SaleStatus.DESIGN_PROPOSAL.value: [
                SaleStatus.DESIGN_APPROVAL.value,
                SaleStatus.DESIGN_CONSULTATION.value,
                SaleStatus.CONFIRMED.value,
                SaleStatus.CANCELLED.value,
            ],
            SaleStatus.DESIGN_APPROVAL.value: [
                SaleStatus.CONFIRMED.value,
                SaleStatus.CANCELLED.value,
            ],
            SaleStatus.CONFIRMED.value: [
                SaleStatus.DEPOSIT_RECEIVED.value,
                SaleStatus.IN_PRODUCTION.value,
                SaleStatus.ON_HOLD.value,
                SaleStatus.CANCELLED.value,
            ],
            SaleStatus.DEPOSIT_RECEIVED.value: [
                SaleStatus.IN_PRODUCTION.value,
                SaleStatus.ON_HOLD.value,
                SaleStatus.CANCELLED.value,
            ],
            SaleStatus.IN_PRODUCTION.value: [
                SaleStatus.READY_FOR_PICKUP.value,
                SaleStatus.FINAL_PAYMENT_PENDING.value,
                SaleStatus.ON_HOLD.value,
                SaleStatus.CANCELLED.value,
            ],
            SaleStatus.READY_FOR_PICKUP.value: [
                SaleStatus.FINAL_PAYMENT_PENDING.value,
                SaleStatus.FINAL_PAYMENT_RECEIVED.value,
                SaleStatus.SHIPPED.value,
                SaleStatus.DELIVERED.value,
                SaleStatus.COMPLETED.value,
                SaleStatus.ON_HOLD.value,
            ],
            SaleStatus.FINAL_PAYMENT_PENDING.value: [
                SaleStatus.FINAL_PAYMENT_RECEIVED.value,
                SaleStatus.ON_HOLD.value,
                SaleStatus.CANCELLED.value,
            ],
            SaleStatus.FINAL_PAYMENT_RECEIVED.value: [
                SaleStatus.SHIPPED.value,
                SaleStatus.DELIVERED.value,
                SaleStatus.COMPLETED.value,
            ],
            SaleStatus.SHIPPED.value: [
                SaleStatus.DELIVERED.value,
                SaleStatus.COMPLETED.value,
            ],
            SaleStatus.DELIVERED.value: [
                SaleStatus.COMPLETED.value,
                SaleStatus.FEEDBACK_REQUESTED.value,
            ],
            SaleStatus.COMPLETED.value: [
                SaleStatus.FEEDBACK_REQUESTED.value,
                SaleStatus.REVIEW_RECEIVED.value,
            ],
            SaleStatus.FEEDBACK_REQUESTED.value: [
                SaleStatus.REVIEW_RECEIVED.value,
                SaleStatus.REVISION_REQUESTED.value,
            ],
            SaleStatus.REVIEW_RECEIVED.value: [SaleStatus.REVISION_REQUESTED.value],
            SaleStatus.REVISION_REQUESTED.value: [SaleStatus.IN_PRODUCTION.value],
            SaleStatus.ON_HOLD.value: [
                SaleStatus.DRAFT.value,
                SaleStatus.INQUIRY.value,
                SaleStatus.CONFIRMED.value,
                SaleStatus.DEPOSIT_RECEIVED.value,
                SaleStatus.IN_PRODUCTION.value,
                SaleStatus.CANCELLED.value,
            ],
            SaleStatus.CANCELLED.value: [SaleStatus.REFUNDED.value],
            SaleStatus.REFUNDED.value: [],
        }

        # Allow transition to same status
        if current_status == new_status:
            return

        # Check if transition is allowed
        if new_status not in allowed_transitions.get(current_status, []):
            from app.core.exceptions import InvalidStatusTransitionException

            raise InvalidStatusTransitionException(
                f"Cannot transition from {current_status} to {new_status}",
                allowed_transitions=allowed_transitions.get(current_status, []),
            )

    def _record_status_change(
        self,
        sale_id: int,
        previous_status: str,
        new_status: str,
        comments: Optional[str] = None,
    ) -> None:
        """
        Record a status change in the sale history.

        Args:
            sale_id: Sale ID
            previous_status: Previous status
            new_status: New status
            comments: Optional comments about the change
        """
        # This method would use a SaleHistoryRepository to record the change
        # For now, just logging the change
        user_id = (
            self.security_context.current_user.id if self.security_context else None
        )
        logger.info(
            f"Sale {sale_id} status changed from {previous_status} to {new_status} by user {user_id}",
            extra={
                "sale_id": sale_id,
                "previous_status": previous_status,
                "new_status": new_status,
                "user_id": user_id,
                "comments": comments,
            },
        )

    def _record_payment_transaction(
        self,
        sale_id: int,
        amount: float,
        transaction_id: Optional[str] = None,
        payment_method: Optional[str] = None,
        payment_type: str = "payment",
    ) -> None:
        """
        Record a payment transaction for a sale.

        Args:
            sale_id: Sale ID
            amount: Amount paid (positive) or refunded (negative)
            transaction_id: Optional external transaction ID
            payment_method: Optional payment method used
            payment_type: Type of payment (deposit, balance, full, refund)
        """
        # This method would use a PaymentTransactionRepository to record the transaction
        # For now, just logging the transaction
        user_id = (
            self.security_context.current_user.id if self.security_context else None
        )
        logger.info(
            f"Sale {sale_id} payment transaction: {payment_type} of {amount} via {payment_method} by user {user_id}",
            extra={
                "sale_id": sale_id,
                "amount": amount,
                "transaction_id": transaction_id,
                "payment_method": payment_method,
                "payment_type": payment_type,
                "user_id": user_id,
            },
        )

    def _allocate_inventory_for_sale(self, sale: Sale) -> None:
        """
        Allocate inventory for items in a sale.

        Args:
            sale: Sale entity

        Raises:
            InventoryException: If inventory allocation fails
        """
        if not self.inventory_service:
            return

        # This method would use the inventory service to allocate materials
        # For a custom product, this might involve reserving materials for a project
        logger.info(f"Allocating inventory for sale {sale.id}")

        # In a real implementation, this would reserve inventory
        # based on the bill of materials for each item in the sale

    def _create_project_for_sale(self, sale: Sale) -> None:
        """
        Create a project associated with a sale.

        Args:
            sale: Sale entity
        """
        if not self.project_service:
            return

        # This method would use the project service to create a project
        # linked to this sale, potentially based on a template
        logger.info(f"Creating project for sale {sale.id}")

        # In a real implementation, this would create a project
        # with appropriate details from the sale

    def _get_payment_history(self, sale_id: int) -> List[Dict[str, Any]]:
        """
        Get payment transaction history for a sale.

        Args:
            sale_id: Sale ID

        Returns:
            List of payment transactions
        """
        # This method would use a PaymentTransactionRepository to get transactions
        # For this example, returning a placeholder
        return []

    def _get_status_history(self, sale_id: int) -> List[Dict[str, Any]]:
        """
        Get status change history for a sale.

        Args:
            sale_id: Sale ID

        Returns:
            List of status changes
        """
        # This method would use a SaleHistoryRepository to get status changes
        # For this example, returning a placeholder
        return []
