from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from enum import Enum


class ReportFormat(str, Enum):
    """Supported report formats."""

    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"
    HTML = "html"


class ReportType(str, Enum):
    """Standard report types."""

    INVENTORY_STATUS = "inventory_status"
    SALES_ANALYSIS = "sales_analysis"
    PROJECT_PERFORMANCE = "project_performance"
    MATERIALS_USAGE = "materials_usage"
    FINANCIAL_SUMMARY = "financial_summary"
    CUSTOMER_ANALYSIS = "customer_analysis"
    PRODUCTION_EFFICIENCY = "production_efficiency"
    SUPPLIER_PERFORMANCE = "supplier_performance"
    CUSTOM = "custom"


class ReportParameter(BaseModel):
    """Report parameter definition."""

    name: str
    type: str
    description: str
    required: bool


class ReportTemplate(BaseModel):
    """Report template definition."""

    type: str
    name: str
    description: str
    parameters: List[ReportParameter]


class ReportRequest(BaseModel):
    """Report generation request."""

    report_type: str
    parameters: Dict[str, Any] = {}
    format: ReportFormat = ReportFormat.JSON
    include_metadata: bool = True


class ReportResponse(BaseModel):
    """Report generation response."""

    metadata: Optional[Dict[str, Any]]
    data: Optional[Dict[str, Any]]
    file_id: Optional[str]
    download_url: Optional[str]
    data_base64: Optional[str]
