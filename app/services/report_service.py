# File: services/report_service.py

"""
Report generation service for the HideSync system.

This module provides functionality for generating comprehensive reports and analytics
across different areas of the HideSync system. It allows users to create various
reports including inventory status, sales analysis, project performance, and financial
summaries with flexible output formats.

Reports provide critical business intelligence to help craftspeople make informed
decisions about their operations, identify trends, and optimize their workflows.
This service centralizes reporting functionality with features for both standard
and custom reports.

Key features:
- Standard report templates for common business needs
- Custom report creation with configurable parameters
- Multiple output formats (PDF, CSV, Excel, JSON)
- Scheduled report generation
- Data visualization preparation
- Historical report storage and retrieval
- Filtering and sorting capabilities
- Aggregation and summary statistics
- Multi-dimensional data analysis

The service follows clean architecture principles with clear separation from
the data access layer through repository interfaces, and integrates with various
domain services to source data for reports.
"""

from typing import List, Optional, Dict, Any, Union, Callable, BinaryIO, Tuple
from datetime import datetime, timedelta, date
import logging
import json
import csv
import io
import uuid
from enum import Enum

from sqlalchemy import Tuple as SQLATuple
from sqlalchemy.orm import Session

from app.core.events import DomainEvent
from app.core.exceptions import (
    HideSyncException,
    ValidationException,
    EntityNotFoundException,
    BusinessRuleException,
)
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class ReportFormat(Enum):
    """Enumeration of supported report formats."""

    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"
    HTML = "html"


class ReportType(Enum):
    """Enumeration of standard report types."""

    INVENTORY_STATUS = "inventory_status"
    SALES_ANALYSIS = "sales_analysis"
    PROJECT_PERFORMANCE = "project_performance"
    MATERIALS_USAGE = "materials_usage"
    FINANCIAL_SUMMARY = "financial_summary"
    CUSTOMER_ANALYSIS = "customer_analysis"
    PRODUCTION_EFFICIENCY = "production_efficiency"
    SUPPLIER_PERFORMANCE = "supplier_performance"
    CUSTOM = "custom"


class ReportGenerated(DomainEvent):
    """Event emitted when a report is generated."""

    def __init__(
        self,
        report_id: str,
        report_type: str,
        format: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize report generated event.

        Args:
            report_id: ID of the generated report
            report_type: Type of report
            format: Format of the report
            user_id: Optional ID of the user who generated the report
        """
        super().__init__()
        self.report_id = report_id
        self.report_type = report_type
        self.format = format
        self.user_id = user_id


class ReportScheduled(DomainEvent):
    """Event emitted when a report is scheduled."""

    def __init__(
        self,
        schedule_id: str,
        report_type: str,
        recurrence: str,
        user_id: Optional[int] = None,
    ):
        """
        Initialize report scheduled event.

        Args:
            schedule_id: ID of the schedule
            report_type: Type of report
            recurrence: Recurrence pattern
            user_id: Optional ID of the user who scheduled the report
        """
        super().__init__()
        self.schedule_id = schedule_id
        self.report_type = report_type
        self.recurrence = recurrence
        self.user_id = user_id


class ReportService(BaseService):
    """
    Service for generating reports and analytics in the HideSync system.

    Provides functionality for:
    - Standard report generation
    - Custom report creation
    - Multiple output formats
    - Data visualization
    - Report scheduling
    - Historical report management
    """

    def __init__(
        self,
        session: Session,
        repository=None,
        security_context=None,
        event_bus=None,
        cache_service=None,
        material_service=None,
        inventory_service=None,
        project_service=None,
        sale_service=None,
        customer_service=None,
        supplier_service=None,
        purchase_service=None,
        file_service=None,
    ):
        """
        Initialize ReportService with dependencies.

        Args:
            session: Database session for persistence operations
            repository: Optional repository for reports
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
            material_service: Optional service for material operations
            inventory_service: Optional service for inventory operations
            project_service: Optional service for project operations
            sale_service: Optional service for sales operations
            customer_service: Optional service for customer operations
            supplier_service: Optional service for supplier operations
            purchase_service: Optional service for purchase operations
            file_service: Optional service for file storage
        """
        self.session = session
        self.repository = repository
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service
        self.material_service = material_service
        self.inventory_service = inventory_service
        self.project_service = project_service
        self.sale_service = sale_service
        self.customer_service = customer_service
        self.supplier_service = supplier_service
        self.purchase_service = purchase_service
        self.file_service = file_service

        # Register report generators
        self.report_generators = {
            ReportType.INVENTORY_STATUS.value: self._generate_inventory_status_report,
            ReportType.SALES_ANALYSIS.value: self._generate_sales_analysis_report,
            ReportType.PROJECT_PERFORMANCE.value: self._generate_project_performance_report,
            ReportType.MATERIALS_USAGE.value: self._generate_materials_usage_report,
            ReportType.FINANCIAL_SUMMARY.value: self._generate_financial_summary_report,
            ReportType.CUSTOMER_ANALYSIS.value: self._generate_customer_analysis_report,
            ReportType.PRODUCTION_EFFICIENCY.value: self._generate_production_efficiency_report,
            ReportType.SUPPLIER_PERFORMANCE.value: self._generate_supplier_performance_report,
        }

        # Register format converters
        self.format_converters = {
            ReportFormat.JSON.value: self._convert_to_json,
            ReportFormat.CSV.value: self._convert_to_csv,
            ReportFormat.EXCEL.value: self._convert_to_excel,
            ReportFormat.PDF.value: self._convert_to_pdf,
            ReportFormat.HTML.value: self._convert_to_html,
        }

    def generate_report(
        self,
        report_type: str,
        parameters: Dict[str, Any] = None,
        format: str = "json",
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a report with the specified type and parameters.

        Args:
            report_type: Type of report to generate
            parameters: Optional parameters for report customization
            format: Output format (json, csv, excel, pdf, html)
            include_metadata: Whether to include metadata in the response

        Returns:
            Dictionary with report data and metadata

        Raises:
            ValidationException: If validation fails
            BusinessRuleException: If report type not supported
        """
        # Validate report type
        if (
            report_type not in self.report_generators
            and report_type != ReportType.CUSTOM.value
        ):
            supported_types = list(self.report_generators.keys())
            supported_types.append(ReportType.CUSTOM.value)

            raise ValidationException(
                f"Unsupported report type: {report_type}",
                {"report_type": [f"Must be one of: {', '.join(supported_types)}"]},
            )

        # Validate format
        if format not in self.format_converters:
            supported_formats = list(self.format_converters.keys())

            raise ValidationException(
                f"Unsupported report format: {format}",
                {"format": [f"Must be one of: {', '.join(supported_formats)}"]},
            )

        # Initialize parameters if None
        parameters = parameters or {}

        try:
            start_time = datetime.now()

            # Generate report ID
            report_id = str(uuid.uuid4())

            # Generate raw report data
            if report_type == ReportType.CUSTOM.value:
                # Custom report requires query definition
                if "query_definition" not in parameters:
                    raise ValidationException(
                        "Custom report requires query definition",
                        {
                            "query_definition": [
                                "This field is required for custom reports"
                            ]
                        },
                    )

                report_data = self._generate_custom_report(parameters)
            else:
                # Standard report type
                generator = self.report_generators[report_type]
                report_data = generator(parameters)

            # Convert to requested format
            converter = self.format_converters[format]
            formatted_data = converter(report_data)

            # Generate metadata
            metadata = {
                "id": report_id,
                "type": report_type,
                "format": format,
                "generated_at": datetime.now().isoformat(),
                "parameters": parameters,
                "generated_by": (
                    self.security_context.current_user.id
                    if self.security_context
                    and hasattr(self.security_context, "current_user")
                    else None
                ),
                "row_count": (
                    len(report_data.get("data", []))
                    if isinstance(report_data.get("data"), list)
                    else None
                ),
                "execution_time_ms": int(
                    (datetime.now() - start_time).total_seconds() * 1000
                ),
            }

            # Save report if repository is available
            if self.repository:
                # Prepare report record
                report_record = {
                    "id": report_id,
                    "type": report_type,
                    "format": format,
                    "parameters": json.dumps(parameters),
                    "generated_at": datetime.now(),
                    "generated_by": metadata["generated_by"],
                    "metadata": json.dumps(metadata),
                }

                # Store formatted data if file service is available, otherwise store in repository
                if self.file_service and isinstance(formatted_data, bytes):
                    file_metadata = self.file_service.store_file(
                        file_data=formatted_data,
                        filename=f"report_{report_id}.{format}",
                        content_type=self._get_content_type(format),
                        metadata={"report_id": report_id, "report_type": report_type},
                    )

                    report_record["file_id"] = file_metadata.get("id")
                else:
                    # Store in repository (if data is not too large)
                    max_size = 1024 * 1024  # 1MB limit

                    if (
                        isinstance(formatted_data, bytes)
                        and len(formatted_data) <= max_size
                    ):
                        report_record["data"] = formatted_data
                    elif (
                        isinstance(formatted_data, str)
                        and len(formatted_data) <= max_size
                    ):
                        report_record["data"] = formatted_data
                    elif isinstance(formatted_data, Dict):
                        json_data = json.dumps(formatted_data)
                        if len(json_data) <= max_size:
                            report_record["data"] = json_data

                # Save report record
                self.repository.create(report_record)

            # Publish event if event bus exists
            if self.event_bus:
                self.event_bus.publish(
                    ReportGenerated(
                        report_id=report_id,
                        report_type=report_type,
                        format=format,
                        user_id=metadata["generated_by"],
                    )
                )

            # Prepare result
            result = {}

            if include_metadata:
                result["metadata"] = metadata

            # Include data based on format
            if format == ReportFormat.JSON.value:
                result["data"] = formatted_data
            else:
                # For non-JSON formats, return a download URL or base64 encoded data
                if (
                    self.file_service
                    and isinstance(formatted_data, bytes)
                    and report_record.get("file_id")
                ):
                    result["file_id"] = report_record["file_id"]
                    result["download_url"] = f"/api/reports/{report_id}/download"
                else:
                    # Include base64 encoded data
                    import base64

                    if isinstance(formatted_data, bytes):
                        result["data_base64"] = base64.b64encode(formatted_data).decode(
                            "utf-8"
                        )
                    elif isinstance(formatted_data, str):
                        result["data"] = formatted_data
                    else:
                        result["data"] = formatted_data

            return result

        except Exception as e:
            logger.error(
                f"Failed to generate {report_type} report: {str(e)}", exc_info=True
            )

            if isinstance(e, (ValidationException, BusinessRuleException)):
                raise

            raise BusinessRuleException(
                f"Failed to generate report: {str(e)}", "REPORT_001"
            )

    def get_report(self, report_id: str, include_data: bool = True) -> Dict[str, Any]:
        """
        Get a previously generated report.

        Args:
            report_id: ID of the report
            include_data: Whether to include report data

        Returns:
            Report with metadata and optionally data

        Raises:
            EntityNotFoundException: If report not found
        """
        # Check if repository is available
        if not self.repository:
            raise BusinessRuleException("Report storage not available", "REPORT_002")

        # Get report from repository
        report = self.repository.get_by_id(report_id)

        if not report:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("Report", report_id)

        # Convert to dictionary
        result = report.to_dict() if hasattr(report, "to_dict") else dict(report)

        # Parse metadata
        if "metadata" in result and isinstance(result["metadata"], str):
            try:
                result["metadata"] = json.loads(result["metadata"])
            except Exception:
                pass

        # Parse parameters
        if "parameters" in result and isinstance(result["parameters"], str):
            try:
                result["parameters"] = json.loads(result["parameters"])
            except Exception:
                pass

        # Include data if requested
        if include_data:
            # If data is in repository
            if hasattr(report, "data") and report.data:
                data = report.data

                # Parse JSON data if format is JSON
                if (
                    hasattr(report, "format")
                    and report.format == ReportFormat.JSON.value
                    and isinstance(data, str)
                ):
                    try:
                        result["data"] = json.loads(data)
                    except Exception:
                        result["data"] = data
                else:
                    result["data"] = data

            # If data is in file storage
            elif hasattr(report, "file_id") and report.file_id and self.file_service:
                try:
                    file_data, file_metadata = self.file_service.retrieve_file(
                        report.file_id
                    )

                    # For JSON data, parse and include directly
                    if (
                        hasattr(report, "format")
                        and report.format == ReportFormat.JSON.value
                    ):
                        try:
                            result["data"] = json.loads(file_data.decode("utf-8"))
                        except Exception:
                            # Include base64 encoded data
                            import base64

                            result["data_base64"] = base64.b64encode(file_data).decode(
                                "utf-8"
                            )
                    else:
                        # Include base64 encoded data for other formats
                        import base64

                        result["data_base64"] = base64.b64encode(file_data).decode(
                            "utf-8"
                        )

                    # Include download URL
                    result["download_url"] = f"/api/reports/{report_id}/download"

                except Exception as e:
                    logger.error(
                        f"Failed to retrieve report file: {str(e)}", exc_info=True
                    )
                    result["data_error"] = f"Failed to retrieve report file: {str(e)}"

        return result

    def download_report(self, report_id: str) -> Tuple[bytes, str, str]:
        """
        Download a report file.

        Args:
            report_id: ID of the report

        Returns:
            Tuple of (file_data, filename, content_type)

        Raises:
            EntityNotFoundException: If report not found
            BusinessRuleException: If report file not available
        """
        # Check if repository is available
        if not self.repository:
            raise BusinessRuleException("Report storage not available", "REPORT_002")

        # Get report from repository
        report = self.repository.get_by_id(report_id)

        if not report:
            from app.core.exceptions import EntityNotFoundException

            raise EntityNotFoundException("Report", report_id)

        # Get file data
        file_data = None
        filename = f"report_{report_id}"
        content_type = "application/octet-stream"

        # If file is in repository
        if hasattr(report, "data") and report.data:
            file_data = report.data

            # Convert to bytes if string
            if isinstance(file_data, str):
                file_data = file_data.encode("utf-8")

        # If file is in file storage
        elif hasattr(report, "file_id") and report.file_id and self.file_service:
            try:
                file_data, file_metadata = self.file_service.retrieve_file(
                    report.file_id
                )

                # Get filename from metadata if available
                if file_metadata and "original_filename" in file_metadata:
                    filename = file_metadata["original_filename"]

                # Get content type from metadata if available
                if file_metadata and "content_type" in file_metadata:
                    content_type = file_metadata["content_type"]

            except Exception as e:
                logger.error(f"Failed to retrieve report file: {str(e)}", exc_info=True)
                raise BusinessRuleException(
                    f"Failed to retrieve report file: {str(e)}", "REPORT_003"
                )
        else:
            raise BusinessRuleException("Report file not available", "REPORT_004")

        # Set filename extension based on format
        if hasattr(report, "format"):
            if report.format == ReportFormat.JSON.value:
                filename = f"{filename}.json"
                content_type = "application/json"
            elif report.format == ReportFormat.CSV.value:
                filename = f"{filename}.csv"
                content_type = "text/csv"
            elif report.format == ReportFormat.EXCEL.value:
                filename = f"{filename}.xlsx"
                content_type = (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            elif report.format == ReportFormat.PDF.value:
                filename = f"{filename}.pdf"
                content_type = "application/pdf"
            elif report.format == ReportFormat.HTML.value:
                filename = f"{filename}.html"
                content_type = "text/html"

        return file_data, filename, content_type

    def get_available_reports(self) -> List[Dict[str, Any]]:
        """
        Get list of available report types with descriptions.

        Returns:
            List of available report types
        """
        return [
            {
                "type": ReportType.INVENTORY_STATUS.value,
                "name": "Inventory Status",
                "description": "Current inventory levels, low stock alerts, and valuation",
                "parameters": [
                    {
                        "name": "status",
                        "type": "string",
                        "description": "Filter by inventory status",
                        "required": False,
                    },
                    {
                        "name": "material_type",
                        "type": "string",
                        "description": "Filter by material type",
                        "required": False,
                    },
                    {
                        "name": "low_stock_only",
                        "type": "boolean",
                        "description": "Show only low stock items",
                        "required": False,
                    },
                ],
            },
            {
                "type": ReportType.SALES_ANALYSIS.value,
                "name": "Sales Analysis",
                "description": "Sales performance, trends, and product popularity",
                "parameters": [
                    {
                        "name": "start_date",
                        "type": "date",
                        "description": "Start date for analysis",
                        "required": False,
                    },
                    {
                        "name": "end_date",
                        "type": "date",
                        "description": "End date for analysis",
                        "required": False,
                    },
                    {
                        "name": "group_by",
                        "type": "string",
                        "description": "Grouping field (day, week, month, product, customer)",
                        "required": False,
                    },
                ],
            },
            {
                "type": ReportType.PROJECT_PERFORMANCE.value,
                "name": "Project Performance",
                "description": "Project timelines, status distribution, and completion metrics",
                "parameters": [
                    {
                        "name": "start_date",
                        "type": "date",
                        "description": "Start date for analysis",
                        "required": False,
                    },
                    {
                        "name": "end_date",
                        "type": "date",
                        "description": "End date for analysis",
                        "required": False,
                    },
                    {
                        "name": "status",
                        "type": "string",
                        "description": "Filter by project status",
                        "required": False,
                    },
                    {
                        "name": "project_type",
                        "type": "string",
                        "description": "Filter by project type",
                        "required": False,
                    },
                ],
            },
            {
                "type": ReportType.MATERIALS_USAGE.value,
                "name": "Materials Usage",
                "description": "Material consumption, waste tracking, and cost analysis",
                "parameters": [
                    {
                        "name": "start_date",
                        "type": "date",
                        "description": "Start date for analysis",
                        "required": False,
                    },
                    {
                        "name": "end_date",
                        "type": "date",
                        "description": "End date for analysis",
                        "required": False,
                    },
                    {
                        "name": "material_type",
                        "type": "string",
                        "description": "Filter by material type",
                        "required": False,
                    },
                    {
                        "name": "group_by",
                        "type": "string",
                        "description": "Grouping field (material, project, customer)",
                        "required": False,
                    },
                ],
            },
            {
                "type": ReportType.FINANCIAL_SUMMARY.value,
                "name": "Financial Summary",
                "description": "Revenue, expenses, profit margins, and financial trends",
                "parameters": [
                    {
                        "name": "start_date",
                        "type": "date",
                        "description": "Start date for analysis",
                        "required": False,
                    },
                    {
                        "name": "end_date",
                        "type": "date",
                        "description": "End date for analysis",
                        "required": False,
                    },
                    {
                        "name": "period",
                        "type": "string",
                        "description": "Summary period (day, week, month, quarter, year)",
                        "required": False,
                    },
                ],
            },
            {
                "type": ReportType.CUSTOMER_ANALYSIS.value,
                "name": "Customer Analysis",
                "description": "Customer segmentation, ordering patterns, and lifetime value",
                "parameters": [
                    {
                        "name": "start_date",
                        "type": "date",
                        "description": "Start date for analysis",
                        "required": False,
                    },
                    {
                        "name": "end_date",
                        "type": "date",
                        "description": "End date for analysis",
                        "required": False,
                    },
                    {
                        "name": "customer_type",
                        "type": "string",
                        "description": "Filter by customer type",
                        "required": False,
                    },
                    {
                        "name": "include_inactive",
                        "type": "boolean",
                        "description": "Include inactive customers",
                        "required": False,
                    },
                ],
            },
            {
                "type": ReportType.PRODUCTION_EFFICIENCY.value,
                "name": "Production Efficiency",
                "description": "Production time analysis, bottlenecks, and efficiency metrics",
                "parameters": [
                    {
                        "name": "start_date",
                        "type": "date",
                        "description": "Start date for analysis",
                        "required": False,
                    },
                    {
                        "name": "end_date",
                        "type": "date",
                        "description": "End date for analysis",
                        "required": False,
                    },
                    {
                        "name": "project_type",
                        "type": "string",
                        "description": "Filter by project type",
                        "required": False,
                    },
                ],
            },
            {
                "type": ReportType.SUPPLIER_PERFORMANCE.value,
                "name": "Supplier Performance",
                "description": "Supplier reliability, pricing trends, and delivery performance",
                "parameters": [
                    {
                        "name": "start_date",
                        "type": "date",
                        "description": "Start date for analysis",
                        "required": False,
                    },
                    {
                        "name": "end_date",
                        "type": "date",
                        "description": "End date for analysis",
                        "required": False,
                    },
                    {
                        "name": "supplier_id",
                        "type": "string",
                        "description": "Filter by specific supplier",
                        "required": False,
                    },
                    {
                        "name": "material_type",
                        "type": "string",
                        "description": "Filter by material type",
                        "required": False,
                    },
                ],
            },
            {
                "type": ReportType.CUSTOM.value,
                "name": "Custom Report",
                "description": "Custom report with user-defined query",
                "parameters": [
                    {
                        "name": "query_definition",
                        "type": "object",
                        "description": "Query definition object",
                        "required": True,
                    },
                    {
                        "name": "title",
                        "type": "string",
                        "description": "Report title",
                        "required": False,
                    },
                    {
                        "name": "description",
                        "type": "string",
                        "description": "Report description",
                        "required": False,
                    },
                ],
            },
        ]

    def get_recent_reports(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get list of recently generated reports.

        Args:
            limit: Maximum number of reports to return

        Returns:
            List of recent reports
        """
        # Check if repository is available
        if not self.repository:
            return []

        # Get recent reports
        reports = self.repository.list(
            limit=limit, sort_by="generated_at", sort_dir="desc"
        )

        # Convert to list of dictionaries
        result = []

        for report in reports:
            report_dict = (
                report.to_dict() if hasattr(report, "to_dict") else dict(report)
            )

            # Parse metadata
            if "metadata" in report_dict and isinstance(report_dict["metadata"], str):
                try:
                    report_dict["metadata"] = json.loads(report_dict["metadata"])
                except Exception:
                    pass

            # Parse parameters
            if "parameters" in report_dict and isinstance(
                report_dict["parameters"], str
            ):
                try:
                    report_dict["parameters"] = json.loads(report_dict["parameters"])
                except Exception:
                    pass

            # Remove data for efficiency
            if "data" in report_dict:
                del report_dict["data"]

            result.append(report_dict)

        return result

    def schedule_report(
        self,
        report_type: str,
        parameters: Dict[str, Any],
        schedule_settings: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Schedule a report for automatic generation.

        Args:
            report_type: Type of report to generate
            parameters: Parameters for report generation
            schedule_settings: Settings for scheduling
                Required fields:
                - recurrence: Recurrence pattern (daily, weekly, monthly)
                Optional fields:
                - start_date: Start date for scheduling
                - end_date: End date for scheduling
                - time: Time of day to generate report
                - day_of_week: Day of week for weekly recurrence
                - day_of_month: Day of month for monthly recurrence
                - format: Output format
                - recipients: List of email recipients

        Returns:
            Dictionary with schedule details

        Raises:
            ValidationException: If validation fails
        """
        # Validate report type
        if (
            report_type not in self.report_generators
            and report_type != ReportType.CUSTOM.value
        ):
            supported_types = list(self.report_generators.keys())
            supported_types.append(ReportType.CUSTOM.value)

            raise ValidationException(
                f"Unsupported report type: {report_type}",
                {"report_type": [f"Must be one of: {', '.join(supported_types)}"]},
            )

        # Validate schedule settings
        if "recurrence" not in schedule_settings:
            raise ValidationException(
                "Recurrence pattern is required",
                {"recurrence": ["This field is required"]},
            )

        # Generate schedule ID
        schedule_id = str(uuid.uuid4())

        # Set default values
        if "start_date" not in schedule_settings:
            schedule_settings["start_date"] = datetime.now().date().isoformat()

        if "format" not in schedule_settings:
            schedule_settings["format"] = ReportFormat.PDF.value

        # Save schedule if repository is available
        if self.repository:
            # Prepare schedule record
            schedule_record = {
                "id": schedule_id,
                "report_type": report_type,
                "parameters": json.dumps(parameters),
                "schedule_settings": json.dumps(schedule_settings),
                "created_at": datetime.now(),
                "created_by": (
                    self.security_context.current_user.id
                    if self.security_context
                    and hasattr(self.security_context, "current_user")
                    else None
                ),
                "active": True,
            }

            # Save to repository
            self.repository.create_schedule(schedule_record)

        # Publish event if event bus exists
        if self.event_bus:
            self.event_bus.publish(
                ReportScheduled(
                    schedule_id=schedule_id,
                    report_type=report_type,
                    recurrence=schedule_settings["recurrence"],
                    user_id=(
                        schedule_record.get("created_by")
                        if "schedule_record" in locals()
                        else None
                    ),
                )
            )

        # Return schedule details
        return {
            "id": schedule_id,
            "report_type": report_type,
            "parameters": parameters,
            "schedule_settings": schedule_settings,
            "created_at": datetime.now().isoformat(),
            "active": True,
        }

    def run_scheduled_reports(self) -> Dict[str, Any]:
        """
        Run scheduled reports that are due.

        This method is typically called by a scheduled task.

        Returns:
            Dictionary with execution results
        """
        # Check if repository is available
        if not self.repository:
            return {
                "success": False,
                "error": "Report repository not available",
                "executed": 0,
                "succeeded": 0,
                "failed": 0,
            }

        # Get active schedules
        schedules = self.repository.list_schedules(active=True)

        results = {
            "success": True,
            "executed": 0,
            "succeeded": 0,
            "failed": 0,
            "details": [],
        }

        # Check each schedule
        for schedule in schedules:
            try:
                # Parse schedule settings
                settings = (
                    json.loads(schedule.schedule_settings)
                    if hasattr(schedule, "schedule_settings")
                    and isinstance(schedule.schedule_settings, str)
                    else {}
                )

                # Check if schedule is due
                if not self._is_schedule_due(settings):
                    continue

                # Parse parameters
                parameters = (
                    json.loads(schedule.parameters)
                    if hasattr(schedule, "parameters")
                    and isinstance(schedule.parameters, str)
                    else {}
                )

                # Generate report
                report = self.generate_report(
                    report_type=schedule.report_type,
                    parameters=parameters,
                    format=settings.get("format", ReportFormat.PDF.value),
                )

                results["executed"] += 1
                results["succeeded"] += 1
                results["details"].append(
                    {
                        "schedule_id": schedule.id,
                        "report_id": (
                            report["metadata"]["id"] if "metadata" in report else None
                        ),
                        "report_type": schedule.report_type,
                        "success": True,
                    }
                )

                # Send report to recipients if specified
                if (
                    "recipients" in settings
                    and settings["recipients"]
                    and isinstance(settings["recipients"], list)
                ):
                    self._send_report_to_recipients(
                        report_id=(
                            report["metadata"]["id"] if "metadata" in report else None
                        ),
                        recipients=settings["recipients"],
                        report_type=schedule.report_type,
                        parameters=parameters,
                    )
            except Exception as e:
                logger.error(
                    f"Failed to execute scheduled report {schedule.id}: {str(e)}",
                    exc_info=True,
                )

                results["executed"] += 1
                results["failed"] += 1
                results["details"].append(
                    {
                        "schedule_id": schedule.id,
                        "report_type": (
                            schedule.report_type
                            if hasattr(schedule, "report_type")
                            else None
                        ),
                        "success": False,
                        "error": str(e),
                    }
                )

        return results

    def _generate_inventory_status_report(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate inventory status report.

        Args:
            parameters: Report parameters

        Returns:
            Dictionary with report data
        """
        # Check if inventory service is available
        if not self.inventory_service and not self.material_service:
            raise BusinessRuleException(
                "Inventory or material service not available", "REPORT_101"
            )

        # Extract parameters
        status = parameters.get("status")
        material_type = parameters.get("material_type")
        low_stock_only = parameters.get("low_stock_only", False)

        # Get inventory data
        inventory_data = []

        if self.inventory_service:
            # Get inventory items
            filters = {}

            if status:
                filters["status"] = status

            inventory_items = self.inventory_service.list_inventory(**filters)

            for item in inventory_items:
                item_dict = item.to_dict() if hasattr(item, "to_dict") else dict(item)

                # Add to data if it passes all filters
                if (
                    material_type
                    and hasattr(item, "materialType")
                    and item.materialType != material_type
                ):
                    continue

                if low_stock_only:
                    # Skip if not low stock
                    if not (
                        hasattr(item, "status")
                        and item.status
                        in ["LOW_STOCK", "CRITICALLY_LOW", "OUT_OF_STOCK"]
                    ):
                        if not (
                            hasattr(item, "quantity")
                            and hasattr(item, "reorderPoint")
                            and item.quantity <= item.reorderPoint
                        ):
                            continue

                inventory_data.append(item_dict)
        elif self.material_service:
            # Get materials
            filters = {}

            if status:
                filters["status"] = status

            if material_type:
                filters["materialType"] = material_type

            materials = self.material_service.list_materials(**filters)

            for material in materials:
                material_dict = (
                    material.to_dict()
                    if hasattr(material, "to_dict")
                    else dict(material)
                )

                # Add to data if it passes all filters
                if low_stock_only:
                    # Skip if not low stock
                    if not (
                        hasattr(material, "status")
                        and material.status
                        in ["LOW_STOCK", "CRITICALLY_LOW", "OUT_OF_STOCK"]
                    ):
                        if not (
                            hasattr(material, "quantity")
                            and hasattr(material, "reorderPoint")
                            and material.quantity <= material.reorderPoint
                        ):
                            continue

                inventory_data.append(material_dict)

        # Calculate summary statistics
        total_items = len(inventory_data)
        total_value = sum(
            item.get("value", item.get("quantity", 0) * item.get("cost", 0))
            for item in inventory_data
            if isinstance(item, dict)
        )

        low_stock_count = sum(
            1
            for item in inventory_data
            if isinstance(item, dict)
            and (
                item.get("status") in ["LOW_STOCK", "CRITICALLY_LOW", "OUT_OF_STOCK"]
                or (
                    item.get("quantity", 0) <= item.get("reorderPoint", 0)
                    and item.get("reorderPoint", 0) > 0
                )
            )
        )

        out_of_stock_count = sum(
            1
            for item in inventory_data
            if isinstance(item, dict)
            and (item.get("status") == "OUT_OF_STOCK" or item.get("quantity", 0) == 0)
        )

        # Group by material type if available
        material_type_summary = {}
        for item in inventory_data:
            if isinstance(item, dict):
                item_type = item.get("materialType", item.get("type", "Unknown"))

                if item_type not in material_type_summary:
                    material_type_summary[item_type] = {
                        "count": 0,
                        "value": 0,
                        "low_stock_count": 0,
                    }

                material_type_summary[item_type]["count"] += 1
                material_type_summary[item_type]["value"] += item.get(
                    "value", item.get("quantity", 0) * item.get("cost", 0)
                )

                if item.get("status") in [
                    "LOW_STOCK",
                    "CRITICALLY_LOW",
                    "OUT_OF_STOCK",
                ] or (
                    item.get("quantity", 0) <= item.get("reorderPoint", 0)
                    and item.get("reorderPoint", 0) > 0
                ):
                    material_type_summary[item_type]["low_stock_count"] += 1

        # Generate report data
        report_data = {
            "title": "Inventory Status Report",
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_items": total_items,
                "total_value": total_value,
                "low_stock_count": low_stock_count,
                "low_stock_percentage": (
                    (low_stock_count / total_items * 100) if total_items > 0 else 0
                ),
                "out_of_stock_count": out_of_stock_count,
                "out_of_stock_percentage": (
                    (out_of_stock_count / total_items * 100) if total_items > 0 else 0
                ),
            },
            "material_type_summary": material_type_summary,
            "parameters": parameters,
            "data": inventory_data,
        }

        return report_data

    def _generate_sales_analysis_report(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate sales analysis report.

        Args:
            parameters: Report parameters

        Returns:
            Dictionary with report data
        """
        # Check if sale service is available
        if not self.sale_service:
            raise BusinessRuleException("Sale service not available", "REPORT_102")

        # Extract parameters
        start_date = parameters.get("start_date")
        end_date = parameters.get("end_date")
        group_by = parameters.get("group_by", "month")

        # Parse dates if provided as strings
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))

        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

        # Default to last 30 days if not provided
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)

        if not end_date:
            end_date = datetime.now()

        # Get sales data
        sales = self.sale_service.list_sales(
            created_at_gte=start_date, created_at_lte=end_date
        )

        # Convert to dictionaries
        sales_data = [
            sale.to_dict() if hasattr(sale, "to_dict") else dict(sale) for sale in sales
        ]

        # Calculate summary statistics
        total_sales = len(sales_data)
        total_revenue = sum(
            sale.get("total_amount", 0) for sale in sales_data if isinstance(sale, dict)
        )
        avg_order_value = total_revenue / total_sales if total_sales > 0 else 0

        # Group data
        grouped_data = self._group_sales_data(sales_data, group_by)

        # Calculate top products
        top_products = self._calculate_top_products(sales_data)

        # Generate report data
        report_data = {
            "title": "Sales Analysis Report",
            "generated_at": datetime.now().isoformat(),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": {
                "total_sales": total_sales,
                "total_revenue": total_revenue,
                "avg_order_value": avg_order_value,
                "top_products": top_products[:5],  # Top 5 products
            },
            "grouped_data": grouped_data,
            "parameters": parameters,
            "data": sales_data,
        }

        return report_data

    def _generate_project_performance_report(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate project performance report.

        Args:
            parameters: Report parameters

        Returns:
            Dictionary with report data
        """
        # Check if project service is available
        if not self.project_service:
            raise BusinessRuleException("Project service not available", "REPORT_103")

        # Extract parameters
        start_date = parameters.get("start_date")
        end_date = parameters.get("end_date")
        status = parameters.get("status")
        project_type = parameters.get("project_type")

        # Parse dates if provided as strings
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))

        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

        # Default to last 90 days if not provided
        if not start_date:
            start_date = datetime.now() - timedelta(days=90)

        if not end_date:
            end_date = datetime.now()

        # Prepare filters
        filters = {"created_at_gte": start_date, "created_at_lte": end_date}

        if status:
            filters["status"] = status

        if project_type:
            filters["type"] = project_type

        # Get project data
        projects = self.project_service.list_projects(**filters)

        # Convert to dictionaries
        project_data = [
            project.to_dict() if hasattr(project, "to_dict") else dict(project)
            for project in projects
        ]

        # Calculate summary statistics
        total_projects = len(project_data)
        completed_projects = sum(
            1
            for project in project_data
            if isinstance(project, dict) and project.get("status") == "COMPLETED"
        )

        # Calculate on-time completion rate
        on_time_count = 0
        delayed_count = 0

        for project in project_data:
            if not isinstance(project, dict):
                continue

            if project.get("status") != "COMPLETED":
                continue

            due_date = project.get("dueDate")
            completed_date = project.get("completedDate")

            if not due_date or not completed_date:
                continue

            # Parse dates if they're strings
            if isinstance(due_date, str):
                due_date = datetime.fromisoformat(due_date.replace("Z", "+00:00"))

            if isinstance(completed_date, str):
                completed_date = datetime.fromisoformat(
                    completed_date.replace("Z", "+00:00")
                )

            if completed_date <= due_date:
                on_time_count += 1
            else:
                delayed_count += 1

        on_time_rate = (
            (on_time_count / completed_projects * 100) if completed_projects > 0 else 0
        )

        # Group by status
        status_counts = {}
        for project in project_data:
            if not isinstance(project, dict):
                continue

            status = project.get("status", "Unknown")
            if status not in status_counts:
                status_counts[status] = 0

            status_counts[status] += 1

        # Group by type
        type_counts = {}
        for project in project_data:
            if not isinstance(project, dict):
                continue

            project_type = project.get("type", "Unknown")
            if project_type not in type_counts:
                type_counts[project_type] = 0

            type_counts[project_type] += 1

        # Calculate average completion time
        completion_times = []
        for project in project_data:
            if not isinstance(project, dict):
                continue

            if project.get("status") != "COMPLETED":
                continue

            start_date = project.get("startDate")
            completed_date = project.get("completedDate")

            if not start_date or not completed_date:
                continue

            # Parse dates if they're strings
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))

            if isinstance(completed_date, str):
                completed_date = datetime.fromisoformat(
                    completed_date.replace("Z", "+00:00")
                )

            completion_time = (completed_date - start_date).days
            completion_times.append(completion_time)

        avg_completion_time = (
            sum(completion_times) / len(completion_times) if completion_times else 0
        )

        # Generate report data
        report_data = {
            "title": "Project Performance Report",
            "generated_at": datetime.now().isoformat(),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": {
                "total_projects": total_projects,
                "completed_projects": completed_projects,
                "completion_rate": (
                    (completed_projects / total_projects * 100)
                    if total_projects > 0
                    else 0
                ),
                "on_time_completion_rate": on_time_rate,
                "avg_completion_time": avg_completion_time,
            },
            "status_distribution": status_counts,
            "type_distribution": type_counts,
            "parameters": parameters,
            "data": project_data,
        }

        return report_data

    def _generate_materials_usage_report(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate materials usage report.

        Args:
            parameters: Report parameters

        Returns:
            Dictionary with report data
        """
        # Check if inventory transaction service is available
        if not self.inventory_service:
            raise BusinessRuleException("Inventory service not available", "REPORT_104")

        # Extract parameters
        start_date = parameters.get("start_date")
        end_date = parameters.get("end_date")
        material_type = parameters.get("material_type")
        group_by = parameters.get("group_by", "material")

        # Parse dates if provided as strings
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))

        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

        # Default to last 30 days if not provided
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)

        if not end_date:
            end_date = datetime.now()

        # Prepare filters
        filters = {
            "transaction_date_gte": start_date,
            "transaction_date_lte": end_date,
            "transaction_type": "USAGE",
        }

        if material_type:
            filters["material_type"] = material_type

        # Get transaction data
        transactions = self.inventory_service.list_transactions(**filters)

        # Convert to dictionaries
        transaction_data = [
            (
                transaction.to_dict()
                if hasattr(transaction, "to_dict")
                else dict(transaction)
            )
            for transaction in transactions
        ]

        # Calculate summary statistics
        total_transactions = len(transaction_data)
        total_usage_quantity = sum(
            abs(transaction.get("quantity_change", 0))
            for transaction in transaction_data
            if isinstance(transaction, dict)
            and transaction.get("quantity_change", 0) < 0
        )

        # Group data based on group_by parameter
        grouped_data = {}

        for transaction in transaction_data:
            if not isinstance(transaction, dict):
                continue

            # Skip transactions that aren't usage (positive quantity changes)
            if transaction.get("quantity_change", 0) >= 0:
                continue

            # Determine group key
            if group_by == "material":
                group_key = transaction.get("material_id", "Unknown")

                # Add material name if available
                if self.material_service and group_key != "Unknown":
                    try:
                        material = self.material_service.get_by_id(group_key)
                        if material and hasattr(material, "name"):
                            group_key = material.name
                    except Exception:
                        pass

            elif group_by == "project":
                group_key = transaction.get("project_id", "Unknown")

                # Add project name if available
                if self.project_service and group_key != "Unknown":
                    try:
                        project = self.project_service.get_by_id(group_key)
                        if project and hasattr(project, "name"):
                            group_key = project.name
                    except Exception:
                        pass

            elif group_by == "customer":
                # Try to get customer through project
                project_id = transaction.get("project_id")
                group_key = "Unknown"

                if project_id and self.project_service:
                    try:
                        project = self.project_service.get_by_id(project_id)
                        if (
                            project
                            and hasattr(project, "customer_id")
                            and project.customer_id
                        ):
                            # Get customer name
                            if self.customer_service:
                                customer = self.customer_service.get_by_id(
                                    project.customer_id
                                )
                                if customer and hasattr(customer, "name"):
                                    group_key = customer.name
                            else:
                                group_key = str(project.customer_id)
                    except Exception:
                        pass
            else:
                # Default to material
                group_key = transaction.get("material_id", "Unknown")

            # Initialize group if needed
            if group_key not in grouped_data:
                grouped_data[group_key] = {
                    "usage_quantity": 0,
                    "usage_value": 0,
                    "transaction_count": 0,
                }

            # Add transaction data to group
            quantity = abs(transaction.get("quantity_change", 0))
            value = quantity * transaction.get("unit_cost", 0)

            grouped_data[group_key]["usage_quantity"] += quantity
            grouped_data[group_key]["usage_value"] += value
            grouped_data[group_key]["transaction_count"] += 1

        # Calculate top materials by usage
        top_materials = []
        if self.material_service:
            material_usage = {}

            for transaction in transaction_data:
                if not isinstance(transaction, dict):
                    continue

                # Skip transactions that aren't usage
                if transaction.get("quantity_change", 0) >= 0:
                    continue

                material_id = transaction.get("material_id")
                if not material_id:
                    continue

                if material_id not in material_usage:
                    material_usage[material_id] = {"quantity": 0, "value": 0}

                quantity = abs(transaction.get("quantity_change", 0))
                value = quantity * transaction.get("unit_cost", 0)

                material_usage[material_id]["quantity"] += quantity
                material_usage[material_id]["value"] += value

            # Get material details and sort by usage
            for material_id, usage in material_usage.items():
                try:
                    material = self.material_service.get_by_id(material_id)
                    if material:
                        material_dict = (
                            material.to_dict()
                            if hasattr(material, "to_dict")
                            else dict(material)
                        )

                        top_materials.append(
                            {
                                "id": material_id,
                                "name": material_dict.get(
                                    "name", f"Material {material_id}"
                                ),
                                "type": material_dict.get("materialType", "Unknown"),
                                "usage_quantity": usage["quantity"],
                                "usage_value": usage["value"],
                                "unit": material_dict.get("unit", "Unknown"),
                            }
                        )
                except Exception:
                    # Add without material details
                    top_materials.append(
                        {
                            "id": material_id,
                            "name": f"Material {material_id}",
                            "type": "Unknown",
                            "usage_quantity": usage["quantity"],
                            "usage_value": usage["value"],
                            "unit": "Unknown",
                        }
                    )

            # Sort by usage value
            top_materials.sort(key=lambda x: x["usage_value"], reverse=True)

        # Generate report data
        report_data = {
            "title": "Materials Usage Report",
            "generated_at": datetime.now().isoformat(),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": {
                "total_transactions": total_transactions,
                "total_usage_quantity": total_usage_quantity,
                "top_materials": top_materials[:5],  # Top 5 materials
            },
            "grouped_data": grouped_data,
            "parameters": parameters,
            "data": transaction_data,
        }

        return report_data

    def _generate_financial_summary_report(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate financial summary report.

        Args:
            parameters: Report parameters

        Returns:
            Dictionary with report data
        """
        # Check if sale and purchase services are available
        if not self.sale_service and not self.purchase_service:
            raise BusinessRuleException(
                "Sale or purchase service not available", "REPORT_105"
            )

        # Extract parameters
        start_date = parameters.get("start_date")
        end_date = parameters.get("end_date")
        period = parameters.get("period", "month")

        # Parse dates if provided as strings
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))

        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

        # Default to last 12 months if not provided
        if not start_date:
            start_date = datetime.now() - timedelta(days=365)

        if not end_date:
            end_date = datetime.now()

        # Get sales data
        sales_data = []
        if self.sale_service:
            sales = self.sale_service.list_sales(
                created_at_gte=start_date, created_at_lte=end_date
            )

            sales_data = [
                sale.to_dict() if hasattr(sale, "to_dict") else dict(sale)
                for sale in sales
            ]

        # Get purchase data
        purchases_data = []
        if self.purchase_service:
            purchases = self.purchase_service.list_purchases(
                created_at_gte=start_date, created_at_lte=end_date
            )

            purchases_data = [
                purchase.to_dict() if hasattr(purchase, "to_dict") else dict(purchase)
                for purchase in purchases
            ]

        # Group data by period
        period_data = {}

        # Group sales
        for sale in sales_data:
            if not isinstance(sale, dict):
                continue

            sale_date = sale.get("created_at")
            if not sale_date:
                continue

            # Parse date if it's a string
            if isinstance(sale_date, str):
                sale_date = datetime.fromisoformat(sale_date.replace("Z", "+00:00"))

            # Calculate period key
            if period == "day":
                period_key = sale_date.strftime("%Y-%m-%d")
            elif period == "week":
                # ISO week number
                period_key = f"{sale_date.strftime('%Y')}-W{sale_date.strftime('%V')}"
            elif period == "month":
                period_key = sale_date.strftime("%Y-%m")
            elif period == "quarter":
                quarter = (sale_date.month - 1) // 3 + 1
                period_key = f"{sale_date.strftime('%Y')}-Q{quarter}"
            elif period == "year":
                period_key = sale_date.strftime("%Y")
            else:
                # Default to month
                period_key = sale_date.strftime("%Y-%m")

            # Initialize period if needed
            if period_key not in period_data:
                period_data[period_key] = {
                    "revenue": 0,
                    "expenses": 0,
                    "profit": 0,
                    "margin": 0,
                    "sales_count": 0,
                    "purchase_count": 0,
                }

            # Add sale data
            period_data[period_key]["revenue"] += sale.get("total_amount", 0)
            period_data[period_key]["sales_count"] += 1

        # Group purchases
        for purchase in purchases_data:
            if not isinstance(purchase, dict):
                continue

            purchase_date = purchase.get("created_at")
            if not purchase_date:
                continue

            # Parse date if it's a string
            if isinstance(purchase_date, str):
                purchase_date = datetime.fromisoformat(
                    purchase_date.replace("Z", "+00:00")
                )

            # Calculate period key
            if period == "day":
                period_key = purchase_date.strftime("%Y-%m-%d")
            elif period == "week":
                # ISO week number
                period_key = (
                    f"{purchase_date.strftime('%Y')}-W{purchase_date.strftime('%V')}"
                )
            elif period == "month":
                period_key = purchase_date.strftime("%Y-%m")
            elif period == "quarter":
                quarter = (purchase_date.month - 1) // 3 + 1
                period_key = f"{purchase_date.strftime('%Y')}-Q{quarter}"
            elif period == "year":
                period_key = purchase_date.strftime("%Y")
            else:
                # Default to month
                period_key = purchase_date.strftime("%Y-%m")

            # Initialize period if needed
            if period_key not in period_data:
                period_data[period_key] = {
                    "revenue": 0,
                    "expenses": 0,
                    "profit": 0,
                    "margin": 0,
                    "sales_count": 0,
                    "purchase_count": 0,
                }

            # Add purchase data
            period_data[period_key]["expenses"] += purchase.get("total", 0)
            period_data[period_key]["purchase_count"] += 1

        # Calculate profit and margin for each period
        for period_key, data in period_data.items():
            data["profit"] = data["revenue"] - data["expenses"]
            data["margin"] = (
                (data["profit"] / data["revenue"] * 100) if data["revenue"] > 0 else 0
            )

        # Sort periods chronologically
        sorted_periods = sorted(period_data.keys())

        # Calculate overall summary
        total_revenue = sum(data["revenue"] for data in period_data.values())
        total_expenses = sum(data["expenses"] for data in period_data.values())
        total_profit = total_revenue - total_expenses
        overall_margin = (
            (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        )

        # Generate trend data
        revenue_trend = [period_data[period]["revenue"] for period in sorted_periods]
        expenses_trend = [period_data[period]["expenses"] for period in sorted_periods]
        profit_trend = [period_data[period]["profit"] for period in sorted_periods]
        margin_trend = [period_data[period]["margin"] for period in sorted_periods]

        # Generate report data
        report_data = {
            "title": "Financial Summary Report",
            "generated_at": datetime.now().isoformat(),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "grouping": period,
            },
            "summary": {
                "total_revenue": total_revenue,
                "total_expenses": total_expenses,
                "total_profit": total_profit,
                "overall_margin": overall_margin,
                "total_sales": len(sales_data),
                "total_purchases": len(purchases_data),
            },
            "period_data": {period: period_data[period] for period in sorted_periods},
            "trends": {
                "periods": sorted_periods,
                "revenue": revenue_trend,
                "expenses": expenses_trend,
                "profit": profit_trend,
                "margin": margin_trend,
            },
            "parameters": parameters,
        }

        return report_data

    def _generate_customer_analysis_report(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate customer analysis report.

        Args:
            parameters: Report parameters

        Returns:
            Dictionary with report data
        """
        # Check if customer and sale services are available
        if not self.customer_service or not self.sale_service:
            raise BusinessRuleException(
                "Customer or sale service not available", "REPORT_106"
            )

        # Extract parameters
        start_date = parameters.get("start_date")
        end_date = parameters.get("end_date")
        customer_type = parameters.get("customer_type")
        include_inactive = parameters.get("include_inactive", False)

        # Parse dates if provided as strings
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))

        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

        # Default to last 12 months if not provided
        if not start_date:
            start_date = datetime.now() - timedelta(days=365)

        if not end_date:
            end_date = datetime.now()

        # Get customer data
        filters = {}

        if customer_type:
            filters["type"] = customer_type

        if not include_inactive:
            filters["status"] = "ACTIVE"

        customers = self.customer_service.list_customers(**filters)

        # Convert to dictionaries
        customer_data = [
            customer.to_dict() if hasattr(customer, "to_dict") else dict(customer)
            for customer in customers
        ]

        # Get sales data
        sales = self.sale_service.list_sales(
            created_at_gte=start_date, created_at_lte=end_date
        )

        # Convert to dictionaries
        sales_data = [
            sale.to_dict() if hasattr(sale, "to_dict") else dict(sale) for sale in sales
        ]

        # Group sales by customer
        customer_sales = {}

        for sale in sales_data:
            if not isinstance(sale, dict):
                continue

            customer_id = sale.get("customer_id")
            if not customer_id:
                continue

            if customer_id not in customer_sales:
                customer_sales[customer_id] = {
                    "sales_count": 0,
                    "total_revenue": 0,
                    "avg_order_value": 0,
                    "first_purchase": None,
                    "last_purchase": None,
                    "purchases": [],
                }

            # Add sale data
            customer_sales[customer_id]["sales_count"] += 1
            customer_sales[customer_id]["total_revenue"] += sale.get("total_amount", 0)
            customer_sales[customer_id]["purchases"].append(sale)

        # Calculate additional metrics
        for customer_id, data in customer_sales.items():
            # Sort purchases by date
            purchases = sorted(
                data["purchases"],
                key=lambda s: (
                    s.get("created_at")
                    if isinstance(s.get("created_at"), datetime)
                    else (
                        datetime.fromisoformat(
                            s.get("created_at").replace("Z", "+00:00")
                        )
                        if isinstance(s.get("created_at"), str)
                        else datetime.min
                    )
                ),
            )

            # First and last purchase
            if purchases:
                data["first_purchase"] = purchases[0].get("created_at")
                data["last_purchase"] = purchases[-1].get("created_at")

                # Parse dates if they're strings
                if isinstance(data["first_purchase"], str):
                    data["first_purchase"] = datetime.fromisoformat(
                        data["first_purchase"].replace("Z", "+00:00")
                    )

                if isinstance(data["last_purchase"], str):
                    data["last_purchase"] = datetime.fromisoformat(
                        data["last_purchase"].replace("Z", "+00:00")
                    )

            # Average order value
            data["avg_order_value"] = (
                data["total_revenue"] / data["sales_count"]
                if data["sales_count"] > 0
                else 0
            )

            # Remove purchases list to reduce size
            del data["purchases"]

        # Add sales data to customer data
        for customer in customer_data:
            if not isinstance(customer, dict):
                continue

            customer_id = customer.get("id")
            if not customer_id or customer_id not in customer_sales:
                customer["sales_data"] = {
                    "sales_count": 0,
                    "total_revenue": 0,
                    "avg_order_value": 0,
                    "first_purchase": None,
                    "last_purchase": None,
                }
            else:
                customer["sales_data"] = customer_sales[customer_id]

        # Calculate customer segments
        segments = {"new": 0, "returning": 0, "inactive": 0, "high_value": 0}

        for customer in customer_data:
            if not isinstance(customer, dict):
                continue

            sales_data = customer.get("sales_data", {})
            sales_count = sales_data.get("sales_count", 0)
            last_purchase = sales_data.get("last_purchase")
            total_revenue = sales_data.get("total_revenue", 0)

            # Skip customers with no purchases
            if sales_count == 0:
                continue

            # New customers (first purchase within last 30 days)
            first_purchase = sales_data.get("first_purchase")
            if first_purchase and (end_date - first_purchase).days <= 30:
                segments["new"] += 1

            # Returning customers (multiple purchases)
            if sales_count > 1:
                segments["returning"] += 1

            # Inactive customers (no purchase in last 90 days)
            if last_purchase and (end_date - last_purchase).days > 90:
                segments["inactive"] += 1

            # High-value customers (revenue above threshold)
            avg_revenue = (
                sum(
                    sale.get("total_amount", 0)
                    for sale in sales_data
                    if isinstance(sale, dict)
                )
                / len(sales_data)
                if sales_data
                else 0
            )
            if total_revenue > avg_revenue * 2:  # Threshold: 2x average
                segments["high_value"] += 1

        # Calculate top customers by revenue
        top_customers = sorted(
            [c for c in customer_data if isinstance(c, dict)],
            key=lambda c: c.get("sales_data", {}).get("total_revenue", 0),
            reverse=True,
        )[
            :10
        ]  # Top 10

        # Generate report data
        report_data = {
            "title": "Customer Analysis Report",
            "generated_at": datetime.now().isoformat(),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": {
                "total_customers": len(customer_data),
                "active_customers": len(
                    [
                        c
                        for c in customer_data
                        if isinstance(c, dict)
                        and c.get("sales_data", {}).get("sales_count", 0) > 0
                    ]
                ),
                "segments": segments,
                "top_customers": [
                    {
                        "id": c.get("id"),
                        "name": c.get("name", f"Customer {c.get('id')}"),
                        "total_revenue": c.get("sales_data", {}).get(
                            "total_revenue", 0
                        ),
                        "sales_count": c.get("sales_data", {}).get("sales_count", 0),
                        "avg_order_value": c.get("sales_data", {}).get(
                            "avg_order_value", 0
                        ),
                    }
                    for c in top_customers
                ],
            },
            "parameters": parameters,
            "data": customer_data,
        }

        return report_data

    def _generate_production_efficiency_report(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate production efficiency report.

        Args:
            parameters: Report parameters

        Returns:
            Dictionary with report data
        """
        # Check if project service is available
        if not self.project_service:
            raise BusinessRuleException("Project service not available", "REPORT_107")

        # Extract parameters
        start_date = parameters.get("start_date")
        end_date = parameters.get("end_date")
        project_type = parameters.get("project_type")

        # Parse dates if provided as strings
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))

        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

        # Default to last 90 days if not provided
        if not start_date:
            start_date = datetime.now() - timedelta(days=90)

        if not end_date:
            end_date = datetime.now()

        # Prepare filters
        filters = {
            "completed_date_gte": start_date,
            "completed_date_lte": end_date,
            "status": "COMPLETED",
        }

        if project_type:
            filters["type"] = project_type

        # Get completed projects
        projects = self.project_service.list_projects(**filters)

        # Convert to dictionaries
        project_data = [
            project.to_dict() if hasattr(project, "to_dict") else dict(project)
            for project in projects
        ]

        # Calculate production metrics
        completion_times = []
        on_time_count = 0
        delayed_count = 0
        efficiency_scores = []

        for project in project_data:
            if not isinstance(project, dict):
                continue

            start_date = project.get("startDate")
            completed_date = project.get("completedDate")
            due_date = project.get("dueDate")

            if not start_date or not completed_date:
                continue

            # Parse dates if they're strings
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))

            if isinstance(completed_date, str):
                completed_date = datetime.fromisoformat(
                    completed_date.replace("Z", "+00:00")
                )

            if isinstance(due_date, str):
                due_date = datetime.fromisoformat(due_date.replace("Z", "+00:00"))

            # Calculate completion time in days
            completion_time = (completed_date - start_date).days
            completion_times.append(completion_time)

            # Check if completed on time
            if due_date:
                if completed_date <= due_date:
                    on_time_count += 1
                else:
                    delayed_count += 1

                # Calculate efficiency score (completion time / expected time)
                expected_time = (due_date - start_date).days
                if expected_time > 0:
                    efficiency = (
                        expected_time / completion_time if completion_time > 0 else 0
                    )
                    efficiency_scores.append(min(efficiency, 1.0))  # Cap at 100%

        # Group by project type
        type_efficiency = {}

        for project in project_data:
            if not isinstance(project, dict):
                continue

            project_type = project.get("type", "Unknown")

            if project_type not in type_efficiency:
                type_efficiency[project_type] = {
                    "count": 0,
                    "avg_completion_time": 0,
                    "total_completion_time": 0,
                    "efficiency_scores": [],
                }

            # Add project data
            type_efficiency[project_type]["count"] += 1

            # Add completion time if available
            start_date = project.get("startDate")
            completed_date = project.get("completedDate")

            if start_date and completed_date:
                # Parse dates if they're strings
                if isinstance(start_date, str):
                    start_date = datetime.fromisoformat(
                        start_date.replace("Z", "+00:00")
                    )

                if isinstance(completed_date, str):
                    completed_date = datetime.fromisoformat(
                        completed_date.replace("Z", "+00:00")
                    )

                completion_time = (completed_date - start_date).days
                type_efficiency[project_type][
                    "total_completion_time"
                ] += completion_time

                # Add efficiency score
                due_date = project.get("dueDate")
                if due_date:
                    if isinstance(due_date, str):
                        due_date = datetime.fromisoformat(
                            due_date.replace("Z", "+00:00")
                        )

                    expected_time = (due_date - start_date).days
                    if expected_time > 0 and completion_time > 0:
                        efficiency = expected_time / completion_time
                        type_efficiency[project_type]["efficiency_scores"].append(
                            min(efficiency, 1.0)
                        )

        # Calculate averages for each type
        for project_type, data in type_efficiency.items():
            if data["count"] > 0:
                data["avg_completion_time"] = (
                    data["total_completion_time"] / data["count"]
                )

            if data["efficiency_scores"]:
                data["avg_efficiency"] = sum(data["efficiency_scores"]) / len(
                    data["efficiency_scores"]
                )
            else:
                data["avg_efficiency"] = 0

            # Remove raw data to reduce size
            del data["efficiency_scores"]
            del data["total_completion_time"]

        # Calculate overall averages
        avg_completion_time = (
            sum(completion_times) / len(completion_times) if completion_times else 0
        )
        avg_efficiency = (
            sum(efficiency_scores) / len(efficiency_scores) if efficiency_scores else 0
        )
        on_time_rate = (
            (on_time_count / (on_time_count + delayed_count) * 100)
            if (on_time_count + delayed_count) > 0
            else 0
        )

        # Generate report data
        report_data = {
            "title": "Production Efficiency Report",
            "generated_at": datetime.now().isoformat(),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": {
                "total_projects": len(project_data),
                "avg_completion_time": avg_completion_time,
                "on_time_completion_rate": on_time_rate,
                "avg_efficiency": avg_efficiency,
                "efficiency_rating": self._get_efficiency_rating(avg_efficiency),
            },
            "by_project_type": type_efficiency,
            "parameters": parameters,
            "data": project_data,
        }

        return report_data

    def _generate_supplier_performance_report(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate supplier performance report.

        Args:
            parameters: Report parameters

        Returns:
            Dictionary with report data
        """
        # Check if supplier and purchase services are available
        if not self.supplier_service or not self.purchase_service:
            raise BusinessRuleException(
                "Supplier or purchase service not available", "REPORT_108"
            )

        # Extract parameters
        start_date = parameters.get("start_date")
        end_date = parameters.get("end_date")
        supplier_id = parameters.get("supplier_id")
        material_type = parameters.get("material_type")

        # Parse dates if provided as strings
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))

        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

        # Default to last 12 months if not provided
        if not start_date:
            start_date = datetime.now() - timedelta(days=365)

        if not end_date:
            end_date = datetime.now()

        # Get supplier data
        supplier_filters = {}

        if supplier_id:
            supplier_filters["id"] = supplier_id

        suppliers = self.supplier_service.list_suppliers(**supplier_filters)

        # Convert to dictionaries
        supplier_data = [
            supplier.to_dict() if hasattr(supplier, "to_dict") else dict(supplier)
            for supplier in suppliers
        ]

        # Get purchase data
        purchase_filters = {"created_at_gte": start_date, "created_at_lte": end_date}

        if supplier_id:
            purchase_filters["supplier_id"] = supplier_id

        purchases = self.purchase_service.list_purchases(**purchase_filters)

        # Convert to dictionaries
        purchase_data = [
            purchase.to_dict() if hasattr(purchase, "to_dict") else dict(purchase)
            for purchase in purchases
        ]

        # Filter for material type if specified
        if material_type:
            # Filter purchases by material type
            # This requires looking at purchase items
            filtered_purchases = []

            for purchase in purchase_data:
                if not isinstance(purchase, dict):
                    continue

                # Check if purchase has items
                items = purchase.get("items", [])

                # Check if any item matches the material type
                has_matching_item = False

                for item in items:
                    if not isinstance(item, dict):
                        continue

                    if item.get("materialType") == material_type:
                        has_matching_item = True
                        break

                if has_matching_item:
                    filtered_purchases.append(purchase)

            purchase_data = filtered_purchases

        # Group purchases by supplier
        supplier_purchases = {}

        for purchase in purchase_data:
            if not isinstance(purchase, dict):
                continue

            supplier_id = purchase.get("supplier_id")
            if not supplier_id:
                continue

            if supplier_id not in supplier_purchases:
                supplier_purchases[supplier_id] = {
                    "purchase_count": 0,
                    "total_spent": 0,
                    "purchases": [],
                }

            # Add purchase data
            supplier_purchases[supplier_id]["purchase_count"] += 1
            supplier_purchases[supplier_id]["total_spent"] += purchase.get("total", 0)
            supplier_purchases[supplier_id]["purchases"].append(purchase)

        # Calculate supplier performance metrics
        for supplier_id, data in supplier_purchases.items():
            # Sort purchases by date
            purchases = sorted(
                data["purchases"],
                key=lambda p: (
                    p.get("created_at")
                    if isinstance(p.get("created_at"), datetime)
                    else (
                        datetime.fromisoformat(
                            p.get("created_at").replace("Z", "+00:00")
                        )
                        if isinstance(p.get("created_at"), str)
                        else datetime.min
                    )
                ),
            )

            # Calculate delivery metrics
            on_time_deliveries = 0
            late_deliveries = 0
            delivery_times = []

            for purchase in purchases:
                # Check if purchase has delivery dates
                order_date = purchase.get("created_at")
                delivery_date = purchase.get("deliveryDate")
                expected_delivery_date = purchase.get("expectedDeliveryDate")

                if not order_date or not delivery_date:
                    continue

                # Parse dates if they're strings
                if isinstance(order_date, str):
                    order_date = datetime.fromisoformat(
                        order_date.replace("Z", "+00:00")
                    )

                if isinstance(delivery_date, str):
                    delivery_date = datetime.fromisoformat(
                        delivery_date.replace("Z", "+00:00")
                    )

                # Calculate delivery time
                delivery_time = (delivery_date - order_date).days
                delivery_times.append(delivery_time)

                # Check if delivered on time
                if expected_delivery_date:
                    if isinstance(expected_delivery_date, str):
                        expected_delivery_date = datetime.fromisoformat(
                            expected_delivery_date.replace("Z", "+00:00")
                        )

                    if delivery_date <= expected_delivery_date:
                        on_time_deliveries += 1
                    else:
                        late_deliveries += 1

            # Calculate metrics
            data["avg_delivery_time"] = (
                sum(delivery_times) / len(delivery_times) if delivery_times else 0
            )
            data["on_time_delivery_rate"] = (
                (on_time_deliveries / (on_time_deliveries + late_deliveries) * 100)
                if (on_time_deliveries + late_deliveries) > 0
                else 0
            )

            # Calculate quality metrics if available
            quality_ratings = []
            for purchase in purchases:
                if "qualityRating" in purchase:
                    quality_ratings.append(purchase["qualityRating"])

            data["avg_quality_rating"] = (
                sum(quality_ratings) / len(quality_ratings) if quality_ratings else 0
            )

            # Remove purchases list to reduce size
            del data["purchases"]

        # Add purchase data to supplier data
        for supplier in supplier_data:
            if not isinstance(supplier, dict):
                continue

            supplier_id = supplier.get("id")
            if not supplier_id or supplier_id not in supplier_purchases:
                supplier["purchase_data"] = {
                    "purchase_count": 0,
                    "total_spent": 0,
                    "avg_delivery_time": 0,
                    "on_time_delivery_rate": 0,
                    "avg_quality_rating": 0,
                }
            else:
                supplier["purchase_data"] = supplier_purchases[supplier_id]

        # Calculate top suppliers by spending
        top_suppliers = sorted(
            [s for s in supplier_data if isinstance(s, dict)],
            key=lambda s: s.get("purchase_data", {}).get("total_spent", 0),
            reverse=True,
        )[
            :10
        ]  # Top 10

        # Generate report data
        report_data = {
            "title": "Supplier Performance Report",
            "generated_at": datetime.now().isoformat(),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": {
                "total_suppliers": len(supplier_data),
                "active_suppliers": len(
                    [
                        s
                        for s in supplier_data
                        if isinstance(s, dict)
                        and s.get("purchase_data", {}).get("purchase_count", 0) > 0
                    ]
                ),
                "total_purchases": len(purchase_data),
                "total_spent": sum(
                    s.get("purchase_data", {}).get("total_spent", 0)
                    for s in supplier_data
                    if isinstance(s, dict)
                ),
                "top_suppliers": [
                    {
                        "id": s.get("id"),
                        "name": s.get("name", f"Supplier {s.get('id')}"),
                        "total_spent": s.get("purchase_data", {}).get("total_spent", 0),
                        "purchase_count": s.get("purchase_data", {}).get(
                            "purchase_count", 0
                        ),
                        "on_time_delivery_rate": s.get("purchase_data", {}).get(
                            "on_time_delivery_rate", 0
                        ),
                    }
                    for s in top_suppliers
                ],
            },
            "parameters": parameters,
            "data": supplier_data,
        }

        return report_data

    def _generate_custom_report(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate custom report based on query definition.

        Args:
            parameters: Report parameters including query_definition

        Returns:
            Dictionary with report data

        Raises:
            ValidationException: If query definition is invalid
        """
        # Extract query definition
        query_definition = parameters.get("query_definition")

        if not query_definition:
            raise ValidationException(
                "Query definition is required",
                {"query_definition": ["This field is required"]},
            )

        # Extract title and description
        title = parameters.get("title", "Custom Report")
        description = parameters.get(
            "description", "Custom report generated with user-defined query"
        )

        # Extract data source
        data_source = query_definition.get("data_source")

        if not data_source:
            raise ValidationException(
                "Data source is required",
                {"data_source": ["This field is required in query definition"]},
            )

        # Extract filters
        filters = query_definition.get("filters", {})

        # Extract grouping
        grouping = query_definition.get("grouping")

        # Extract sorting
        sorting = query_definition.get("sorting", {})

        # Extract fields
        fields = query_definition.get("fields", [])

        # Get service based on data source
        service = self._get_service_for_data_source(data_source)

        if not service:
            raise ValidationException(
                f"Unsupported data source: {data_source}",
                {"data_source": ["Invalid data source"]},
            )

        # Resolve data based on data source
        try:
            # Get data from appropriate service
            if data_source == "materials":
                data = service.list_materials(**filters)
            elif data_source == "inventory":
                data = service.list_inventory(**filters)
            elif data_source == "projects":
                data = service.list_projects(**filters)
            elif data_source == "sales":
                data = service.list_sales(**filters)
            elif data_source == "purchases":
                data = service.list_purchases(**filters)
            elif data_source == "customers":
                data = service.list_customers(**filters)
            elif data_source == "suppliers":
                data = service.list_suppliers(**filters)
            else:
                # Generic list method
                data = service.list(**filters)

            # Convert to dictionaries
            data = [
                item.to_dict() if hasattr(item, "to_dict") else dict(item)
                for item in data
            ]

            # Filter fields if specified
            if fields:
                filtered_data = []

                for item in data:
                    if not isinstance(item, dict):
                        continue

                    filtered_item = {
                        field: item.get(field) for field in fields if field in item
                    }
                    filtered_data.append(filtered_item)

                data = filtered_data

            # Apply grouping if specified
            grouped_data = None
            if grouping:
                group_field = grouping.get("field")
                aggregations = grouping.get("aggregations", [])

                if group_field:
                    grouped_data = self._group_data(data, group_field, aggregations)

            # Apply sorting if specified
            if sorting:
                sort_field = sorting.get("field")
                sort_direction = sorting.get("direction", "asc")

                if sort_field:
                    data = sorted(
                        data,
                        key=lambda item: (
                            item.get(sort_field)
                            if isinstance(item, dict) and sort_field in item
                            else None
                        ),
                        reverse=(sort_direction.lower() == "desc"),
                    )

            # Generate report data
            report_data = {
                "title": title,
                "description": description,
                "generated_at": datetime.now().isoformat(),
                "query_definition": query_definition,
                "parameters": parameters,
                "data": data,
            }

            # Add grouped data if available
            if grouped_data:
                report_data["grouped_data"] = grouped_data

            return report_data

        except Exception as e:
            logger.error(f"Error executing custom query: {str(e)}", exc_info=True)
            raise BusinessRuleException(
                f"Error executing custom query: {str(e)}", "REPORT_201"
            )

    def _convert_to_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert report data to JSON format.

        Args:
            data: Report data

        Returns:
            JSON data
        """
        # JSON format is the native format, just return as is
        return data

    def _convert_to_csv(self, data: Dict[str, Any]) -> bytes:
        """
        Convert report data to CSV format.

        Args:
            data: Report data

        Returns:
            CSV data as bytes
        """
        # Extract raw data
        raw_data = data.get("data", [])

        # Handle empty data
        if not raw_data:
            return b"No data available"

        # Create CSV in memory
        output = io.StringIO()

        # Get all possible fields
        all_fields = set()
        for item in raw_data:
            if isinstance(item, dict):
                all_fields.update(item.keys())

        # Create CSV writer
        writer = csv.DictWriter(output, fieldnames=sorted(all_fields))

        # Write header
        writer.writeheader()

        # Write data
        for item in raw_data:
            if isinstance(item, dict):
                # Ensure all values are strings for CSV
                row = {}
                for key, value in item.items():
                    if isinstance(value, dict) or isinstance(value, list):
                        row[key] = json.dumps(value)
                    else:
                        row[key] = value

                writer.writerow(row)

        # Return CSV data
        return output.getvalue().encode("utf-8")

    def _convert_to_excel(self, data: Dict[str, Any]) -> bytes:
        """
        Convert report data to Excel format.

        Args:
            data: Report data

        Returns:
            Excel data as bytes
        """
        try:
            import xlsxwriter
        except ImportError:
            raise BusinessRuleException(
                "Excel conversion requires xlsxwriter package", "REPORT_301"
            )

        # Extract report title and raw data
        title = data.get("title", "Report")
        raw_data = data.get("data", [])

        # Handle empty data
        if not raw_data:
            # Create a simple workbook
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output)
            worksheet = workbook.add_worksheet("Report")
            worksheet.write(0, 0, "No data available")
            workbook.close()
            return output.getvalue()

        # Create Excel workbook in memory
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet("Data")

        # Add title
        title_format = workbook.add_format({"bold": True, "font_size": 14})
        worksheet.write(0, 0, title, title_format)

        # Add generation timestamp
        date_format = workbook.add_format({"italic": True})
        worksheet.write(
            1,
            0,
            f"Generated: {data.get('generated_at', datetime.now().isoformat())}",
            date_format,
        )

        # Get all possible fields
        all_fields = set()
        for item in raw_data:
            if isinstance(item, dict):
                all_fields.update(item.keys())

        # Sort fields for consistency
        sorted_fields = sorted(all_fields)

        # Write header row
        header_format = workbook.add_format({"bold": True, "bg_color": "#D0D0D0"})
        for col, field in enumerate(sorted_fields):
            worksheet.write(3, col, field, header_format)

        # Write data rows
        for row, item in enumerate(raw_data, start=4):
            if not isinstance(item, dict):
                continue

            for col, field in enumerate(sorted_fields):
                value = item.get(field)

                # Format complex types as JSON strings
                if isinstance(value, dict) or isinstance(value, list):
                    value = json.dumps(value)

                worksheet.write(row, col, value)

        # Add summary worksheet if summary data exists
        if "summary" in data:
            summary_sheet = workbook.add_worksheet("Summary")
            summary_sheet.write(0, 0, f"{title} - Summary", title_format)

            # Write summary data
            row = 2
            for key, value in data["summary"].items():
                # Format key as a readable title
                readable_key = " ".join(word.capitalize() for word in key.split("_"))
                summary_sheet.write(row, 0, readable_key)

                # Handle different value types
                if isinstance(value, dict):
                    # Write dict as multiple rows
                    for sub_key, sub_value in value.items():
                        readable_sub_key = " ".join(
                            word.capitalize() for word in sub_key.split("_")
                        )
                        summary_sheet.write(row, 1, readable_sub_key)
                        summary_sheet.write(row, 2, sub_value)
                        row += 1
                elif isinstance(value, list):
                    # Write first list item
                    if value:
                        summary_sheet.write(
                            row,
                            1,
                            (
                                json.dumps(value[0])
                                if isinstance(value[0], (dict, list))
                                else value[0]
                            ),
                        )
                    row += 1
                    # Write remaining items
                    for item in value[1:]:
                        summary_sheet.write(
                            row,
                            1,
                            (
                                json.dumps(item)
                                if isinstance(item, (dict, list))
                                else item
                            ),
                        )
                        row += 1
                else:
                    summary_sheet.write(row, 1, value)
                    row += 1

                # Add spacing between sections
                row += 1

        # Add parameters worksheet
        if "parameters" in data:
            params_sheet = workbook.add_worksheet("Parameters")
            params_sheet.write(0, 0, "Report Parameters", title_format)

            # Write parameters
            row = 2
            for key, value in data["parameters"].items():
                # Format key as a readable title
                readable_key = " ".join(word.capitalize() for word in key.split("_"))
                params_sheet.write(row, 0, readable_key)

                # Format value based on type
                if isinstance(value, dict):
                    params_sheet.write(row, 1, json.dumps(value))
                elif isinstance(value, list):
                    params_sheet.write(row, 1, json.dumps(value))
                else:
                    params_sheet.write(row, 1, value)

                row += 1

        # Finalize and return
        workbook.close()
        return output.getvalue()
