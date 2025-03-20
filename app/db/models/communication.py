# File: app/db/models/communication.py

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Boolean,
    Text,
    Enum,
)
from sqlalchemy.orm import relationship, validates
from datetime import datetime

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin
from app.db.models.enums import CommunicationChannel, CommunicationType


class CustomerCommunication(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Model for tracking all communications with customers in the HideSync system.

    Stores information about interactions with customers across various channels,
    including emails, phone calls, text messages, social media, etc.
    """

    __tablename__ = "customer_communication"

    # Core fields
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    communication_date = Column(DateTime, nullable=False, default=datetime.now)
    channel = Column(Enum(CommunicationChannel), nullable=False)
    communication_type = Column(Enum(CommunicationType), nullable=False)

    # Content fields
    subject = Column(String(255))
    content = Column(Text, nullable=False)
    needs_response = Column(Boolean, default=False)
    response_content = Column(Text)
    response_date = Column(DateTime)

    # Metadata
    staff_id = Column(Integer, ForeignKey("users.id"))
    direction = Column(String(20), default="INBOUND")  # INBOUND or OUTBOUND
    related_entity_type = Column(String(50))  # project, sale, etc.
    related_entity_id = Column(String(50))
    meta_data = Column(Text)  # JSON serialized additional data
    attachment_ids = Column(Text)  # JSON serialized array of file IDs

    # Relationships
    customer = relationship("Customer", back_populates="communications")
    staff = relationship("User", back_populates="customer_communications")

    @validates("channel")
    def validate_channel(self, key, value):
        """Validate and normalize communication channel."""
        if isinstance(value, str):
            try:
                return CommunicationChannel[value.upper()]
            except (KeyError, AttributeError):
                # Default to EMAIL if invalid
                return CommunicationChannel.EMAIL
        return value

    @validates("communication_type")
    def validate_type(self, key, value):
        """Validate and normalize communication type."""
        if isinstance(value, str):
            try:
                return CommunicationType[value.upper()]
            except (KeyError, AttributeError):
                # Default to INQUIRY if invalid
                return CommunicationType.INQUIRY
        return value

    @validates("direction")
    def validate_direction(self, key, value):
        """Validate communication direction."""
        if value not in ["INBOUND", "OUTBOUND"]:
            return "INBOUND"
        return value

    def to_dict(self):
        """Convert communication to dictionary."""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "communication_date": (
                self.communication_date.isoformat() if self.communication_date else None
            ),
            "channel": (
                self.channel.name
                if hasattr(self.channel, "name")
                else str(self.channel)
            ),
            "communication_type": (
                self.communication_type.name
                if hasattr(self.communication_type, "name")
                else str(self.communication_type)
            ),
            "subject": self.subject,
            "content": self.content,
            "needs_response": self.needs_response,
            "response_content": self.response_content,
            "response_date": (
                self.response_date.isoformat() if self.response_date else None
            ),
            "staff_id": self.staff_id,
            "direction": self.direction,
            "related_entity_type": self.related_entity_type,
            "related_entity_id": self.related_entity_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "meta_data": self.meta_data,
            "attachment_ids": self.attachment_ids,
        }
