# tests/test_db_models.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models.base import Base  # Your base model
from app.db.models.project import ProjectTemplate  # Only import ProjectTemplate

TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_import_project_template(test_db):
    # This test simply imports ProjectTemplate and creates/drops tables
    assert True  # If we get here without an error, it's a partial success
