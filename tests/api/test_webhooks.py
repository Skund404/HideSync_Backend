# tests/api/test_webhooks.py
"""
Tests for webhook handling endpoints.

This module provides test cases for the webhook endpoints,
verifying that webhooks from various platforms are correctly
processed and appropriate responses are returned.
"""

import json
import hmac
import hashlib
import base64
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.core.config import settings
from app.tests.utils.utils import get_superuser_token_headers
from app.tests.utils.db import override_get_db

# Test client setup
client = TestClient(app)
# Override dependency
app.dependency_overrides[get_db] = override_get_db


def test_process_shopify_webhook():
    """Test processing a Shopify webhook."""
    # Mock payload for a Shopify order webhook
    payload = {
        "id": 1234567890,
        "order_number": "1001",
        "email": "customer@example.com",
        "total_price": "199.99",
        "currency": "USD",
        "financial_status": "paid",
        "line_items": [
            {
                "id": 9876543210,
                "title": "Leather Wallet",
                "quantity": 1,
                "price": "99.99",
                "sku": "LW-001"
            },
            {
                "id": 9876543211,
                "title": "Leather Belt",
                "quantity": 1,
                "price": "99.99",
                "sku": "LB-001"
            }
        ],
        "customer": {
            "id": 5555555555,
            "email": "customer@example.com",
            "first_name": "John",
            "last_name": "Doe"
        },
        "created_at": datetime.now().isoformat()
    }

    # Create a signature using a test shared secret
    test_shared_secret = "shpss_1234567890abcdef1234567890abcdef"
    signature = hmac.new(
        test_shared_secret.encode('utf-8'),
        json.dumps(payload).encode('utf-8'),
        hashlib.sha256
    ).digest()
    encoded_signature = base64.b64encode(signature).decode('utf-8')

    # Headers for Shopify webhook
    headers = {
        "X-Shopify-Hmac-SHA256": encoded_signature,
        "X-Shopify-Shop-Domain": "test-shop.myshopify.com"
    }

    # Mock the platform_integration_service.verify_webhook_signature to return True
    # This would typically be done with a patch or mock

    # Make request to webhook endpoint
    response = client.post(
        "/api/webhooks/shopify/test-shop",
        json=payload,
        headers=headers
    )

    # Check that response is as expected
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "Webhook processed" in response.json()["message"]


def test_process_etsy_webhook():
    """Test processing an Etsy webhook."""
    # Mock payload for an Etsy receipt webhook
    payload = {
        "receipt_id": 1234567890,
        "was_paid": True,
        "was_shipped": False,
        "create_timestamp": int(datetime.now().timestamp()),
        "transactions": [
            {
                "transaction_id": 9876543210,
                "title": "Handcrafted Leather Journal",
                "quantity": 1,
                "price": {
                    "amount": 4999,
                    "divisor": 100,
                    "currency_code": "USD"
                },
                "variations": [
                    {
                        "property_id": 555,
                        "value_id": 666,
                        "formatted_name": "Color",
                        "formatted_value": "Brown"
                    }
                ]
            }
        ],
        "buyer": {
            "user_id": 5555555555,
            "email": "buyer@example.com",
            "name": "Jane Smith"
        }
    }

    # Create a signature using a test shared secret
    test_shared_secret = "etsy_api_secret_1234567890abcdef"
    signature = hmac.new(
        test_shared_secret.encode('utf-8'),
        json.dumps(payload).encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # Headers for Etsy webhook
    headers = {
        "X-Etsy-Signature": signature
    }

    # Make request to webhook endpoint
    response = client.post(
        "/api/webhooks/etsy/test-shop",
        json=payload,
        headers=headers
    )

    # Check that response is as expected
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "Webhook processed" in response.json()["message"]


def test_webhook_no_integration():
    """Test behavior when no integration exists for a shop."""
    # Mock payload
    payload = {"test": "data"}

    # Make request to non-existent shop
    response = client.post(
        "/api/webhooks/shopify/non-existent-shop",
        json=payload
    )

    # Check that appropriate error is returned
    assert response.status_code == 200  # Still returns 200 as per implementation
    assert response.json()["success"] is False
    assert "No integration found" in response.json()["message"]


def test_invalid_signature():
    """Test behavior when webhook signature is invalid."""
    # Mock payload
    payload = {"test": "data"}

    # Invalid signature
    headers = {
        "X-Shopify-Hmac-SHA256": "invalid_signature",
        "X-Shopify-Shop-Domain": "test-shop.myshopify.com"
    }

    # Mock the integration existence check to return True,
    # but signature verification to return False

    # Make request with invalid signature
    response = client.post(
        "/api/webhooks/shopify/test-shop",
        json=payload,
        headers=headers
    )

    # Check that appropriate error is returned
    assert response.status_code == 200  # Still returns 200 as per implementation
    assert response.json()["success"] is False
    assert "Invalid webhook signature" in response.json()["message"]


def test_test_webhook_endpoint():
    """Test the test webhook endpoint."""
    # Mock payload
    payload = {"test": "data"}

    # Get admin token headers
    headers = get_superuser_token_headers()

    # Make request to test webhook endpoint
    response = client.post(
        "/api/webhooks/test/shopify/test-shop",
        json={"event_type": "order.created", "payload": payload},
        headers=headers
    )

    # Check that test webhook processed correctly
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "Test webhook processed" in response.json()["message"]