# File: app/schemas/webhook.py
"""
Webhook schemas for the HideSync system.

This module defines schema models for webhook payloads, responses,
and related data structures used in the platform integration system.
These schemas are used for validating incoming webhook data from external
e-commerce platforms and services.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import uuid


class WebhookPayload(BaseModel):
    """
    Base schema for webhook payloads.

    This is the generic webhook payload structure that captures
    common fields across different platform webhooks.
    """

    event_type: str
    timestamp: datetime = Field(default_factory=datetime.now)
    data: Dict[str, Any]
    signature: Optional[str] = None

    class Config:
        from_attributes = True


class OrderWebhookPayload(WebhookPayload):
    """
    Schema for order-related webhook payloads.

    Extends the base webhook payload with specific fields
    for order-related events.
    """

    order_id: str
    order_status: str
    customer_info: Optional[Dict[str, Any]] = None


class ProductWebhookPayload(WebhookPayload):
    """
    Schema for product-related webhook payloads.

    Extends the base webhook payload with specific fields
    for product-related events.
    """

    product_id: str
    product_title: str
    price: Optional[float] = None
    inventory_quantity: Optional[int] = None


class CustomerWebhookPayload(WebhookPayload):
    """
    Schema for customer-related webhook payloads.

    Extends the base webhook payload with specific fields
    for customer-related events.
    """

    customer_id: str
    email: Optional[str] = None
    name: Optional[str] = None


class InventoryWebhookPayload(WebhookPayload):
    """
    Schema for inventory-related webhook payloads.

    Extends the base webhook payload with specific fields
    for inventory-related events.
    """

    product_id: str
    variant_id: Optional[str] = None
    inventory_quantity: int
    location_id: Optional[str] = None


class WebhookResponse(BaseModel):
    """
    Response schema for webhook processing.

    Provides a standardized structure for responses to webhook
    requests, indicating success or failure and relevant details.
    """

    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class WebhookConfigurationBase(BaseModel):
    """
    Base schema for webhook configuration.

    Defines the configuration for setting up a webhook
    with an external platform.
    """

    topic: str
    address: str
    format: str = "json"
    integration_id: str
    description: Optional[str] = None
    fields: Optional[List[str]] = None
    active: bool = True


class WebhookConfigurationCreate(WebhookConfigurationBase):
    """Schema for creating a webhook configuration."""

    class Config:
        from_attributes = True


class WebhookConfiguration(WebhookConfigurationBase):
    """Schema for webhook configuration response."""

    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    platform_webhook_id: Optional[str] = None

    class Config:
        from_attributes = True


class WebhookDelivery(BaseModel):
    """
    Schema for webhook delivery information.

    Contains details about a specific webhook delivery attempt,
    including success/failure information and response data.
    """

    id: str
    webhook_id: str
    event_type: str
    request_url: str
    request_headers: Dict[str, str]
    request_body: Dict[str, Any]
    response_code: int
    response_body: Optional[Dict[str, Any]] = None
    success: bool
    created_at: datetime
    response_time_ms: Optional[int] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class WebhookDeliveryList(BaseModel):
    """Schema for a list of webhook deliveries."""

    items: List[WebhookDelivery]
    total: int
    page: int
    page_size: int
