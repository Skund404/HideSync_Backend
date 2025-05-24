# File: app/repositories/entity_translation_repository.py

"""
Universal Entity Translation Repository

This repository handles all translation operations for any entity type in the HideSync system.
It follows the same architectural patterns established by other repositories in the system
and provides comprehensive error handling, logging, and performance optimization.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func, and_, or_

from app.repositories.base_repository import BaseRepository
from app.db.models.entity_translation import EntityTranslation
from app.core.exceptions import (
    DatabaseException,
    ValidationException,
    EntityNotFoundException
)

logger = logging.getLogger(__name__)


class EntityTranslationRepository(BaseRepository[EntityTranslation]):
    """
    Universal repository for all entity translation operations.

    This repository provides a complete set of translation management operations
    for any entity type in the system, following the established patterns from
    the Dynamic Enum System while providing enhanced functionality for complex
    translation scenarios.
    """

    def __init__(self, db_session: Session):
        """
        Initialize the translation repository.

        Args:
            db_session: SQLAlchemy database session
        """
        super().__init__(db_session, EntityTranslation)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def find_translation(
            self,
            entity_type: str,
            entity_id: int,
            locale: str,
            field_name: str
    ) -> Optional[EntityTranslation]:
        """
        Find a specific translation by entity, locale, and field.

        Args:
            entity_type: Type of entity (e.g., 'product', 'workflow')
            entity_id: ID of the specific entity instance
            locale: Language code (e.g., 'en', 'de')
            field_name: Name of the field being translated

        Returns:
            EntityTranslation object if found, None otherwise

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            self.logger.debug(
                f"Finding translation: entity_type={entity_type}, entity_id={entity_id}, "
                f"locale={locale}, field_name={field_name}"
            )

            translation = self.db_session.query(EntityTranslation).filter(
                and_(
                    EntityTranslation.entity_type == entity_type,
                    EntityTranslation.entity_id == entity_id,
                    EntityTranslation.locale == locale,
                    EntityTranslation.field_name == field_name
                )
            ).first()

            if translation:
                self.logger.debug(f"Found translation with ID: {translation.id}")
            else:
                self.logger.debug("No translation found for specified criteria")

            return translation

        except SQLAlchemyError as e:
            self.logger.error(f"Database error finding translation: {e}", exc_info=True)
            raise DatabaseException(f"Failed to find translation: {str(e)}")

    def find_translations_for_entity(
            self,
            entity_type: str,
            entity_id: int,
            locale: Optional[str] = None,
            field_names: Optional[List[str]] = None
    ) -> List[EntityTranslation]:
        """
        Find all translations for an entity, optionally filtered by locale and fields.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            locale: Optional locale filter
            field_names: Optional list of field names to filter by

        Returns:
            List of EntityTranslation objects

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            self.logger.debug(
                f"Finding translations for entity: entity_type={entity_type}, "
                f"entity_id={entity_id}, locale={locale}, fields={field_names}"
            )

            query = self.db_session.query(EntityTranslation).filter(
                and_(
                    EntityTranslation.entity_type == entity_type,
                    EntityTranslation.entity_id == entity_id
                )
            )

            if locale:
                query = query.filter(EntityTranslation.locale == locale)

            if field_names:
                query = query.filter(EntityTranslation.field_name.in_(field_names))

            # Order by locale and field_name for consistent results
            translations = query.order_by(
                EntityTranslation.locale,
                EntityTranslation.field_name
            ).all()

            self.logger.debug(f"Found {len(translations)} translations")
            return translations

        except SQLAlchemyError as e:
            self.logger.error(f"Database error finding entity translations: {e}", exc_info=True)
            raise DatabaseException(f"Failed to find entity translations: {str(e)}")

    def find_translations_for_field(
            self,
            entity_type: str,
            entity_id: int,
            field_name: str,
            locales: Optional[List[str]] = None
    ) -> List[EntityTranslation]:
        """
        Find all translations for a specific field across locales.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            field_name: Name of the field
            locales: Optional list of locales to filter by

        Returns:
            List of EntityTranslation objects

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            self.logger.debug(
                f"Finding field translations: entity_type={entity_type}, "
                f"entity_id={entity_id}, field_name={field_name}, locales={locales}"
            )

            query = self.db_session.query(EntityTranslation).filter(
                and_(
                    EntityTranslation.entity_type == entity_type,
                    EntityTranslation.entity_id == entity_id,
                    EntityTranslation.field_name == field_name
                )
            )

            if locales:
                query = query.filter(EntityTranslation.locale.in_(locales))

            translations = query.order_by(EntityTranslation.locale).all()

            self.logger.debug(f"Found {len(translations)} field translations")
            return translations

        except SQLAlchemyError as e:
            self.logger.error(f"Database error finding field translations: {e}", exc_info=True)
            raise DatabaseException(f"Failed to find field translations: {str(e)}")

    def find_all_for_entity_type(
            self,
            entity_type: str,
            locale: Optional[str] = None,
            limit: Optional[int] = None,
            offset: Optional[int] = None
    ) -> Tuple[List[EntityTranslation], int]:
        """
        Find all translations for an entity type with pagination.

        Args:
            entity_type: Type of entity
            locale: Optional locale filter
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            Tuple of (translations_list, total_count)

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            self.logger.debug(
                f"Finding translations for entity type: {entity_type}, "
                f"locale={locale}, limit={limit}, offset={offset}"
            )

            query = self.db_session.query(EntityTranslation).filter(
                EntityTranslation.entity_type == entity_type
            )

            if locale:
                query = query.filter(EntityTranslation.locale == locale)

            # Get total count before applying pagination
            total_count = query.count()

            # Apply pagination
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)

            translations = query.order_by(
                EntityTranslation.entity_id,
                EntityTranslation.locale,
                EntityTranslation.field_name
            ).all()

            self.logger.debug(f"Found {len(translations)} translations (total: {total_count})")
            return translations, total_count

        except SQLAlchemyError as e:
            self.logger.error(f"Database error finding entity type translations: {e}", exc_info=True)
            raise DatabaseException(f"Failed to find entity type translations: {str(e)}")

    def upsert_translation(
            self,
            entity_type: str,
            entity_id: int,
            locale: str,
            field_name: str,
            translated_value: str,
            user_id: Optional[int] = None
    ) -> EntityTranslation:
        """
        Create or update a translation with comprehensive error handling.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            locale: Language code
            field_name: Name of the field
            translated_value: The translated content
            user_id: Optional user ID for audit logging

        Returns:
            The created or updated EntityTranslation object

        Raises:
            ValidationException: If input validation fails
            DatabaseException: If database operation fails
        """
        try:
            # Input validation
            if not entity_type or not entity_type.strip():
                raise ValidationException("Entity type cannot be empty")
            if entity_id <= 0:
                raise ValidationException("Entity ID must be positive")
            if not locale or not locale.strip():
                raise ValidationException("Locale cannot be empty")
            if not field_name or not field_name.strip():
                raise ValidationException("Field name cannot be empty")
            if not translated_value or not translated_value.strip():
                raise ValidationException("Translated value cannot be empty")

            # Clean inputs
            entity_type = entity_type.strip().lower()
            locale = locale.strip().lower()
            field_name = field_name.strip().lower()
            translated_value = translated_value.strip()

            self.logger.info(
                f"Upserting translation: entity_type={entity_type}, entity_id={entity_id}, "
                f"locale={locale}, field_name={field_name}, user_id={user_id}"
            )

            # Try to find existing translation
            existing = self.find_translation(entity_type, entity_id, locale, field_name)

            if existing:
                # Update existing translation
                old_value = existing.translated_value
                updated_data = {
                    "translated_value": translated_value,
                    "updated_at": datetime.utcnow()
                }

                updated = self.update(existing.id, updated_data)

                self.logger.info(
                    f"Updated translation ID {existing.id}: "
                    f"'{old_value[:50]}...' -> '{translated_value[:50]}...'"
                )

                return updated
            else:
                # Create new translation
                new_data = {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "locale": locale,
                    "field_name": field_name,
                    "translated_value": translated_value
                }

                created = self.create(new_data)

                self.logger.info(
                    f"Created translation ID {created.id} for "
                    f"{entity_type}#{entity_id}.{field_name} [{locale}]"
                )

                return created

        except ValidationException:
            # Re-raise validation exceptions as-is
            raise
        except IntegrityError as e:
            self.logger.error(f"Integrity error in upsert_translation: {e}", exc_info=True)
            # Handle potential race condition where translation was created between find and create
            self.db_session.rollback()
            existing = self.find_translation(entity_type, entity_id, locale, field_name)
            if existing:
                # Another process created it, update instead
                return self.update(existing.id, {
                    "translated_value": translated_value,
                    "updated_at": datetime.utcnow()
                })
            else:
                raise DatabaseException(f"Database integrity error: {str(e)}")
        except SQLAlchemyError as e:
            self.logger.error(f"Database error in upsert_translation: {e}", exc_info=True)
            raise DatabaseException(f"Failed to upsert translation: {str(e)}")

    def bulk_upsert_translations(
            self,
            translations_data: List[Dict[str, Any]],
            user_id: Optional[int] = None
    ) -> Tuple[List[EntityTranslation], List[str]]:
        """
        Bulk create/update translations with transaction safety.

        Args:
            translations_data: List of translation dictionaries
            user_id: Optional user ID for audit logging

        Returns:
            Tuple of (successful_translations, error_messages)

        Raises:
            DatabaseException: If transaction fails
        """
        successful_translations = []
        error_messages = []

        try:
            self.logger.info(f"Starting bulk upsert of {len(translations_data)} translations")

            for i, data in enumerate(translations_data):
                try:
                    translation = self.upsert_translation(
                        entity_type=data.get('entity_type'),
                        entity_id=data.get('entity_id'),
                        locale=data.get('locale'),
                        field_name=data.get('field_name'),
                        translated_value=data.get('translated_value'),
                        user_id=user_id
                    )
                    successful_translations.append(translation)

                except (ValidationException, DatabaseException) as e:
                    error_msg = f"Item {i}: {str(e)}"
                    error_messages.append(error_msg)
                    self.logger.warning(error_msg)

            # Commit successful operations
            self.db_session.commit()

            self.logger.info(
                f"Bulk upsert completed: {len(successful_translations)} successful, "
                f"{len(error_messages)} errors"
            )

            return successful_translations, error_messages

        except SQLAlchemyError as e:
            self.logger.error(f"Database error in bulk_upsert_translations: {e}", exc_info=True)
            self.db_session.rollback()
            raise DatabaseException(f"Bulk upsert transaction failed: {str(e)}")

    def delete_translations_for_entity(
            self,
            entity_type: str,
            entity_id: int,
            user_id: Optional[int] = None
    ) -> int:
        """
        Delete all translations for a specific entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            user_id: Optional user ID for audit logging

        Returns:
            Number of translations deleted

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            self.logger.info(
                f"Deleting all translations for {entity_type}#{entity_id} "
                f"(requested by user {user_id})"
            )

            deleted_count = self.db_session.query(EntityTranslation).filter(
                and_(
                    EntityTranslation.entity_type == entity_type,
                    EntityTranslation.entity_id == entity_id
                )
            ).delete(synchronize_session=False)

            self.db_session.commit()

            self.logger.info(f"Deleted {deleted_count} translations for {entity_type}#{entity_id}")
            return deleted_count

        except SQLAlchemyError as e:
            self.logger.error(f"Database error deleting entity translations: {e}", exc_info=True)
            self.db_session.rollback()
            raise DatabaseException(f"Failed to delete entity translations: {str(e)}")

    def delete_translations_for_entity_type(
            self,
            entity_type: str,
            user_id: Optional[int] = None
    ) -> int:
        """
        Delete all translations for an entire entity type.

        WARNING: This is a destructive operation that should be used carefully.

        Args:
            entity_type: Type of entity
            user_id: Optional user ID for audit logging

        Returns:
            Number of translations deleted

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            self.logger.warning(
                f"Deleting ALL translations for entity type '{entity_type}' "
                f"(requested by user {user_id})"
            )

            deleted_count = self.db_session.query(EntityTranslation).filter(
                EntityTranslation.entity_type == entity_type
            ).delete(synchronize_session=False)

            self.db_session.commit()

            self.logger.warning(f"Deleted {deleted_count} translations for entity type '{entity_type}'")
            return deleted_count

        except SQLAlchemyError as e:
            self.logger.error(f"Database error deleting entity type translations: {e}", exc_info=True)
            self.db_session.rollback()
            raise DatabaseException(f"Failed to delete entity type translations: {str(e)}")

    def get_entity_types_with_translations(self) -> List[str]:
        """
        Get list of entity types that have translations.

        Returns:
            List of entity type strings

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            result = self.db_session.query(
                EntityTranslation.entity_type
            ).distinct().order_by(EntityTranslation.entity_type).all()

            entity_types = [row[0] for row in result]
            self.logger.debug(f"Found entity types with translations: {entity_types}")
            return entity_types

        except SQLAlchemyError as e:
            self.logger.error(f"Database error getting entity types: {e}", exc_info=True)
            raise DatabaseException(f"Failed to get entity types: {str(e)}")

    def get_locales_for_entity_type(self, entity_type: str) -> List[str]:
        """
        Get list of locales available for an entity type.

        Args:
            entity_type: Type of entity

        Returns:
            List of locale strings

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            result = self.db_session.query(
                EntityTranslation.locale
            ).filter(
                EntityTranslation.entity_type == entity_type
            ).distinct().order_by(EntityTranslation.locale).all()

            locales = [row[0] for row in result]
            self.logger.debug(f"Found locales for {entity_type}: {locales}")
            return locales

        except SQLAlchemyError as e:
            self.logger.error(f"Database error getting locales: {e}", exc_info=True)
            raise DatabaseException(f"Failed to get locales for entity type: {str(e)}")

    def get_translation_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about translations in the system.

        Returns:
            Dictionary containing various translation statistics

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            self.logger.debug("Generating translation statistics")

            # Total count
            total_translations = self.db_session.query(EntityTranslation).count()

            # Count by entity type
            entity_type_counts = self.db_session.query(
                EntityTranslation.entity_type,
                func.count(EntityTranslation.id).label('count')
            ).group_by(EntityTranslation.entity_type).all()

            # Count by locale
            locale_counts = self.db_session.query(
                EntityTranslation.locale,
                func.count(EntityTranslation.id).label('count')
            ).group_by(EntityTranslation.locale).all()

            # Unique entities with translations
            unique_entities = self.db_session.query(
                EntityTranslation.entity_type,
                EntityTranslation.entity_id
            ).distinct().count()

            # Most recent update
            latest_update = self.db_session.query(
                func.max(EntityTranslation.updated_at)
            ).scalar()

            stats = {
                'total_translations': total_translations,
                'unique_entities': unique_entities,
                'entity_type_distribution': {
                    entity_type: count for entity_type, count in entity_type_counts
                },
                'locale_distribution': {
                    locale: count for locale, count in locale_counts
                },
                'latest_update': latest_update.isoformat() if latest_update else None,
                'entity_types': [entity_type for entity_type, _ in entity_type_counts],
                'locales': [locale for locale, _ in locale_counts]
            }

            self.logger.debug(f"Generated translation statistics: {stats}")
            return stats

        except SQLAlchemyError as e:
            self.logger.error(f"Database error generating statistics: {e}", exc_info=True)
            raise DatabaseException(f"Failed to generate translation statistics: {str(e)}")

    def cleanup_orphaned_translations(
            self,
            entity_type: str,
            valid_entity_ids: List[int],
            dry_run: bool = True
    ) -> Tuple[int, List[int]]:
        """
        Clean up translations for entities that no longer exist.

        Args:
            entity_type: Type of entity to clean up
            valid_entity_ids: List of entity IDs that should be kept
            dry_run: If True, only count orphaned translations without deleting

        Returns:
            Tuple of (count_of_orphaned, list_of_orphaned_entity_ids)

        Raises:
            DatabaseException: If database operation fails
        """
        try:
            self.logger.info(
                f"Cleaning up orphaned translations for {entity_type} "
                f"(dry_run={dry_run}, valid_ids={len(valid_entity_ids)})"
            )

            # Find translations for entity type that don't have valid entity IDs
            orphaned_query = self.db_session.query(EntityTranslation).filter(
                and_(
                    EntityTranslation.entity_type == entity_type,
                    ~EntityTranslation.entity_id.in_(valid_entity_ids) if valid_entity_ids else True
                )
            )

            # Get orphaned entity IDs
            orphaned_entity_ids = [
                t.entity_id for t in orphaned_query.with_entities(EntityTranslation.entity_id).distinct()
            ]

            if dry_run:
                count = orphaned_query.count()
                self.logger.info(f"Found {count} orphaned translations (dry run)")
                return count, orphaned_entity_ids
            else:
                count = orphaned_query.delete(synchronize_session=False)
                self.db_session.commit()
                self.logger.info(f"Deleted {count} orphaned translations")
                return count, orphaned_entity_ids

        except SQLAlchemyError as e:
            self.logger.error(f"Database error cleaning up orphaned translations: {e}", exc_info=True)
            if not dry_run:
                self.db_session.rollback()
            raise DatabaseException(f"Failed to cleanup orphaned translations: {str(e)}")