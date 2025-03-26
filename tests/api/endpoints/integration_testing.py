import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.main import app
from app.db.models.platform_integration import PlatformIntegration, SyncEvent
from app.services.platform_integration_service import PlatformIntegrationService
from app.schemas.platform_integration import SyncSettings, SyncEventCreate


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


@pytest.fixture
def mock_integration_service():
    service = MagicMock(spec=PlatformIntegrationService)
    return service


# Tests for PUT /{integration_id}/settings
def test_update_sync_settings_success(client, mock_db, mock_integration_service):
    """Test successful update of sync settings."""
    # Mock setup
    integration_id = "12345"
    mock_user_id = "user123"
    mock_integration = PlatformIntegration(
        id=integration_id,
        platform="shopify",
        shop_name="testshop",
        active=True,
        settings={},
    )

    # Mock the service method
    with patch("app.api.deps.get_db", return_value=mock_db), \
            patch("app.api.deps.get_current_active_user", return_value={"id": mock_user_id}), \
            patch("app.services.platform_integration_service.PlatformIntegrationService",
                  return_value=mock_integration_service):
        mock_integration_service.update_sync_settings.return_value = mock_integration

        # Test data
        settings_data = {
            "auto_sync_enabled": True,
            "sync_interval_minutes": 30,
            "sync_orders": True,
            "sync_products": True,
            "sync_inventory": True,
            "sync_customers": False,
        }

        # Make request
        response = client.put(
            f"/api/v1/integrations/{integration_id}/settings",
            json=settings_data
        )

        # Assertions
        assert response.status_code == 200
        assert response.json()["id"] == integration_id
        mock_integration_service.update_sync_settings.assert_called_once()


def test_update_sync_settings_not_found(client, mock_db, mock_integration_service):
    """Test update sync settings when integration not found."""
    # Mock setup
    integration_id = "99999"
    mock_user_id = "user123"

    # Mock the service method to raise exception
    with patch("app.api.deps.get_db", return_value=mock_db), \
            patch("app.api.deps.get_current_active_user", return_value={"id": mock_user_id}), \
            patch("app.services.platform_integration_service.PlatformIntegrationService",
                  return_value=mock_integration_service):
        from app.core.exceptions import EntityNotFoundException
        mock_integration_service.update_sync_settings.side_effect = EntityNotFoundException(
            f"Integration with ID {integration_id} not found"
        )

        # Test data
        settings_data = {
            "auto_sync_enabled": True,
            "sync_interval_minutes": 30,
        }

        # Make request
        response = client.put(
            f"/api/v1/integrations/{integration_id}/settings",
            json=settings_data
        )

        # Assertions
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


# Tests for POST /{integration_id}/events
def test_create_sync_event_success(client, mock_db, mock_integration_service):
    """Test successful creation of sync event."""
    # Mock setup
    integration_id = "12345"
    mock_user_id = "user123"
    event_id = "event789"
    created_at = datetime.now(timezone.utc)

    mock_event = SyncEvent(
        id=event_id,
        platform_integration_id=integration_id,
        event_type="inventory_update",
        status="success",
        items_processed=10,
        message="Test event",
        created_at=created_at
    )

    # Mock the service method
    with patch("app.api.deps.get_db", return_value=mock_db), \
            patch("app.api.deps.get_current_active_user", return_value={"id": mock_user_id}), \
            patch("app.services.platform_integration_service.PlatformIntegrationService",
                  return_value=mock_integration_service):
        mock_integration_service.create_sync_event.return_value = mock_event

        # Test data
        event_data = {
            "event_type": "inventory_update",
            "status": "success",
            "items_processed": 10,
            "message": "Test event"
        }

        # Make request
        response = client.post(
            f"/api/v1/integrations/{integration_id}/events",
            json=event_data
        )

        # Assertions
        assert response.status_code == 201
        assert response.json()["id"] == event_id
        assert response.json()["platform_integration_id"] == integration_id
        assert response.json()["event_type"] == "inventory_update"
        mock_integration_service.create_sync_event.assert_called_once()


def test_create_sync_event_invalid_type(client, mock_db, mock_integration_service):
    """Test creation of sync event with invalid event type."""
    # Mock setup
    integration_id = "12345"
    mock_user_id = "user123"

    # Mock the service method
    with patch("app.api.deps.get_db", return_value=mock_db), \
            patch("app.api.deps.get_current_active_user", return_value={"id": mock_user_id}), \
            patch("app.services.platform_integration_service.PlatformIntegrationService",
                  return_value=mock_integration_service):
        from app.core.exceptions import BusinessRuleException
        mock_integration_service.create_sync_event.side_effect = BusinessRuleException(
            "Invalid event type"
        )

        # Test data with invalid event type
        event_data = {
            "event_type": "invalid_type",
            "status": "success",
            "items_processed": 10,
            "message": "Test event"
        }

        # Make request
        response = client.post(
            f"/api/v1/integrations/{integration_id}/events",
            json=event_data
        )

        # Assertions
        assert response.status_code == 400
        assert "Invalid" in response.json()["detail"]


# Tests for GET /{integration_id}/with-details
def test_get_integration_with_details_success(client, mock_db, mock_integration_service):
    """Test successful retrieval of integration with details."""
    # Mock setup
    integration_id = "12345"
    mock_user_id = "user123"

    # Create a detailed mock response
    mock_details = {
        "id": integration_id,
        "platform": "shopify",
        "shop_name": "testshop",
        "active": True,
        "last_sync_at": datetime.now(timezone.utc).isoformat(),
        "settings": {
            "auto_sync_enabled": True,
            "sync_interval_minutes": 30
        },
        "events": [
            {
                "id": "event1",
                "platform_integration_id": integration_id,
                "event_type": "inventory_update",
                "status": "success",
                "items_processed": 150,
                "message": "Successfully updated inventory",
                "created_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "id": "event2",
                "platform_integration_id": integration_id,
                "event_type": "order_import",
                "status": "success",
                "items_processed": 25,
                "message": "Successfully imported orders",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        ],
        "statistics": {
            "total_events": 245,
            "success_events": 230,
            "error_events": 15,
            "success_rate": 93.88,
            "total_items_processed": 15678,
            "last_sync": {
                "event_type": "inventory_update",
                "status": "success",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "items_processed": 150,
                "message": "Successfully updated inventory"
            }
        },
        "connection_status": "Connected",
        "connection_health": "Good",
        "platform_details": {
            "shopify_plan": "Advanced",
            "api_version": "2023-04"
        }
    }

    # Mock the service method
    with patch("app.api.deps.get_db", return_value=mock_db), \
            patch("app.api.deps.get_current_active_user", return_value={"id": mock_user_id}), \
            patch("app.services.platform_integration_service.PlatformIntegrationService",
                  return_value=mock_integration_service):
        mock_integration_service.get_integration_with_details.return_value = mock_details

        # Make request
        response = client.get(f"/api/v1/integrations/{integration_id}/with-details")

        # Assertions
        assert response.status_code == 200
        result = response.json()
        assert result["id"] == integration_id
        assert "events" in result
        assert len(result["events"]) == 2
        assert "statistics" in result
        assert "connection_health" in result
        mock_integration_service.get_integration_with_details.assert_called_once_with(integration_id)


def test_get_integration_with_details_not_found(client, mock_db, mock_integration_service):
    """Test get integration with details when integration not found."""
    # Mock setup
    integration_id = "99999"
    mock_user_id = "user123"

    # Mock the service method to raise exception
    with patch("app.api.deps.get_db", return_value=mock_db), \
            patch("app.api.deps.get_current_active_user", return_value={"id": mock_user_id}), \
            patch("app.services.platform_integration_service.PlatformIntegrationService",
                  return_value=mock_integration_service):
        from app.core.exceptions import EntityNotFoundException
        mock_integration_service.get_integration_with_details.side_effect = EntityNotFoundException(
            f"Integration with ID {integration_id} not found"
        )

        # Make request
        response = client.get(f"/api/v1/integrations/{integration_id}/with-details")

        # Assertions
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]