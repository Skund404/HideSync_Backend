# File: app/services/localization_service.py

"""
Centralized Localization Service

This service manages entity field translations for all entity types in the HideSync system.
It mirrors the EnumService pattern for consistency with the Dynamic Enum System and provides
a unified interface for translation operations across all domains.
"""

import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime

from app.repositories.repository_factory import RepositoryFactory
from app.repositories.entity_translation_repository import EntityTranslationRepository
from app.core.config import settings
from app.core.exceptions import EntityNotFoundException, ValidationException

logger = logging.getLogger(__name__)


class LocalizationService:
    """
    Centralized service for managing entity field translations.

    This service follows the exact same architectural pattern as EnumService,
    providing a single point of control for all translation operations while
    maintaining clear separation from the Dynamic Enum System.
    """

    # Registry of supported entity types and their configurations
    ENTITY_REGISTRY = {
        "workflow": {
            "main_repo_method": "create_workflow_repository",
            "translatable_fields": ["name", "description"]
        },
        "workflow_step": {
            "main_repo_method": "create_workflow_step_repository",
            "translatable_fields": ["name", "description", "instructions"]
        },
        "workflow_outcome": {
            "main_repo_method": "create_workflow_outcome_repository",
            "translatable_fields": ["name", "description"]
        },
        "workflow_decision_option": {
            "main_repo_method": "create_workflow_decision_option_repository",
            "translatable_fields": ["option_text", "description", "tooltip"]
        },
        "workflow_theme": {
            "main_repo_method": "create_workflow_theme_repository",
            "translatable_fields": ["name", "description"]
        },
        "product": {
            "main_repo_method": "create_product_repository",
            "translatable_fields": ["name", "description", "summary", "features"]
        },
        "tool": {
            "main_repo_method": "create_tool_repository",
            "translatable_fields": ["name", "description", "usage_notes", "specifications"]
        },
        "dynamic_material": {
            "main_repo_method": "create_dynamic_material_repository",
            "translatable_fields": ["name", "description", "notes"]
        },
        "material_type": {
            "main_repo_method": "create_material_type_repository",
            "translatable_fields": ["name", "description"]
        }
        # Add additional entities as needed
    }

    def __init__(self, session: Session, repository_factory: Optional[RepositoryFactory] = None):
        """
        Initialize the LocalizationService.

        Args:
            session: SQLAlchemy database session
            repository_factory: Optional repository factory instance
        """
        self.session = session
        self.repo_factory = repository_factory or RepositoryFactory(session)
        self.default_locale = getattr(settings, 'DEFAULT_LOCALE', 'en')

        # Single translation repository handles all entities
        self.translation_repo: EntityTranslationRepository = (
            self.repo_factory.create_entity_translation_repository()
        )

        # Cache for main entity repositories
        self._main_repo_cache = {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_supported_locales(self) -> List[str]:
        """
        Get list of supported locales from configuration.

        Returns:
            List of supported locale codes
        """
        return getattr(settings, 'SUPPORTED_LOCALES', ["en", "de", "fr", "es"])

    def get_supported_entity_types(self) -> List[str]:
        """
        Get list of supported entity types for translation.

        Returns:
            List of entity type strings
        """
        return list(self.ENTITY_REGISTRY.keys())

    def get_translatable_fields(self, entity_type: str) -> List[str]:
        """
        Get list of translatable fields for an entity type.

        Args:
            entity_type: Type of entity

        Returns:
            List of field names that can be translated

        Raises:
            ValidationException: If entity type is not supported
        """
        if entity_type not in self.ENTITY_REGISTRY:
            raise ValidationException(f"Unsupported entity type: {entity_type}")
        return self.ENTITY_REGISTRY[entity_type]["translatable_fields"]

    def _get_main_entity_repository(self, entity_type: str) -> Optional[Any]:
        """
        Get main entity repository with caching.

        Args:
            entity_type: Type of entity

        Returns:
            Repository instance or None if not found
        """
        if entity_type not in self.ENTITY_REGISTRY:
            return None

        if entity_type not in self._main_repo_cache:
            config = self.ENTITY_REGISTRY[entity_type]
            repo_method = getattr(self.repo_factory, config["main_repo_method"], None)
            if repo_method:
                self._main_repo_cache[entity_type] = repo_method()
            else:
                self.logger.error(
                    f"Main repository factory method not found: {config['main_repo_method']}"
                )
                return None

        return self._main_repo_cache[entity_type]

    def _get_entity_default_value(
            self,
            entity_type: str,
            entity_id: int,
            field_name: str
    ) -> Optional[str]:
        """
        Fetch default field value from main entity for fallback.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            field_name: Name of the field

        Returns:
            Default field value or None if not found
        """
        main_repo = self._get_main_entity_repository(entity_type)
        if not main_repo:
            self.logger.warning(f"Cannot fetch default value - no main repository for {entity_type}")
            return None

        try:
            entity = main_repo.get_by_id(entity_id)
            if entity and hasattr(entity, field_name):
                return getattr(entity, field_name)
        except Exception as e:
            self.logger.error(f"Error fetching default value for {entity_type} {entity_id}.{field_name}: {e}")

        return None

    def get_translation(
            self,
            entity_type: str,
            entity_id: int,
            field_name: str,
            locale: str,
            use_fallback: bool = True
    ) -> Optional[str]:
        """
        Get translation for an entity field with intelligent fallback strategy.

        Fallback order:
        1. Requested locale translation
        2. Default locale translation (if different from requested)
        3. Original entity field value

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            field_name: Name of the field
            locale: Requested locale code
            use_fallback: Whether to use fallback strategy

        Returns:
            Translated value or None if not found

        Raises:
            ValidationException: If entity type or field is not supported
        """
        # Validate entity type and field
        if entity_type not in self.ENTITY_REGISTRY:
            raise ValidationException(f"Unsupported entity type: {entity_type}")

        translatable_fields = self.get_translatable_fields(entity_type)
        if field_name not in translatable_fields:
            raise ValidationException(
                f"Field '{field_name}' is not translatable for entity type '{entity_type}'. "
                f"Supported fields: {translatable_fields}"
            )

        # Try requested locale
        translation_obj = self.translation_repo.find_translation(entity_type, entity_id, locale, field_name)
        if translation_obj:
            return translation_obj.translated_value

        # Fallback to default locale if different
        if use_fallback and locale != self.default_locale:
            fallback_translation = self.translation_repo.find_translation(
                entity_type, entity_id, self.default_locale, field_name
            )
            if fallback_translation:
                return fallback_translation.translated_value

        # Final fallback to original field value
        if use_fallback:
            return self._get_entity_default_value(entity_type, entity_id, field_name)

        return None

    def get_all_translations_for_field(
            self,
            entity_type: str,
            entity_id: int,
            field_name: str
    ) -> Dict[str, str]:
        """
        Get all available translations for a specific field, keyed by locale.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            field_name: Name of the field

        Returns:
            Dictionary mapping locale codes to translated values

        Raises:
            ValidationException: If entity type is not supported
        """
        if entity_type not in self.ENTITY_REGISTRY:
            raise ValidationException(f"Unsupported entity type: {entity_type}")

        translations = self.translation_repo.find_translations_for_field(entity_type, entity_id, field_name)
        return {t.locale: t.translated_value for t in translations}

    def get_translations_for_entity_by_locale(
            self,
            entity_type: str,
            entity_id: int,
            locale: str
    ) -> Dict[str, str]:
        """
        Get all translated fields for an entity in a specific locale.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            locale: Locale code

        Returns:
            Dictionary mapping field names to translated values

        Raises:
            ValidationException: If entity type is not supported
        """
        if entity_type not in self.ENTITY_REGISTRY:
            raise ValidationException(f"Unsupported entity type: {entity_type}")

        translations = self.translation_repo.find_translations_for_entity(
            entity_type, entity_id, locale=locale
        )
        return {t.field_name: t.translated_value for t in translations}

    def create_or_update_translation(
            self,
            entity_type: str,
            entity_id: int,
            locale: str,
            field_name: str,
            translated_value: str,
            user_id: Optional[int] = None
    ) -> Any:
        """
        Create or update a translation with comprehensive validation.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            locale: Locale code
            field_name: Name of the field
            translated_value: The translated content
            user_id: Optional user ID for audit logging

        Returns:
            The created or updated EntityTranslation object

        Raises:
            ValidationException: If validation fails
            EntityNotFoundException: If the main entity doesn't exist
        """
        # Validate inputs
        if entity_type not in self.ENTITY_REGISTRY:
            raise ValidationException(f"Unsupported entity type: {entity_type}")

        if locale not in self.get_supported_locales():
            raise ValidationException(f"Unsupported locale: {locale}")

        translatable_fields = self.get_translatable_fields(entity_type)
        if field_name not in translatable_fields:
            raise ValidationException(
                f"Field '{field_name}' is not translatable for {entity_type}. "
                f"Supported: {translatable_fields}"
            )

        # Validate entity exists
        main_repo = self._get_main_entity_repository(entity_type)
        if main_repo and not main_repo.get_by_id(entity_id):
            raise EntityNotFoundException(entity_type.capitalize(), entity_id)

        # Create or update translation
        try:
            translation_obj = self.translation_repo.upsert_translation(
                entity_type, entity_id, locale, field_name, translated_value, user_id
            )
            self.logger.info(
                f"Translation upserted: {entity_type}#{entity_id}.{field_name} "
                f"[{locale}] by user {user_id}"
            )
            return translation_obj
        except Exception as e:
            self.logger.error(f"Failed to upsert translation: {e}")
            raise ValidationException(f"Failed to save translation: {str(e)}")

    def delete_translation(
            self,
            translation_id: int,
            user_id: Optional[int] = None
    ) -> bool:
        """
        Delete a specific translation by its ID.

        Args:
            translation_id: ID of the translation to delete
            user_id: Optional user ID for audit logging

        Returns:
            True if deletion was successful

        Raises:
            EntityNotFoundException: If translation doesn't exist
            ValidationException: If deletion fails
        """
        # Verify translation exists
        translation = self.translation_repo.get_by_id(translation_id)
        if not translation:
            raise EntityNotFoundException("EntityTranslation", translation_id)

        try:
            result = self.translation_repo.delete(translation_id)
            if result:
                self.logger.info(f"Translation deleted: ID {translation_id} by user {user_id}")
            return result
        except Exception as e:
            self.logger.error(f"Failed to delete translation {translation_id}: {e}")
            raise ValidationException(f"Failed to delete translation: {str(e)}")

    def hydrate_entity_with_translations(
            self,
            entity: Any,
            entity_type: str,
            locale: str,
            fields_to_translate: Optional[List[str]] = None
    ) -> Any:
        """
        Hydrate entity object with translated field values.

        This method modifies the entity object in-place by replacing field values
        with their translated equivalents for the specified locale.

        Args:
            entity: The entity object to hydrate
            entity_type: Type of entity
            locale: Locale code for translations
            fields_to_translate: Optional list of specific fields to translate

        Returns:
            The modified entity object
        """
        if not entity or not hasattr(entity, 'id'):
            return entity

        if entity_type not in self.ENTITY_REGISTRY:
            self.logger.warning(f"Cannot hydrate unsupported entity type: {entity_type}")
            return entity

        # Use provided fields or default translatable fields
        if fields_to_translate is None:
            fields_to_translate = self.get_translatable_fields(entity_type)

        for field_name in fields_to_translate:
            if hasattr(entity, field_name):
                try:
                    translated_value = self.get_translation(
                        entity_type, entity.id, field_name, locale, use_fallback=True
                    )
                    if translated_value is not None:
                        setattr(entity, field_name, translated_value)
                except Exception as e:
                    self.logger.warning(f"Failed to translate {entity_type}.{field_name}: {e}")
                    # Continue with original value

        return entity

    def bulk_hydrate_entities(
            self,
            entities: List[Any],
            entity_type: str,
            locale: str,
            fields_to_translate: Optional[List[str]] = None
    ) -> List[Any]:
        """
        Efficiently hydrate multiple entities with translations.

        Args:
            entities: List of entity objects to hydrate
            entity_type: Type of entities
            locale: Locale code for translations
            fields_to_translate: Optional list of specific fields to translate

        Returns:
            List of modified entity objects
        """
        if not entities:
            return entities

        for entity in entities:
            self.hydrate_entity_with_translations(entity, entity_type, locale, fields_to_translate)

        return entities

    # Utility and administrative methods
    def get_translation_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about available translations.

        Returns:
            Dictionary containing translation system statistics
        """
        try:
            # Get database statistics
            db_stats = self.translation_repo.get_translation_statistics()

            # Enhance with service-level information
            stats = {
                "total_entity_types": len(db_stats.get("entity_types", [])),
                "entity_types": db_stats.get("entity_types", []),
                "supported_locales": self.get_supported_locales(),
                "supported_entity_types": self.get_supported_entity_types(),
                "configured_entity_types": len(self.ENTITY_REGISTRY),
                "total_translations": db_stats.get("total_translations", 0),
                "unique_entities": db_stats.get("unique_entities", 0),
                "latest_update": db_stats.get("latest_update"),
                "distribution": {
                    "by_entity_type": db_stats.get("entity_type_distribution", {}),
                    "by_locale": db_stats.get("locale_distribution", {})
                }
            }

            return stats
        except Exception as e:
            self.logger.error(f"Failed to get translation statistics: {e}")
            return {
                "error": str(e),
                "supported_locales": self.get_supported_locales(),
                "supported_entity_types": self.get_supported_entity_types()
            }

    def validate_entity_translation_setup(self, entity_type: str, entity_id: int) -> Dict[str, Any]:
        """
        Validate translation setup for a specific entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Returns:
            Dictionary containing validation results and recommendations

        Raises:
            ValidationException: If entity type is not supported
        """
        if entity_type not in self.ENTITY_REGISTRY:
            raise ValidationException(f"Unsupported entity type: {entity_type}")

        # Check if entity exists
        main_repo = self._get_main_entity_repository(entity_type)
        entity_exists = bool(main_repo and main_repo.get_by_id(entity_id))

        # Get available translations
        translations = self.translation_repo.find_translations_for_entity(entity_type, entity_id)
        available_locales = list(set(t.locale for t in translations))
        translated_fields = list(set(t.field_name for t in translations))

        # Calculate completeness
        supported_locales = self.get_supported_locales()
        translatable_fields = self.get_translatable_fields(entity_type)

        total_possible = len(supported_locales) * len(translatable_fields)
        total_existing = len(translations)
        completeness_percentage = (total_existing / total_possible * 100) if total_possible > 0 else 0

        # Generate recommendations
        recommendations = []
        missing_locales = set(supported_locales) - set(available_locales)
        missing_fields = set(translatable_fields) - set(translated_fields)

        if missing_locales:
            recommendations.append(f"Add translations for locales: {', '.join(sorted(missing_locales))}")
        if missing_fields:
            recommendations.append(f"Add translations for fields: {', '.join(sorted(missing_fields))}")
        if completeness_percentage < 100:
            recommendations.append(
                f"Translation coverage is {completeness_percentage:.1f}% - consider completing all translations")

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_exists": entity_exists,
            "translatable_fields": translatable_fields,
            "translated_fields": translated_fields,
            "available_locales": available_locales,
            "supported_locales": supported_locales,
            "translation_count": len(translations),
            "completeness_percentage": round(completeness_percentage, 1),
            "recommendations": recommendations
        }

    def cleanup_orphaned_translations(
            self,
            entity_type: str,
            dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Clean up translations for entities that no longer exist.

        Args:
            entity_type: Type of entity to clean up
            dry_run: If True, only report what would be cleaned up

        Returns:
            Dictionary containing cleanup results

        Raises:
            ValidationException: If entity type is not supported
        """
        if entity_type not in self.ENTITY_REGISTRY:
            raise ValidationException(f"Unsupported entity type: {entity_type}")

        try:
            # Get valid entity IDs from the main repository
            main_repo = self._get_main_entity_repository(entity_type)
            if not main_repo:
                return {"error": f"No main repository available for {entity_type}"}

            # Get all entity IDs (this assumes main repo has a method to get all IDs)
            # This might need to be adjusted based on your base repository implementation
            valid_entities = main_repo.get_all()  # or appropriate method
            valid_entity_ids = [entity.id for entity in valid_entities] if valid_entities else []

            # Perform cleanup
            orphaned_count, orphaned_ids = self.translation_repo.cleanup_orphaned_translations(
                entity_type, valid_entity_ids, dry_run
            )

            return {
                "entity_type": entity_type,
                "dry_run": dry_run,
                "valid_entities": len(valid_entity_ids),
                "orphaned_translations": orphaned_count,
                "orphaned_entity_ids": orphaned_ids,
                "action": "would_delete" if dry_run else "deleted"
            }

        except Exception as e:
            self.logger.error(f"Failed to cleanup orphaned translations for {entity_type}: {e}")
            return {"error": str(e)}