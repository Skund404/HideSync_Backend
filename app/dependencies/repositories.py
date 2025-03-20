# File: app/dependencies/repositories.py

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_encryption_service
from app.db.session import get_db
from app.repositories.repository_factory import RepositoryFactory
from app.repositories.customer_repository import CustomerRepository
from app.repositories.material_repository import MaterialRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.sale_repository import SaleRepository


def get_repository_factory(
    db: Session = Depends(get_db),
    encryption_service=(
        Depends(get_encryption_service) if settings.USE_ENCRYPTION else None
    ),
) -> RepositoryFactory:
    """
    Dependency provider for the RepositoryFactory.

    Args:
        db (Session): Database session dependency
        encryption_service: Optional encryption service dependency

    Returns:
        RepositoryFactory: Factory for creating repositories
    """
    return RepositoryFactory(db, encryption_service)


def get_customer_repository(
    factory: RepositoryFactory = Depends(get_repository_factory),
) -> CustomerRepository:
    """
    Dependency provider for CustomerRepository.

    Args:
        factory (RepositoryFactory): Repository factory dependency

    Returns:
        CustomerRepository: Repository for customer operations
    """
    return factory.create_customer_repository()


def get_material_repository(
    factory: RepositoryFactory = Depends(get_repository_factory),
) -> MaterialRepository:
    """
    Dependency provider for MaterialRepository.

    Args:
        factory (RepositoryFactory): Repository factory dependency

    Returns:
        MaterialRepository: Repository for material operations
    """
    return factory.create_material_repository()


def get_project_repository(
    factory: RepositoryFactory = Depends(get_repository_factory),
) -> ProjectRepository:
    """
    Dependency provider for ProjectRepository.

    Args:
        factory (RepositoryFactory): Repository factory dependency

    Returns:
        ProjectRepository: Repository for project operations
    """
    return factory.create_project_repository()


def get_sale_repository(
    factory: RepositoryFactory = Depends(get_repository_factory),
) -> SaleRepository:
    """
    Dependency provider for SaleRepository.

    Args:
        factory (RepositoryFactory): Repository factory dependency

    Returns:
        SaleRepository: Repository for sale operations
    """
    return factory.create_sale_repository()


# Add more dependency providers for other repositories as needed
