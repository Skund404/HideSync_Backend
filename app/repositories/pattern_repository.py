# File: app/repositories/pattern_repository.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from datetime import datetime

from app.db.models.pattern import Pattern, ProjectTemplate, ProjectTemplateComponent
from app.db.models.enums import ProjectType, SkillLevel
from app.repositories.base_repository import BaseRepository


class PatternRepository(BaseRepository[Pattern]):
    """
    Repository for Pattern entity operations.

    Handles operations related to leather pattern data, including
    searching, filtering, and access to pattern files and metadata.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the PatternRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = Pattern

    def get_patterns_by_project_type(
        self, project_type: ProjectType, skip: int = 0, limit: int = 100
    ) -> List[Pattern]:
        """
        Get patterns by project type.

        Args:
            project_type (ProjectType): The project type to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Pattern]: List of patterns for the specified project type
        """
        query = self.session.query(self.model).filter(
            self.model.projectType == project_type
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_patterns_by_skill_level(
        self, skill_level: SkillLevel, skip: int = 0, limit: int = 100
    ) -> List[Pattern]:
        """
        Get patterns by skill level.

        Args:
            skill_level (SkillLevel): The skill level to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Pattern]: List of patterns for the specified skill level
        """
        query = self.session.query(self.model).filter(
            self.model.skillLevel == skill_level
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_patterns_by_author(
        self, author_name: str, skip: int = 0, limit: int = 100
    ) -> List[Pattern]:
        """
        Get patterns by author.

        Args:
            author_name (str): Name of the author
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Pattern]: List of patterns by the specified author
        """
        query = self.session.query(self.model).filter(
            self.model.authorName == author_name
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_favorite_patterns(self, skip: int = 0, limit: int = 100) -> List[Pattern]:
        """
        Get favorite patterns.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Pattern]: List of favorite patterns
        """
        query = self.session.query(self.model).filter(self.model.isFavorite == True)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_public_patterns(self, skip: int = 0, limit: int = 100) -> List[Pattern]:
        """
        Get public patterns.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Pattern]: List of public patterns
        """
        query = self.session.query(self.model).filter(self.model.isPublic == True)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_patterns_by_tags(
        self, tags: List[str], skip: int = 0, limit: int = 100
    ) -> List[Pattern]:
        """
        Get patterns by tags.

        Args:
            tags (List[str]): List of tags to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Pattern]: List of patterns with any of the specified tags
        """
        # This assumes tags is stored as a JSON array or similar
        query = self.session.query(self.model)

        # Filter by any of the provided tags
        for tag in tags:
            query = query.filter(self.model.tags.contains(tag))

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def search_patterns(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> List[Pattern]:
        """
        Search for patterns by name or description.

        Args:
            query (str): The search query
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[Pattern]: List of matching patterns
        """
        search_query = self.session.query(self.model).filter(
            or_(
                self.model.name.ilike(f"%{query}%"),
                self.model.description.ilike(f"%{query}%"),
            )
        )

        entities = search_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def toggle_favorite(self, pattern_id: int) -> Optional[Pattern]:
        """
        Toggle a pattern's favorite status.

        Args:
            pattern_id (int): ID of the pattern

        Returns:
            Optional[Pattern]: Updated pattern if found, None otherwise
        """
        pattern = self.get_by_id(pattern_id)
        if not pattern:
            return None

        pattern.isFavorite = not pattern.isFavorite

        self.session.commit()
        self.session.refresh(pattern)
        return self._decrypt_sensitive_fields(pattern)

    def update_pattern_tags(
        self, pattern_id: int, tags: List[str]
    ) -> Optional[Pattern]:
        """
        Update a pattern's tags.

        Args:
            pattern_id (int): ID of the pattern
            tags (List[str]): New list of tags

        Returns:
            Optional[Pattern]: Updated pattern if found, None otherwise
        """
        pattern = self.get_by_id(pattern_id)
        if not pattern:
            return None

        pattern.tags = tags

        self.session.commit()
        self.session.refresh(pattern)
        return self._decrypt_sensitive_fields(pattern)


class ProjectTemplateRepository(BaseRepository[ProjectTemplate]):
    """
    Repository for ProjectTemplate entity operations.

    Manages project templates, which define standardized project structures
    including components, materials, and production steps.
    """

    def __init__(self, session: Session, encryption_service=None):
        """
        Initialize the ProjectTemplateRepository.

        Args:
            session (Session): SQLAlchemy database session
            encryption_service (Optional): Service for handling field encryption/decryption
        """
        super().__init__(session, encryption_service)
        self.model = ProjectTemplate

    def get_templates_by_project_type(
        self, project_type: ProjectType, skip: int = 0, limit: int = 100
    ) -> List[ProjectTemplate]:
        """
        Get project templates by project type.

        Args:
            project_type (ProjectType): The project type to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[ProjectTemplate]: List of templates for the specified project type
        """
        query = self.session.query(self.model).filter(
            self.model.projectType == project_type
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_templates_by_skill_level(
        self, skill_level: SkillLevel, skip: int = 0, limit: int = 100
    ) -> List[ProjectTemplate]:
        """
        Get project templates by skill level.

        Args:
            skill_level (SkillLevel): The skill level to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[ProjectTemplate]: List of templates for the specified skill level
        """
        query = self.session.query(self.model).filter(
            self.model.skillLevel == skill_level
        )

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_public_templates(
        self, skip: int = 0, limit: int = 100
    ) -> List[ProjectTemplate]:
        """
        Get public project templates.

        Args:
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[ProjectTemplate]: List of public templates
        """
        query = self.session.query(self.model).filter(self.model.isPublic == True)

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_templates_by_tags(
        self, tags: List[str], skip: int = 0, limit: int = 100
    ) -> List[ProjectTemplate]:
        """
        Get project templates by tags.

        Args:
            tags (List[str]): List of tags to filter by
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[ProjectTemplate]: List of templates with any of the specified tags
        """
        # This assumes tags is stored as a JSON array or similar
        query = self.session.query(self.model)

        # Filter by any of the provided tags
        for tag in tags:
            query = query.filter(self.model.tags.contains(tag))

        entities = query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def search_templates(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> List[ProjectTemplate]:
        """
        Search for project templates by name or description.

        Args:
            query (str): The search query
            skip (int): Number of records to skip (for pagination)
            limit (int): Maximum number of records to return

        Returns:
            List[ProjectTemplate]: List of matching templates
        """
        search_query = self.session.query(self.model).filter(
            or_(
                self.model.name.ilike(f"%{query}%"),
                self.model.description.ilike(f"%{query}%"),
            )
        )

        entities = search_query.offset(skip).limit(limit).all()
        return [self._decrypt_sensitive_fields(entity) for entity in entities]

    def get_template_with_components(
        self, template_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a project template with its components.

        Args:
            template_id (str): ID of the project template

        Returns:
            Optional[Dict[str, Any]]: Dictionary with template and components if found, None otherwise
        """
        template = self.get_by_id(template_id)
        if not template:
            return None

        # Get template components
        components = (
            self.session.query(ProjectTemplateComponent)
            .filter(ProjectTemplateComponent.templateId == template_id)
            .all()
        )

        return {
            "template": self._decrypt_sensitive_fields(template),
            "components": components,
        }
