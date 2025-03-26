# File: app/schemas/customer.py
"""
Customer schemas for the HideSync API.

This module contains Pydantic models for customer-related request validations and responses,
supporting the customer management functionality in the application.
"""


from typing import Optional

from typing import Dict, List, Any
import json
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator

from app.db.models.enums import (
    CustomerStatus,
    CustomerTier,
    CustomerSource,
    CommunicationChannel,
    CommunicationType,
)

from app.db.models.enums import CustomerStatus, CustomerTier, CustomerSource


class CustomerBase(BaseModel):
    """
    Base schema for customer data shared across different operations.

    Contains common fields used for both request validation and responses.
    """

    name: str = Field(
        ..., description="Full name of the customer", min_length=1, max_length=100
    )
    email: EmailStr = Field(..., description="Email address of the customer")
    phone: Optional[str] = Field(None, description="Phone number of the customer")
    status: Optional[CustomerStatus] = Field(
        None, description="Status of the customer relationship"
    )
    tier: Optional[CustomerTier] = Field(
        None, description="Customer tier classification"
    )
    source: Optional[CustomerSource] = Field(
        None, description="How the customer discovered the business"
    )
    company_name: Optional[str] = Field(
        None, description="Company name for business customers"
    )
    address: Optional[str] = Field(None, description="Physical address of the customer")
    notes: Optional[str] = Field(
        None, description="Additional notes about the customer"
    )


class CustomerCreate(CustomerBase):
    """
    Schema for creating a new customer.

    Extends the base schema and adds any fields required specifically for customer creation.
    """

    # Changed from CustomerStatus.NEW to None to avoid AttributeError
    status: Optional[CustomerStatus] = Field(
        None, description="Status of the new customer"
    )
    # Using optional with default None instead of a specific enum value to be safer
    tier: Optional[CustomerTier] = Field(
        None, description="Initial tier for the new customer"
    )

    @validator("phone")
    def validate_phone(cls, v):
        """Validate phone number format."""
        if v is not None:
            # Remove non-digit characters for standardization
            digits_only = "".join(filter(str.isdigit, v))
            if len(digits_only) < 10:
                raise ValueError("Phone number must have at least 10 digits")
        return v


class CustomerUpdate(BaseModel):
    """
    Schema for updating customer information.

    All fields are optional to allow partial updates.
    """

    name: Optional[str] = Field(
        None, description="Full name of the customer", min_length=1, max_length=100
    )
    email: Optional[EmailStr] = Field(None, description="Email address of the customer")
    phone: Optional[str] = Field(None, description="Phone number of the customer")
    status: Optional[CustomerStatus] = Field(
        None, description="Status of the customer relationship"
    )
    tier: Optional[CustomerTier] = Field(
        None, description="Customer tier classification"
    )
    source: Optional[CustomerSource] = Field(
        None, description="How the customer discovered the business"
    )
    company_name: Optional[str] = Field(
        None, description="Company name for business customers"
    )
    address: Optional[str] = Field(None, description="Physical address of the customer")
    notes: Optional[str] = Field(
        None, description="Additional notes about the customer"
    )

    @validator("phone")
    def validate_phone(cls, v):
        """Validate phone number format if provided."""
        if v is not None:
            # Remove non-digit characters for standardization
            digits_only = "".join(filter(str.isdigit, v))
            if len(digits_only) < 10:
                raise ValueError("Phone number must have at least 10 digits")
        return v


class CustomerInDB(CustomerBase):
    """
    Schema for customer information as stored in the database.

    Extends the base schema and adds database-specific fields.
    """

    id: int = Field(..., description="Unique identifier for the customer")
    created_at: datetime = Field(
        ..., description="Timestamp when the customer was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the customer was last updated"
    )

    class Config:
        from_attributes = True


# Adding Customer class to match the import in customers.py endpoint
class Customer(CustomerInDB):
    """
    Schema for customer responses in the API.

    This model directly maps to the db Customer model and is used by the endpoint file.
    """

    pass


class CustomerResponse(CustomerInDB):
    """
    Schema for customer responses in the API with additional calculated fields.

    May include additional calculated or derived fields not directly stored in the database.
    """

    total_sales: Optional[float] = Field(
        None, description="Total amount of sales made by this customer"
    )
    last_order_date: Optional[datetime] = Field(
        None, description="Date of the customer's most recent order"
    )
    order_count: Optional[int] = Field(
        None, description="Total number of orders placed by this customer"
    )


class CustomerWithSales(Customer):
    """Schema for customer with sales history."""

    sales: List = []
    total_spent: float = 0.0
    average_order_value: float = 0.0
    first_purchase_date: Optional[datetime] = None
    last_purchase_date: Optional[datetime] = None
    sales_count: int = 0


class CustomerList(BaseModel):
    """
    Schema for paginated customer list responses.
    """

    items: List[CustomerResponse]
    total: int = Field(..., description="Total number of customers matching the query")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


class CustomerSearchParams(BaseModel):
    """Schema for customer search parameters."""

    status: Optional[str] = None
    tier: Optional[str] = None
    search: Optional[str] = None


# For status and tier updates
class CustomerStatusUpdate(BaseModel):
    """Schema for customer status update requests."""

    status: CustomerStatus = Field(
        ..., description="New status to assign to the customer"
    )
    reason: Optional[str] = Field(None, description="Reason for the status change")


class CustomerTierUpdate(BaseModel):
    """Schema for customer tier update requests."""

    tier: CustomerTier = Field(..., description="New tier to assign to the customer")
    reason: Optional[str] = Field(None, description="Reason for the tier change")


# For communications
class CustomerCommunicationBase(BaseModel):
    """Base schema for customer communication data."""

    communication_date: Optional[datetime] = Field(
        None, description="Date and time of the communication"
    )
    channel: CommunicationChannel = Field(..., description="Communication channel used")
    communication_type: CommunicationType = Field(
        ..., description="Type of communication"
    )
    subject: Optional[str] = Field(None, description="Subject of the communication")
    content: str = Field(..., description="Content of the communication")
    direction: str = Field(
        "OUTBOUND", description="Direction of communication (INBOUND/OUTBOUND)"
    )
    needs_response: Optional[bool] = Field(
        False, description="Whether this communication needs a response"
    )
    related_entity_type: Optional[str] = Field(
        None, description="Type of related entity (sale, project, etc.)"
    )
    related_entity_id: Optional[str] = Field(None, description="ID of related entity")
    meta_data: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @validator("meta_data", pre=True)
    def validate_meta_data(cls, v):
        """Convert string to dict if needed."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v or {}


class CustomerCommunicationCreate(CustomerCommunicationBase):
    """Schema for creating customer communication records."""

    pass


class CustomerCommunicationResponse(CustomerCommunicationBase):
    """Schema for customer communication responses."""

    id: int = Field(..., description="ID of the communication record")
    customer_id: int = Field(..., description="ID of the customer")
    staff_id: Optional[int] = Field(None, description="ID of the staff member")
    response_content: Optional[str] = Field(
        None, description="Content of the response if any"
    )
    response_date: Optional[datetime] = Field(
        None, description="Date of the response if any"
    )
    created_at: datetime = Field(..., description="Date the record was created")
    updated_at: datetime = Field(..., description="Date the record was last updated")

    class Config:
        from_attributes = True


# For analytics
class CustomerAnalytics(BaseModel):
    """Schema for customer analytics data."""

    total_customers: int = Field(..., description="Total number of customers")
    active_customers: int = Field(..., description="Number of active customers")
    new_customers_30d: int = Field(..., description="New customers in the last 30 days")
    customer_distribution: Dict[str, Dict[str, int]] = Field(
        ..., description="Distribution of customers by status, tier, source"
    )
    average_lifetime_value: float = Field(
        ..., description="Average customer lifetime value"
    )
    top_customers: List[Dict[str, Any]] = Field(
        ..., description="Top customers by sales volume"
    )


# For bulk import/export
class CustomerImportRow(CustomerBase):
    """Schema for a single customer row in import data."""

    pass


class CustomerImport(BaseModel):
    """Schema for bulk customer import requests."""

    customers: List[CustomerImportRow] = Field(
        ..., description="List of customers to import"
    )
    update_existing: bool = Field(
        False, description="Whether to update existing customers"
    )


class BulkImportResult(BaseModel):
    """Schema for bulk import operation results."""

    total_processed: int = Field(..., description="Total number of records processed")
    created: int = Field(..., description="Number of records created")
    updated: int = Field(..., description="Number of records updated")
    failed: int = Field(..., description="Number of records that failed to import")
    errors: List[Dict[str, Any]] = Field(..., description="Details of import errors")
