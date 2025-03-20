# File: app/schemas/customer.py
"""
Customer schemas for the HideSync API.

This module contains Pydantic models for customer-related request validations and responses,
supporting the customer management functionality in the application.
"""

from datetime import datetime
from typing import List, Optional, Union
from pydantic import BaseModel, EmailStr, Field, validator

from app.db.models.enums import CustomerStatus, CustomerTier, CustomerSource


class CustomerBase(BaseModel):
    """
    Base schema for customer data shared across different operations.

    Contains common fields used for both request validation and responses.
    """
    name: str = Field(..., description="Full name of the customer", min_length=1, max_length=100)
    email: EmailStr = Field(..., description="Email address of the customer")
    phone: Optional[str] = Field(None, description="Phone number of the customer")
    status: Optional[CustomerStatus] = Field(None, description="Status of the customer relationship")
    tier: Optional[CustomerTier] = Field(None, description="Customer tier classification")
    source: Optional[CustomerSource] = Field(None, description="How the customer discovered the business")
    company_name: Optional[str] = Field(None, description="Company name for business customers")
    address: Optional[str] = Field(None, description="Physical address of the customer")
    notes: Optional[str] = Field(None, description="Additional notes about the customer")


class CustomerCreate(CustomerBase):
    """
    Schema for creating a new customer.

    Extends the base schema and adds any fields required specifically for customer creation.
    """
    # Changed from CustomerStatus.NEW to None to avoid AttributeError
    status: Optional[CustomerStatus] = Field(None, description="Status of the new customer")
    # Using optional with default None instead of a specific enum value to be safer
    tier: Optional[CustomerTier] = Field(None, description="Initial tier for the new customer")

    @validator('phone')
    def validate_phone(cls, v):
        """Validate phone number format."""
        if v is not None:
            # Remove non-digit characters for standardization
            digits_only = ''.join(filter(str.isdigit, v))
            if len(digits_only) < 10:
                raise ValueError('Phone number must have at least 10 digits')
        return v


class CustomerUpdate(BaseModel):
    """
    Schema for updating customer information.

    All fields are optional to allow partial updates.
    """
    name: Optional[str] = Field(None, description="Full name of the customer", min_length=1, max_length=100)
    email: Optional[EmailStr] = Field(None, description="Email address of the customer")
    phone: Optional[str] = Field(None, description="Phone number of the customer")
    status: Optional[CustomerStatus] = Field(None, description="Status of the customer relationship")
    tier: Optional[CustomerTier] = Field(None, description="Customer tier classification")
    source: Optional[CustomerSource] = Field(None, description="How the customer discovered the business")
    company_name: Optional[str] = Field(None, description="Company name for business customers")
    address: Optional[str] = Field(None, description="Physical address of the customer")
    notes: Optional[str] = Field(None, description="Additional notes about the customer")

    @validator('phone')
    def validate_phone(cls, v):
        """Validate phone number format if provided."""
        if v is not None:
            # Remove non-digit characters for standardization
            digits_only = ''.join(filter(str.isdigit, v))
            if len(digits_only) < 10:
                raise ValueError('Phone number must have at least 10 digits')
        return v


class CustomerInDB(CustomerBase):
    """
    Schema for customer information as stored in the database.

    Extends the base schema and adds database-specific fields.
    """
    id: int = Field(..., description="Unique identifier for the customer")
    created_at: datetime = Field(..., description="Timestamp when the customer was created")
    updated_at: datetime = Field(..., description="Timestamp when the customer was last updated")

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
    total_sales: Optional[float] = Field(None, description="Total amount of sales made by this customer")
    last_order_date: Optional[datetime] = Field(None, description="Date of the customer's most recent order")
    order_count: Optional[int] = Field(None, description="Total number of orders placed by this customer")


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