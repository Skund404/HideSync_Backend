# File: app/api/endpoints/webhooks.py
"""
Webhook handling endpoints for the HideSync system.

This module defines the API endpoints for receiving and processing webhooks
from external e-commerce platforms and services. Webhooks enable real-time
synchronization of orders, inventory, and customer data between HideSync and
integrated platforms like Shopify, Etsy, and other marketplaces.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Path, Body, status
from sqlalchemy.orm import Session
import json
import logging
from datetime import datetime

from app.api.deps import get_db, get_current_active_user
from app.core.exceptions import (
    ValidationException,
    BusinessRuleException,
    EntityNotFoundException
)
from app.db.session import get_db
from app.schemas.webhook import (
    WebhookPayload,
    OrderWebhookPayload,
    WebhookResponse
)
from app.services.platform_integration_service import PlatformIntegrationService

# Create logger
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{platform}/{shop_identifier}", response_model=WebhookResponse)
async def process_webhook(
        platform: str = Path(..., description="Platform identifier (shopify, etsy, etc.)"),
        shop_identifier: str = Path(..., description="Shop identifier or subdomain"),
        payload: Dict[str, Any] = Body(...),
        x_shopify_hmac_sha256: Optional[str] = Header(None),
        x_shopify_shop_domain: Optional[str] = Header(None),
        x_etsy_signature: Optional[str] = Header(None),
        x_webhook_signature: Optional[str] = Header(None),
        db: Session = Depends(get_db)
) -> Any:
    """
    Process webhooks from external platforms.

    This endpoint receives webhook payloads from e-commerce platforms and other
    external services, verifies their authenticity, and processes the data
    to synchronize orders, inventory, and other information with HideSync.

    The endpoint supports various platforms including Shopify, Etsy, WooCommerce,
    and others, each with their specific signature verification methods.

    Args:
        platform: Platform identifier (shopify, etsy, etc.)
        shop_identifier: Shop identifier or subdomain
        payload: The webhook payload
        x_shopify_hmac_sha256: Shopify signature header for verification
        x_shopify_shop_domain: Shopify shop domain header
        x_etsy_signature: Etsy signature header for verification
        x_webhook_signature: Generic signature header for other platforms

    Returns:
        WebhookResponse indicating success or failure
    """
    integration_service = PlatformIntegrationService(db)

    # Log webhook receipt
    logger.info(f"Received webhook from {platform}/{shop_identifier}")

    # Normalize platform identifier
    platform = platform.lower()

    try:
        # Find the integration for this platform and shop
        integration = integration_service.find_integration_by_platform_and_shop(
            platform, shop_identifier
        )

        if not integration:
            logger.warning(f"No integration found for {platform}/{shop_identifier}")
            return WebhookResponse(
                success=False,
                message=f"No integration found for {platform}/{shop_identifier}",
                details={"error": "integration_not_found"}
            )

        # Verify webhook signature based on platform
        signature = None
        if platform == "shopify":
            signature = x_shopify_hmac_sha256
            shop_domain = x_shopify_shop_domain

            # Additional validation for Shopify
            if shop_domain and shop_domain != shop_identifier:
                logger.warning(f"Shop domain mismatch: {shop_domain} != {shop_identifier}")
                return WebhookResponse(
                    success=False,
                    message="Shop domain mismatch",
                    details={"error": "domain_mismatch"}
                )

        elif platform == "etsy":
            signature = x_etsy_signature
        else:
            signature = x_webhook_signature

        # Verify signature if the platform requires it
        if signature:
            is_valid = integration_service.verify_webhook_signature(
                integration.id,
                platform,
                signature,
                payload
            )

            if not is_valid:
                logger.warning(f"Invalid webhook signature for {platform}/{shop_identifier}")
                return WebhookResponse(
                    success=False,
                    message="Invalid webhook signature",
                    details={"error": "invalid_signature"}
                )

        # Process webhook based on platform and event type
        event_type = payload.get("event_type") or payload.get("type") or "unknown"

        # Process webhook
        result = integration_service.process_webhook(
            integration.id,
            platform,
            event_type,
            payload
        )

        # Record the webhook event
        sync_event = integration_service.record_sync_event(
            integration.id,
            event_type,
            "success" if result.get("success") else "error",
            result.get("items_processed", 0),
            result.get("message", "")
        )

        return WebhookResponse(
            success=True,
            message=f"Webhook processed: {event_type}",
            details=result
        )

    except ValidationException as e:
        logger.error(f"Validation error processing webhook: {str(e)}")
        return WebhookResponse(
            success=False,
            message=f"Validation error: {str(e)}",
            details={"error": "validation_error", "validation_errors": e.errors}
        )
    except BusinessRuleException as e:
        logger.error(f"Business rule error processing webhook: {str(e)}")
        return WebhookResponse(
            success=False,
            message=f"Business rule error: {str(e)}",
            details={"error": "business_rule_error", "code": e.code}
        )
    except Exception as e:
        logger.exception(f"Error processing webhook: {str(e)}")
        return WebhookResponse(
            success=False,
            message=f"Error processing webhook: {str(e)}",
            details={"error": "internal_error"}
        )


@router.post("/test/{platform}/{shop_identifier}", response_model=WebhookResponse)
async def test_webhook(
        platform: str = Path(..., description="Platform identifier (shopify, etsy, etc.)"),
        shop_identifier: str = Path(..., description="Shop identifier or subdomain"),
        event_type: str = Body(..., embed=True),
        payload: Dict[str, Any] = Body({}, embed=True),
        db: Session = Depends(get_db),
        current_user=Depends(get_current_active_user)
) -> Any:
    """
    Test webhook processing without external platform.

    This endpoint allows testing webhook processing without requiring an actual
    webhook from an external platform. It's useful for development, testing,
    and troubleshooting webhook handlers.

    Args:
        platform: Platform identifier (shopify, etsy, etc.)
        shop_identifier: Shop identifier or subdomain
        event_type: Type of event to simulate
        payload: Webhook payload to simulate

    Returns:
        WebhookResponse indicating success or failure
    """
    integration_service = PlatformIntegrationService(db)

    # Log test webhook
    logger.info(f"Testing webhook for {platform}/{shop_identifier}: {event_type}")

    # Normalize platform identifier
    platform = platform.lower()

    try:
        # Find the integration
        integration = integration_service.find_integration_by_platform_and_shop(
            platform, shop_identifier
        )

        if not integration:
            return WebhookResponse(
                success=False,
                message=f"No integration found for {platform}/{shop_identifier}",
                details={"error": "integration_not_found"}
            )

        # Add event_type to payload if not present
        if "event_type" not in payload and "type" not in payload:
            payload["event_type"] = event_type

        # Add timestamp if not present
        if "timestamp" not in payload:
            payload["timestamp"] = datetime.now().isoformat()

        # Process test webhook
        result = integration_service.process_webhook(
            integration.id,
            platform,
            event_type,
            payload,
            is_test=True
        )

        # Record the test event
        sync_event = integration_service.record_sync_event(
            integration.id,
            f"test_{event_type}",
            "success" if result.get("success") else "error",
            result.get("items_processed", 0),
            result.get("message", "")
        )

        return WebhookResponse(
            success=True,
            message=f"Test webhook processed: {event_type}",
            details=result
        )

    except Exception as e:
        logger.exception(f"Error processing test webhook: {str(e)}")
        return WebhookResponse(
            success=False,
            message=f"Error processing test webhook: {str(e)}",
            details={"error": "internal_error"}
        )