# app/repositories/settings_repository.py

from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func

from app.db.models.settings import (
    SettingsDefinition, SettingsDefinitionTranslation,
    SettingsValue, SettingsTemplate, SettingsTemplateItem
)
from app.repositories.base_repository import BaseRepository


class SettingsDefinitionRepository(BaseRepository[SettingsDefinition]):
    """
    Repository for SettingsDefinition entity operations.
    """

    def __init__(self, session: Session, encryption_service=None):
        super().__init__(session, encryption_service)
        self.model = SettingsDefinition

    def get_by_key(self, key: str) -> Optional[SettingsDefinition]:
        """
        Get a settings definition by its key.

        Args:
            key: Unique key of the setting

        Returns:
            SettingsDefinition if found, None otherwise
        """
        return self.session.query(self.model).filter(
            self.model.key == key
        ).first()

    def list_with_translations(
            self,
            category: Optional[str] = None,
            subcategory: Optional[str] = None,
            applies_to: Optional[str] = None,
            skip: int = 0,
            limit: int = 100
    ) -> List[SettingsDefinition]:
        """
        List settings definitions with their translations.

        Args:
            category: Optional filter by category
            subcategory: Optional filter by subcategory
            applies_to: Optional filter by applies_to
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of settings definitions with eager-loaded translations
        """
        query = self.session.query(self.model)

        if category:
            query = query.filter(self.model.category == category)

        if subcategory:
            query = query.filter(self.model.subcategory == subcategory)

        if applies_to:
            query = query.filter(self.model.applies_to == applies_to)

        query = query.options(joinedload(self.model.translations))

        return query.offset(skip).limit(limit).all()


class SettingsValueRepository:
    """
    Repository for SettingsValue entity operations.

    Note: This repository doesn't inherit from BaseRepository because
    SettingsValue uses a compound primary key.
    """

    def __init__(self, session: Session):
        self.session = session
        self.model = SettingsValue

    def get_value(
            self,
            scope_type: str,
            scope_id: str,
            setting_key: str
    ) -> Optional[SettingsValue]:
        """
        Get a setting value.

        Args:
            scope_type: Type of scope (system, organization, user)
            scope_id: ID of the scope entity
            setting_key: Key of the setting

        Returns:
            SettingsValue if found, None otherwise
        """
        return self.session.query(self.model).filter(
            self.model.scope_type == scope_type,
            self.model.scope_id == scope_id,
            self.model.setting_key == setting_key
        ).first()

    def get_values_by_scope(
            self,
            scope_type: str,
            scope_id: str,
            category: Optional[str] = None
    ) -> List[SettingsValue]:
        """
        Get all setting values for a scope.

        Args:
            scope_type: Type of scope (system, organization, user)
            scope_id: ID of the scope entity
            category: Optional filter by category

        Returns:
            List of settings values
        """
        query = self.session.query(self.model).filter(
            self.model.scope_type == scope_type,
            self.model.scope_id == scope_id
        )

        if category:
            query = query.join(SettingsDefinition).filter(
                SettingsDefinition.key == self.model.setting_key,
                SettingsDefinition.category == category
            )

        return query.all()

    def get_values_by_keys(
            self,
            scope_type: str,
            scope_id: str,
            keys: List[str]
    ) -> List[SettingsValue]:
        """
        Get setting values by keys.

        Args:
            scope_type: Type of scope (system, organization, user)
            scope_id: ID of the scope entity
            keys: List of setting keys

        Returns:
            List of settings values
        """
        return self.session.query(self.model).filter(
            self.model.scope_type == scope_type,
            self.model.scope_id == scope_id,
            self.model.setting_key.in_(keys)
        ).all()

    def set_value(
            self,
            scope_type: str,
            scope_id: str,
            setting_key: str,
            value: Any
    ) -> SettingsValue:
        """
        Set a setting value.

        Args:
            scope_type: Type of scope (system, organization, user)
            scope_id: ID of the scope entity
            setting_key: Key of the setting
            value: Value to set

        Returns:
            Updated or created SettingsValue
        """
        setting_value = self.get_value(scope_type, scope_id, setting_key)

        if setting_value:
            # Update existing value
            setting_value.value = value
            setting_value.updated_at = datetime.now()
        else:
            # Create new setting value
            setting_value = SettingsValue(
                scope_type=scope_type,
                scope_id=scope_id,
                setting_key=setting_key,
                value=value
            )
            self.session.add(setting_value)

        return setting_value

    def delete_value(
            self,
            scope_type: str,
            scope_id: str,
            setting_key: str
    ) -> bool:
        """
        Delete a setting value.

        Args:
            scope_type: Type of scope (system, organization, user)
            scope_id: ID of the scope entity
            setting_key: Key of the setting

        Returns:
            True if deleted, False if not found
        """
        deleted = self.session.query(self.model).filter(
            self.model.scope_type == scope_type,
            self.model.scope_id == scope_id,
            self.model.setting_key == setting_key
        ).delete()

        return deleted > 0

    def delete_values_by_scope(
            self,
            scope_type: str,
            scope_id: str
    ) -> int:
        """
        Delete all setting values for a scope.

        Args:
            scope_type: Type of scope (system, organization, user)
            scope_id: ID of the scope entity

        Returns:
            Number of deleted values
        """
        deleted = self.session.query(self.model).filter(
            self.model.scope_type == scope_type,
            self.model.scope_id == scope_id
        ).delete()

        return deleted


class SettingsTemplateRepository(BaseRepository[SettingsTemplate]):
    """
    Repository for SettingsTemplate entity operations.
    """

    def __init__(self, session: Session, encryption_service=None):
        super().__init__(session, encryption_service)
        self.model = SettingsTemplate

    def list_with_items(
            self,
            category: Optional[str] = None,
            applies_to: Optional[str] = None,
            skip: int = 0,
            limit: int = 100
    ) -> List[SettingsTemplate]:
        """
        List settings templates with their items.

        Args:
            category: Optional filter by category
            applies_to: Optional filter by applies_to
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of settings templates with eager-loaded items
        """
        query = self.session.query(self.model)

        if category:
            query = query.filter(self.model.category == category)

        if applies_to:
            query = query.filter(self.model.applies_to == applies_to)

        query = query.options(joinedload(self.model.items))

        return query.offset(skip).limit(limit).all()

    def get_by_id_with_items(self, id: int) -> Optional[SettingsTemplate]:
        """
        Get a settings template by ID with its items.

        Args:
            id: ID of the template

        Returns:
            SettingsTemplate if found, None otherwise
        """
        return self.session.query(self.model).filter(
            self.model.id == id
        ).options(
            joinedload(self.model.items)
        ).first()