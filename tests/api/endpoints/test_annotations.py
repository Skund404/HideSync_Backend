# tests/api/endpoints/test_annotations.py
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Assuming your project structure allows these imports
from app.api.deps import get_db, get_current_active_user
from app.api.endpoints import annotations
from app.core.config import settings
from app.db.models.base import Base
from app.db.models.user import User  # Import the User model
from app.schemas.annotation import Annotation, AnnotationCreate, AnnotationUpdate
from app.services.user_service import UserService
from app import schemas

# Define a test database URL
TEST_DATABASE_URL = (
    "sqlite:///./test_annotations.db"  # Use a separate file for isolation
)

# Create a test engine and session
engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)  # Add check_same_thread for SQLite
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Override the database dependency
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Store the test user ID globally for reuse in tests
test_user_id = None
test_user_email = "test_annotator@example.com"


# Override the authentication dependency
def override_get_current_active_user(
    db: Session = Depends(override_get_db),
) -> User:
    global test_user_id  # Reconsider using globals if possible
    user_service = UserService(db)
    user = user_service.get_by_email(email=test_user_email)

    if not user:
        # --- REMOVE TRY...EXCEPT START ---
        # try:
        user_create_schema = schemas.UserCreate(
            username="test_annotator",
            full_name="Test Annotator",
            email=test_user_email,
            password="testpassword",
            # Add other required fields from UserCreate schema if any
        )
        user = user_service.create_user(user_in=user_create_schema)
        if user:
            test_user_id = user.id
        # except ValidationError as ve:
        #      pytest.fail(f"Failed to create UserCreate schema in override: {ve}")
        # except Exception as e:
        #      pytest.fail(f"Failed to create test user in override: {e}")
        # --- REMOVE TRY...EXCEPT END ---

    if not user:
        # If user is still None after trying to create, fail explicitly
        pytest.fail("Test user could not be found or created.")

    return user


@pytest.fixture(scope="module")
def test_app():
    # Create the test database tables
    Base.metadata.create_all(bind=engine)

    # Create a FastAPI app instance
    app = FastAPI()

    # Override the dependencies
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_active_user] = override_get_current_active_user

    # Include the annotations router
    app.include_router(annotations.router, prefix="/annotations", tags=["annotations"])

    yield app

    # Drop the test database tables
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def client(test_app):
    """Get a TestClient instance that reads/writes to the test database."""
    with TestClient(test_app) as client:
        yield client


# --- Test Data ---
test_entity_type = "project"
test_entity_id = 1
test_annotation_content = "This is a test annotation."
test_annotation_visibility = "private"


# --- Test Functions ---


def test_list_annotations_empty(client: TestClient):
    response = client.get("/annotations/")
    assert response.status_code == 200
    assert response.json() == []


def test_create_annotation(client: TestClient):
    annotation_data = AnnotationCreate(
        entity_type=test_entity_type,
        entity_id=test_entity_id,
        content=test_annotation_content,
        visibility=test_annotation_visibility,
    )
    response = client.post("/annotations/", json=annotation_data.dict())
    assert response.status_code == 201
    data = response.json()
    assert data["content"] == test_annotation_content
    assert data["entity_type"] == test_entity_type
    assert data["entity_id"] == test_entity_id
    assert data["visibility"] == test_annotation_visibility
    assert "id" in data
    assert data["created_by"] == test_user_id  # Check creator


def test_create_entity_annotation(client: TestClient):
    response = client.post(
        f"/annotations/entity/{test_entity_type}/{test_entity_id}",
        json={
            "content": "Entity-specific annotation",
            "visibility": "team",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "Entity-specific annotation"
    assert data["entity_type"] == test_entity_type
    assert data["entity_id"] == test_entity_id
    assert data["visibility"] == "team"
    assert "id" in data
    assert data["created_by"] == test_user_id


def test_list_annotations_populated(client: TestClient):
    # Assumes annotations were created in previous tests
    response = client.get("/annotations/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["content"] == test_annotation_content


def test_get_annotation(client: TestClient):
    # Create one first to get an ID
    annotation_data = AnnotationCreate(
        entity_type="material", entity_id=5, content="Annotation to get"
    )
    create_response = client.post("/annotations/", json=annotation_data.dict())
    assert create_response.status_code == 201
    annotation_id = create_response.json()["id"]

    # Get the created annotation
    response = client.get(f"/annotations/{annotation_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == annotation_id
    assert data["content"] == "Annotation to get"
    assert data["entity_type"] == "material"


def test_get_annotation_not_found(client: TestClient):
    response = client.get("/annotations/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_update_annotation(client: TestClient):
    # Create one first
    annotation_data = AnnotationCreate(
        entity_type="sale", entity_id=10, content="Annotation to update"
    )
    create_response = client.post("/annotations/", json=annotation_data.dict())
    assert create_response.status_code == 201
    annotation_id = create_response.json()["id"]

    # Update the annotation
    update_data = AnnotationUpdate(
        content="Updated annotation content", visibility="public"
    )
    response = client.patch(
        f"/annotations/{annotation_id}", json=update_data.dict(exclude_unset=True)
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == annotation_id
    assert data["content"] == "Updated annotation content"
    assert data["visibility"] == "public"
    # Ensure other fields remain
    assert data["entity_type"] == "sale"


def test_update_annotation_not_found(client: TestClient):
    update_data = AnnotationUpdate(content="Won't work")
    response = client.patch("/annotations/99999", json=update_data.dict())
    assert response.status_code == 404


def test_delete_annotation(client: TestClient):
    # Create one first
    annotation_data = AnnotationCreate(
        entity_type="pattern", entity_id=2, content="Annotation to delete"
    )
    create_response = client.post("/annotations/", json=annotation_data.dict())
    assert create_response.status_code == 201
    annotation_id = create_response.json()["id"]

    # Delete the annotation
    response = client.delete(f"/annotations/{annotation_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_response = client.get(f"/annotations/{annotation_id}")
    assert get_response.status_code == 404


def test_delete_annotation_not_found(client: TestClient):
    response = client.delete("/annotations/99999")
    assert response.status_code == 404


def test_get_annotations_by_entity(client: TestClient):
    # Create some annotations for a specific entity
    entity_type = "unique_entity"
    entity_id = 123
    client.post(
        f"/annotations/entity/{entity_type}/{entity_id}",
        json={"content": "Anno 1", "visibility": "private"},
    )
    client.post(
        f"/annotations/entity/{entity_type}/{entity_id}",
        json={"content": "Anno 2", "visibility": "team"},
    )

    # Get annotations for that entity
    response = client.get(f"/annotations/entity/{entity_type}/{entity_id}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Check if at least the created annotations are present (could be more if other tests used same entity)
    assert len(data) >= 2
    contents = [item["content"] for item in data]
    assert "Anno 1" in contents
    assert "Anno 2" in contents
    for item in data:
        assert item["entity_type"] == entity_type
        assert item["entity_id"] == entity_id


def test_list_annotations_with_filters(client: TestClient):
    # Use annotations created in previous tests
    # Filter by entity type and ID used in test_create_entity_annotation
    response = client.get(
        f"/annotations/?entity_type={test_entity_type}&entity_id={test_entity_id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    for item in data:
        assert item["entity_type"] == test_entity_type
        assert item["entity_id"] == test_entity_id

    # Filter by creator
    response = client.get(f"/annotations/?created_by={test_user_id}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    for item in data:
        assert item["created_by"] == test_user_id

    # Filter by search term
    response = client.get(
        "/annotations/?search=specific annotation"
    )  # From test_create_entity_annotation
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "specific annotation" in data[0]["content"].lower()
