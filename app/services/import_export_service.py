# File: services/import_export_service.py

"""
Import and export service for the HideSync system.

This module provides comprehensive functionality for importing and exporting data
in various formats to and from the HideSync system. It handles data validation,
transformation, and batch processing for reliable data exchange.

The import/export service enables users to migrate data from other systems,
export data for external analysis, and provides a foundation for integrations
with other platforms and tools used in leatherworking workflows.

Key features:
- Data import from CSV, JSON, and Excel formats
- Data export to multiple formats
- Batch processing with error handling
- Data validation and transformation
- Entity relationship preservation
- Progress tracking for large imports
- Error reporting and validation feedback
- Template generation for imports

The service follows clean architecture principles with clear separation from
the data access layer through domain services, and integrates with validation
frameworks to ensure data integrity.
"""

from typing import Dict, Any, List, Optional, BinaryIO, Callable, Union, Type
from sqlalchemy.orm import Session
import csv
import json
import io
import uuid
import logging
from datetime import datetime
import traceback
import re

logger = logging.getLogger(__name__)


class ImportResult:
    """Container for import results and statistics."""

    def __init__(self):
        self.total_rows = 0
        self.successful_rows = 0
        self.failed_rows = 0
        self.created_ids = []
        self.updated_ids = []
        self.errors = []
        self.warnings = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary."""
        return {
            "total_rows": self.total_rows,
            "successful_rows": self.successful_rows,
            "failed_rows": self.failed_rows,
            "success_rate": (
                round(self.successful_rows / self.total_rows * 100, 1)
                if self.total_rows > 0
                else 0
            ),
            "created_count": len(self.created_ids),
            "updated_count": len(self.updated_ids),
            "created_ids": self.created_ids,
            "updated_ids": self.updated_ids,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class ExportOptions:
    """Options for data export operations."""

    def __init__(
        self,
        format: str = "csv",
        include_headers: bool = True,
        excluded_fields: Optional[List[str]] = None,
        filename: Optional[str] = None,
        date_format: str = "%Y-%m-%d",
    ):
        self.format = format.lower()
        self.include_headers = include_headers
        self.excluded_fields = excluded_fields or []
        self.filename = filename
        self.date_format = date_format


class ImportExportService:
    """
    Service for importing and exporting data in various formats.

    Provides functionality for:
    - Importing data from CSV, Excel, and JSON files
    - Exporting data to various formats
    - Data validation and transformation
    - Batch processing with error handling
    """

    def __init__(
        self,
        session: Session,
        service_factory=None,
        file_service=None,
        security_context=None,
        event_bus=None,
    ):
        """
        Initialize import/export service with dependencies.

        Args:
            session: Database session for persistence operations
            service_factory: Factory for getting appropriate services
            file_service: Optional service for file storage
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
        """
        self.session = session
        self.service_factory = service_factory
        self.file_service = file_service
        self.security_context = security_context
        self.event_bus = event_bus

    def import_data(
        self,
        entity_type: str,
        file_data: Union[BinaryIO, str, bytes],
        file_format: str = "csv",
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Import data from a file.

        Args:
            entity_type: Type of entity to import
            file_data: File data as file-like object, string, or bytes
            file_format: Format of the file (csv, json, excel)
            options: Optional import options including:
                - batch_size: Number of records to process in each batch
                - update_existing: Whether to update existing records (default: True)
                - identifier_field: Field to use for identifying existing records (default: 'id')
                - skip_validation: Whether to skip validation (default: False)
                - date_format: Format string for date parsing (default: '%Y-%m-%d')
                - field_mapping: Dictionary mapping source field names to destination field names
                - enum_fields: Dictionary mapping field names to enum types
                - date_fields: List of field names to parse as dates
                - numeric_fields: List of field names to parse as numbers
                - bool_fields: List of field names to parse as booleans

        Returns:
            Import results with statistics

        Raises:
            ValidationException: If validation fails
            BusinessRuleException: If import fails
        """
        from app.core.exceptions import ValidationException, BusinessRuleException

        # Initialize results
        result = ImportResult()

        # Set default options
        options = options or {}

        # Validate entity type
        if not self._is_valid_entity_type(entity_type):
            raise ValidationException(
                f"Unsupported entity type: {entity_type}",
                {
                    "entity_type": [
                        f"Must be one of: {', '.join(self._get_supported_entity_types())}"
                    ]
                },
            )

        # Validate file format
        if file_format.lower() not in ["csv", "json", "excel"]:
            raise ValidationException(
                f"Unsupported file format: {file_format}",
                {"file_format": ["Must be one of: csv, json, excel"]},
            )

        try:
            # Parse file based on format
            if file_format.lower() == "csv":
                records = self._parse_csv(file_data, options)
            elif file_format.lower() == "json":
                records = self._parse_json(file_data, options)
            elif file_format.lower() == "excel":
                records = self._parse_excel(file_data, options)
            else:
                raise ValidationException(
                    f"Unsupported file format: {file_format}",
                    {"file_format": ["Must be one of: csv, json, excel"]},
                )

            # Set total rows
            result.total_rows = len(records)

            if result.total_rows == 0:
                result.warnings.append("No records found in file")
                return result.to_dict()

            # Get appropriate service for entity type
            service = self._get_service_for_entity_type(entity_type)

            # Check if we should update existing records
            update_existing = options.get("update_existing", True)
            identifier_field = options.get("identifier_field", "id")

            # Process records in batches
            batch_size = options.get("batch_size", 100)

            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]

                # Process batch with transaction
                try:
                    # Use service's transaction context if possible
                    transaction_context = getattr(service, "transaction", None)

                    if transaction_context:
                        with transaction_context():
                            self._process_batch(
                                batch=batch,
                                service=service,
                                entity_type=entity_type,
                                result=result,
                                options=options,
                                update_existing=update_existing,
                                identifier_field=identifier_field,
                                batch_offset=i,
                            )
                    else:
                        # Fall back to session transaction
                        with self.session.begin():
                            self._process_batch(
                                batch=batch,
                                service=service,
                                entity_type=entity_type,
                                result=result,
                                options=options,
                                update_existing=update_existing,
                                identifier_field=identifier_field,
                                batch_offset=i,
                            )

                except Exception as e:
                    # Handle batch transaction failure
                    logger.error(f"Error in import batch: {str(e)}", exc_info=True)

                    # Count all records in the failed batch
                    result.failed_rows += len(batch)

                    # Add detailed error
                    result.errors.append(
                        {
                            "batch": f"{i + 1} to {i + len(batch)}",
                            "error": str(e),
                            "traceback": traceback.format_exc(),
                        }
                    )

            # Emit event if event bus exists
            if self.event_bus:
                self.event_bus.publish(
                    {
                        "type": "DataImported",
                        "entity_type": entity_type,
                        "user_id": (
                            self.security_context.current_user.id
                            if self.security_context
                            else None
                        ),
                        "file_format": file_format,
                        "total_rows": result.total_rows,
                        "successful_rows": result.successful_rows,
                        "failed_rows": result.failed_rows,
                        "created_count": len(result.created_ids),
                        "updated_count": len(result.updated_ids),
                    }
                )

            return result.to_dict()

        except Exception as e:
            logger.error(f"Import failed: {str(e)}", exc_info=True)
            raise BusinessRuleException(f"Import failed: {str(e)}", "IMPORT_001")

    def export_data(
        self,
        entity_type: str,
        query_params: Optional[Dict[str, Any]] = None,
        options: Optional[ExportOptions] = None,
    ) -> Union[bytes, str, Dict[str, Any]]:
        """
        Export data to specified format.

        Args:
            entity_type: Type of entity to export
            query_params: Optional query parameters to filter data
            options: Export options

        Returns:
            Exported data in requested format

        Raises:
            ValidationException: If validation fails
            BusinessRuleException: If export fails
        """
        from app.core.exceptions import ValidationException, BusinessRuleException

        # Set default options
        if options is None:
            options = ExportOptions()

        # Default query params
        query_params = query_params or {}

        # Validate entity type
        if not self._is_valid_entity_type(entity_type):
            raise ValidationException(
                f"Unsupported entity type: {entity_type}",
                {
                    "entity_type": [
                        f"Must be one of: {', '.join(self._get_supported_entity_types())}"
                    ]
                },
            )

        try:
            # Get appropriate service for entity type
            service = self._get_service_for_entity_type(entity_type)

            # Get entities
            entities = service.list(**query_params)

            # Transform to list of dictionaries
            records = []
            for entity in entities:
                # Convert to dict if not already
                if not isinstance(entity, dict):
                    entity_dict = (
                        entity.to_dict() if hasattr(entity, "to_dict") else dict(entity)
                    )
                else:
                    entity_dict = entity

                # Format dates
                for key, value in entity_dict.items():
                    if isinstance(value, datetime):
                        entity_dict[key] = value.strftime(options.date_format)

                # Exclude specified fields
                for field in options.excluded_fields:
                    if field in entity_dict:
                        del entity_dict[field]

                records.append(entity_dict)

            # Export based on requested format
            if options.format == "csv":
                return self._export_to_csv(records, options)
            elif options.format == "json":
                return self._export_to_json(records, options)
            elif options.format == "excel":
                return self._export_to_excel(records, options)
            else:
                raise ValidationException(
                    f"Unsupported export format: {options.format}",
                    {"format": ["Must be one of: csv, json, excel"]},
                )

            # Emit event if event bus exists
            if self.event_bus:
                self.event_bus.publish(
                    {
                        "type": "DataExported",
                        "entity_type": entity_type,
                        "user_id": (
                            self.security_context.current_user.id
                            if self.security_context
                            else None
                        ),
                        "format": options.format,
                        "record_count": len(records),
                    }
                )

        except Exception as e:
            logger.error(f"Export failed: {str(e)}", exc_info=True)
            raise BusinessRuleException(f"Export failed: {str(e)}", "EXPORT_001")

    def generate_import_template(
        self, entity_type: str, format: str = "csv"
    ) -> Union[bytes, str]:
        """
        Generate an import template with column headers.

        Args:
            entity_type: Type of entity to generate template for
            format: Format of the template (csv, json, excel)

        Returns:
            Template data in requested format

        Raises:
            ValidationException: If validation fails
        """
        from app.core.exceptions import ValidationException

        # Validate entity type
        if not self._is_valid_entity_type(entity_type):
            raise ValidationException(
                f"Unsupported entity type: {entity_type}",
                {
                    "entity_type": [
                        f"Must be one of: {', '.join(self._get_supported_entity_types())}"
                    ]
                },
            )

        # Validate format
        if format.lower() not in ["csv", "json", "excel"]:
            raise ValidationException(
                f"Unsupported template format: {format}",
                {"format": ["Must be one of: csv, json, excel"]},
            )

        # Get field definitions for entity type
        fields = self._get_template_fields(entity_type)

        # Generate template based on format
        if format.lower() == "csv":
            return self._generate_csv_template(entity_type, fields)
        elif format.lower() == "json":
            return self._generate_json_template(entity_type, fields)
        elif format.lower() == "excel":
            return self._generate_excel_template(entity_type, fields)

    def save_export(
        self, data: Union[bytes, str], filename: str, content_type: str
    ) -> Dict[str, Any]:
        """
        Save exported data as a file.

        Args:
            data: Exported data
            filename: Filename to save as
            content_type: MIME type of the file

        Returns:
            Metadata for the saved file

        Raises:
            BusinessRuleException: If file service not available or save fails
        """
        from app.core.exceptions import BusinessRuleException

        # Check if file service is available
        if not self.file_service:
            raise BusinessRuleException(
                "File storage service not available", "EXPORT_002"
            )

        try:
            # Ensure data is bytes
            if isinstance(data, str):
                data = data.encode("utf-8")

            # Generate metadata
            metadata = {
                "generated_by": (
                    self.security_context.current_user.id
                    if self.security_context
                    else None
                ),
                "generated_at": datetime.now().isoformat(),
                "original_filename": filename,
            }

            # Store file
            result = self.file_service.store_file(
                file_data=data,
                filename=filename,
                content_type=content_type,
                metadata=metadata,
            )

            return result

        except Exception as e:
            logger.error(f"Failed to save export: {str(e)}", exc_info=True)
            raise BusinessRuleException(
                f"Failed to save export: {str(e)}", "EXPORT_003"
            )

    def _process_batch(
        self,
        batch: List[Dict[str, Any]],
        service: Any,
        entity_type: str,
        result: ImportResult,
        options: Dict[str, Any],
        update_existing: bool,
        identifier_field: str,
        batch_offset: int,
    ) -> None:
        """
        Process a batch of records.

        Args:
            batch: Batch of records to process
            service: Service to use for processing
            entity_type: Type of entity being processed
            result: ImportResult to update
            options: Import options
            update_existing: Whether to update existing records
            identifier_field: Field to use for identifying existing records
            batch_offset: Offset of this batch in the overall dataset
        """
        for idx, record in enumerate(batch):
            try:
                # Transform record if needed
                transformed_record = self._transform_record(
                    record, entity_type, options
                )

                # Skip validation if requested
                skip_validation = options.get("skip_validation", False)

                # Determine if create or update
                entity_id = transformed_record.get(identifier_field)

                if entity_id and update_existing:
                    # Check if entity exists
                    try:
                        existing_entity = service.get_by_id(entity_id)
                    except Exception:
                        existing_entity = None

                    if existing_entity:
                        # Update existing entity
                        if skip_validation:
                            # Use repository directly if available
                            if hasattr(service, "repository"):
                                service.repository.update(entity_id, transformed_record)
                            else:
                                service.update(entity_id, transformed_record)
                        else:
                            service.update(entity_id, transformed_record)

                        result.updated_ids.append(entity_id)
                        result.successful_rows += 1
                    else:
                        # Entity with ID doesn't exist, create new
                        if skip_validation:
                            # Use repository directly if available
                            if hasattr(service, "repository"):
                                created = service.repository.create(transformed_record)
                            else:
                                created = service.create(transformed_record)
                        else:
                            created = service.create(transformed_record)

                        result.created_ids.append(getattr(created, "id", None))
                        result.successful_rows += 1
                else:
                    # Create new entity
                    if skip_validation:
                        # Use repository directly if available
                        if hasattr(service, "repository"):
                            created = service.repository.create(transformed_record)
                        else:
                            created = service.create(transformed_record)
                    else:
                        created = service.create(transformed_record)

                    result.created_ids.append(getattr(created, "id", None))
                    result.successful_rows += 1

            except Exception as e:
                # Add error for this record
                result.failed_rows += 1
                error_message = str(e)

                # Add record index information
                record_index = batch_offset + idx + 1
                result.errors.append(
                    {
                        "row": record_index,
                        "error": error_message,
                        "data": {
                            k: v
                            for k, v in record.items()
                            if k not in ["password", "api_secret", "token"]
                        },
                    }
                )

                logger.error(f"Error importing record {record_index}: {error_message}")

    def _parse_csv(
        self, file_data: Union[BinaryIO, str, bytes], options: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Parse CSV file data.

        Args:
            file_data: CSV file data
            options: Import options

        Returns:
            List of records as dictionaries
        """
        # Convert to string if bytes
        if isinstance(file_data, bytes):
            file_content = file_data.decode("utf-8-sig")  # Handle BOM
        elif hasattr(file_data, "read"):
            file_content = file_data.read()
            if isinstance(file_content, bytes):
                file_content = file_content.decode("utf-8-sig")
        else:
            file_content = file_data

        # Create CSV reader
        csv_reader = csv.DictReader(
            file_content.splitlines(), delimiter=options.get("delimiter", ",")
        )

        # Convert to list of dictionaries
        records = []
        for row in csv_reader:
            # Clean up values (strip whitespace, handle empty strings)
            cleaned_row = {}
            for key, value in row.items():
                # Skip empty keys
                if key is None or key.strip() == "":
                    continue

                # Clean keys
                clean_key = key.strip()

                # Clean values
                if value is None:
                    clean_value = None
                elif value.strip() == "":
                    clean_value = None
                else:
                    clean_value = value.strip()

                cleaned_row[clean_key] = clean_value

            records.append(cleaned_row)

        return records

    def _parse_json(
        self, file_data: Union[BinaryIO, str, bytes], options: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Parse JSON file data.

        Args:
            file_data: JSON file data
            options: Import options

        Returns:
            List of records as dictionaries
        """
        # Convert to string if bytes
        if isinstance(file_data, bytes):
            file_content = file_data.decode("utf-8")
        elif hasattr(file_data, "read"):
            file_content = file_data.read()
            if isinstance(file_content, bytes):
                file_content = file_content.decode("utf-8")
        else:
            file_content = file_data

        # Parse JSON
        data = json.loads(file_content)

        # Ensure we have a list of dictionaries
        if isinstance(data, list):
            records = data
        elif (
            isinstance(data, dict) and "data" in data and isinstance(data["data"], list)
        ):
            records = data["data"]
        elif isinstance(data, dict):
            # Single record
            records = [data]
        else:
            records = []

        return records

    def _parse_excel(
        self, file_data: Union[BinaryIO, bytes], options: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Parse Excel file data.

        Args:
            file_data: Excel file data
            options: Import options

        Returns:
            List of records as dictionaries
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "Pandas is required for Excel file parsing. Install with: pip install pandas"
            )

        # Read Excel file
        sheet_name = options.get("sheet_name", 0)  # Default to first sheet

        # Read to DataFrame
        df = pd.read_excel(file_data, sheet_name=sheet_name)

        # Convert to list of dictionaries
        records = df.to_dict("records")

        # Clean up values (handle empty strings, etc.)
        for record in records:
            for key, value in list(record.items()):
                # Handle NaN values
                if pd.isna(value):
                    record[key] = None

        return records

    def _export_to_csv(
        self, records: List[Dict[str, Any]], options: ExportOptions
    ) -> bytes:
        """
        Export records to CSV format.

        Args:
            records: Records to export
            options: Export options

        Returns:
            CSV data as bytes
        """
        # Create CSV in memory
        output = io.StringIO()

        # Get all field names from records
        all_fields = set()
        for record in records:
            all_fields.update(record.keys())

        # Sort field names for consistency
        fieldnames = sorted(all_fields)

        # Create CSV writer
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")

        # Write header if requested
        if options.include_headers:
            writer.writeheader()

        # Write records
        for record in records:
            writer.writerow(record)

        # Return CSV data
        return output.getvalue().encode("utf-8")

    def _export_to_json(
        self, records: List[Dict[str, Any]], options: ExportOptions
    ) -> Union[str, Dict[str, Any]]:
        """
        Export records to JSON format.

        Args:
            records: Records to export
            options: Export options

        Returns:
            JSON data as string or dictionary
        """
        # Create result
        result = {
            "data": records,
            "metadata": {
                "count": len(records),
                "generated_at": datetime.now().isoformat(),
                "format": "json",
            },
        }

        # Return as string or dict based on options
        if options.format == "json_string":
            return json.dumps(result, default=str, indent=2)
        else:
            return result

    def _export_to_excel(
        self, records: List[Dict[str, Any]], options: ExportOptions
    ) -> bytes:
        """
        Export records to Excel format.

        Args:
            records: Records to export
            options: Export options

        Returns:
            Excel data as bytes
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "Pandas is required for Excel export. Install with: pip install pandas"
            )

        # Convert to DataFrame
        df = pd.DataFrame(records)

        # Create Excel in memory
        output = io.BytesIO()

        # Write to Excel
        df.to_excel(output, index=False, sheet_name=options.filename or "Export")

        # Return Excel data
        output.seek(0)
        return output.getvalue()

    def _transform_record(
        self, record: Dict[str, Any], entity_type: str, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform a record for import.

        Args:
            record: Record to transform
            entity_type: Entity type
            options: Import options

        Returns:
            Transformed record
        """
        # Get transformer for entity type
        transformer = self._get_transformer_for_entity_type(entity_type)

        if transformer:
            return transformer(record, options)
        else:
            # Default transformation
            return self._default_transform(record, entity_type, options)

    def _default_transform(
        self, record: Dict[str, Any], entity_type: str, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Default record transformation.

        Args:
            record: Record to transform
            entity_type: Entity type
            options: Import options

        Returns:
            Transformed record
        """
        # Create a copy to avoid modifying the original
        transformed = record.copy()

        # Handle field mapping
        field_mapping = options.get("field_mapping", {})
        for source, target in field_mapping.items():
            if source in transformed:
                transformed[target] = transformed.pop(source)

        # Handle enums
        enum_fields = options.get("enum_fields", {})
        for field, enum_type in enum_fields.items():
            if field in transformed and transformed[field]:
                # Convert enum values (assumes values are uppercase in enum)
                transformed[field] = str(transformed[field]).upper()

        # Handle dates
        date_fields = options.get("date_fields", [])
        date_format = options.get("date_format", "%Y-%m-%d")

        for field in date_fields:
            if field in transformed and transformed[field]:
                # Simple date parsing, would need more robust handling in production
                try:
                    # Try to parse as specified format
                    date_value = datetime.strptime(transformed[field], date_format)
                    transformed[field] = date_value
                except (ValueError, TypeError):
                    # Try ISO format as fallback
                    try:
                        date_value = datetime.fromisoformat(
                            transformed[field].replace("Z", "+00:00")
                        )
                        transformed[field] = date_value
                    except (ValueError, TypeError):
                        # Keep as is if parsing fails
                        pass

        # Handle boolean fields
        bool_fields = options.get("bool_fields", [])
        for field in bool_fields:
            if field in transformed:
                value = transformed[field]
                if isinstance(value, str):
                    transformed[field] = value.lower() in ["true", "yes", "1", "y", "t"]

        # Handle numeric fields
        numeric_fields = options.get("numeric_fields", [])
        for field in numeric_fields:
            if field in transformed and transformed[field] is not None:
                try:
                    # Remove any currency symbols or commas
                    if isinstance(transformed[field], str):
                        clean_value = re.sub(r"[^\d.-]", "", transformed[field])
                        transformed[field] = float(clean_value)
                    else:
                        transformed[field] = float(transformed[field])
                except (ValueError, TypeError):
                    # If conversion fails, keep as is
                    pass

        return transformed

    def _get_service_for_entity_type(self, entity_type: str) -> Any:
        """
        Get appropriate service for entity type.

        Args:
            entity_type: Entity type

        Returns:
            Service instance
        """
        # Check if service factory is available
        if self.service_factory:
            # Map entity types to service factory methods
            service_map = {
                "material": self.service_factory.get_material_service,
                "project": self.service_factory.get_project_service,
                "customer": self.service_factory.get_customer_service,
                "project_template": self.service_factory.get_pattern_service,  # Handles templates too
                "pattern": self.service_factory.get_pattern_service,
                "product": self.service_factory.get_product_service,
                "supplier": self.service_factory.get_supplier_service,
                "tool": self.service_factory.get_tool_service,
                "storage_location": self.service_factory.get_storage_location_service,
                "sale": self.service_factory.get_sale_service,
                "purchase": self.service_factory.get_purchase_service,
                "component": self.service_factory.get_component_service,
                "picking_list": self.service_factory.get_picking_list_service,
            }

            # Get service factory method
            service_factory_method = service_map.get(entity_type)

            if service_factory_method:
                # Call factory method to get service
                return service_factory_method()

        raise ValueError(f"No service available for entity type: {entity_type}")

    def _get_transformer_for_entity_type(self, entity_type: str) -> Optional[Callable]:
        """
        Get transformer function for entity type.

        Args:
            entity_type: Entity type

        Returns:
            Transformer function or None for default
        """
        # Map entity types to transformer functions
        transformer_map = {
            "material": self._transform_material,
            "customer": self._transform_customer,
            # Add more entity-specific transformers as needed
        }

        return transformer_map.get(entity_type)

    def _transform_material(
        self, record: Dict[str, Any], options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform a material record.

        Args:
            record: Record to transform
            options: Import options

        Returns:
            Transformed record
        """
        # Start with default transform
        transformed = self._default_transform(record, "material", options)

        # Material-specific transformations
        if "material_type" in transformed and transformed["material_type"]:
            # Normalize material type
            material_type = transformed["material_type"].upper()
            transformed["material_type"] = material_type

            # Set default values based on material type
            if material_type == "LEATHER" and "thickness" not in transformed:
                transformed["thickness"] = 0.0

        # Calculate reorder point if not provided but we have quantity
        if "reorder_point" not in transformed and "quantity" in transformed:
            quantity = transformed.get("quantity", 0)
            if isinstance(quantity, (int, float)) and quantity > 0:
                transformed["reorder_point"] = max(
                    1, quantity * 0.2
                )  # 20% of current quantity

        return transformed

    def _transform_customer(
        self, record: Dict[str, Any], options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform a customer record.

        Args:
            record: Record to transform
            options: Import options

        Returns:
            Transformed record
        """
        # Start with default transform
        transformed = self._default_transform(record, "customer", options)

        # Customer-specific transformations

        # Normalize email
        if "email" in transformed and transformed["email"]:
            transformed["email"] = transformed["email"].lower().strip()

        # Set default tier if not provided
        if "tier" not in transformed or not transformed["tier"]:
            transformed["tier"] = "STANDARD"

        # Set default status if not provided
        if "status" not in transformed or not transformed["status"]:
            transformed["status"] = "ACTIVE"

        return transformed

    def _is_valid_entity_type(self, entity_type: str) -> bool:
        """
        Check if entity type is supported for import/export.

        Args:
            entity_type: Entity type to check

        Returns:
            True if entity type is supported
        """
        return entity_type in self._get_supported_entity_types()

    def _get_supported_entity_types(self) -> List[str]:
        """
        Get list of supported entity types.

        Returns:
            List of supported entity types
        """
        return [
            "material",
            "project",
            "customer",
            "project_template",
            "pattern",
            "product",
            "supplier",
            "tool",
            "storage_location",
            "sale",
            "purchase",
            "component",
            "picking_list",
        ]

    def _get_id_field(self, entity_type: str) -> str:
        """
        Get ID field name for entity type.

        Args:
            entity_type: Entity type

        Returns:
            ID field name
        """
        # Most entities use 'id'
        return "id"

    def _get_template_fields(self, entity_type: str) -> List[Dict[str, Any]]:
        """
        Get field definitions for template generation.

        Args:
            entity_type: Entity type

        Returns:
            List of field definitions
        """
        # Common fields
        common_fields = [
            {
                "name": "id",
                "type": "string",
                "description": "Unique identifier (leave blank for new records)",
                "required": False,
            },
            {"name": "name", "type": "string", "description": "Name", "required": True},
            {
                "name": "description",
                "type": "string",
                "description": "Description",
                "required": False,
            },
            {
                "name": "notes",
                "type": "string",
                "description": "Notes",
                "required": False,
            },
        ]

        # Entity-specific fields
        entity_fields = {
            "material": [
                {
                    "name": "material_type",
                    "type": "enum",
                    "description": "Material type (LEATHER, HARDWARE, SUPPLIES, etc.)",
                    "required": True,
                },
                {
                    "name": "quantity",
                    "type": "number",
                    "description": "Quantity",
                    "required": True,
                },
                {
                    "name": "unit",
                    "type": "enum",
                    "description": "Unit of measurement",
                    "required": True,
                },
                {
                    "name": "reorder_point",
                    "type": "number",
                    "description": "Reorder point",
                    "required": False,
                },
                {
                    "name": "cost",
                    "type": "number",
                    "description": "Cost per unit",
                    "required": False,
                },
                {
                    "name": "supplier_id",
                    "type": "string",
                    "description": "Supplier ID",
                    "required": False,
                },
                {
                    "name": "storage_location",
                    "type": "string",
                    "description": "Storage location",
                    "required": False,
                },
            ],
            "customer": [
                {
                    "name": "email",
                    "type": "string",
                    "description": "Email address",
                    "required": True,
                },
                {
                    "name": "phone",
                    "type": "string",
                    "description": "Phone number",
                    "required": False,
                },
                {
                    "name": "company_name",
                    "type": "string",
                    "description": "Company name",
                    "required": False,
                },
                {
                    "name": "address",
                    "type": "string",
                    "description": "Address",
                    "required": False,
                },
                {
                    "name": "status",
                    "type": "enum",
                    "description": "Status (ACTIVE, INACTIVE, etc.)",
                    "required": False,
                },
                {
                    "name": "tier",
                    "type": "enum",
                    "description": "Customer tier",
                    "required": False,
                },
                {
                    "name": "source",
                    "type": "enum",
                    "description": "Where the customer came from",
                    "required": False,
                },
            ],
            "project": [
                {
                    "name": "type",
                    "type": "enum",
                    "description": "Project type",
                    "required": True,
                },
                {
                    "name": "status",
                    "type": "enum",
                    "description": "Project status",
                    "required": False,
                },
                {
                    "name": "customer_id",
                    "type": "string",
                    "description": "Customer ID",
                    "required": False,
                },
                {
                    "name": "start_date",
                    "type": "date",
                    "description": "Start date (YYYY-MM-DD)",
                    "required": False,
                },
                {
                    "name": "due_date",
                    "type": "date",
                    "description": "Due date (YYYY-MM-DD)",
                    "required": False,
                },
                {
                    "name": "pattern_id",
                    "type": "string",
                    "description": "Pattern ID",
                    "required": False,
                },
            ],
        }

        # Combine common fields with entity-specific fields
        if entity_type in entity_fields:
            return common_fields + entity_fields[entity_type]
        else:
            return common_fields

    def _generate_csv_template(
        self, entity_type: str, fields: List[Dict[str, Any]]
    ) -> bytes:
        """
        Generate CSV template.

        Args:
            entity_type: Entity type
            fields: Field definitions

        Returns:
            CSV template as bytes
        """
        # Create CSV in memory
        output = io.StringIO()

        # Extract field names
        fieldnames = [field["name"] for field in fields]

        # Create CSV writer
        writer = csv.DictWriter(output, fieldnames=fieldnames)

        # Write header
        writer.writeheader()

        # Write example row with placeholders
        example_row = {}
        for field in fields:
            if field["required"]:
                example_row[field["name"]] = f"REQUIRED - {field['description']}"
            else:
                example_row[field["name"]] = f"OPTIONAL - {field['description']}"

        writer.writerow(example_row)

        # Return CSV data
        return output.getvalue().encode("utf-8")

    def _generate_json_template(
        self, entity_type: str, fields: List[Dict[str, Any]]
    ) -> str:
        """
        Generate JSON template.

        Args:
            entity_type: Entity type
            fields: Field definitions

        Returns:
            JSON template as string
        """
        # Create example object
        example = {}

        for field in fields:
            if field["required"]:
                example[field["name"]] = f"REQUIRED - {field['description']}"
            else:
                example[field["name"]] = f"OPTIONAL - {field['description']}"

        # Create template object
        template = {
            "data": [example],
            "documentation": {
                "entity_type": entity_type,
                "fields": fields,
                "import_instructions": f"Fill in the data array with your {entity_type} records. Required fields must be populated.",
            },
        }

        # Convert to JSON
        return json.dumps(template, indent=2)

    def _generate_excel_template(
        self, entity_type: str, fields: List[Dict[str, Any]]
    ) -> bytes:
        """
        Generate Excel template.

        Args:
            entity_type: Entity type
            fields: Field definitions

        Returns:
            Excel template as bytes
        """
        try:
            import pandas as pd
            import numpy as np
        except ImportError:
            raise ImportError(
                "Pandas is required for Excel template generation. Install with: pip install pandas"
            )

        # Create example data
        data = []

        # Add example row
        example_row = {}
        for field in fields:
            if field["required"]:
                example_row[field["name"]] = f"REQUIRED - {field['description']}"
            else:
                example_row[field["name"]] = f"OPTIONAL - {field['description']}"

        data.append(example_row)

        # Create DataFrame
        df = pd.DataFrame(data)

        # Create Excel in memory
        output = io.BytesIO()

        # Create Excel writer with pandas
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            # Write data sheet
            df.to_excel(writer, sheet_name="Data", index=False)

            # Get workbook and worksheet objects
            workbook = writer.book
            worksheet = writer.sheets["Data"]

            # Add format for headers
            header_format = workbook.add_format(
                {"bold": True, "bg_color": "#D3D3D3", "border": 1}
            )

            # Apply header format
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Auto-size columns
            for col_num, column in enumerate(df.columns):
                max_len = max(df[column].astype(str).map(len).max(), len(column)) + 2
                worksheet.set_column(col_num, col_num, max_len)

            # Add instructions sheet
            instructions_sheet = workbook.add_worksheet("Instructions")

            # Add instructions
            instructions_sheet.write(
                0,
                0,
                f"{entity_type.capitalize()} Import Instructions",
                workbook.add_format({"bold": True, "font_size": 14}),
            )
            instructions_sheet.write(2, 0, "Field Definitions:")

            # Add field definitions
            for i, field in enumerate(fields):
                instructions_sheet.write(i + 4, 0, field["name"])
                instructions_sheet.write(i + 4, 1, field["type"])
                instructions_sheet.write(
                    i + 4, 2, "Required" if field["required"] else "Optional"
                )
                instructions_sheet.write(i + 4, 3, field["description"])

            # Set column widths
            instructions_sheet.set_column(0, 0, 20)
            instructions_sheet.set_column(1, 1, 15)
            instructions_sheet.set_column(2, 2, 15)
            instructions_sheet.set_column(3, 3, 40)

        # Get the output as bytes
        output.seek(0)
        return output.getvalue()
