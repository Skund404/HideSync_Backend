# File: app/schemas/platform_integration.py
"""
Platform Integration schemas for the HideSync API.

This module contains Pydantic models for managing integrations with external
e-commerce platforms like Shopify, Etsy, and others.
"""

from datetime import datetime
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, validator, SecretStr


class SyncEvent(BaseModel):
    """
    Schema for synchronization event data.
    """

    id: str = Field(..., description="Unique identifier for the sync event")
    platform_integration_id: str = Field(
        ..., description="ID of the platform integration"
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the event was created"
    )
    event_type: str = Field(
        ..., description="Type of event (order_import, inventory_update, etc.)"
    )
    status: str = Field(..., description="Status of the event (success, error)")
    items_processed: Optional[int] = Field(
        None, description="Number of items processed"
    )
    message: Optional[str] = Field(None, description="Event message or error details")

    class Config:
        from_attributes = True


class SyncEventCreate(BaseModel):
    """
    Schema for creating a new synchronization event.
    """

    event_type: str = Field(
        ..., description="Type of event (order_import, inventory_update, etc.)"
    )
    status: str = Field(..., description="Status of the event (success, error)")
    items_processed: Optional[int] = Field(
        None, description="Number of items processed"
    )
    message: Optional[str] = Field(None, description="Event message or error details")


class SyncSettings(BaseModel):
    """
    Schema for platform integration synchronization settings.
    """

    auto_sync_enabled: bool = Field(
        False, description="Whether automatic synchronization is enabled"
    )
    sync_interval_minutes: Optional[int] = Field(
        None, description="Synchronization interval in minutes", gt=0
    )
    sync_orders: bool = Field(True, description="Whether to synchronize orders")
    sync_products: bool = Field(True, description="Whether to synchronize products")
    sync_inventory: bool = Field(True, description="Whether to synchronize inventory")
    sync_customers: bool = Field(True, description="Whether to synchronize customers")
    import_new_orders: bool = Field(True, description="Whether to import new orders")
    export_inventory_changes: bool = Field(
        True, description="Whether to export inventory changes"
    )
    mark_shipped_orders: bool = Field(
        True, description="Whether to mark shipped orders as such in the platform"
    )
    order_status_mapping: Optional[Dict[str, str]] = Field(
        None, description="Mapping between HideSync and platform order statuses"
    )
    product_type_mapping: Optional[Dict[str, str]] = Field(
        None, description="Mapping between HideSync and platform product types"
    )
    default_material_type: Optional[str] = Field(
        None, description="Default material type for imported products"
    )
    product_sync_filters: Optional[Dict[str, Any]] = Field(
        None, description="Filters for product synchronization"
    )
    order_sync_filters: Optional[Dict[str, Any]] = Field(
        None, description="Filters for order synchronization"
    )


class PlatformIntegrationBase(BaseModel):
    """
    Base schema for platform integration data shared across different operations.
    """

    platform: str = Field(
        ..., description="Platform name (shopify, etsy, amazon, etc.)"
    )
    shop_name: str = Field(..., description="Shop name or identifier")
    active: bool = Field(True, description="Whether the integration is active")
    settings: Optional[SyncSettings] = Field(None, description="Integration settings")


class PlatformIntegrationCreate(PlatformIntegrationBase):
    """
    Schema for creating a new platform integration.
    """

    api_key: Optional[str] = Field(None, description="API key for authentication")
    api_secret: Optional[SecretStr] = Field(
        None, description="API secret for authentication"
    )
    access_token: Optional[str] = Field(None, description="Access token if available")
    refresh_token: Optional[str] = Field(None, description="Refresh token if available")
    token_expires_at: Optional[datetime] = Field(
        None, description="Token expiration timestamp"
    )

    @validator("platform")
    def validate_platform(cls, v):
        """Validate platform name."""
        allowed_platforms = {
            "shopify",
            "etsy",
            "amazon",
            "ebay",
            "woocommerce",
            "bigcommerce",
            "squarespace",
            "custom",
        }
        if v.lower() not in allowed_platforms:
            raise ValueError(f"Platform must be one of: {', '.join(allowed_platforms)}")
        return v.lower()


class PlatformIntegrationUpdate(BaseModel):
    """
    Schema for updating platform integration information.

    All fields are optional to allow partial updates.
    """

    shop_name: Optional[str] = Field(None, description="Shop name or identifier")
    active: Optional[bool] = Field(
        None, description="Whether the integration is active"
    )
    api_key: Optional[str] = Field(None, description="API key for authentication")
    api_secret: Optional[SecretStr] = Field(
        None, description="API secret for authentication"
    )
    access_token: Optional[str] = Field(None, description="Access token if available")
    refresh_token: Optional[str] = Field(None, description="Refresh token if available")
    token_expires_at: Optional[datetime] = Field(
        None, description="Token expiration timestamp"
    )
    settings: Optional[SyncSettings] = Field(None, description="Integration settings")


class PlatformIntegration(PlatformIntegrationBase):
    """
    Schema for platform integration information as stored in the database.
    """

    id: str = Field(..., description="Unique identifier for the integration")
    last_sync_at: Optional[datetime] = Field(
        None, description="Timestamp of last synchronization"
    )

    class Config:
        from_attributes = True


class PlatformIntegrationWithEvents(PlatformIntegration):
    """
    Schema for platform integration with related sync events.
    """

    events: List[SyncEvent] = Field([], description="Recent synchronization events")

    class Config:
        from_attributes = True


class SyncResult(BaseModel):
    """
    Schema for synchronization operation result.
    """

    success: bool = Field(..., description="Whether the synchronization was successful")
    message: str = Field(..., description="Result message")
    items_processed: Optional[int] = Field(
        None, description="Number of items processed"
    )
    errors: Optional[List[str]] = Field(None, description="List of errors if any")
    warnings: Optional[List[str]] = Field(None, description="List of warnings if any")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional synchronization details"
    )
    created_at: datetime = Field(..., description="Timestamp of the synchronization")
    duration_seconds: Optional[float] = Field(
        None, description="Duration of the synchronization in seconds"
    )


class ConnectPlatformRequest(BaseModel):
    """
    Schema for connecting to a platform.
    """

    auth_code: Optional[str] = Field(
        None, description="Authorization code (if using OAuth)"
    )
    shop_url: Optional[str] = Field(
        None, description="Shop URL (for certain platforms)"
    )
    credentials: Optional[Dict[str, str]] = Field(
        None, description="Alternative credentials for authentication"
    )


class ConnectPlatformResponse(BaseModel):
    """
    Schema for platform connection response.
    """

    success: bool = Field(..., description="Whether the connection was successful")
    message: str = Field(..., description="Result message")
    integration_id: Optional[str] = Field(
        None, description="ID of the connected integration"
    )
    connected_at: datetime = Field(..., description="Timestamp of the connection")
    expires_at: Optional[datetime] = Field(
        None, description="Expiration timestamp for the connection"
    )
    additional_info: Optional[Dict[str, Any]] = Field(
        None, description="Additional connection information"
    )
