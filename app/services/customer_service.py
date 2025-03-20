# File: app/services/customer_service.py

from typing import List, Optional, Dict, Any, Tuple, Union
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.services.base_service import BaseService
from app.db.models.customer import Customer
from app.db.models.communication import CustomerCommunication
from app.db.models.enums import (
    CustomerStatus,
    CustomerTier,
    CustomerSource,
    CommunicationType,
)
from app.repositories.customer_repository import CustomerRepository
from app.repositories.communication_repository import CustomerCommunicationRepository
from app.core.exceptions import (
    CustomerNotFoundException,
    ValidationException,
    SecurityException,
)
from app.core.events import DomainEvent
from app.core.validation import (
    validate_input,
    validate_entity,
    validate_email,
    validate_phone,
)


# Domain events
class CustomerCreated(DomainEvent):
    """Event emitted when a customer is created."""

    def __init__(
        self, customer_id: int, customer_name: str, user_id: Optional[int] = None
    ):
        """
        Initialize customer created event.

        Args:
            customer_id: ID of the created customer
            customer_name: Name of the created customer
            user_id: Optional ID of the user who created the customer
        """
        super().__init__()
        self.customer_id = customer_id
        self.customer_name = customer_name
        self.user_id = user_id


class CustomerUpdated(DomainEvent):
    """Event emitted when a customer is updated."""

    def __init__(
        self, customer_id: int, changes: Dict[str, Any], user_id: Optional[int] = None
    ):
        """
        Initialize customer updated event.

        Args:
            customer_id: ID of the updated customer
            changes: Dictionary of changed fields with old and new values
            user_id: Optional ID of the user who updated the customer
        """
        super().__init__()
        self.customer_id = customer_id
        self.changes = changes
        self.user_id = user_id


class CustomerTierChanged(DomainEvent):
    """Event emitted when a customer's tier changes."""

    def __init__(
        self,
        customer_id: int,
        previous_tier: str,
        new_tier: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize customer tier changed event.

        Args:
            customer_id: ID of the customer
            previous_tier: Previous tier
            new_tier: New tier
            user_id: Optional ID of the user who changed the tier
        """
        super().__init__()
        self.customer_id = customer_id
        self.previous_tier = previous_tier
        self.new_tier = new_tier
        self.user_id = user_id


class CustomerCommunicationRecorded(DomainEvent):
    """Event emitted when customer communication is recorded."""

    def __init__(
        self,
        communication_id: int,
        customer_id: int,
        communication_type: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize customer communication recorded event.

        Args:
            communication_id: ID of the recorded communication
            customer_id: ID of the customer
            communication_type: Type of communication
            user_id: Optional ID of the user who recorded the communication
        """
        super().__init__()
        self.communication_id = communication_id
        self.customer_id = customer_id
        self.communication_type = communication_type
        self.user_id = user_id


# Validation functions
validate_customer = validate_entity(Customer)
validate_customer_communication = validate_entity(CustomerCommunication)


class CustomerService(BaseService[Customer]):
    """
    Service for managing customers in the HideSync system.

    Provides functionality for:
    - Customer management
    - Communication history
    - Customer segmentation and analysis
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        key_service=None,
        communication_repository=None,
    ):
        """
        Initialize CustomerService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository override
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            key_service: Optional key service for encryption/decryption
            communication_repository: Optional communication repository
        """
        self.session = session
        self.repository = repository or CustomerRepository(session, key_service)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.key_service = key_service
        self.communication_repository = (
            communication_repository or CustomerCommunicationRepository(session)
        )

    @validate_input(validate_customer)
    def create_customer(self, data: Dict[str, Any]) -> Customer:
        """
        Create a new customer.

        Args:
            data: Customer data with required fields

        Returns:
            Created customer entity

        Raises:
            ValidationException: If data validation fails
        """
        # Validate email format if provided
        if "email" in data and data["email"]:
            if not validate_email(data["email"]):
                raise ValidationException(
                    "Invalid email format", {"email": ["Invalid email format"]}
                )

        # Validate phone format if provided
        if "phone" in data and data["phone"]:
            if not validate_phone(data["phone"]):
                raise ValidationException(
                    "Invalid phone format", {"phone": ["Invalid phone format"]}
                )

        # Set default status if not provided
        if "status" not in data:
            data["status"] = CustomerStatus.NEW.value

        # Set default tier if not provided
        if "tier" not in data:
            data["tier"] = CustomerTier.STANDARD.value

        with self.transaction():
            # Check for duplicate email
            if "email" in data and data["email"]:
                existing = self.repository.find_by_email(data["email"])
                if existing:
                    raise ValidationException(
                        "Customer with this email already exists",
                        {"email": ["Customer with this email already exists"]},
                    )

            # Create customer
            customer = self.repository.create(data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    CustomerCreated(
                        customer_id=customer.id,
                        customer_name=customer.name,
                        user_id=user_id,
                    )
                )

            return customer

    def update_customer(self, customer_id: int, data: Dict[str, Any]) -> Customer:
        """
        Update an existing customer.

        Args:
            customer_id: Customer ID
            data: Updated customer data

        Returns:
            Updated customer entity

        Raises:
            CustomerNotFoundException: If customer not found
            ValidationException: If data validation fails
        """
        # Validate email format if provided
        if "email" in data and data["email"]:
            if not validate_email(data["email"]):
                raise ValidationException(
                    "Invalid email format", {"email": ["Invalid email format"]}
                )

        # Validate phone format if provided
        if "phone" in data and data["phone"]:
            if not validate_phone(data["phone"]):
                raise ValidationException(
                    "Invalid phone format", {"phone": ["Invalid phone format"]}
                )

        with self.transaction():
            # Check if customer exists
            original_customer = self.repository.get_by_id(customer_id)
            if not original_customer:
                raise CustomerNotFoundException(customer_id)

            # Check for duplicate email if email is being changed
            if (
                "email" in data
                and data["email"]
                and data["email"] != original_customer.email
            ):
                existing = self.repository.find_by_email(data["email"])
                if existing and existing.id != customer_id:
                    raise ValidationException(
                        "Customer with this email already exists",
                        {"email": ["Customer with this email already exists"]},
                    )

            # Check if tier is being changed
            tier_changed = "tier" in data and data["tier"] != original_customer.tier
            previous_tier = original_customer.tier if tier_changed else None

            # Update customer
            updated_customer = self.repository.update(customer_id, data)

            # Create changes dictionary for the event
            changes = {}
            for key, new_value in data.items():
                old_value = getattr(original_customer, key, None)
                if old_value != new_value:
                    # For sensitive fields, don't include actual values
                    if key in ["email", "phone", "address"]:
                        changes[key] = {"changed": True}
                    else:
                        changes[key] = {"old": old_value, "new": new_value}

            # Publish events if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )

                # Publish general update event
                self.event_bus.publish(
                    CustomerUpdated(
                        customer_id=customer_id, changes=changes, user_id=user_id
                    )
                )

                # Publish tier change event if applicable
                if tier_changed:
                    self.event_bus.publish(
                        CustomerTierChanged(
                            customer_id=customer_id,
                            previous_tier=previous_tier,
                            new_tier=data["tier"],
                            user_id=user_id,
                        )
                    )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Customer:{customer_id}")

            return updated_customer

    def change_customer_tier(
        self, customer_id: int, new_tier: str, reason: Optional[str] = None
    ) -> Customer:
        """
        Change a customer's tier with audit trail.

        Args:
            customer_id: Customer ID
            new_tier: New customer tier
            reason: Optional reason for tier change

        Returns:
            Updated customer entity

        Raises:
            CustomerNotFoundException: If customer not found
            ValidationException: If tier is invalid
        """
        with self.transaction():
            # Check if customer exists
            customer = self.repository.get_by_id(customer_id)
            if not customer:
                raise CustomerNotFoundException(customer_id)

            # Validate tier
            if new_tier not in [tier.value for tier in CustomerTier]:
                raise ValidationException(
                    f"Invalid customer tier: {new_tier}",
                    {"tier": [f"Invalid customer tier: {new_tier}"]},
                )

            # Store previous tier for event
            previous_tier = customer.tier

            # Skip if tier is not changing
            if previous_tier == new_tier:
                return customer

            # Update customer tier
            updated_customer = self.repository.update(customer_id, {"tier": new_tier})

            # Record tier change in audit trail
            self._record_tier_change(
                customer_id=customer_id,
                previous_tier=previous_tier,
                new_tier=new_tier,
                reason=reason,
            )

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    CustomerTierChanged(
                        customer_id=customer_id,
                        previous_tier=previous_tier,
                        new_tier=new_tier,
                        user_id=user_id,
                    )
                )

            # Invalidate cache if cache service exists
            if self.cache_service:
                self.cache_service.invalidate(f"Customer:{customer_id}")

            return updated_customer

    def record_communication(
        self, customer_id: int, communication_data: Dict[str, Any]
    ) -> CustomerCommunication:
        """
        Record a communication with a customer.

        Args:
            customer_id: Customer ID
            communication_data: Communication data

        Returns:
            Created communication entity

        Raises:
            CustomerNotFoundException: If customer not found
            ValidationException: If data validation fails
        """
        with self.transaction():
            # Check if customer exists
            customer = self.repository.get_by_id(customer_id)
            if not customer:
                raise CustomerNotFoundException(customer_id)

            # Add customer ID and timestamp if not provided
            communication_data["customer_id"] = customer_id
            if "communication_date" not in communication_data:
                communication_data["communication_date"] = datetime.now()

            # Add user ID if available
            if self.security_context and hasattr(self.security_context, "current_user"):
                communication_data["user_id"] = self.security_context.current_user.id

            # Validate communication data
            if not validate_customer_communication(communication_data):
                raise ValidationException(
                    "Invalid communication data",
                    {"communication": ["Invalid communication data"]},
                )

            # Create communication record
            communication = self.communication_repository.create(communication_data)

            # Publish event if event bus exists
            if self.event_bus:
                user_id = (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                )
                self.event_bus.publish(
                    CustomerCommunicationRecorded(
                        communication_id=communication.id,
                        customer_id=customer_id,
                        communication_type=communication.communication_type,
                        user_id=user_id,
                    )
                )

            return communication

    def get_customer_communications(
        self,
        customer_id: int,
        limit: int = 50,
        communication_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[CustomerCommunication]:
        """
        Get communication history for a customer.

        Args:
            customer_id: Customer ID
            limit: Maximum number of communications to return
            communication_type: Optional filter by communication type
            start_date: Optional filter by start date
            end_date: Optional filter by end date

        Returns:
            List of communication records

        Raises:
            CustomerNotFoundException: If customer not found
        """
        # Check if customer exists
        customer = self.repository.get_by_id(customer_id)
        if not customer:
            raise CustomerNotFoundException(customer_id)

        # Build filter parameters
        filters = {"customer_id": customer_id}

        if communication_type:
            filters["communication_type"] = communication_type

        if start_date:
            filters["date_from"] = start_date

        if end_date:
            filters["date_to"] = end_date

        # Query communications
        return self.communication_repository.list(limit=limit, **filters)

    def get_customer_with_details(self, customer_id: int) -> Dict[str, Any]:
        """
        Get customer with comprehensive details including sales, projects, and communications.

        Args:
            customer_id: Customer ID

        Returns:
            Customer with additional details

        Raises:
            CustomerNotFoundException: If customer not found
        """
        # Check if customer exists
        customer = self.repository.get_by_id(customer_id)
        if not customer:
            raise CustomerNotFoundException(customer_id)

        # Convert to dict
        result = (
            customer.to_dict()
            if hasattr(customer, "to_dict")
            else {
                "id": customer.id,
                "name": customer.name,
                "email": customer.email,
                "phone": customer.phone,
                "status": customer.status,
                "tier": customer.tier,
                "source": customer.source,
                "company_name": customer.company_name,
                "address": customer.address,
                "created_at": (
                    customer.created_at.isoformat()
                    if hasattr(customer, "created_at")
                    else None
                ),
                "updated_at": (
                    customer.updated_at.isoformat()
                    if hasattr(customer, "updated_at")
                    else None
                ),
                "notes": customer.notes,
            }
        )

        # Add recent communications
        communications = self.get_customer_communications(customer_id, limit=10)
        result["recent_communications"] = [
            comm.to_dict() if hasattr(comm, "to_dict") else comm
            for comm in communications
        ]

        # Add sales and projects if available
        result["sales"] = self.repository.get_customer_sales(customer_id, limit=10)
        result["projects"] = self.repository.get_customer_projects(
            customer_id, limit=10
        )

        # Add customer statistics
        result["statistics"] = self._calculate_customer_statistics(customer_id)

        return result

    def search_customers(self, query: str, limit: int = 50) -> List[Customer]:
        """
        Search customers by name, email, or phone.

        Args:
            query: Search query
            limit: Maximum number of results to return

        Returns:
            List of matching customers
        """
        return self.repository.search(query, limit=limit)

    def get_customers_by_tier(self, tier: str, limit: int = 100) -> List[Customer]:
        """
        Get customers by tier.

        Args:
            tier: Customer tier
            limit: Maximum number of results to return

        Returns:
            List of customers in the specified tier
        """
        return self.repository.list(tier=tier, limit=limit)

    def get_customers_by_status(self, status: str, limit: int = 100) -> List[Customer]:
        """
        Get customers by status.

        Args:
            status: Customer status
            limit: Maximum number of results to return

        Returns:
            List of customers with the specified status
        """
        return self.repository.list(status=status, limit=limit)

    def get_recently_active_customers(
        self, days: int = 30, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get recently active customers.

        Args:
            days: Number of days to look back
            limit: Maximum number of results to return

        Returns:
            List of recently active customers with activity details
        """
        start_date = datetime.now() - timedelta(days=days)
        return self.repository.get_active_customers(start_date, limit=limit)

    def _calculate_customer_statistics(self, customer_id: int) -> Dict[str, Any]:
        """
        Calculate statistics for a customer.

        Args:
            customer_id: Customer ID

        Returns:
            Dictionary of customer statistics
        """
        stats = {}

        # Get sales data
        sales_data = self.repository.get_customer_sales_data(customer_id)
        stats["total_sales"] = sales_data["total_count"]
        stats["total_revenue"] = sales_data["total_revenue"]
        stats["average_order_value"] = sales_data["average_order_value"]
        stats["first_purchase_date"] = sales_data["first_purchase_date"]
        stats["last_purchase_date"] = sales_data["last_purchase_date"]

        # Get communication statistics
        comm_stats = self.repository.get_customer_communication_stats(customer_id)
        stats["total_communications"] = comm_stats["total_count"]
        stats["last_communication_date"] = comm_stats["last_date"]

        # Get project statistics
        project_stats = self.repository.get_customer_project_stats(customer_id)
        stats["total_projects"] = project_stats["total_count"]
        stats["active_projects"] = project_stats["active_count"]
        stats["completed_projects"] = project_stats["completed_count"]

        # Calculate customer lifetime value
        if sales_data["first_purchase_date"] and sales_data["total_revenue"] > 0:
            days_as_customer = (
                datetime.now().date() - sales_data["first_purchase_date"]
            ).days
            if days_as_customer > 0:
                stats["customer_lifetime_value"] = sales_data["total_revenue"]
                stats["annual_value"] = (
                    sales_data["total_revenue"] * 365 / days_as_customer
                )
            else:
                stats["customer_lifetime_value"] = sales_data["total_revenue"]
                stats["annual_value"] = sales_data["total_revenue"]
        else:
            stats["customer_lifetime_value"] = 0
            stats["annual_value"] = 0

        return stats

    def _record_tier_change(
        self,
        customer_id: int,
        previous_tier: str,
        new_tier: str,
        reason: Optional[str] = None,
    ) -> None:
        """
        Record a tier change in the audit trail.

        Args:
            customer_id: Customer ID
            previous_tier: Previous tier
            new_tier: New tier
            reason: Optional reason for tier change
        """
        # Implementation depends on audit trail model
        audit_data = {
            "customer_id": customer_id,
            "previous_tier": previous_tier,
            "new_tier": new_tier,
            "change_date": datetime.now(),
            "user_id": (
                self.security_context.current_user.id if self.security_context else None
            ),
            "reason": reason,
        }

        # Use repository to create audit record
        self.repository.create_tier_change_audit(audit_data)

    def _create_created_event(self, entity: Customer) -> DomainEvent:
        """
        Create event for customer creation.

        Args:
            entity: Created customer entity

        Returns:
            CustomerCreated event
        """
        user_id = (
            self.security_context.current_user.id if self.security_context else None
        )
        return CustomerCreated(
            customer_id=entity.id, customer_name=entity.name, user_id=user_id
        )

    def _create_updated_event(
        self, original: Customer, updated: Customer
    ) -> DomainEvent:
        """
        Create event for customer update.

        Args:
            original: Original customer entity
            updated: Updated customer entity

        Returns:
            CustomerUpdated event
        """
        changes = {}
        for key, new_value in updated.__dict__.items():
            if key.startswith("_"):
                continue
            old_value = getattr(original, key, None)
            if old_value != new_value:
                # For sensitive fields, don't include actual values
                if key in ["email", "phone", "address"]:
                    changes[key] = {"changed": True}
                else:
                    changes[key] = {"old": old_value, "new": new_value}

        user_id = (
            self.security_context.current_user.id if self.security_context else None
        )
        return CustomerUpdated(customer_id=updated.id, changes=changes, user_id=user_id)
