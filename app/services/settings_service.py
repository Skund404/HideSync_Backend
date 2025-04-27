# app/services/settings_service.py

from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session
from datetime import datetime

from app.services.base_service import BaseService
from app.db.models.settings import (
    SettingsDefinition, SettingsValue, SettingsTemplate, SettingsTemplateItem
)
from app.repositories.settings_repository import (
    SettingsDefinitionRepository, SettingsValueRepository, SettingsTemplateRepository
)
from app.core.exceptions import EntityNotFoundException, ValidationException


class SettingsService:
    """
    Service for managing application settings.

    Provides functionality for:
    - Managing settings definitions
    - Retrieving setting values at different scopes
    - Setting values at different scopes
    - Working with settings templates
    """

    def __init__(
            self,
            session: Session,
            definition_repository=None,
            value_repository=None,
            template_repository=None,
            cache_service=None,
    ):
        """
        Initialize the SettingsService.

        Args:
            session: Database session
            definition_repository: Optional repository for settings definitions
            value_repository: Optional repository for settings values
            template_repository: Optional repository for settings templates
            cache_service: Optional cache service
        """
        self.session = session
        self.definition_repository = definition_repository or SettingsDefinitionRepository(session)
        self.value_repository = value_repository or SettingsValueRepository(session)
        self.template_repository = template_repository or SettingsTemplateRepository(session)
        self.cache_service = cache_service

    def get_definition(self, key: str) -> Optional[SettingsDefinition]:
        """
        Get a settings definition by key.

        Args:
            key: Key of the setting

        Returns:
            SettingsDefinition if found, None otherwise
        """
        # Try cache first if available
        if self.cache_service:
            cache_key = f"settings_definition:{key}"
            cached_definition = self.cache_service.get(cache_key)
            if cached_definition:
                return cached_definition

        # Get from database
        definition = self.definition_repository.get_by_key(key)

        # Cache result if found
        if definition and self.cache_service:
            self.cache_service.set(cache_key, definition, ttl=3600)

        return definition

    def list_definitions(
            self,
            category: Optional[str] = None,
            subcategory: Optional[str] = None,
            applies_to: Optional[str] = None,
            skip: int = 0,
            limit: int = 100
    ) -> List[SettingsDefinition]:
        """
        List settings definitions with filtering.

        Args:
            category: Optional filter by category
            subcategory: Optional filter by subcategory
            applies_to: Optional filter by applies_to
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of settings definitions
        """
        return self.definition_repository.list_with_translations(
            category=category,
            subcategory=subcategory,
            applies_to=applies_to,
            skip=skip,
            limit=limit
        )

    def create_definition(self, data: Dict[str, Any]) -> SettingsDefinition:
        """
        Create a new settings definition.

        Args:
            data: Dictionary with definition fields

        Returns:
            Created SettingsDefinition

        Raises:
            ValidationException: If validation fails
        """
        try:
            # Validate required fields
            for field in ["key", "name", "data_type", "applies_to"]:
                if field not in data or not data[field]:
                    raise ValidationException(f"Field '{field}' is required")

            # Check that the key doesn't exist
            existing = self.definition_repository.get_by_key(data["key"])
            if existing:
                raise ValidationException(f"Setting with key '{data['key']}' already exists")

            # Create the definition
            definition = self.definition_repository.create(data)

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate_pattern("settings_definition:*")
                self.cache_service.invalidate_pattern("settings_definitions:*")

            return definition

        except Exception as e:
            # Ensure transaction is rolled back
            self.session.rollback()
            raise

    def update_definition(self, key: str, data: Dict[str, Any]) -> Optional[SettingsDefinition]:
        """
        Update a settings definition.

        Args:
            key: Key of the setting to update
            data: Dictionary with fields to update

        Returns:
            Updated SettingsDefinition if found, None otherwise

        Raises:
            ValidationException: If validation fails
        """
        try:
            # Get the definition
            definition = self.definition_repository.get_by_key(key)
            if not definition:
                return None

            # Key can't be changed
            if "key" in data:
                data.pop("key")

            # Update the definition
            for field, value in data.items():
                if hasattr(definition, field):
                    setattr(definition, field, value)

            # Update translations if provided
            if "translations" in data:
                # Clear existing translations
                for translation in definition.translations:
                    self.session.delete(translation)

                # Add new translations
                for locale, trans_data in data["translations"].items():
                    translation = SettingsDefinitionTranslation(
                        definition_id=definition.id,
                        locale=locale,
                        display_name=trans_data.get("display_name", definition.name),
                        description=trans_data.get("description")
                    )
                    self.session.add(translation)

            self.session.commit()

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"settings_definition:{key}")
                self.cache_service.invalidate_pattern("settings_definitions:*")

            return definition

        except Exception as e:
            # Ensure transaction is rolled back
            self.session.rollback()
            raise

    def delete_definition(self, key: str) -> bool:
        """
        Delete a settings definition.

        Args:
            key: Key of the setting to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            # Get the definition
            definition = self.definition_repository.get_by_key(key)
            if not definition:
                return False

            # Can't delete system settings
            if definition.is_system:
                return False

            # Delete the definition (will cascade to translations)
            self.session.delete(definition)
            self.session.commit()

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"settings_definition:{key}")
                self.cache_service.invalidate_pattern("settings_definitions:*")

            return True

        except Exception as e:
            # Ensure transaction is rolled back
            self.session.rollback()
            raise

    def get_setting(
            self,
            key: str,
            scope_type: str = "system",
            scope_id: str = "1"
    ) -> Any:
        """
        Get a setting value with fallback to default.

        Args:
            key: Key of the setting
            scope_type: Type of scope (system, organization, user)
            scope_id: ID of the scope entity

        Returns:
            Setting value, or default value if not set

        Raises:
            EntityNotFoundException: If setting definition doesn't exist
        """
        # Try cache first if available
        if self.cache_service:
            cache_key = f"setting:{scope_type}:{scope_id}:{key}"
            cached_value = self.cache_service.get(cache_key)
            if cached_value is not None:  # Allow for false/zero/empty values
                return cached_value

        # Get the definition
        definition = self.get_definition(key)
        if not definition:
            raise EntityNotFoundException(f"Setting definition with key '{key}' not found")

        # Try to get the value
        setting_value = self.value_repository.get_value(scope_type, scope_id, key)

        # Get the actual value or default
        value = setting_value.value if setting_value else definition.default_value

        # Cache the result if needed
        if self.cache_service:
            cache_key = f"setting:{scope_type}:{scope_id}:{key}"
            self.cache_service.set(cache_key, value, ttl=3600)

        return value

    def get_settings_by_category(
            self,
            category: str,
            scope_type: str = "system",
            scope_id: str = "1"
    ) -> Dict[str, Any]:
        """
        Get all settings for a category.

        Args:
            category: Category of settings
            scope_type: Type of scope (system, organization, user)
            scope_id: ID of the scope entity

        Returns:
            Dictionary of setting keys and values
        """
        # Try cache first if available
        if self.cache_service:
            cache_key = f"settings:{scope_type}:{scope_id}:{category}"
            cached_values = self.cache_service.get(cache_key)
            if cached_values:
                return cached_values

        # Get all definitions for the category
        definitions = self.list_definitions(category=category)

        # Get all values for this scope
        setting_keys = [d.key for d in definitions]
        values = self.value_repository.get_values_by_keys(scope_type, scope_id, setting_keys)

        # Build result with values or defaults
        result = {}
        values_dict = {v.setting_key: v.value for v in values}

        for definition in definitions:
            if definition.key in values_dict:
                result[definition.key] = values_dict[definition.key]
            else:
                result[definition.key] = definition.default_value

        # Cache the result if needed
        if self.cache_service and result:
            cache_key = f"settings:{scope_type}:{scope_id}:{category}"
            self.cache_service.set(cache_key, result, ttl=3600)

        return result

    def set_setting(
            self,
            key: str,
            value: Any,
            scope_type: str = "system",
            scope_id: str = "1"
    ) -> None:
        """
        Set a setting value.

        Args:
            key: Key of the setting
            value: Value to set
            scope_type: Type of scope (system, organization, user)
            scope_id: ID of the scope entity

        Raises:
            EntityNotFoundException: If setting definition doesn't exist
            ValidationException: If value doesn't validate
        """
        try:
            # Get the definition
            definition = self.get_definition(key)
            if not definition:
                raise EntityNotFoundException(f"Setting definition with key '{key}' not found")

            # Check that the scope is valid for this setting
            if definition.applies_to != "all" and definition.applies_to != scope_type:
                raise ValidationException(
                    f"Setting '{key}' cannot be applied to scope '{scope_type}'"
                )

            # Validate the value
            self._validate_setting_value(definition, value)

            # Set the value
            self.value_repository.set_value(scope_type, scope_id, key, value)
            self.session.commit()

            # Invalidate cache if needed
            if self.cache_service:
                self.cache_service.invalidate(f"setting:{scope_type}:{scope_id}:{key}")
                self.cache_service.invalidate_pattern(f"settings:{scope_type}:{scope_id}:*")

        except Exception as e:
            # Ensure transaction is rolled back
            self.session.rollback()
            raise

    def _validate_setting_value(self, definition: SettingsDefinition, value: Any) -> None:
        """
        Validate a setting value against its definition.

        Args:
            definition: Setting definition
            value: Value to validate

        Raises:
            ValidationException: If validation fails
        """
        data_type = definition.data_type
        validation_rules = definition.validation_rules or {}

        # Check data type
        if data_type == "string":
            if not isinstance(value, str):
                raise ValidationException(f"Value must be a string for setting '{definition.key}'")

            # Check string validation rules
            if "min_length" in validation_rules and len(value) < validation_rules["min_length"]:
                raise ValidationException(
                    f"Value must be at least {validation_rules['min_length']} characters for setting '{definition.key}'"
                )

            if "max_length" in validation_rules and len(value) > validation_rules["max_length"]:
                raise ValidationException(
                    f"Value must be at most {validation_rules['max_length']} characters for setting '{definition.key}'"
                )

            if "pattern" in validation_rules:
                import re
                if not re.match(validation_rules["pattern"], value):
                    raise ValidationException(
                        f"Value doesn't match pattern '{validation_rules['pattern']}' for setting '{definition.key}'"
                    )

        elif data_type == "number":
            if not isinstance(value, (int, float)):
                raise ValidationException(f"Value must be a number for setting '{definition.key}'")

            # Check number validation rules
            if "min" in validation_rules and value < validation_rules["min"]:
                raise ValidationException(
                    f"Value must be at least {validation_rules['min']} for setting '{definition.key}'"
                )

            if "max" in validation_rules and value > validation_rules["max"]:
                raise ValidationException(
                    f"Value must be at most {validation_rules['max']} for setting '{definition.key}'"
                )

        elif data_type == "boolean":
            if not isinstance(value, bool):
                raise ValidationException(f"Value must be a boolean for setting '{definition.key}'")

        elif data_type == "enum":
            if "options" in validation_rules and value not in validation_rules["options"]:
                raise ValidationException(
                    f"Value must be one of {validation_rules['options']} for setting '{definition.key}'"
                )

        # For 'json' and other types, we don't validate structure here

    def apply_template(
            self,
            template_id: int,
            scope_type: str,
            scope_id: str
    ) -> Dict[str, Any]:
        """
        Apply a settings template to a scope.

        Args:
            template_id: ID of the template
            scope_type: Type of scope (system, organization, user)
            scope_id: ID of the scope entity

        Returns:
            Dictionary of applied settings

        Raises:
            EntityNotFoundException: If template doesn't exist
            ValidationException: If scope is invalid for the template
        """
        try:
            # Get the template
            template = self.template_repository.get_by_id_with_items(template_id)
            if not template:
                raise EntityNotFoundException(f"Settings template with ID {template_id} not found")

            # Check that the scope is valid for this template
            if template.applies_to != "all" and template.applies_to != scope_type:
                raise ValidationException(
                    f"Template '{template.name}' cannot be applied to scope '{scope_type}'"
                )

            # Apply all settings from the template
            result = {}
            for item in template.items:
                # Get the definition
                definition = self.get_definition(item.setting_key)
                if not definition:
                    continue

                # Validate the value
                self._validate_setting_value(definition, item.value)

                # Set the value
                self.value_repository.set_value(scope_type, scope_id, item.setting_key, item.value)
                result[item.setting_key] = item.value

            self.session.commit()

            # Invalidate cache if needed
            if self.cache_service:
                for key in result:
                    self.cache_service.invalidate(f"setting:{scope_type}:{scope_id}:{key}")
                self.cache_service.invalidate_pattern(f"settings:{scope_type}:{scope_id}:*")

            return result

        except Exception as e:
            # Ensure transaction is rolled back
            self.session.rollback()
            raise

    def register_settings(self, definitions: List[Dict[str, Any]]) -> List[SettingsDefinition]:
        """
        Register multiple settings definitions, skipping existing ones.

        Args:
            definitions: List of setting definitions

        Returns:
            List of created/updated definitions
        """
        try:
            result = []

            for definition_data in definitions:
                # Check if definition already exists
                key = definition_data.get("key")
                if not key:
                    continue

                existing = self.definition_repository.get_by_key(key)

                if existing:
                    # Update only if it's not a system setting
                    if not existing.is_system or definition_data.get("is_system", False):
                        # Update existing definition
                        for field, value in definition_data.items():
                            if field != "key" and hasattr(existing, field):
                                setattr(existing, field, value)

                        # Add to result
                        result.append(existing)
                else:
                    # Create new definition
                    new_definition = self.definition_repository.create(definition_data)
                    result.append(new_definition)

            self.session.commit()

            # Invalidate cache if needed
            if self.cache_service and result:
                self.cache_service.invalidate_pattern("settings_definition:*")
                self.cache_service.invalidate_pattern("settings_definitions:*")

            return result

        except Exception as e:
            # Ensure transaction is rolled back
            self.session.rollback()
            raise