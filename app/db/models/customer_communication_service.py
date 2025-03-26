# File: app/services/customer_communication_service.py

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import csv
import io
from sqlalchemy.orm import Session

from app.core.exceptions import (
    EntityNotFoundException,
    BusinessRuleException,
    ValidationException,
)
from app.db.models.customer import Customer
from app.db.models.communication import CustomerCommunication
from app.db.models.enums import (
    CustomerStatus,
    CustomerTier,
    CustomerSource,
    CommunicationType,
)
from app.repositories.customer_repository import CustomerRepository
from app.repositories.communication_repository import CommunicationRepository


class CustomerCommunicationService:
    """
    Service for managing customer communications in the HideSync system.

    Handles recording, retrieving, and managing customer communications across
    different channels and communication types.
    """

    def __init__(self, session: Session, repository=None):
        """
        Initialize CustomerCommunicationService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository override
        """
        self.session = session
        self.repository = repository or CommunicationRepository(session)
        self.customer_repository = CustomerRepository(session)

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
            EntityNotFoundException: If customer not found
            ValidationException: If data validation fails
        """
        # Check if customer exists
        customer = self.customer_repository.get_by_id(customer_id)
        if not customer:
            raise EntityNotFoundException(f"Customer with ID {customer_id} not found")

        # Add customer ID and timestamp if not provided
        communication_data["customer_id"] = customer_id
        if "communication_date" not in communication_data:
            communication_data["communication_date"] = datetime.now()

        # Create communication record
        communication = self.repository.create(communication_data)

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
            EntityNotFoundException: If customer not found
        """
        # Check if customer exists
        customer = self.customer_repository.get_by_id(customer_id)
        if not customer:
            raise EntityNotFoundException(f"Customer with ID {customer_id} not found")

        # Build filter parameters
        filters = {"customer_id": customer_id}

        if communication_type:
            filters["communication_type"] = communication_type

        if start_date:
            filters["date_from"] = start_date

        if end_date:
            filters["date_to"] = end_date

        # Query communications
        return self.repository.list(limit=limit, **filters)


# File: app/services/customer_analytics_service.py

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.repositories.customer_repository import CustomerRepository
from app.db.models.enums import CustomerStatus, CustomerTier, CustomerSource


class CustomerAnalyticsService:
    """
    Service for analyzing customer data in the HideSync system.

    Provides analytics, reporting, and insights on customer behavior,
    segmentation, and value.
    """

    def __init__(self, session: Session, repository=None):
        """
        Initialize CustomerAnalyticsService with dependencies.

        Args:
            session: Database session for data access
            repository: Optional repository override
        """
        self.session = session
        self.repository = repository or CustomerRepository(session)

    def get_customer_analytics(self) -> Dict[str, Any]:
        """
        Get aggregated customer analytics data.

        Returns:
            Dictionary with various customer analytics metrics
        """
        # Get today's date for calculations
        today = datetime.now().date()
        thirty_days_ago = today - timedelta(days=30)

        # Get total customer count
        total_customers = self.repository.count()

        # Get active customers (using CustomerStatus.ACTIVE)
        active_customers = self.repository.count(status=CustomerStatus.ACTIVE)

        # Get new customers in the last 30 days
        new_customers = self.repository.count_new_since(thirty_days_ago)

        # Get customer distribution by status, tier, and source
        status_distribution = self.repository.get_distribution_by_field("status")
        tier_distribution = self.repository.get_distribution_by_field("tier")
        source_distribution = self.repository.get_distribution_by_field("source")

        # Get average lifetime value
        avg_ltv = self.repository.get_average_lifetime_value()

        # Get top customers by sales volume
        top_customers = self.repository.get_top_customers_by_sales(limit=10)

        return {
            "total_customers": total_customers,
            "active_customers": active_customers,
            "new_customers_30d": new_customers,
            "customer_distribution": {
                "status": status_distribution,
                "tier": tier_distribution,
                "source": source_distribution,
            },
            "average_lifetime_value": avg_ltv,
            "top_customers": top_customers,
        }

    def get_customer_distribution(self, field: str) -> Dict[str, int]:
        """
        Get distribution of customers by a specific field.

        Args:
            field: Field to get distribution for (status, tier, source)

        Returns:
            Dictionary mapping field values to counts
        """
        return self.repository.get_distribution_by_field(field)

    def get_customer_growth(self, months: int = 12) -> Dict[str, Any]:
        """
        Get customer growth data over time.

        Args:
            months: Number of months to analyze

        Returns:
            Customer growth data by month
        """
        return self.repository.get_growth_by_month(months)

    def get_top_customers(
        self, limit: int = 10, by_field: str = "sales"
    ) -> List[Dict[str, Any]]:
        """
        Get top customers by a specific metric.

        Args:
            limit: Number of customers to return
            by_field: Field to rank customers by (sales, orders, average_order)

        Returns:
            List of top customers with details
        """
        if by_field == "sales":
            return self.repository.get_top_customers_by_sales(limit)
        elif by_field == "orders":
            return self.repository.get_top_customers_by_order_count(limit)
        elif by_field == "average_order":
            return self.repository.get_top_customers_by_average_order(limit)
        else:
            return self.repository.get_top_customers_by_sales(limit)
