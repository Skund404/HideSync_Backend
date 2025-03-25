# File: app/api/endpoints/customers.py
"""
Customer API endpoints for HideSync.

This module provides endpoints for managing customer data,
including CRUD operations and customer-specific functionalities.
"""
# File: app/api/endpoints/customers.py (additions)

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from datetime import datetime

from app.api.deps import get_current_active_user, get_current_active_superuser
from app.db.session import get_db
from app.schemas.customer import (
    Customer,
    CustomerCreate,
    CustomerUpdate,
    CustomerSearchParams,
    CustomerWithSales,
    CustomerStatusUpdate,
    CustomerTierUpdate,
    CustomerCommunicationCreate,
    CustomerCommunicationResponse,
    CustomerAnalytics,
    CustomerImport,
    BulkImportResult,
)
from app.services.customer_service import CustomerService
from app.services.customer_communication_service import CustomerCommunicationService
from app.core.exceptions import EntityNotFoundExcept

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


@router.patch("/{customer_id}/status", response_model=Customer)
def update_customer_status(
        *,
        db: Session = Depends(get_db),
        customer_id: int = Path(..., ge=1, description="The ID of the customer"),
        status_update: CustomerStatusUpdate,
        current_user: Any = Depends(get_current_active_user),
) -> Customer:
    """
    Update a customer's status.

    Args:
        db: Database session
        customer_id: ID of the customer to update
        status_update: New status and reason
        current_user: Currently authenticated user

    Returns:
        Updated customer information

    Raises:
        HTTPException: If the customer doesn't exist or update violates business rules
    """
    customer_service = CustomerService(db)
    try:
        return customer_service.update_customer(
            customer_id,
            {"status": status_update.status, "status_change_reason": status_update.reason},
            current_user.id
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{customer_id}/tier", response_model=Customer)
def update_customer_tier(
        *,
        db: Session = Depends(get_db),
        customer_id: int = Path(..., ge=1, description="The ID of the customer"),
        tier_update: CustomerTierUpdate,
        current_user: Any = Depends(get_current_active_user),
) -> Customer:
    """
    Update a customer's tier.

    Args:
        db: Database session
        customer_id: ID of the customer to update
        tier_update: New tier and reason
        current_user: Currently authenticated user

    Returns:
        Updated customer information

    Raises:
        HTTPException: If the customer doesn't exist or update violates business rules
    """
    customer_service = CustomerService(db)
    try:
        return customer_service.change_customer_tier(
            customer_id, tier_update.tier, tier_update.reason
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{customer_id}/communications", response_model=List[CustomerCommunicationResponse])
def get_customer_communications(
        *,
        db: Session = Depends(get_db),
        customer_id: int = Path(..., ge=1, description="The ID of the customer"),
        limit: int = Query(50, ge=1, le=1000, description="Maximum number of communications to return"),
        communication_type: Optional[str] = Query(None, description="Filter by communication type"),
        from_date: Optional[datetime] = Query(None, description="Filter by start date"),
        to_date: Optional[datetime] = Query(None, description="Filter by end date"),
        current_user: Any = Depends(get_current_active_user),
) -> List[CustomerCommunicationResponse]:
    """
    Get communication history for a customer.

    Args:
        db: Database session
        customer_id: ID of the customer
        limit: Maximum number of communications to return
        communication_type: Optional filter by communication type
        from_date: Optional filter by start date
        to_date: Optional filter by end date
        current_user: Currently authenticated user

    Returns:
        List of communication records

    Raises:
        HTTPException: If the customer doesn't exist
    """
    communication_service = CustomerCommunicationService(db)
    try:
        return communication_service.get_customer_communications(
            customer_id, limit, communication_type, from_date, to_date
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )


@router.post("/{customer_id}/communications", response_model=CustomerCommunicationResponse)
def add_customer_communication(
        *,
        db: Session = Depends(get_db),
        customer_id: int = Path(..., ge=1, description="The ID of the customer"),
        communication: CustomerCommunicationCreate,
        current_user: Any = Depends(get_current_active_user),
) -> CustomerCommunicationResponse:
    """
    Add a new communication record for a customer.

    Args:
        db: Database session
        customer_id: ID of the customer
        communication: Communication data
        current_user: Currently authenticated user

    Returns:
        Created communication record

    Raises:
        HTTPException: If the customer doesn't exist or validation fails
    """
    communication_service = CustomerCommunicationService(db)
    try:
        communication_data = dict(communication)
        communication_data["staff_id"] = current_user.id
        return communication_service.record_communication(
            customer_id, communication_data
        )
    except EntityNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/analytics", response_model=CustomerAnalytics)
def get_customer_analytics(
        *,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_active_user),
) -> CustomerAnalytics:
    """
    Get customer analytics data.

    Args:
        db: Database session
        current_user: Currently authenticated user

    Returns:
        Customer analytics data
    """
    customer_service = CustomerService(db)
    return customer_service.get_customer_analytics()


@router.post("/import", response_model=BulkImportResult)
def import_customers(
        *,
        db: Session = Depends(get_db),
        import_data: CustomerImport = Body(...),
        current_user: Any = Depends(get_current_active_user),
) -> BulkImportResult:
    """
    Bulk import customers.

    Args:
        db: Database session
        import_data: Customer data to import
        current_user: Currently authenticated user

    Returns:
        Import result summary

    Raises:
        HTTPException: If the import fails
    """
    customer_service = CustomerService(db)
    try:
        customers_data = [dict(customer) for customer in import_data.customers]
        return customer_service.bulk_import_customers(
            customers_data, import_data.update_existing
        )
    except BusinessRuleException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/export")
def export_customers(
        *,
        db: Session = Depends(get_db),
        format: str = Query("csv", description="Export format (csv or json)"),
        status: Optional[str] = Query(None, description="Filter by customer status"),
        tier: Optional[str] = Query(None, description="Filter by customer tier"),
        current_user: Any = Depends(get_current_active_user),
):
    """
    Export customer data.

    Args:
        db: Database session
        format: Export format (csv or json)
        status: Optional filter by customer status
        tier: Optional filter by customer tier
        current_user: Currently authenticated user

    Returns:
        Downloadable file with customer data
    """
    customer_service = CustomerService(db)
    search_params = {}
    if status:
        search_params["status"] = status
    if tier:
        search_params["tier"] = tier

    content, filename = customer_service.export_customers(search_params, format)

    content_type = "text/csv" if format.lower() == "csv" else "application/json"
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )