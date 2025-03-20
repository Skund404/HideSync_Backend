# File: app/repositories/customer_communication_repository.py

from typing import List, Optional, Dict, Any, Union, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, asc
from datetime import datetime, timedelta

from app.repositories.base_repository import BaseRepository
from app.db.models.communication import CustomerCommunication
from app.db.models.enums import CommunicationChannel, CommunicationType


class CustomerCommunicationRepository(BaseRepository[CustomerCommunication]):
    """
    Repository for customer communication operations in the HideSync system.

    Provides methods for creating, retrieving, updating, and deleting customer
    communications, as well as specialized queries for communication-specific needs.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the CustomerCommunicationRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, CustomerCommunication, encryption_service)

    def create_communication(self, data: Dict[str, Any]) -> CustomerCommunication:
        """
        Create a new customer communication record.

        Args:
            data: Communication data

        Returns:
            Created CustomerCommunication instance
        """
        # Ensure dates are set
        if "communication_date" not in data:
            data["communication_date"] = datetime.now()

        return self.create(data)

    def get_by_customer_id(
        self,
        customer_id: int,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "communication_date",
        sort_dir: str = "desc",
    ) -> List[CustomerCommunication]:
        """
        Get communications for a specific customer.

        Args:
            customer_id: ID of the customer
            limit: Maximum number of results
            offset: Number of records to skip
            sort_by: Field to sort by
            sort_dir: Sort direction ('asc' or 'desc')

        Returns:
            List of CustomerCommunication instances
        """
        query = self.session.query(CustomerCommunication).filter(
            CustomerCommunication.customer_id == customer_id
        )

        # Apply sorting
        if sort_dir.lower() == "asc":
            query = query.order_by(getattr(CustomerCommunication, sort_by))
        else:
            query = query.order_by(desc(getattr(CustomerCommunication, sort_by)))

        return query.offset(offset).limit(limit).all()

    def find_by_channel(
        self, channel: Union[str, CommunicationChannel], limit: int = 50
    ) -> List[CustomerCommunication]:
        """
        Find communications by channel.

        Args:
            channel: Communication channel
            limit: Maximum number of results

        Returns:
            List of CustomerCommunication instances
        """
        # Convert string to enum if needed
        if isinstance(channel, str):
            try:
                channel = CommunicationChannel[channel.upper()]
            except (KeyError, AttributeError):
                # Default to string value if not an enum
                pass

        return (
            self.session.query(CustomerCommunication)
            .filter(CustomerCommunication.channel == channel)
            .order_by(desc(CustomerCommunication.communication_date))
            .limit(limit)
            .all()
        )

    def find_by_type(
        self, comm_type: Union[str, CommunicationType], limit: int = 50
    ) -> List[CustomerCommunication]:
        """
        Find communications by type.

        Args:
            comm_type: Communication type
            limit: Maximum number of results

        Returns:
            List of CustomerCommunication instances
        """
        # Convert string to enum if needed
        if isinstance(comm_type, str):
            try:
                comm_type = CommunicationType[comm_type.upper()]
            except (KeyError, AttributeError):
                # Default to string value if not an enum
                pass

        return (
            self.session.query(CustomerCommunication)
            .filter(CustomerCommunication.communication_type == comm_type)
            .order_by(desc(CustomerCommunication.communication_date))
            .limit(limit)
            .all()
        )

    def find_recent(
        self, days: int = 7, limit: int = 50
    ) -> List[CustomerCommunication]:
        """
        Find recent communications.

        Args:
            days: Number of days to look back
            limit: Maximum number of results

        Returns:
            List of CustomerCommunication instances
        """
        since_date = datetime.now() - timedelta(days=days)

        return (
            self.session.query(CustomerCommunication)
            .filter(CustomerCommunication.communication_date >= since_date)
            .order_by(desc(CustomerCommunication.communication_date))
            .limit(limit)
            .all()
        )

    def find_unanswered(self, limit: int = 50) -> List[CustomerCommunication]:
        """
        Find unanswered communications.

        Args:
            limit: Maximum number of results

        Returns:
            List of CustomerCommunication instances that need response
        """
        return (
            self.session.query(CustomerCommunication)
            .filter(
                CustomerCommunication.needs_response == True,
                CustomerCommunication.response_date.is_(None),
            )
            .order_by(desc(CustomerCommunication.communication_date))
            .limit(limit)
            .all()
        )

    def mark_as_responded(
        self,
        communication_id: int,
        response_content: str,
        response_date: Optional[datetime] = None,
    ) -> Optional[CustomerCommunication]:
        """
        Mark a communication as responded.

        Args:
            communication_id: ID of the communication
            response_content: Content of the response
            response_date: Date of the response (defaults to now)

        Returns:
            Updated CustomerCommunication if found, None otherwise
        """
        communication = self.get_by_id(communication_id)
        if communication:
            communication.response_content = response_content
            communication.response_date = response_date or datetime.now()
            communication.needs_response = False
            self.session.commit()
            return communication
        return None

    def search_by_content(
        self, search_term: str, customer_id: Optional[int] = None, limit: int = 50
    ) -> List[CustomerCommunication]:
        """
        Search communications by content.

        Args:
            search_term: Text to search for in content
            customer_id: Optional customer ID to limit search
            limit: Maximum number of results

        Returns:
            List of matching CustomerCommunication instances
        """
        query = self.session.query(CustomerCommunication).filter(
            CustomerCommunication.content.ilike(f"%{search_term}%")
        )

        if customer_id is not None:
            query = query.filter(CustomerCommunication.customer_id == customer_id)

        return (
            query.order_by(desc(CustomerCommunication.communication_date))
            .limit(limit)
            .all()
        )

    def get_communication_volume_by_day(
        self, days: int = 30, customer_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get communication volume by day for reporting.

        Args:
            days: Number of days to analyze
            customer_id: Optional customer ID to limit analysis

        Returns:
            List of dictionaries with date and count
        """
        since_date = datetime.now() - timedelta(days=days)

        query = self.session.query(
            func.date(CustomerCommunication.communication_date).label("date"),
            func.count(CustomerCommunication.id).label("count"),
        ).filter(CustomerCommunication.communication_date >= since_date)

        if customer_id is not None:
            query = query.filter(CustomerCommunication.customer_id == customer_id)

        query = query.group_by(func.date(CustomerCommunication.communication_date))
        query = query.order_by(asc("date"))

        results = query.all()

        return [{"date": str(row.date), "count": row.count} for row in results]

    def get_communication_stats_by_channel(self, days: int = 30) -> Dict[str, int]:
        """
        Get communication statistics by channel.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary mapping channel names to counts
        """
        since_date = datetime.now() - timedelta(days=days)

        results = (
            self.session.query(
                CustomerCommunication.channel,
                func.count(CustomerCommunication.id).label("count"),
            )
            .filter(CustomerCommunication.communication_date >= since_date)
            .group_by(CustomerCommunication.channel)
            .all()
        )

        return {
            str(
                row.channel.name if hasattr(row.channel, "name") else row.channel
            ): row.count
            for row in results
        }

    def list_paginated(
        self,
        page: int = 1,
        per_page: int = 20,
        customer_id: Optional[int] = None,
        channel: Optional[Union[str, CommunicationChannel]] = None,
        comm_type: Optional[Union[str, CommunicationType]] = None,
        needs_response: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search_term: Optional[str] = None,
        sort_by: str = "communication_date",
        sort_dir: str = "desc",
    ) -> Tuple[List[CustomerCommunication], int]:
        """
        Get paginated list of communications with filtering options.

        Args:
            page: Page number (1-indexed)
            per_page: Number of items per page
            customer_id: Filter by customer ID
            channel: Filter by communication channel
            comm_type: Filter by communication type
            needs_response: Filter by whether communication needs response
            start_date: Filter by communication date (start)
            end_date: Filter by communication date (end)
            search_term: Search in content
            sort_by: Field to sort by
            sort_dir: Sort direction ('asc' or 'desc')

        Returns:
            Tuple of (list of CustomerCommunication, total count)
        """
        query = self.session.query(CustomerCommunication)

        # Apply filters
        if customer_id is not None:
            query = query.filter(CustomerCommunication.customer_id == customer_id)

        if channel is not None:
            # Convert string to enum if needed
            if isinstance(channel, str):
                try:
                    channel = CommunicationChannel[channel.upper()]
                except (KeyError, AttributeError):
                    # Default to string value if not an enum
                    pass
            query = query.filter(CustomerCommunication.channel == channel)

        if comm_type is not None:
            # Convert string to enum if needed
            if isinstance(comm_type, str):
                try:
                    comm_type = CommunicationType[comm_type.upper()]
                except (KeyError, AttributeError):
                    # Default to string value if not an enum
                    pass
            query = query.filter(CustomerCommunication.communication_type == comm_type)

        if needs_response is not None:
            query = query.filter(CustomerCommunication.needs_response == needs_response)

        if start_date is not None:
            query = query.filter(CustomerCommunication.communication_date >= start_date)

        if end_date is not None:
            query = query.filter(CustomerCommunication.communication_date <= end_date)

        if search_term:
            search_term = f"%{search_term}%"
            query = query.filter(
                or_(
                    CustomerCommunication.content.ilike(search_term),
                    CustomerCommunication.subject.ilike(search_term),
                )
            )

        # Get total count
        total = query.count()

        # Apply sorting
        if sort_dir.lower() == "asc":
            query = query.order_by(getattr(CustomerCommunication, sort_by))
        else:
            query = query.order_by(desc(getattr(CustomerCommunication, sort_by)))

        # Apply pagination
        query = query.offset((page - 1) * per_page).limit(per_page)

        return query.all(), total
