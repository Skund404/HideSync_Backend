# File: app/db/models/documentation.py
"""
Documentation models for the Leathercraft ERP system.

This module defines the DocumentationResource and DocumentationCategory models
for storing and organizing help content, guides, tutorials, and reference materials.
These models support a knowledge base for users of the leathercraft system.
"""

from typing import List, Optional, Dict, Any, ClassVar, Set
from datetime import datetime

from sqlalchemy import Column, String, Text, Enum, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.models.base import AbstractBase, ValidationMixin, TimestampMixin
from app.db.models.enums import SkillLevel


class DocumentationCategory(AbstractBase, ValidationMixin, TimestampMixin):
    """
    DocumentationCategory model for organizing documentation resources.

    This model defines categories for documentation, enabling organization
    of content into logical sections for easier navigation.

    Attributes:
        name: Category name
        description: Category description
        icon: Icon name/identifier
        resources: IDs of resources in this category
        parent_id: ID of parent category (for hierarchical organization)
        order: Display order within parent category
    """

    __tablename__ = "documentation_categories"
    __validated_fields__: ClassVar[Set[str]] = {"name"}

    # Basic information
    name = Column(String(100), nullable=False)
    description = Column(Text)
    icon = Column(String(50))

    # Organizational structure
    resources = Column(JSON, nullable=True)  # List of resource IDs
    parent_id = Column(
        Integer, ForeignKey("documentation_categories.id"), nullable=True
    )
    order = Column(Integer, default=0)

    # Relationships
    parent = relationship(
        "DocumentationCategory", remote_side=[id], backref="subcategories"
    )
    resources_rel = relationship(
        "DocumentationResource",
        back_populates="categories",
        secondary="documentation_resource_category",
    )

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """
        Validate category name.

        Args:
            key: Field name ('name')
            name: Category name to validate

        Returns:
            Validated name

        Raises:
            ValueError: If name is empty or too short
        """
        if not name or len(name.strip()) < 2:
            raise ValueError("Category name must be at least 2 characters")
        return name.strip()

    @hybrid_property
    def resource_count(self) -> int:
        """
        Count resources in this category.

        Returns:
            Number of resources in the category
        """
        if hasattr(self, "resources_rel"):
            return len(self.resources_rel)

        if self.resources:
            if isinstance(self.resources, list):
                return len(self.resources)
            elif isinstance(self.resources, str):
                import json

                try:
                    resources_list = json.loads(self.resources)
                    return len(resources_list)
                except:
                    return 0
        return 0

    @hybrid_property
    def has_subcategories(self) -> bool:
        """
        Check if category has subcategories.

        Returns:
            True if category has subcategories, False otherwise
        """
        return hasattr(self, "subcategories") and len(self.subcategories) > 0

    def get_all_resources(self) -> List[int]:
        """
        Get all resource IDs, including from subcategories.

        Returns:
            List of all resource IDs
        """
        all_resources = []

        # Add resources from this category
        if self.resources:
            if isinstance(self.resources, list):
                all_resources.extend(self.resources)
            elif isinstance(self.resources, str):
                import json

                try:
                    resources_list = json.loads(self.resources)
                    all_resources.extend(resources_list)
                except:
                    pass

        # Add resources from relationship if available
        if hasattr(self, "resources_rel"):
            all_resources.extend([r.id for r in self.resources_rel])

        # Add resources from subcategories
        if hasattr(self, "subcategories"):
            for subcategory in self.subcategories:
                if hasattr(subcategory, "get_all_resources"):
                    all_resources.extend(subcategory.get_all_resources())

        return list(set(all_resources))  # Remove duplicates

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert DocumentationCategory instance to a dictionary.

        Returns:
            Dictionary representation of the documentation category
        """
        result = super().to_dict()

        # Handle JSON fields
        if isinstance(result.get("resources"), str):
            import json

            try:
                result["resources"] = json.loads(result["resources"])
            except:
                result["resources"] = []

        # Add calculated properties
        result["resource_count"] = self.resource_count
        result["has_subcategories"] = self.has_subcategories

        return result

    def __repr__(self) -> str:
        """Return string representation of the DocumentationCategory."""
        return f"<DocumentationCategory(id={self.id}, name='{self.name}')>"


# Association table for many-to-many relationship between resources and categories
from sqlalchemy import Table

documentation_resource_category = Table(
    "documentation_resource_category",
    AbstractBase.metadata,
    Column(
        "resource_id",
        Integer,
        ForeignKey("documentation_resources.id"),
        primary_key=True,
    ),
    Column(
        "category_id",
        Integer,
        ForeignKey("documentation_categories.id"),
        primary_key=True,
    ),
)


class DocumentationResource(AbstractBase, ValidationMixin, TimestampMixin):
    """
    DocumentationResource model for storing documentation content.

    This model represents individual documentation resources, such as guides,
    tutorials, and reference documentation, with content and metadata.

    Attributes:
        title: Resource title
        description: Brief resource description
        content: Main content
        category: Primary category
        type: Resource type (GUIDE/TUTORIAL/REFERENCE)
        skill_level: Required skill level
        tags: Tags for categorization
        related_resources: IDs of related resources
        last_updated: Last update date
        author: Resource author
        contextual_help_keys: Context identifiers for in-app help
        videos: Video references
    """

    __tablename__ = "documentation_resources"
    __validated_fields__: ClassVar[Set[str]] = {"title", "content"}

    # Basic information
    title = Column(String(255), nullable=False)
    description = Column(Text)
    content = Column(Text, nullable=False)

    # Categorization
    category = Column(String(50))  # Primary category string
    type = Column(String(50))  # GUIDE, TUTORIAL, REFERENCE, etc.
    skill_level = Column(Enum(SkillLevel))
    tags = Column(JSON, nullable=True)  # List of tags
    related_resources = Column(JSON, nullable=True)  # List of resource IDs

    # Metadata
    last_updated = Column(String(50))  # ISO date string
    author = Column(String(100))
    contextual_help_keys = Column(JSON, nullable=True)  # List of UI context keys
    videos = Column(JSON, nullable=True)  # List of video references

    # Relationships
    categories = relationship(
        "DocumentationCategory",
        back_populates="resources_rel",
        secondary=documentation_resource_category,
    )

    @validates("title")
    def validate_title(self, key: str, title: str) -> str:
        """
        Validate resource title.

        Args:
            key: Field name ('title')
            title: Resource title to validate

        Returns:
            Validated title

        Raises:
            ValueError: If title is empty or too short
        """
        if not title or len(title.strip()) < 3:
            raise ValueError("Resource title must be at least 3 characters")
        return title.strip()

    @validates("content")
    def validate_content(self, key: str, content: str) -> str:
        """
        Validate resource content.

        Args:
            key: Field name ('content')
            content: Resource content to validate

        Returns:
            Validated content

        Raises:
            ValueError: If content is empty or too short
        """
        if not content or len(content.strip()) < 10:
            raise ValueError("Resource content must be at least 10 characters")
        return content

    @hybrid_property
    def word_count(self) -> int:
        """
        Count words in content.

        Returns:
            Number of words in content
        """
        if not self.content:
            return 0
        return len(self.content.split())

    @hybrid_property
    def reading_time_minutes(self) -> int:
        """
        Estimate reading time in minutes.

        Uses average reading speed of 200 words per minute.

        Returns:
            Estimated reading time in minutes
        """
        return max(1, self.word_count // 200)

    def update_content(self, new_content: str, author: str) -> None:
        """
        Update resource content with versioning metadata.

        Args:
            new_content: New content
            author: Person making the update
        """
        self.content = new_content
        self.author = author
        self.last_updated = datetime.now().isoformat()

    def add_to_category(self, category_id: int) -> None:
        """
        Add resource to a category.

        Args:
            category_id: ID of the category
        """
        # Handle direct relationship if loaded
        if hasattr(self, "categories"):
            from sqlalchemy import select
            from sqlalchemy.orm import Session

            if self.session:
                category = self.session.query(DocumentationCategory).get(category_id)
                if category and category not in self.categories:
                    self.categories.append(category)

        # Update JSON field for redundancy
        related_res = self.related_resources or []
        if isinstance(related_res, str):
            import json

            try:
                related_res = json.loads(related_res)
            except:
                related_res = []

        if category_id not in related_res:
            related_res.append(category_id)
            self.related_resources = related_res

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert DocumentationResource instance to a dictionary.

        Returns:
            Dictionary representation of the documentation resource
        """
        result = super().to_dict()

        # Convert enum values to strings
        if self.skill_level:
            result["skill_level"] = self.skill_level.name

        # Handle JSON fields
        for field in ["tags", "related_resources", "contextual_help_keys", "videos"]:
            if isinstance(result.get(field), str):
                import json

                try:
                    result[field] = json.loads(result[field])
                except:
                    result[field] = []

        # Add calculated properties
        result["word_count"] = self.word_count
        result["reading_time_minutes"] = self.reading_time_minutes

        return result

    def __repr__(self) -> str:
        """Return string representation of the DocumentationResource."""
        return f"<DocumentationResource(id={self.id}, title='{self.title}', type='{self.type}')>"


class Refund(AbstractBase, ValidationMixin, TimestampMixin):
    """
    Refund model for tracking customer refunds.

    This model represents refund transactions for sales, including
    amount, reason, and status information.

    Attributes:
        sale_id: ID of the associated sale
        refund_date: Date of refund
        refund_amount: Refund amount
        reason: Reason for refund
        status: Refund status
        processed_by: Person who processed the refund
        payment_method: Method of refund payment
        transaction_id: External transaction ID
    """

    __tablename__ = "refunds"
    __validated_fields__: ClassVar[Set[str]] = {"sale_id", "refund_amount"}

    # Relationships
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)

    # Refund information
    refund_date = Column(DateTime, default=datetime.now)
    refund_amount = Column(Float, nullable=False)
    reason = Column(String(255))
    status = Column(String(50), default="PENDING")  # PENDING, PROCESSED, CANCELLED

    # Processing information
    processed_by = Column(String(100))
    payment_method = Column(String(50))
    transaction_id = Column(String(100))

    # Relationships
    sale = relationship("Sale", back_populates="refund")

    @validates("refund_amount")
    def validate_refund_amount(self, key: str, amount: float) -> float:
        """
        Validate refund amount.

        Args:
            key: Field name ('refund_amount')
            amount: Refund amount to validate

        Returns:
            Validated refund amount

        Raises:
            ValueError: If amount is not positive
        """
        if amount <= 0:
            raise ValueError("Refund amount must be positive")
        return amount

    def process_refund(
        self,
        processed_by: str,
        payment_method: str,
        transaction_id: Optional[str] = None,
    ) -> None:
        """
        Mark refund as processed.

        Args:
            processed_by: Person processing the refund
            payment_method: Method of refund payment
            transaction_id: External transaction ID
        """
        self.status = "PROCESSED"
        self.processed_by = processed_by
        self.payment_method = payment_method
        self.transaction_id = transaction_id
        self.refund_date = datetime.now()

        # Update sale if available
        if hasattr(self, "sale") and self.sale:
            from app.db.models.enums import SaleStatus

            if hasattr(self.sale, "status") and hasattr(self.sale, "update_status"):
                self.sale.update_status(
                    SaleStatus.REFUNDED,
                    processed_by,
                    f"Refunded {self.refund_amount} via {payment_method}",
                )

    def cancel_refund(self, cancelled_by: str, reason: str) -> None:
        """
        Cancel a pending refund.

        Args:
            cancelled_by: Person cancelling the refund
            reason: Reason for cancellation

        Raises:
            ValueError: If refund is already processed
        """
        if self.status == "PROCESSED":
            raise ValueError("Cannot cancel a processed refund")

        self.status = "CANCELLED"

        # Update notes with cancellation reason
        full_reason = f"Cancelled by {cancelled_by}: {reason}"
        if self.reason:
            self.reason += f" | {full_reason}"
        else:
            self.reason = full_reason

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Refund instance to a dictionary.

        Returns:
            Dictionary representation of the refund
        """
        result = super().to_dict()

        # Format dates for display
        if result.get("refund_date"):
            try:
                dt = datetime.fromisoformat(str(result["refund_date"]))
                result["refund_date_formatted"] = dt.strftime("%b %d, %Y")
            except (ValueError, TypeError):
                pass

        return result

    def __repr__(self) -> str:
        """Return string representation of the Refund."""
        return f"<Refund(id={self.id}, sale_id={self.sale_id}, amount={self.refund_amount}, status='{self.status}')>"
