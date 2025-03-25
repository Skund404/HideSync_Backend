# File: app/services/customer_communication_service.py

from typing import Dict, Any, List, Optional, Tuple, Union
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from app.services.base_service import BaseService
from app.repositories.customer_communication_repository import (
    CustomerCommunicationRepository,
)
from app.db.models.communication import CustomerCommunication
from app.db.models.enums import CommunicationChannel, CommunicationType
from app.core.events import DomainEvent
from app.core.exceptions import EntityNotFoundException, ValidationException
from app.core.validation import validate_entity, validate_input
from services.customer_service import validate_customer

logger = logging.getLogger(__name__)


# Domain events
class CommunicationCreated(DomainEvent):
    """Event emitted when a customer communication is created."""

    def __init__(
        self,
        communication_id: int,
        customer_id: int,
        channel: str,
        user_id: Optional[int] = None,
    ):
        super().__init__()
        self.communication_id = communication_id
        self.customer_id = customer_id
        self.channel = channel
        self.user_id = user_id


class CommunicationResponded(DomainEvent):
    """Event emitted when a customer communication is responded to."""

    def __init__(
        self, communication_id: int, customer_id: int, user_id: Optional[int] = None
    ):
        super().__init__()
        self.communication_id = communication_id
        self.customer_id = customer_id
        self.user_id = user_id


class CustomerCommunicationService(BaseService[CustomerCommunication]):
    """
    Service for managing customer communications in the HideSync system.

    Provides functionality for:
    - Recording communications across various channels
    - Tracking responses and follow-ups
    - Analyzing communication patterns
    - Generating reports on customer interactions
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        notification_service=None,
        customer_repository=None,
        file_storage_service=None,
    ):
        """
        Initialize CustomerCommunicationService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Repository for customer communications
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            notification_service: Optional service for sending notifications
            customer_repository: Optional repository for customer data
            file_storage_service: Optional service for handling file attachments
        """
        self.session = session
        self.repository = repository or CustomerCommunicationRepository(session)
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.notification_service = notification_service
        self.customer_repository = customer_repository
        self.file_storage_service = file_storage_service

    def record_communication(
        self,
        customer_id: int,
        channel: Union[str, CommunicationChannel],
        communication_type: Union[str, CommunicationType],
        content: str,
        subject: Optional[str] = None,
        needs_response: bool = False,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[Union[str, int]] = None,
        direction: str = "INBOUND",
        staff_id: Optional[int] = None,
        communication_date: Optional[datetime] = None,
        attachment_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record a new customer communication.

        Args:
            customer_id: ID of the customer
            channel: Communication channel (EMAIL, PHONE, etc.)
            communication_type: Type of communication (INQUIRY, ORDER_CONFIRMATION, etc.)
            content: Content of the communication
            subject: Optional subject or title
            needs_response: Whether this communication requires a response
            related_entity_type: Optional type of related entity
            related_entity_id: Optional ID of related entity
            direction: Direction of communication (INBOUND or OUTBOUND)
            staff_id: Optional ID of staff member involved
            communication_date: Optional date of communication (defaults to now)
            attachment_ids: Optional list of attachment file IDs
            metadata: Optional additional metadata

        Returns:
            Created communication data

        Raises:
            EntityNotFoundException: If customer not found
            ValidationException: If validation fails
        """
        # Validate customer exists if repository is available
        if self.customer_repository:
            customer = self.customer_repository.get_by_id(customer_id)
            if not customer:
                raise EntityNotFoundException(
                    "Customer not found", "CUSTOMER_001", {"id": customer_id}
                )

        # Get staff ID from security context if not provided
        if (
            staff_id is None
            and self.security_context
            and hasattr(self.security_context, "user_id")
        ):
            staff_id = self.security_context.user_id

        # Format attachment IDs as JSON string if provided
        attachment_ids_str = None
        if attachment_ids:
            import json

            attachment_ids_str = json.dumps(attachment_ids)

        # Format metadata as JSON string if provided
        metadata_str = None
        if metadata:
            import json

            metadata_str = json.dumps(metadata)

        # Prepare communication data
        communication_data = {
            "customer_id": customer_id,
            "channel": channel,
            "communication_type": communication_type,
            "content": content,
            "subject": subject,
            "needs_response": needs_response,
            "direction": direction,
            "staff_id": staff_id,
            "related_entity_type": related_entity_type,
            "related_entity_id": (
                str(related_entity_id) if related_entity_id is not None else None
            ),
            "communication_date": communication_date or datetime.now(),
            "attachment_ids": attachment_ids_str,
            "metadata": metadata_str,
        }

        # Create communication record
        with self.transaction():
            communication = self.repository.create_communication(communication_data)

            # Publish event if event bus exists
            if self.event_bus:
                self.event_bus.publish(
                    CommunicationCreated(
                        communication_id=communication.id,
                        customer_id=customer_id,
                        channel=str(channel),
                        user_id=staff_id,
                    )
                )

            # Send notification if service exists and communication needs response
            if self.notification_service and needs_response:
                self._send_response_needed_notification(communication)

            return communication.to_dict()

    def respond_to_communication(
        self,
        communication_id: int,
        response_content: str,
        staff_id: Optional[int] = None,
        response_date: Optional[datetime] = None,
        attachment_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Record a response to a communication.

        Args:
            communication_id: ID of the communication being responded to
            response_content: Content of the response
            staff_id: Optional ID of staff member responding
            response_date: Optional date of response (defaults to now)
            attachment_ids: Optional list of attachment file IDs

        Returns:
            Updated communication data

        Raises:
            EntityNotFoundException: If communication not found
        """
        # Get communication
        communication = self.repository.get_by_id(communication_id)
        if not communication:
            raise EntityNotFoundException(
                "Communication not found", "COMMUNICATION_001", {"id": communication_id}
            )

        # Get staff ID from security context if not provided
        if (
            staff_id is None
            and self.security_context
            and hasattr(self.security_context, "user_id")
        ):
            staff_id = self.security_context.user_id

        # Format attachment IDs
        if attachment_ids:
            import json

            current_ids = (
                json.loads(communication.attachment_ids)
                if communication.attachment_ids
                else []
            )
            all_ids = current_ids + attachment_ids
            attachment_ids_str = json.dumps(all_ids)

            # Update attachment IDs
            communication.attachment_ids = attachment_ids_str

        # Record response
        with self.transaction():
            # Update communication
            communication.response_content = response_content
            communication.response_date = response_date or datetime.now()
            communication.needs_response = False

            if staff_id:
                communication.staff_id = staff_id

            self.session.commit()

            # Publish event if event bus exists
            if self.event_bus:
                self.event_bus.publish(
                    CommunicationResponded(
                        communication_id=communication_id,
                        customer_id=communication.customer_id,
                        user_id=staff_id,
                    )
                )

            # Check if we should record an outbound communication
            if communication.direction == "INBOUND":
                # Record outbound communication
                self.record_communication(
                    customer_id=communication.customer_id,
                    channel=communication.channel,
                    communication_type=communication.communication_type,
                    content=response_content,
                    subject=(
                        f"RE: {communication.subject}"
                        if communication.subject
                        else None
                    ),
                    needs_response=False,
                    related_entity_type=communication.related_entity_type,
                    related_entity_id=communication.related_entity_id,
                    direction="OUTBOUND",
                    staff_id=staff_id,
                    communication_date=response_date or datetime.now(),
                    attachment_ids=attachment_ids,
                )

            return communication.to_dict()

    def get_communications_for_customer(
        self,
        customer_id: int,
        page: int = 1,
        per_page: int = 20,
        include_responses: bool = True,
        channel: Optional[Union[str, CommunicationChannel]] = None,
        communication_type: Optional[Union[str, CommunicationType]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[Union[str, int]] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get paginated communications for a customer.

        Args:
            customer_id: ID of the customer
            page: Page number
            per_page: Items per page
            include_responses: Whether to include communications with responses
            channel: Optional filter by channel
            communication_type: Optional filter by type
            start_date: Optional filter by start date
            end_date: Optional filter by end date
            related_entity_type: Optional filter by related entity type
            related_entity_id: Optional filter by related entity ID

        Returns:
            Tuple of (list of communications, total count)
        """
        # Validate customer exists if repository is available
        if self.customer_repository:
            customer = self.customer_repository.get_by_id(customer_id)
            if not customer:
                raise EntityNotFoundException(
                    "Customer not found", "CUSTOMER_001", {"id": customer_id}
                )

        # Build filters
        filters = {"customer_id": customer_id, "page": page, "per_page": per_page}

        if not include_responses:
            filters["needs_response"] = True

        if channel:
            filters["channel"] = channel

        if communication_type:
            filters["comm_type"] = communication_type

        if start_date:
            filters["start_date"] = start_date

        if end_date:
            filters["end_date"] = end_date

        if related_entity_type:
            filters["related_entity_type"] = related_entity_type

        if related_entity_id:
            filters["related_entity_id"] = str(related_entity_id)

        # Get communications
        communications, total = self.repository.list_paginated(**filters)

        # Parse attachment IDs and metadata
        return [self._parse_communication_json_fields(c) for c in communications], total

    def get_unanswered_communications(
        self, limit: int = 50, customer_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get communications that need a response.

        Args:
            limit: Maximum number of results
            customer_id: Optional filter by customer ID

        Returns:
            List of communications needing response
        """
        # Get communications
        communications = self.repository.find_unanswered(limit)

        # Filter by customer if needed
        if customer_id is not None:
            communications = [c for c in communications if c.customer_id == customer_id]

        # Parse attachment IDs and metadata
        return [self._parse_communication_json_fields(c) for c in communications]

    def get_communication_history(
        self, customer_id: int, days: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Get full communication history for a customer.

        Args:
            customer_id: ID of the customer
            days: Number of days of history to retrieve

        Returns:
            List of all communications in chronological order
        """
        # Calculate start date
        start_date = datetime.now() - timedelta(days=days)

        # Get communications with pagination
        page = 1
        per_page = 100
        all_communications = []

        while True:
            communications, total = self.get_communications_for_customer(
                customer_id=customer_id,
                page=page,
                per_page=per_page,
                include_responses=True,
                start_date=start_date,
            )

            all_communications.extend(communications)

            if len(all_communications) >= total:
                break

            page += 1

        # Sort by date
        all_communications.sort(key=lambda x: x.get("communication_date", ""))

        return all_communications

    def get_communication_stats(
        self, days: int = 30, customer_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get communication statistics.

        Args:
            days: Number of days to analyze
            customer_id: Optional filter by customer ID

        Returns:
            Dictionary with communication statistics
        """
        # Get volume by day
        volume_by_day = self.repository.get_communication_volume_by_day(
            days, customer_id
        )

        # Get stats by channel
        channel_stats = self.repository.get_communication_stats_by_channel(days)

        # Calculate response rates
        # This would need to be implemented in the repository
        response_stats = {"total": 0, "responded": 0, "avg_response_time": 0}

        return {
            "volume_by_day": volume_by_day,
            "by_channel": channel_stats,
            "response_stats": response_stats,
        }

    def search_communications(
        self,
        search_term: str,
        customer_id: Optional[int] = None,
        channel: Optional[Union[str, CommunicationChannel]] = None,
        communication_type: Optional[Union[str, CommunicationType]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Search for communications.

        Args:
            search_term: Text to search for
            customer_id: Optional filter by customer ID
            channel: Optional filter by channel
            communication_type: Optional filter by type
            start_date: Optional filter by start date
            end_date: Optional filter by end date
            page: Page number
            per_page: Items per page

        Returns:
            Tuple of (list of matching communications, total count)
        """
        # Build filters
        filters = {"search_term": search_term, "page": page, "per_page": per_page}

        if customer_id is not None:
            filters["customer_id"] = customer_id

        if channel:
            filters["channel"] = channel

        if communication_type:
            filters["comm_type"] = communication_type

        if start_date:
            filters["start_date"] = start_date

        if end_date:
            filters["end_date"] = end_date

        # Get communications
        communications, total = self.repository.list_paginated(**filters)

        # Parse attachment IDs and metadata
        return [self._parse_communication_json_fields(c) for c in communications], total

    def add_attachment(self, communication_id: int, file_id: str) -> Dict[str, Any]:
        """
        Add a file attachment to a communication.

        Args:
            communication_id: ID of the communication
            file_id: ID of the file

        Returns:
            Updated communication data

        Raises:
            EntityNotFoundException: If communication or file not found
        """
        # Validate file exists if file storage service is available
        if self.file_storage_service:
            file_metadata = self.file_storage_service.get_file_metadata(file_id)
            if not file_metadata:
                raise EntityNotFoundException(
                    "File not found", "FILE_001", {"id": file_id}
                )

        # Get communication
        communication = self.repository.get_by_id(communication_id)
        if not communication:
            raise EntityNotFoundException(
                "Communication not found", "COMMUNICATION_001", {"id": communication_id}
            )

        # Add attachment ID
        import json

        current_ids = (
            json.loads(communication.attachment_ids)
            if communication.attachment_ids
            else []
        )

        if file_id not in current_ids:
            current_ids.append(file_id)

        communication.attachment_ids = json.dumps(current_ids)
        self.session.commit()

        # Associate file with communication if file storage service is available
        if self.file_storage_service:
            self.file_storage_service.associate_with_entity(
                file_id=file_id, entity_type="communication", entity_id=communication_id
            )

        return self._parse_communication_json_fields(communication)

    def get_attachments(self, communication_id: int) -> List[Dict[str, Any]]:
        """
        Get all attachments for a communication.

        Args:
            communication_id: ID of the communication

        Returns:
            List of file metadata dictionaries

        Raises:
            EntityNotFoundException: If communication not found
        """
        # Get communication
        communication = self.repository.get_by_id(communication_id)
        if not communication:
            raise EntityNotFoundException(
                "Communication not found", "COMMUNICATION_001", {"id": communication_id}
            )

        # Get attachment IDs
        import json

        attachment_ids = (
            json.loads(communication.attachment_ids)
            if communication.attachment_ids
            else []
        )

        # Get file metadata if file storage service is available
        if self.file_storage_service and attachment_ids:
            attachments = []
            for file_id in attachment_ids:
                metadata = self.file_storage_service.get_file_metadata(file_id)
                if metadata:
                    attachments.append(metadata)
            return attachments

        return []

    def _parse_communication_json_fields(
        self, communication: CustomerCommunication
    ) -> Dict[str, Any]:
        """
        Parse JSON fields in communication.

        Args:
            communication: CustomerCommunication instance

        Returns:
            Dictionary with parsed fields
        """
        comm_dict = communication.to_dict()

        # Parse attachment IDs
        if comm_dict.get("attachment_ids"):
            import json

            try:
                comm_dict["attachment_ids"] = json.loads(comm_dict["attachment_ids"])
            except (json.JSONDecodeError, TypeError):
                comm_dict["attachment_ids"] = []
        else:
            comm_dict["attachment_ids"] = []

        # Parse metadata
        if comm_dict.get("metadata"):
            import json

            try:
                comm_dict["metadata"] = json.loads(comm_dict["metadata"])
            except (json.JSONDecodeError, TypeError):
                comm_dict["metadata"] = {}
        else:
            comm_dict["metadata"] = {}

        return comm_dict

    def _send_response_needed_notification(
        self, communication: CustomerCommunication
    ) -> None:
        """
        Send notification for communication needing response.

        Args:
            communication: CustomerCommunication instance
        """
        if not self.notification_service:
            return

        # This would use the notification service to send alerts about communications needing response
        # Actual implementation would depend on notification service API
        pass


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


# File: app/services/customer_service.py (additions)

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import csv
import io


def bulk_import_customers(
        self, customers_data: List[Dict[str, Any]], update_existing: bool = False
) -> Dict[str, Any]:
    """
    Bulk import customers from a list of customer data.

    Args:
        customers_data: List of customer data dictionaries
        update_existing: Whether to update customers that already exist

    Returns:
        Dictionary with import results

    Raises:
        ValidationException: If validation fails
    """
    results = {
        "total_processed": len(customers_data),
        "created": 0,
        "updated": 0,
        "failed": 0,
        "errors": []
    }

    with self.transaction():
        for idx, customer_data in enumerate(customers_data):
            try:
                # Validate customer data
                if not validate_customer(customer_data):
                    raise ValidationException(
                        f"Invalid customer data at index {idx}",
                        {"validation": ["Invalid customer data format"]}
                    )

                # Check if customer exists by email
                existing = None
                if "email" in customer_data and customer_data["email"]:
                    existing = self.repository.find_by_email(customer_data["email"])

                if existing and update_existing:
                    # Update existing customer
                    self.repository.update(existing.id, customer_data)
                    results["updated"] += 1
                elif not existing:
                    # Create new customer
                    self.repository.create(customer_data)
                    results["created"] += 1
                else:
                    # Customer exists but update_existing is False
                    results["failed"] += 1
                    results["errors"].append({
                        "index": idx,
                        "email": customer_data.get("email", ""),
                        "reason": "Customer already exists and update_existing is False"
                    })
            except Exception as e:
                # Record any errors
                results["failed"] += 1
                results["errors"].append({
                    "index": idx,
                    "email": customer_data.get("email", ""),
                    "reason": str(e)
                })

    return results


def export_customers(
        self, search_params: Optional[Dict[str, Any]] = None, format: str = "csv"
) -> Tuple[str, str]:
    """
    Export customers to CSV or JSON.

    Args:
        search_params: Optional search parameters
        format: Export format (csv or json)

    Returns:
        Tuple of (content, filename)
    """
    # Get customers based on search parameters
    customers = self.repository.list(**search_params if search_params else {})

    # Format current date for filename
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"customers_export_{date_str}.{format}"

    # Convert to list of dictionaries
    customer_dicts = []
    for c in customers:
        customer_dict = {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "status": str(c.status) if hasattr(c.status, "name") else c.status,
            "tier": str(c.tier) if hasattr(c.tier, "name") else c.tier,
            "source": str(c.source) if hasattr(c.source, "name") else c.source,
            "company_name": c.company_name,
            "address": c.address,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "notes": c.notes
        }
        customer_dicts.append(customer_dict)

    if format.lower() == "json":
        content = json.dumps(customer_dicts, indent=2)
    else:  # csv
        output = io.StringIO()
        if customer_dicts:
            fieldnames = customer_dicts[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(customer_dicts)

        content = output.getvalue()
        output.close()

    return content, filename


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
            "source": source_distribution
        },
        "average_lifetime_value": avg_ltv,
        "top_customers": top_customers
    }