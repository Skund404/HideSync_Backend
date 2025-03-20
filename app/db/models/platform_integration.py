# File: app/db/models/platform_integration.py
"""
Platform integration models for the Leathercraft ERP system.

This module defines models for integrating with e-commerce platforms,
including the PlatformIntegration model for connections and the SyncEvent
model for tracking synchronization status and history.
"""

from typing import List, Optional, Dict, Any, ClassVar, Set
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Text,
    ForeignKey,
    Integer,
    Boolean,
    DateTime,
    JSON,
)
from sqlalchemy.orm import relationship, validates

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin


class PlatformIntegration(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Platform integration model for e-commerce connections.

    This model represents integration connections to e-commerce platforms
    like Shopify, Etsy, and Amazon, storing credentials and configuration
    for synchronizing orders, inventory, and customers.

    Attributes:
        platform: Platform name (shopify, etsy, amazon, etc.)
        shop_name: Shop identifier
        api_key: API key (encrypted)
        api_secret: API secret (encrypted)
        access_token: OAuth access token (encrypted)
        refresh_token: OAuth refresh token (encrypted)
        token_expires_at: Token expiration date/time
        active: Whether the integration is active
        settings: Platform-specific settings
        last_sync_at: Last synchronization time
    """

    __tablename__ = "platform_integrations"
    __validated_fields__: ClassVar[Set[str]] = {"platform", "shop_name"}

    # Basic platform information
    platform = Column(String(50), nullable=False)
    shop_name = Column(String(255), nullable=False)

    # Authentication (all sensitive fields that should be encrypted)
    api_key = Column(String(255), nullable=True)
    api_secret = Column(String(255), nullable=True)
    access_token = Column(String(255), nullable=True)
    refresh_token = Column(String(255), nullable=True)
    token_expires_at = Column(DateTime, nullable=True)

    # Settings and status
    active = Column(Boolean, default=True)
    settings = Column(JSON, nullable=True)
    last_sync_at = Column(DateTime, nullable=True)

    # List of sensitive fields that need encryption
    SENSITIVE_FIELDS = ["api_key", "api_secret", "access_token", "refresh_token"]

    # Relationships
    sync_events = relationship(
        "SyncEvent", back_populates="platform_integration", cascade="all, delete-orphan"
    )
    sales = relationship(
        "Sale",
        back_populates="platform_integration",
        foreign_keys="[Sale.platform_integration_id]",
    )
    customers = relationship(
        "Customer",
        secondary="customer_platform_integration",
        back_populates="platform_integrations",
    )

    @validates("platform", "shop_name")
    def validate_required(self, key: str, value: str) -> str:
        """
        Validate required fields.

        Args:
            key: Field name
            value: Field value to validate

        Returns:
            Validated value

        Raises:
            ValueError: If value is empty
        """
        if not value or not value.strip():
            raise ValueError(f"{key} is required")
        return value.strip()

    @validates("token_expires_at")
    def validate_expiration(
        self, key: str, value: Optional[datetime]
    ) -> Optional[datetime]:
        """
        Validate token expiration date.

        Args:
            key: Field name ('token_expires_at')
            value: Expiration date to validate

        Returns:
            Validated expiration date

        Raises:
            ValueError: If date is in the past
        """
        if value and value < datetime.now(timezone.utc):
            # Instead of raising an error, we'll just mark as inactive
            self.active = False
        return value

    def is_token_expired(self) -> bool:
        """
        Check if the access token is expired.

        Returns:
            True if token is expired, False otherwise
        """
        if not self.token_expires_at:
            return True
        return self.token_expires_at < datetime.now(timezone.utc)

    def record_sync(
        self,
        event_type: str,
        status: str,
        items_processed: int = 0,
        message: Optional[str] = None,
    ) -> "SyncEvent":
        """
        Record a synchronization event.

        Args:
            event_type: Type of sync event (order_import, inventory_update, etc.)
            status: Status of the event (success, error, etc.)
            items_processed: Number of items processed
            message: Optional message or details

        Returns:
            The created SyncEvent instance
        """
        sync_event = SyncEvent(
            platform_integration_id=self.id,
            event_type=event_type,
            status=status,
            items_processed=items_processed,
            message=message,
        )

        # Update last_sync_at timestamp
        self.last_sync_at = datetime.now(timezone.utc)

        return sync_event

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert PlatformIntegration instance to a dictionary.

        Returns:
            Dictionary representation of the platform integration, with
            sensitive fields masked
        """
        result = super().to_dict()

        # Mask sensitive fields
        for field in self.SENSITIVE_FIELDS:
            if result.get(field):
                result[field] = "******"

        # Handle JSON fields
        if isinstance(result.get("settings"), str):
            import json

            try:
                result["settings"] = json.loads(result["settings"])
            except:
                result["settings"] = {}

        # Add computed properties
        result["is_token_expired"] = self.is_token_expired()

        return result

    def __repr__(self) -> str:
        """Return string representation of the PlatformIntegration."""
        return f"<PlatformIntegration(id={self.id}, platform='{self.platform}', shop='{self.shop_name}', active={self.active})>"


class SyncEvent(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Sync event model for tracking platform synchronization.

    This model records synchronization events between the ERP system
    and e-commerce platforms, including status, details, and timestamps.

    Attributes:
        platform_integration_id: ID of the associated platform integration
        event_type: Type of sync event
        status: Status of the event
        items_processed: Number of items processed
        message: Optional message or details
    """

    __tablename__ = "sync_events"
    __validated_fields__: ClassVar[Set[str]] = {"event_type", "status"}

    # Relationships
    platform_integration_id = Column(
        Integer, ForeignKey("platform_integrations.id"), nullable=False
    )

    # Event information
    event_type = Column(
        String(50), nullable=False
    )  # order_import, inventory_update, etc.
    status = Column(String(50), nullable=False)  # success, error, etc.
    items_processed = Column(Integer, default=0)
    message = Column(Text, nullable=True)

    # Relationships
    platform_integration = relationship(
        "PlatformIntegration", back_populates="sync_events"
    )

    @validates("event_type", "status")
    def validate_required(self, key: str, value: str) -> str:
        """
        Validate required fields.

        Args:
            key: Field name
            value: Field value to validate

        Returns:
            Validated value

        Raises:
            ValueError: If value is empty
        """
        if not value or not value.strip():
            raise ValueError(f"{key} is required")
        return value.strip()

    def __repr__(self) -> str:
        """Return string representation of the SyncEvent."""
        return f"<SyncEvent(id={self.id}, platform_integration_id={self.platform_integration_id}, type='{self.event_type}', status='{self.status}')>"
