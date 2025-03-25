# File: app/schemas/purchase_timeline.py
"""
Purchase timeline schemas for the HideSync system.

This module defines schemas related to purchase timelines,
including scheduled deliveries, purchase planning, and
supplier order tracking across time periods.
"""

from typing import List, Dict, Optional, Any
from datetime import date, datetime
from pydantic import BaseModel, Field, validator


class PurchaseTimelineItemBase(BaseModel):
    """Base schema for purchase timeline items."""

    supplier: str
    delivery_date: date
    status: str
    items: Dict[str, Any]
    total: float


class PurchaseTimelineItemCreate(PurchaseTimelineItemBase):
    """Schema for creating purchase timeline items."""

    class Config:
        from_attributes = True


class PurchaseTimelineItem(PurchaseTimelineItemBase):
    """Schema for purchase timeline items."""

    id: str
    purchase_id: str

    # Additional calculated fields
    days_until_delivery: Optional[int] = None
    is_overdue: Optional[bool] = False

    class Config:
        from_attributes = True

    @validator('days_until_delivery', pre=True, always=True)
    def calculate_days_until_delivery(cls, v, values):
        """Calculate days until delivery."""
        if 'delivery_date' in values:
            today = date.today()
            delta = values['delivery_date'] - today
            return delta.days
        return v

    @validator('is_overdue', pre=True, always=True)
    def calculate_is_overdue(cls, v, values):
        """Calculate if delivery is overdue."""
        if 'delivery_date' in values:
            today = date.today()
            return values['delivery_date'] < today
        return v


class PurchaseTimelinePeriod(BaseModel):
    """Schema for a period in the purchase timeline."""

    period_name: str
    start_date: date
    end_date: date
    items: List[PurchaseTimelineItem]
    total_amount: float
    item_count: int


class PurchaseTimeline(BaseModel):
    """Schema for the purchase timeline."""

    periods: List[PurchaseTimelinePeriod]
    total_purchases: int
    total_amount: float
    date_range_start: date
    date_range_end: date
    suppliers: List[str]


class PurchasePlanItemBase(BaseModel):
    """Base schema for purchase plan items."""

    material_id: int
    material_name: str
    material_type: str
    current_stock: float
    min_stock_level: float
    recommended_order_quantity: float
    unit: str
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    estimated_cost: Optional[float] = None
    last_purchase_date: Optional[date] = None
    last_purchase_price: Optional[float] = None


class PurchasePlanItem(PurchasePlanItemBase):
    """Schema for purchase plan items."""

    days_until_stockout: Optional[int] = None
    usage_rate: Optional[float] = None
    priority: Optional[str] = None

    class Config:
        from_attributes = True


class PurchasePlan(BaseModel):
    """Schema for purchase planning."""

    items: List[PurchasePlanItem]
    total_estimated_cost: float
    supplier_breakdown: Dict[str, float]
    generated_at: datetime = Field(default_factory=datetime.now)
    recommended_purchases: Dict[str, List[PurchasePlanItem]]