# File: app/api/endpoints/customers.py
"""
Customer API endpoints for HideSync.

This module provides endpoints for managing customer data,
including CRUD operations and customer-specific functionalities.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_current_active_superuser
from app.db.session import get_db
from app.schemas.customer import (
    Customer,
    CustomerCreate,
    CustomerUpdate,
    CustomerSearchParams,
    CustomerWithSales,
)
from app.services.customer_service import CustomerService
from app.core.exceptions import EntityNotFoundException, BusinessRuleException

router = APIRouter()


@router.get("/", response_model=List[Customer])
def list_customers(
    *,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of records to return"
    ),
    status: Optional[str] = Query(None, description="Filter by customer status"),
    tier: Optional[str] = Query(None, description="Filter by customer tier"),
    search: Optional[str] = Query(None, description="Search term for name or email"),
) -> List[Customer]:
    """
    Retrieve customers with optional filtering and pagination.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        status: Optional filter by customer status
        tier: Optional filter by customer tier
        search: Optional search term for name or email

    Returns:
        List of customer records
    """
    search_params = CustomerSearchParams(status=status, tier=tier, search=search)

    customer_service = CustomerService(db)
    return customer_service.get_customers(
        skip=skip, limit=limit, search_params=search_params
    )


@router.post("/", response_model=Customer, status_code=status.HTTP_201_CREATED)
def create_customer(
    *,
    db: Session = Depends(get_db),
    customer_in: CustomerCreate,
    current_user: Any = Depends(get_current_active_user),
) -> Customer:
    """
    Create a new customer.

    Args:
        db: Database session
        customer_in: Customer data for creation
        current_user: Currently authenticated user

    Returns:
        Created customer information

    Raises:
        HTTPException: If customer creation fails due to business rules
    """
    customer_service = CustomerService(db)
    try:
        return customer_service.create_customer(customer_in, current_user.id)
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{customer_id}", response_model=Customer)
def get_customer(
    *,
    db: Session = Depends(get_db),
    customer_id: int = Path(
        ..., ge=1, description="The ID of the customer to retrieve"
    ),
    current_user: Any = Depends(get_current_active_user),
) -> Customer:
    """
    Get detailed information about a specific customer.

    Args:
        db: Database session
        customer_id: ID of the customer to retrieve
        current_user: Currently authenticated user

    Returns:
        Customer information

    Raises:
        HTTPException: If the customer doesn't exist
    """
    customer_service = CustomerService(db)
    try:
        return customer_service.get_customer(customer_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )


@router.get("/{customer_id}/with-sales", response_model=CustomerWithSales)
def get_customer_with_sales(
    *,
    db: Session = Depends(get_db),
    customer_id: int = Path(..., ge=1, description="The ID of the customer"),
    current_user: Any = Depends(get_current_active_user),
) -> CustomerWithSales:
    """
    Get customer information with their sales history.

    Args:
        db: Database session
        customer_id: ID of the customer
        current_user: Currently authenticated user

    Returns:
        Customer information with sales history

    Raises:
        HTTPException: If the customer doesn't exist
    """
    customer_service = CustomerService(db)
    try:
        return customer_service.get_customer_with_sales(customer_id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )


@router.put("/{customer_id}", response_model=Customer)
def update_customer(
    *,
    db: Session = Depends(get_db),
    customer_id: int = Path(..., ge=1, description="The ID of the customer to update"),
    customer_in: CustomerUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> Customer:
    """
    Update a customer.

    Args:
        db: Database session
        customer_id: ID of the customer to update
        customer_in: Updated customer data
        current_user: Currently authenticated user

    Returns:
        Updated customer information

    Raises:
        HTTPException: If the customer doesn't exist or update violates business rules
    """
    customer_service = CustomerService(db)
    try:
        return customer_service.update_customer(
            customer_id, customer_in, current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    *,
    db: Session = Depends(get_db),
    customer_id: int = Path(..., ge=1, description="The ID of the customer to delete"),
    current_user: Any = Depends(get_current_active_superuser),
) -> None:
    """
    Delete a customer.

    Note: This operation requires superuser privileges.

    Args:
        db: Database session
        customer_id: ID of the customer to delete
        current_user: Currently authenticated superuser

    Raises:
        HTTPException: If the customer doesn't exist or can't be deleted
    """
    customer_service = CustomerService(db)
    try:
        customer_service.delete_customer(customer_id, current_user.id)
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
