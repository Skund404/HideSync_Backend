# tests/api/endpoints/test_analytics.py
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db, get_current_user
from app.api.endpoints import analytics
from app.core.config import settings
from app.db.models.base import Base
from app.db.models.user import User
from app.schemas.analytics import DashboardSummary
from app.services.user_service import UserService
from app.core import security

# Define a test database URL
TEST_DATABASE_URL = "sqlite:///./test.db"  # Use an in-memory SQLite database for testing

# Create a test engine and session
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the database dependency
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override the authentication dependency
def override_get_current_user(db: TestingSessionLocal = Depends(override_get_db)):
    # Create a test user
    email = "testuser@example.com"
    user_service = UserService(db)
    user = user_service.get_by_email(email=email)
    if not user:
        user_in = {
            "full_name": "Test User",
            "email": email,
            "password": "testpassword",
            "is_active": True,
            "is_superuser": False,
        }
        user = user_service.create(**user_in)

    # Return the test user
    return user


@pytest.fixture()
def test_app():
    # Create the test database tables
    Base.metadata.create_all(bind=engine)

    # Create a FastAPI app instance
    app = FastAPI()

    # Override the dependencies
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    # Include the analytics router
    app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])

    yield app

    # Drop the test database tables
    Base.metadata.drop_all(bind=engine)

@pytest.fixture()
def client(test_app):
    """Get a TestClient instance that reads/writes to the test database."""
    with TestClient(test_app) as client:
        yield client


def test_get_dashboard_summary(client: TestClient):
    response = client.get("/analytics/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


def test_get_financial_summary(client: TestClient):
    response = client.get("/analytics/financial/summary")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


def test_get_revenue_analysis(client: TestClient):
    response = client.get("/analytics/financial/revenue")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


def test_get_stock_level_analysis(client: TestClient):
    response = client.get("/analytics/inventory/stock-levels")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


def test_get_supplier_performance(client: TestClient):
    response = client.get("/analytics/suppliers/performance")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


def test_get_customer_lifetime_value(client: TestClient):
    response = client.get("/analytics/customers/lifetime-value")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)