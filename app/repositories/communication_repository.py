# File: app/repositories/communication_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func
from datetime import datetime, timedelta

from app.db.models.communication import CustomerCommunication
from app.db.models.enums import CommunicationChannel, CommunicationType
from app.repositories.base_repository import BaseRepository


class CommunicationRepository(BaseRepository[CustomerCommunication]):
    """
    Repository for CustomerCommunication entity operations.

    Handles data access for customer communications, including email,
    phone, and in-person interactions. Tracks communication history and
    provides methods for analyzing customer engagement patterns.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the CommunicationRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = CustomerCommunication

        # Define sensitive fields that need encryption
        if not hasattr(self.model, "SENSITIVE_FIELDS"):
            self.model.SENSITIVE_FIELDS = [
                "content"  # The communication content may contain sensitive information
            ]

    def get_communications_by_customer(
        self, customer_id: int, skip: int = 0, limit: int = 100
    ) -> List[CustomerCommunication]:
        """
        Get communications for a specific customer.

        Args:
            customer_id (int): ID of the customer
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[CustomerCommunication]: List of communications for the customer
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.customer_id == customer_id)
            .order_by(desc(self.model.created_at))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_communications_by_channel(
        self, channel: CommunicationChannel, skip: int = 0, limit: int = 100
    ) -> List[CustomerCommunication]:
        """
        Get communications by channel.

        Args:
            channel (CommunicationChannel): The communication channel to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[CustomerCommunication]: List of communications via the specified channel
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.channel == channel)
            .order_by(desc(self.model.created_at))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_communications_by_type(
        self, comm_type: CommunicationType, skip: int = 0, limit: int = 100
    ) -> List[CustomerCommunication]:
        """
        Get communications by type.

        Args:
            comm_type (CommunicationType): The communication type to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[CustomerCommunication]: List of communications of the specified type
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.type == comm_type)
            .order_by(desc(self.model.created_at))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_communications_by_date_range(
        self, start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100
    ) -> List[CustomerCommunication]:
        """
        Get communications within a specific date range.

        Args:
            start_date (datetime): Start of the date range
            end_date (datetime): End of the date range
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[CustomerCommunication]: List of communications within the date range
        """
        query = (
            self.session.query(self.model)
            .filter(
                and_(
                    self.model.created_at >= start_date,
                    self.model.created_at <= end_date,
                )
            )
            .order_by(desc(self.model.created_at))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_recent_communications(
        self, days: int = 7, skip: int = 0, limit: int = 100
    ) -> List[CustomerCommunication]:
        """
        Get communications from the last specified number of days.

        Args:
            days (int): Number of days to look back
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[CustomerCommunication]: List of recent communications
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        query = (
            self.session.query(self.model)
            .filter(self.model.created_at >= cutoff_date)
            .order_by(desc(self.model.created_at))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_communications_by_project(
        self, project_id: int, skip: int = 0, limit: int = 100
    ) -> List[CustomerCommunication]:
        """
        Get communications related to a specific project.

        Args:
            project_id (int): ID of the project
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[CustomerCommunication]: List of communications related to the project
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.project_id == project_id)
            .order_by(desc(self.model.created_at))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_communications_by_sale(
        self, sale_id: int, skip: int = 0, limit: int = 100
    ) -> List[CustomerCommunication]:
        """
        Get communications related to a specific sale.

        Args:
            sale_id (int): ID of the sale
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[CustomerCommunication]: List of communications related to the sale
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.sale_id == sale_id)
            .order_by(desc(self.model.created_at))
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def search_communications(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> List[CustomerCommunication]:
        """
        Search for communications by content or subject.

        Args:
            query (str): The search query
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[CustomerCommunication]: List of matching communications
        """
        search_query = (
            self.session.query(self.model)
            .filter(
                or_(
                    self.model.subject.ilike(f"%{query}%"),
                    self.model.content.ilike(f"%{query}%"),
                )
            )
            .order_by(desc(self.model.created_at))
        )

        entities = search_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_communication_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about customer communications.

        Returns:
            Dict[str, Any]: Dictionary with communication statistics
        """
        # Total communications
        total_count = self.session.query(func.count(self.model.id)).scalar() or 0

        # Communications by channel
        channel_counts = (
            self.session.query(
                self.model.channel, func.count(self.model.id).label("count")
            )
            .group_by(self.model.channel)
            .all()
        )

        # Communications by type
        type_counts = (
            self.session.query(
                self.model.type, func.count(self.model.id).label("count")
            )
            .group_by(self.model.type)
            .all()
        )

        # Communications by month (last 12 months)
        twelve_months_ago = datetime.now() - timedelta(days=365)
        monthly_counts = (
            self.session.query(
                func.strftime("%Y-%m", self.model.created_at).label("month"),
                func.count(self.model.id).label("count"),
            )
            .filter(self.model.created_at >= twelve_months_ago)
            .group_by("month")
            .order_by("month")
            .all()
        )

        # Average communications per customer
        customer_counts = (
            self.session.query(
                self.model.customer_id, func.count(self.model.id).label("count")
            )
            .group_by(self.model.customer_id)
            .all()
        )

        avg_per_customer = 0
        if customer_counts:
            avg_per_customer = sum(count for _, count in customer_counts) / len(
                customer_counts
            )

        return {
            "total_count": total_count,
            "average_per_customer": avg_per_customer,
            "by_channel": [
                {
                    "channel": (
                        channel.value if hasattr(channel, "value") else str(channel)
                    ),
                    "count": count,
                }
                for channel, count in channel_counts
            ],
            "by_type": [
                {
                    "type": type_.value if hasattr(type_, "value") else str(type_),
                    "count": count,
                }
                for type_, count in type_counts
            ],
            "monthly_trend": [
                {"month": month, "count": count} for month, count in monthly_counts
            ],
        }

    def create_customer_communication(
        self,
        customer_id: int,
        channel: CommunicationChannel,
        comm_type: CommunicationType,
        subject: str,
        content: str,
        project_id: Optional[int] = None,
        sale_id: Optional[int] = None,
    ) -> CustomerCommunication:
        """
        Create a new customer communication record.

        Args:
            customer_id (int): ID of the customer
            channel (CommunicationChannel): Communication channel used
            comm_type (CommunicationType): Type of communication
            subject (str): Subject or title of the communication
            content (str): Content of the communication
            project_id (Optional[int]): ID of the related project, if any
            sale_id (Optional[int]): ID of the related sale, if any

        Returns:
            CustomerCommunication: The created communication record
        """
        communication_data = {
            "customer_id": customer_id,
            "channel": channel,
            "type": comm_type,
            "subject": subject,
            "content": content,
            "project_id": project_id,
            "sale_id": sale_id,
            "created_at": datetime.now(),
        }

        return self.create(communication_data)
