# app/services/preset_service.py

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime
import json
import uuid

from app.services.base_service import BaseService
from app.repositories.preset_repository import PresetRepository
from app.db.models.preset import MaterialPreset, PresetApplication
from app.core.exceptions import EntityNotFoundException, ValidationException
from app.services.property_definition_service import PropertyDefinitionService
from app.services.material_type_service import MaterialTypeService
from app.services.dynamic_material_service import DynamicMaterialService
from app.services.settings_service import SettingsService


class PresetService(BaseService[MaterialPreset]):
    """
    Service for managing material presets in the Dynamic Material Management System.

    Provides functionality for:
    - Creating and managing presets
    - Applying presets to create/update material types and properties
    - Importing and exporting preset configurations
    """

    def __init__(
            self,
            session: Session,
            repository=None,
            property_service=None,
            material_type_service=None,
            material_service=None,
            settings_service=None,
            security_context=None,
            event_bus=None,
            cache_service=None,
    ):
        """
        Initialize PresetService with dependencies.

        Args:
            session: Database session
            repository: Optional repository override
            property_service: PropertyDefinitionService for managing properties
            material_type_service: MaterialTypeService for managing material types
            material_service: DynamicMaterialService for managing materials
            settings_service: SettingsService for managing settings
            security_context: Optional security context for authorization
            event_bus: Optional event bus for publishing domain events
            cache_service: Optional cache service for data caching
        """
        self.session = session
        self.repository = repository or PresetRepository(session)
        self.property_service = property_service
        self.material_type_service = material_type_service
        self.material_service = material_service
        self.settings_service = settings_service
        self.security_context = security_context
        self.event_bus = event_bus
        self.cache_service = cache_service

    def get_presets(
            self,
            skip: int = 0,
            limit: int = 100,
            search: Optional[str] = None,
            user_id: Optional[int] = None,
            is_public: Optional[bool] = None,
            tags: Optional[List[str]] = None,
    ) -> Tuple[List[MaterialPreset], int]:
        """
        Get presets with filtering and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            search: Optional search string for name and description
            user_id: Optional filter by creator
            is_public: Optional filter by public status
            tags: Optional filter by tags

        Returns:
            Tuple of (list of presets, total count)
        """
        return self.repository.list_presets(
            skip=skip,
            limit=limit,
            search=search,
            user_id=user_id,
            is_public=is_public,
            tags=tags
        )

    def get_preset(self, preset_id: int) -> Optional[MaterialPreset]:
        """
        Get a preset by ID.

        Args:
            preset_id: ID of the preset

        Returns:
            Preset if found, None otherwise
        """
        return self.repository.get_by_id(preset_id)

    def create_preset(
            self,
            name: str,
            description: Optional[str] = None,
            author: Optional[str] = None,
            is_public: bool = False,
            config: Dict[str, Any] = None,
            created_by: Optional[int] = None
    ) -> MaterialPreset:
        """
        Create a new preset.

        Args:
            name: Name of the preset
            description: Optional description
            author: Optional author name
            is_public: Whether the preset is public
            config: Preset configuration
            created_by: Optional ID of user creating the preset

        Returns:
            Created preset

        Raises:
            ValidationException: If preset data is invalid
        """
        # Validate config
        if not config:
            config = {
                "metadata": {
                    "version": "1.0.0",
                    "created_at": datetime.utcnow().isoformat(),
                    "created_by": author,
                    "tags": []
                },
                "property_definitions": [],
                "material_types": [],
                "sample_materials": [],
                "settings": {},
                "theme": {}
            }

        # Validate structure
        self._validate_preset_structure(config)

        # Create preset
        preset_data = {
            "name": name,
            "description": description,
            "author": author,
            "is_public": is_public,
            "config": config,
            "created_by": created_by
        }

        with self.transaction():
            preset = self.repository.create(preset_data)

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate_pattern("presets:*")

            return preset

    def update_preset(self, preset_id: int, data: Dict[str, Any]) -> Optional[MaterialPreset]:
        """
        Update an existing preset.

        Args:
            preset_id: ID of the preset to update
            data: Updated preset data

        Returns:
            Updated preset if found, None otherwise

        Raises:
            ValidationException: If preset data is invalid
        """
        # Validate config if provided
        if "config" in data:
            self._validate_preset_structure(data["config"])

        with self.transaction():
            # Update preset
            preset = self.repository.update(preset_id, data)

            # Invalidate cache if needed
            if self.cache_service and preset:
                self.cache_service.invalidate(f"presets:{preset_id}")
                self.cache_service.invalidate_pattern("presets:*")

            return preset

    def delete_preset(self, preset_id: int) -> bool:
        """
        Delete a preset.

        Args:
            preset_id: ID of the preset to delete

        Returns:
            True if deleted, False otherwise
        """
        with self.transaction():
            # Delete preset
            result = self.repository.delete(preset_id)

            # Invalidate cache if needed
            if self.cache_service and result:
                self.cache_service.invalidate(f"presets:{preset_id}")
                self.cache_service.invalidate_pattern("presets:*")

            return result

    def generate_preset_from_system(
            self,
            material_type_ids: List[int],
            include_samples: bool = True,
            include_settings: bool = True,
            user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate a preset configuration from the current system state.

        Args:
            material_type_ids: IDs of material types to include
            include_samples: Whether to include sample materials
            include_settings: Whether to include settings
            user_id: Optional ID of the user

        Returns:
            Preset configuration

        Raises:
            EntityNotFoundException: If a material type is not found
        """
        if not self.material_type_service:
            raise ValidationException("Material type service is required")

        # Initialize configuration
        config = {
            "metadata": {
                "version": "1.0.0",
                "created_at": datetime.utcnow().isoformat(),
                "tags": []
            },
            "property_definitions": [],
            "material_types": [],
            "sample_materials": [],
            "settings": {},
            "theme": {}
        }

        # Property definition set to avoid duplicates
        property_ids = set()

        # Process each material type
        for type_id in material_type_ids:
            # Get material type
            material_type = self.material_type_service.get_material_type(type_id)
            if not material_type:
                raise EntityNotFoundException(f"Material type with ID {type_id} not found")

            # Add material type to config
            material_type_config = {
                "name": material_type.name,
                "icon": material_type.icon,
                "color_scheme": material_type.color_scheme,
                "ui_config": material_type.ui_config,
                "storage_config": material_type.storage_config,
                "properties": []
            }

            # Process translations if available
            if hasattr(material_type, 'translations') and material_type.translations:
                material_type_config["translations"] = {}
                for translation in material_type.translations:
                    material_type_config["translations"][translation.locale] = {
                        "display_name": translation.display_name,
                        "description": translation.description
                    }

            # Process properties
            for type_prop in material_type.properties:
                property_ids.add(type_prop.property_id)

                # Add property configuration
                property_config = {
                    "property_name": type_prop.property.name,
                    "display_order": type_prop.display_order,
                    "is_required": type_prop.is_required,
                    "is_filterable": type_prop.is_filterable,
                    "is_displayed_in_list": type_prop.is_displayed_in_list,
                    "is_displayed_in_card": type_prop.is_displayed_in_card,
                    "default_value": type_prop.default_value
                }

                material_type_config["properties"].append(property_config)

            config["material_types"].append(material_type_config)

            # Add sample materials if requested
            if include_samples and self.material_service:
                # Get a few samples of this material type
                materials, _ = self.material_service.get_materials(
                    limit=5,
                    material_type_id=type_id
                )

                for material in materials:
                    sample_material = {
                        "material_type": material_type.name,
                        "name": material.name,
                        "status": material.status,
                        "quantity": material.quantity,
                        "unit": material.unit,
                        "properties": {}
                    }

                    # Process property values
                    for prop_value in material.property_values:
                        prop_def = self.property_service.get_property_definition(prop_value.property_id)
                        if prop_def:
                            # Get property value based on data type
                            value = None
                            if prop_def.data_type == "string":
                                value = prop_value.value_string
                            elif prop_def.data_type == "number":
                                value = prop_value.value_number
                            elif prop_def.data_type == "boolean":
                                value = prop_value.value_boolean
                            elif prop_def.data_type == "enum":
                                value = prop_value.value_enum_id
                            # Add more data types as needed

                            sample_material["properties"][prop_def.name] = value

                    config["sample_materials"].append(sample_material)

        # Add property definitions
        if self.property_service:
            for property_id in property_ids:
                prop_def = self.property_service.get_property_definition(property_id)
                if prop_def:
                    property_config = {
                        "name": prop_def.name,
                        "data_type": prop_def.data_type,
                        "group_name": prop_def.group_name,
                        "unit": prop_def.unit,
                        "is_required": prop_def.is_required,
                        "has_multiple_values": prop_def.has_multiple_values,
                        "validation_rules": prop_def.validation_rules
                    }

                    # Process translations if available
                    if hasattr(prop_def, 'translations') and prop_def.translations:
                        property_config["translations"] = {}
                        for translation in prop_def.translations:
                            property_config["translations"][translation.locale] = {
                                "display_name": translation.display_name,
                                "description": translation.description
                            }

                    # Process enum options if applicable
                    if prop_def.data_type == "enum" and hasattr(prop_def, 'enum_options'):
                        property_config["enum_options"] = []
                        for option in prop_def.enum_options:
                            property_config["enum_options"].append({
                                "value": option.value,
                                "display_value": option.display_value,
                                "color": option.color,
                                "display_order": option.display_order
                            })

                    # Add enum type if applicable
                    if prop_def.enum_type_id:
                        property_config["enum_type_id"] = prop_def.enum_type_id

                    config["property_definitions"].append(property_config)

        # Add settings if requested
        if include_settings and self.settings_service and user_id:
            # Material UI settings
            material_ui = self.settings_service.get_setting(
                key="material_ui",
                scope_type="user",
                scope_id=str(user_id)
            )

            if material_ui:
                if "settings" not in config:
                    config["settings"] = {}
                config["settings"]["material_ui"] = material_ui

            # Material system settings
            material_system = self.settings_service.get_setting(
                key="material_system",
                scope_type="user",
                scope_id=str(user_id)
            )

            if material_system:
                if "settings" not in config:
                    config["settings"] = {}
                config["settings"]["material_system"] = material_system

        return config

    def apply_preset(
            self,
            preset_id: int,
            options: Dict[str, Any],
            user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Apply a preset to create/update material types and properties.

        Args:
            preset_id: ID of the preset to apply
            options: Application options
            user_id: Optional ID of the user applying the preset

        Returns:
            Application result with counts of created/updated items

        Raises:
            EntityNotFoundException: If preset not found
            ValidationException: If preset application fails
        """
        # Get preset
        preset = self.repository.get_by_id(preset_id)
        if not preset:
            raise EntityNotFoundException(f"Preset with ID {preset_id} not found")

        # Validate required services
        if not self.property_service:
            raise ValidationException("Property definition service is required")
        if not self.material_type_service:
            raise ValidationException("Material type service is required")

        # Initialize statistics and errors
        stats = {
            "created_property_definitions": 0,
            "updated_property_definitions": 0,
            "created_material_types": 0,
            "updated_material_types": 0,
            "created_materials": 0,
            "error_count": 0
        }
        errors = []

        # Set default options if not provided
        if not options:
            options = {
                "material_types_to_include": [],
                "include_properties": True,
                "include_sample_materials": True,
                "include_settings": True,
                "theme_handling": "skip",
                "conflict_resolution": "skip"
            }

        config = preset.config

        # Get material types to include
        material_types_to_include = options.get("material_types_to_include", [])
        all_material_types = [mt.get("name") for mt in config.get("material_types", [])]

        # If no specific types requested, include all
        if not material_types_to_include:
            material_types_to_include = all_material_types

        with self.transaction():
            # Create a preset application record
            application = self.repository.create_preset_application(
                preset_id=preset_id,
                user_id=user_id,
                options_used=options,
                stats={}  # Will update later
            )

            try:
                # Process property definitions if requested
                if options.get("include_properties", True):
                    self._apply_property_definitions(
                        config.get("property_definitions", []),
                        options.get("conflict_resolution", "skip"),
                        stats,
                        application.id
                    )

                # Process material types
                self._apply_material_types(
                    [mt for mt in config.get("material_types", []) if mt.get("name") in material_types_to_include],
                    options.get("conflict_resolution", "skip"),
                    stats,
                    application.id
                )

                # Create sample materials if requested
                if options.get("include_sample_materials", True) and self.material_service:
                    self._apply_sample_materials(
                        [sm for sm in config.get("sample_materials", [])
                         if sm.get("material_type") in material_types_to_include],
                        options.get("conflict_resolution", "skip"),
                        stats,
                        application.id
                    )

                # Apply settings if requested
                if options.get("include_settings", True) and self.settings_service and user_id:
                    settings = config.get("settings", {})
                    for key, value in settings.items():
                        try:
                            self.settings_service.set_setting(
                                key=key,
                                value=value,
                                scope_type="user",
                                scope_id=str(user_id)
                            )
                        except Exception as e:
                            error_message = f"Failed to apply setting '{key}': {str(e)}"
                            self._add_application_error(
                                application.id,
                                "setting_error",
                                error_message,
                                "setting",
                                key
                            )
                            stats["error_count"] += 1
                            errors.append(error_message)

                # Apply theme if requested
                if options.get("theme_handling", "skip") != "skip" and self.settings_service and user_id:
                    theme = config.get("theme", {})
                    if theme:
                        try:
                            self.settings_service.set_setting(
                                key="ui.theme",
                                value=theme,
                                scope_type="user",
                                scope_id=str(user_id)
                            )
                        except Exception as e:
                            error_message = f"Failed to apply theme: {str(e)}"
                            self._add_application_error(
                                application.id,
                                "theme_error",
                                error_message,
                                "theme",
                                None
                            )
                            stats["error_count"] += 1
                            errors.append(error_message)

                # Update application stats
                self.session.query(PresetApplication).filter(
                    PresetApplication.id == application.id
                ).update(stats)

                # Commit changes
                self.session.commit()

                # Emit event if event bus is available
                if self.event_bus:
                    self.event_bus.publish({
                        "type": "preset.applied",
                        "preset_id": preset_id,
                        "user_id": user_id,
                        "options": options,
                        "stats": stats,
                        "timestamp": datetime.now().isoformat()
                    })

                # Return application result
                result = {
                    "preset_id": preset_id,
                    "user_id": user_id,
                    "applied_at": application.applied_at,
                    "options_used": options,
                    "created_property_definitions": stats["created_property_definitions"],
                    "updated_property_definitions": stats["updated_property_definitions"],
                    "created_material_types": stats["created_material_types"],
                    "updated_material_types": stats["updated_material_types"],
                    "created_materials": stats["created_materials"],
                    "errors": errors
                }

                return result

            except Exception as e:
                # Roll back transaction
                self.session.rollback()

                # Record error
                error_message = f"Preset application failed: {str(e)}"
                if application:
                    self._add_application_error(
                        application.id,
                        "application_error",
                        error_message
                    )

                raise ValidationException(error_message)

    def _apply_property_definitions(
            self,
            property_definitions: List[Dict[str, Any]],
            conflict_resolution: str,
            stats: Dict[str, int],
            application_id: int
    ):
        """Apply property definitions from a preset."""
        for prop_def in property_definitions:
            try:
                # Check if property already exists
                existing_property = self.property_service.get_property_definition_by_name(prop_def.get("name"))

                if existing_property:
                    # Handle conflict based on resolution strategy
                    if conflict_resolution == "skip":
                        continue
                    elif conflict_resolution == "overwrite":
                        # Update property
                        self.property_service.update_property_definition(
                            existing_property.id,
                            {k: v for k, v in prop_def.items() if k != "name"}
                        )
                        stats["updated_property_definitions"] += 1
                    elif conflict_resolution == "rename":
                        # Generate a new name
                        new_name = f"{prop_def.get('name')}_{uuid.uuid4().hex[:8]}"
                        prop_def["name"] = new_name

                        # Create with new name
                        self.property_service.create_property_definition(prop_def)
                        stats["created_property_definitions"] += 1
                else:
                    # Create new property
                    self.property_service.create_property_definition(prop_def)
                    stats["created_property_definitions"] += 1

            except Exception as e:
                error_message = f"Failed to apply property definition '{prop_def.get('name')}': {str(e)}"
                self._add_application_error(
                    application_id,
                    "property_error",
                    error_message,
                    "property_definition",
                    prop_def.get("name")
                )
                stats["error_count"] += 1

    def _apply_material_types(
            self,
            material_types: List[Dict[str, Any]],
            conflict_resolution: str,
            stats: Dict[str, int],
            application_id: int
    ):
        """Apply material types from a preset."""
        for mt in material_types:
            try:
                # Check if material type already exists
                existing_type = self.material_type_service.get_material_type_by_name(mt.get("name"))

                if existing_type:
                    # Handle conflict based on resolution strategy
                    if conflict_resolution == "skip":
                        continue
                    elif conflict_resolution == "overwrite":
                        # Update material type
                        self.material_type_service.update_material_type(
                            existing_type.id,
                            {k: v for k, v in mt.items() if k != "name"}
                        )
                        stats["updated_material_types"] += 1
                    elif conflict_resolution == "rename":
                        # Generate a new name
                        new_name = f"{mt.get('name')}_{uuid.uuid4().hex[:8]}"
                        mt["name"] = new_name

                        # Create with new name
                        self.material_type_service.create_material_type(mt)
                        stats["created_material_types"] += 1
                else:
                    # Create new material type
                    self.material_type_service.create_material_type(mt)
                    stats["created_material_types"] += 1

            except Exception as e:
                error_message = f"Failed to apply material type '{mt.get('name')}': {str(e)}"
                self._add_application_error(
                    application_id,
                    "material_type_error",
                    error_message,
                    "material_type",
                    mt.get("name")
                )
                stats["error_count"] += 1

    def _apply_sample_materials(
            self,
            sample_materials: List[Dict[str, Any]],
            conflict_resolution: str,
            stats: Dict[str, int],
            application_id: int
    ):
        """Apply sample materials from a preset."""
        for sm in sample_materials:
            try:
                # Get material type by name
                material_type = self.material_type_service.get_material_type_by_name(sm.get("material_type"))
                if not material_type:
                    error_message = f"Material type '{sm.get('material_type')}' not found for sample material '{sm.get('name')}'"
                    self._add_application_error(
                        application_id,
                        "sample_material_error",
                        error_message,
                        "sample_material",
                        sm.get("name")
                    )
                    stats["error_count"] += 1
                    continue

                # Check if material already exists
                existing_material = self.material_service.get_material_by_sku(sm.get("name"))

                if existing_material:
                    # Handle conflict based on resolution strategy
                    if conflict_resolution == "skip":
                        continue
                    elif conflict_resolution == "overwrite":
                        # Not updating existing materials for safety
                        continue
                    elif conflict_resolution == "rename":
                        # Generate a new name
                        new_name = f"{sm.get('name')} (Sample)"
                        sm["name"] = new_name

                        # Create with new name
                        material_data = {
                            "material_type_id": material_type.id,
                            "name": new_name,
                            "status": sm.get("status", "in_stock"),
                            "quantity": sm.get("quantity", 0),
                            "unit": sm.get("unit"),
                            "property_values": []
                        }

                        # Convert properties to property values
                        for prop_name, value in sm.get("properties", {}).items():
                            # Get property definition by name
                            prop_def = self.property_service.get_property_definition_by_name(prop_name)
                            if prop_def:
                                material_data["property_values"].append({
                                    "property_id": prop_def.id,
                                    "value": value
                                })

                        self.material_service.create_material(material_data)
                        stats["created_materials"] += 1
                else:
                    # Create new material
                    material_data = {
                        "material_type_id": material_type.id,
                        "name": sm.get("name"),
                        "status": sm.get("status", "in_stock"),
                        "quantity": sm.get("quantity", 0),
                        "unit": sm.get("unit"),
                        "property_values": []
                    }

                    # Convert properties to property values
                    for prop_name, value in sm.get("properties", {}).items():
                        # Get property definition by name
                        prop_def = self.property_service.get_property_definition_by_name(prop_name)
                        if prop_def:
                            material_data["property_values"].append({
                                "property_id": prop_def.id,
                                "value": value
                            })

                    self.material_service.create_material(material_data)
                    stats["created_materials"] += 1

            except Exception as e:
                error_message = f"Failed to apply sample material '{sm.get('name')}': {str(e)}"
                self._add_application_error(
                    application_id,
                    "sample_material_error",
                    error_message,
                    "sample_material",
                    sm.get("name")
                )
                stats["error_count"] += 1

    def _add_application_error(
            self,
            application_id: int,
            error_type: str,
            error_message: str,
            entity_type: Optional[str] = None,
            entity_name: Optional[str] = None
    ):
        """Add an error record for a preset application."""
        return self.repository.add_application_error(
            application_id=application_id,
            error_type=error_type,
            error_message=error_message,
            entity_type=entity_type,
            entity_name=entity_name
        )

    def _validate_preset_structure(self, config: Dict[str, Any]):
        """
        Validate the structure of a preset configuration.

        Args:
            config: Preset configuration

        Raises:
            ValidationException: If configuration is invalid
        """
        # Check for required sections
        if not isinstance(config, dict):
            raise ValidationException("Preset configuration must be a dictionary")

        # Check metadata
        if "metadata" not in config:
            # Add default metadata
            config["metadata"] = {
                "version": "1.0.0",
                "created_at": datetime.utcnow().isoformat(),
                "tags": []
            }

        # Check property definitions
        if "property_definitions" not in config:
            config["property_definitions"] = []
        elif not isinstance(config["property_definitions"], list):
            raise ValidationException("Property definitions must be a list")

        # Check material types
        if "material_types" not in config:
            config["material_types"] = []
        elif not isinstance(config["material_types"], list):
            raise ValidationException("Material types must be a list")

        # Check sample materials
        if "sample_materials" not in config:
            config["sample_materials"] = []
        elif not isinstance(config["sample_materials"], list):
            raise ValidationException("Sample materials must be a list")

        # Check settings
        if "settings" not in config:
            config["settings"] = {}
        elif not isinstance(config["settings"], dict):
            raise ValidationException("Settings must be a dictionary")

        # Check theme
        if "theme" not in config:
            config["theme"] = {}
        elif not isinstance(config["theme"], dict):
            raise ValidationException("Theme must be a dictionary")

        # Check property definitions
        for prop_def in config["property_definitions"]:
            if not isinstance(prop_def, dict):
                raise ValidationException("Property definition must be a dictionary")
            if "name" not in prop_def:
                raise ValidationException("Property definition must have a name")
            if "data_type" not in prop_def:
                raise ValidationException("Property definition must have a data type")

        # Check material types
        for mat_type in config["material_types"]:
            if not isinstance(mat_type, dict):
                raise ValidationException("Material type must be a dictionary")
            if "name" not in mat_type:
                raise ValidationException("Material type must have a name")

        # Check sample materials
        for sample in config["sample_materials"]:
            if not isinstance(sample, dict):
                raise ValidationException("Sample material must be a dictionary")
            if "material_type" not in sample:
                raise ValidationException("Sample material must have a material type")
            if "name" not in sample:
                raise ValidationException("Sample material must have a name")
            if "unit" not in sample:
                raise ValidationException("Sample material must have a unit")