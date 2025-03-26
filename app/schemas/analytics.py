from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

# New Schemas for Pricing Calculator
class PricingCalculatorInputs(BaseModel):
    """Input data for the pricing calculator."""
    materialCost: float = Field(..., ge=0, description="Cost of materials for one unit.")
    hardwareCost: float = Field(..., ge=0, description="Cost of hardware for one unit.")
    laborHours: float = Field(..., ge=0, description="Estimated hours of labor per unit.")
    laborRate: float = Field(..., ge=0, description="Cost per hour of labor.")
    overhead: float = Field(
        ...,
        ge=0,
        description="Overhead percentage applied to direct costs (e.g., 20 for 20%)."
    )
    targetMargin: float = Field(
        ...,
        ge=0,
        lt=100,
        description="Desired profit margin percentage based on selling price (e.g., 40 for 40%)."
    )
    shippingCost: float = Field(
        0.0, ge=0, description="Optional. Estimated shipping cost per unit."
    )
    packagingCost: float = Field(
        0.0, ge=0, description="Optional. Estimated packaging cost per unit."
    )
    platformFees: float = Field(
        0.0,
        ge=0,
        lt=100,
        description="Optional. Platform fee percentage on selling price (e.g., 5 for 5%)."
    )
    marketingCost: float = Field(
        0.0, ge=0, description="Optional. Fixed marketing cost allocated per unit."
    )


class PricingCalculatorResults(BaseModel):
    """Results from the pricing calculator."""
    totalCost: float = Field(..., description="Total cost to produce one unit.")
    breakEvenPrice: float = Field(
        ..., description="Price to cover all costs including shipping and fees (zero profit)."
    )
    suggestedPrice: float = Field(
        ..., description="Selling price to achieve target margin after costs and fees."
    )
    profitAtSuggested: float = Field(
        ..., description="Profit amount per unit if sold at the suggested price."
    )

class DashboardSummary(BaseModel):
    """Dashboard summary response."""
    timestamp: str
    projects: Dict[str, Any]
    materials: Dict[str, Any]
    sales: Dict[str, Any]
    purchases: Dict[str, Any]
    customers: Dict[str, Any]
    recent_activity: List[Dict[str, Any]]


class FinancialSummary(BaseModel):
    """Financial summary response."""
    timestamp: str
    period: Dict[str, str]
    summary: Dict[str, Any]
    period_data: Dict[str, Dict[str, Any]]
    trends: Dict[str, Any]


class RevenueSummary(BaseModel):
    """Revenue analysis response."""
    timestamp: str
    period: Dict[str, str]
    summary: Dict[str, Any]
    grouped_data: Dict[str, Any]


class InventoryStockLevels(BaseModel):
    """Inventory stock levels response."""
    timestamp: str
    materials_to_reorder: int
    low_stock_materials: List[Dict[str, Any]]
    material_counts: Dict[str, Any]
    material_stock_distribution: List[Dict[str, Any]]


class SupplierPerformance(BaseModel):
    """Supplier performance analysis response."""
    timestamp: str
    period: Dict[str, str]
    summary: Dict[str, Any]
    data: List[Dict[str, Any]]


class CustomerLifetimeValue(BaseModel):
    """Customer lifetime value analysis response."""
    timestamp: str
    summary: Dict[str, Any]
    top_customers: List[Dict[str, Any]]
    customer_distribution: Dict[str, Any]