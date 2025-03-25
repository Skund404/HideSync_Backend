from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from datetime import datetime


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