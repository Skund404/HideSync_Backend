# File: services/search_service.py

"""
Advanced search service for the HideSync system.

This module provides comprehensive search functionality across multiple entity types
in the HideSync system. It enables users to find information quickly through
full-text search, filtering, and relevance-based ranking of results.

The search service acts as a centralized search gateway, coordinating with
different repositories to provide a unified search experience across the system.

Key features:
- Full-text search across multiple entity types
- Contextual relevance ranking
- Faceted search results
- Filtering capabilities
- Cross-entity search with unified result format
- Search result highlighting
- Type-ahead suggestions
- Recent and saved searches

The service follows clean architecture principles and integrates with the
repository layer for data access while providing a consistent interface
for search operations throughout the application.
"""
import uuid
import re
from typing import List, Dict, Any, Optional, Union, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, text
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class SearchService:
    """
    Service for advanced search functionality across HideSync entities.

    Provides full-text search capabilities with filters, relevance ranking,
    and cross-entity search to help users find information quickly and efficiently.
    """

    def __init__(
        self,
        session: Session,
        repositories=None,
        security_context=None,
        cache_service=None,
    ):
        """
        Initialize search service with dependencies.

        Args:
            session: Database session for persistence operations
            repositories: Dictionary of repositories for different entity types
            security_context: Optional security context for authorization
            cache_service: Optional cache service for caching frequent searches
        """
        self.session = session
        self.repositories = repositories or {}
        self.security_context = security_context
        self.cache_service = cache_service

        # Default search weight configuration
        self.search_weights = {
            "name": 1.0,
            "description": 0.8,
            "tag": 0.7,
            "id": 0.5,
            "notes": 0.5,
            "content": 0.6,
        }

    def search(
        self,
        query: str,
        entity_types: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "relevance",
        sort_dir: str = "desc",
        highlight: bool = False,
    ) -> Dict[str, Any]:
        """
        Perform a search across multiple entity types.

        Args:
            query: Search query string
            entity_types: Optional list of entity types to search (default: all searchable)
            filters: Optional filters to apply to search results
            page: Page number for pagination
            page_size: Number of results per page
            sort_by: Field to sort by (relevance, created_at, updated_at, etc.)
            sort_dir: Sort direction (asc or desc)
            highlight: Whether to highlight matching terms in results

        Returns:
            Dictionary with search results and metadata
        """
        # Try to get from cache if available
        cache_key = None
        if self.cache_service and query:
            cache_key = f"search:{query}:{','.join(entity_types or [])}:{json.dumps(filters or {})}:{page}:{page_size}:{sort_by}:{sort_dir}"
            cached_results = self.cache_service.get(cache_key)
            if cached_results:
                return cached_results

        results = {
            "query": query,
            "total_results": 0,
            "page": page,
            "page_size": page_size,
            "results": [],
            "facets": {},
            "entity_counts": {},
        }

        # Skip empty queries
        if not query or len(query.strip()) == 0:
            return results

        # Default to all searchable entity types if not specified
        if not entity_types:
            entity_types = self._get_searchable_entity_types()

        # Record search if security context available
        if self.security_context and hasattr(self.security_context, "current_user"):
            self._record_user_search(
                query, entity_types, self.security_context.current_user.id
            )

        # Search each entity type
        all_results = []
        entity_counts = {}

        for entity_type in entity_types:
            try:
                entity_results = self._search_entity_type(
                    entity_type=entity_type,
                    query=query,
                    filters=filters,
                    highlight=highlight,
                )

                if entity_results:
                    all_results.extend(entity_results)
                    entity_counts[entity_type] = len(entity_results)

            except Exception as e:
                logger.error(f"Search error for {entity_type}: {str(e)}", exc_info=True)

        # Calculate total results
        total_results = len(all_results)
        results["total_results"] = total_results
        results["entity_counts"] = entity_counts

        # Sort results
        if sort_by == "relevance":
            all_results.sort(
                key=lambda x: x.get("_score", 0), reverse=(sort_dir.lower() == "desc")
            )
        else:
            all_results.sort(
                key=lambda x: x.get(sort_by, ""), reverse=(sort_dir.lower() == "desc")
            )

        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        results["results"] = all_results[start_idx:end_idx]

        # Calculate facets
        results["facets"] = self._calculate_facets(all_results)

        # Add metadata
        results["metadata"] = {
            "search_time": datetime.now().isoformat(),
            "entity_types_searched": entity_types,
        }

        # Cache results if cache service available
        if self.cache_service and cache_key:
            # Cache for a short time (5 minutes)
            self.cache_service.set(cache_key, results, ttl=300)

        return results

    def get_suggestions(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get type-ahead search suggestions based on prefix.

        Args:
            query: Partial query string
            limit: Maximum number of suggestions to return

        Returns:
            List of suggestion objects with query string and entity type
        """
        # Skip empty queries
        if not query or len(query.strip()) < 2:
            return []

        # Try to get from cache if available
        if self.cache_service:
            cache_key = f"suggestions:{query}:{limit}"
            cached_suggestions = self.cache_service.get(cache_key)
            if cached_suggestions:
                return cached_suggestions

        # Search for suggestions across repositories
        all_suggestions = []

        # Add suggestions from recent searches if available
        recent_searches = self._get_recent_searches(limit=5)
        for search in recent_searches:
            search_query = search.get("query", "")
            if (
                query.lower() in search_query.lower()
                and search_query.lower() != query.lower()
            ):
                all_suggestions.append(
                    {
                        "query": search_query,
                        "type": "recent_search",
                        "entity_type": None,
                        "score": 1.0,  # High score for recent searches
                    }
                )

        # Get entity-specific suggestions
        entity_types = self._get_searchable_entity_types()
        for entity_type in entity_types:
            try:
                suggestions = self._get_entity_suggestions(entity_type, query, limit=3)
                if suggestions:
                    all_suggestions.extend(suggestions)
            except Exception as e:
                logger.error(f"Error getting suggestions for {entity_type}: {str(e)}")

        # Sort by score and limit results
        all_suggestions.sort(key=lambda x: x.get("score", 0), reverse=True)
        results = all_suggestions[:limit]

        # Cache results if cache service available
        if self.cache_service:
            cache_key = f"suggestions:{query}:{limit}"
            self.cache_service.set(cache_key, results, ttl=300)  # Cache for 5 minutes

        return results

    def get_recent_searches(
        self, user_id: Optional[int] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent searches for a user.

        Args:
            user_id: Optional user ID (defaults to current user)
            limit: Maximum number of recent searches to return

        Returns:
            List of recent search data
        """
        # Use current user if not specified and security context available
        if (
            user_id is None
            and self.security_context
            and hasattr(self.security_context, "current_user")
        ):
            user_id = self.security_context.current_user.id

        if not user_id:
            return []

        # Try to get from cache if available
        if self.cache_service:
            cache_key = f"recent_searches:{user_id}:{limit}"
            cached_searches = self.cache_service.get(cache_key)
            if cached_searches:
                return cached_searches

        # In a real implementation, this would query a search_history table
        # For this example, we'll return a sample
        return self._get_recent_searches(user_id, limit)

    def save_search(
        self,
        query: str,
        entity_types: List[str],
        name: str,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Save a search for later use.

        Args:
            query: Search query string
            entity_types: Entity types to search
            name: Name to identify the saved search
            user_id: Optional user ID (defaults to current user)

        Returns:
            Saved search object
        """
        # Use current user if not specified and security context available
        if (
            user_id is None
            and self.security_context
            and hasattr(self.security_context, "current_user")
        ):
            user_id = self.security_context.current_user.id

        if not user_id:
            raise ValueError("User ID is required to save a search")

        # Create saved search object
        saved_search = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "name": name,
            "query": query,
            "entity_types": entity_types,
            "created_at": datetime.now().isoformat(),
        }

        # In a real implementation, this would save to a database
        # For this example, we'll just return the object

        # Invalidate cache if cache service available
        if self.cache_service:
            cache_key = f"saved_searches:{user_id}"
            self.cache_service.invalidate(cache_key)

        return saved_search

    def get_saved_searches(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get saved searches for a user.

        Args:
            user_id: Optional user ID (defaults to current user)

        Returns:
            List of saved search data
        """
        # Use current user if not specified and security context available
        if (
            user_id is None
            and self.security_context
            and hasattr(self.security_context, "current_user")
        ):
            user_id = self.security_context.current_user.id

        if not user_id:
            return []

        # Try to get from cache if available
        if self.cache_service:
            cache_key = f"saved_searches:{user_id}"
            cached_searches = self.cache_service.get(cache_key)
            if cached_searches:
                return cached_searches

        # In a real implementation, this would query a saved_searches table
        # For this example, we'll return a sample
        return [
            {
                "id": "1",
                "name": "Low leather inventory",
                "query": "leather low stock",
                "entity_types": ["material"],
                "created_at": (datetime.now().isoformat()),
            },
            {
                "id": "2",
                "name": "Active wallet projects",
                "query": "wallet",
                "entity_types": ["project"],
                "created_at": (datetime.now().isoformat()),
            },
        ]

    def delete_saved_search(
        self, search_id: str, user_id: Optional[int] = None
    ) -> bool:
        """
        Delete a saved search.

        Args:
            search_id: ID of the saved search
            user_id: Optional user ID (defaults to current user)

        Returns:
            True if deletion was successful
        """
        # Use current user if not specified and security context available
        if (
            user_id is None
            and self.security_context
            and hasattr(self.security_context, "current_user")
        ):
            user_id = self.security_context.current_user.id

        if not user_id:
            raise ValueError("User ID is required to delete a saved search")

        # In a real implementation, this would delete from a database
        # For this example, we'll just return success

        # Invalidate cache if cache service available
        if self.cache_service:
            cache_key = f"saved_searches:{user_id}"
            self.cache_service.invalidate(cache_key)

        return True

    def _search_entity_type(
        self,
        entity_type: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        highlight: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Search a specific entity type.

        Args:
            entity_type: Entity type to search
            query: Search query string
            filters: Optional filters to apply
            highlight: Whether to highlight matching terms

        Returns:
            List of search results for this entity type
        """
        # Get repository for entity type
        repository = self.repositories.get(entity_type)
        if not repository:
            logger.warning(f"No repository found for entity type: {entity_type}")
            return []

        # Build search query based on entity type
        search_query = self._build_search_query(entity_type, query)

        # Apply filters if provided
        filter_query = {}
        if filters:
            # Extract filters relevant to this entity type
            entity_filters = filters.get(entity_type, {})

            # Add to filter query
            filter_query.update(entity_filters)

        # Perform search through repository
        try:
            # This assumes each repository has a search method
            # Real implementation would need to adapt to actual repository methods
            results = repository.search(search_query=search_query, **filter_query)

            # Process and transform results
            processed_results = []

            for item in results:
                # Convert to dictionary if not already
                if not isinstance(item, dict):
                    item_dict = (
                        item.to_dict() if hasattr(item, "to_dict") else dict(item)
                    )
                else:
                    item_dict = item

                # Add metadata
                item_dict["entity_type"] = entity_type

                # Calculate relevance score if not provided
                if "_score" not in item_dict:
                    item_dict["_score"] = self._calculate_relevance_score(
                        item_dict, query
                    )

                # Add highlighted fields if requested
                if highlight:
                    item_dict["highlights"] = self._highlight_matches(item_dict, query)

                processed_results.append(item_dict)

            return processed_results

        except Exception as e:
            logger.error(f"Error searching {entity_type}: {str(e)}", exc_info=True)
            return []

    def _build_search_query(self, entity_type: str, query: str) -> Dict[str, Any]:
        """
        Build a search query for a specific entity type.

        Args:
            entity_type: Entity type to build query for
            query: Search query string

        Returns:
            Search query specification
        """
        # This is a simplified implementation
        # A real implementation would build more sophisticated queries
        # based on the entity type and available fields

        search_fields = self._get_searchable_fields(entity_type)

        # Normalize query: trim, lowercase, handle special characters
        normalized_query = query.strip().lower()

        # Tokenize the query for multi-term search
        tokens = normalized_query.split()

        # Build a dictionary representation of the search specification
        search_spec = {
            "query": normalized_query,
            "fields": search_fields,
            "tokens": tokens,
            "match_type": "phrase_prefix",  # could be exact, phrase, wildcard, etc.
        }

        return search_spec

    def _calculate_relevance_score(self, item: Dict[str, Any], query: str) -> float:
        """
        Calculate a relevance score for an item.

        Args:
            item: Item to calculate score for
            query: Original search query

        Returns:
            Relevance score (higher is more relevant)
        """
        score = 0.0
        query_lower = query.lower()

        # Simple scoring based on field matches
        for field, weight in self.search_weights.items():
            if field in item:
                field_value = str(item[field]).lower()

                # Exact match
                if field_value == query_lower:
                    score += weight * 2.0

                # Contains match
                elif query_lower in field_value:
                    score += weight * 1.5

                # Partial match
                else:
                    # Check if any word in the query is in the field
                    query_words = query_lower.split()
                    for word in query_words:
                        if word in field_value:
                            score += weight * 0.5

        return score

    def _highlight_matches(
        self, item: Dict[str, Any], query: str
    ) -> Dict[str, List[str]]:
        """
        Create highlighted excerpts showing query matches in context.

        Args:
            item: Item to highlight matches in
            query: Original search query

        Returns:
            Dictionary of field names to highlighted excerpts
        """
        highlights = {}
        query_lower = query.lower()
        query_terms = query_lower.split()

        # Look for matches in searchable fields
        for field in self._get_searchable_fields(item.get("entity_type", "")):
            if field in item and isinstance(item[field], str):
                field_value = item[field]
                field_lower = field_value.lower()

                # Skip if no match
                if not any(term in field_lower for term in query_terms):
                    continue

                # Create highlighted excerpts
                excerpts = []

                # Simple approach: identify sentences containing matches
                sentences = field_value.split(". ")
                for sentence in sentences:
                    sentence_lower = sentence.lower()
                    if any(term in sentence_lower for term in query_terms):
                        # Add sentence with highlighted term
                        highlighted = sentence
                        for term in query_terms:
                            if term in sentence_lower:
                                # Simple highlighting with <mark> tag
                                # In a real implementation, this would be more sophisticated
                                pattern = re.compile(re.escape(term), re.IGNORECASE)
                                highlighted = pattern.sub(
                                    f"<mark>{term}</mark>", highlighted
                                )

                        excerpts.append(highlighted)

                if excerpts:
                    highlights[field] = excerpts

        return highlights

    def _get_entity_suggestions(
        self, entity_type: str, query: str, limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get search suggestions for an entity type.

        Args:
            entity_type: Entity type to get suggestions for
            query: Partial query string
            limit: Maximum number of suggestions to return

        Returns:
            List of suggestion objects
        """
        # Get repository for entity type
        repository = self.repositories.get(entity_type)
        if not repository:
            return []

        # This would use repository-specific methods for suggestions
        # For this example, we'll return a placeholder
        if entity_type == "material":
            return [
                {
                    "query": f"leather {query}",
                    "type": "material",
                    "entity_type": "material",
                    "score": 0.9,
                },
                {
                    "query": f"{query} hardware",
                    "type": "material",
                    "entity_type": "material",
                    "score": 0.8,
                },
            ]
        elif entity_type == "project":
            return [
                {
                    "query": f"project {query}",
                    "type": "project",
                    "entity_type": "project",
                    "score": 0.85,
                }
            ]

        return []

    def _get_searchable_entity_types(self) -> List[str]:
        """
        Get list of entity types that can be searched.

        Returns:
            List of searchable entity types
        """
        # This would be configured based on the system
        return [
            "material",
            "project",
            "customer",
            "project_template",
            "pattern",
            "product",
            "supplier",
            "tool",
            "documentation",
        ]

    def _get_searchable_fields(self, entity_type: str) -> List[str]:
        """
        Get searchable fields for an entity type.

        Args:
            entity_type: Entity type to get fields for

        Returns:
            List of searchable fields
        """
        # Common fields across many entities
        common_fields = ["id", "name", "description", "notes"]

        # Entity-specific fields
        entity_fields = {
            "material": [
                "sku",
                "supplier",
                "type",
                "status",
                "storageLocation",
                "tags",
            ],
            "project": ["customer", "type", "status", "tags"],
            "customer": ["email", "phone", "company_name", "status", "tier"],
            "project_template": ["projectType", "skillLevel", "tags"],
            "pattern": ["fileType", "projectType", "authorName", "tags"],
            "product": ["sku", "productType", "materials", "color", "dimensions"],
            "supplier": [
                "contactName",
                "email",
                "phone",
                "category",
                "materialCategories",
            ],
            "tool": ["category", "brand", "model", "serialNumber", "status"],
            "documentation": [
                "title",
                "content",
                "category",
                "type",
                "tags",
                "contextualHelpKeys",
            ],
        }

        # Return common fields plus entity-specific fields
        return common_fields + entity_fields.get(entity_type, [])

    def _calculate_facets(
        self, results: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, int]]:
        """
        Calculate facets from search results.

        Args:
            results: Search results to calculate facets from

        Returns:
            Dictionary of facets
        """
        facets = {}

        # Entity type facet
        entity_type_facet = {}
        for result in results:
            entity_type = result.get("entity_type", "unknown")
            entity_type_facet[entity_type] = entity_type_facet.get(entity_type, 0) + 1

        facets["entity_type"] = entity_type_facet

        # Status facet (if applicable)
        status_facet = {}
        for result in results:
            status = result.get("status")
            if status:
                status_facet[status] = status_facet.get(status, 0) + 1

        if status_facet:
            facets["status"] = status_facet

        # Material type facet (if applicable)
        material_type_facet = {}
        for result in results:
            if result.get("entity_type") == "material":
                material_type = result.get("materialType")
                if material_type:
                    material_type_facet[material_type] = (
                        material_type_facet.get(material_type, 0) + 1
                    )

        if material_type_facet:
            facets["material_type"] = material_type_facet

        # Project type facet (if applicable)
        project_type_facet = {}
        for result in results:
            if result.get("entity_type") == "project":
                project_type = result.get("type")
                if project_type:
                    project_type_facet[project_type] = (
                        project_type_facet.get(project_type, 0) + 1
                    )

        if project_type_facet:
            facets["project_type"] = project_type_facet

        return facets

    def _record_user_search(
        self, query: str, entity_types: List[str], user_id: int
    ) -> None:
        """
        Record a search in the user's search history.

        Args:
            query: Search query string
            entity_types: Entity types searched
            user_id: User ID
        """
        # In a real implementation, this would save to a database
        # For this example, we'll just log
        logger.info(
            f"User {user_id} searched for '{query}' in {','.join(entity_types)}"
        )

    def _get_recent_searches(
        self, user_id: Optional[int] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent searches from history.

        Args:
            user_id: Optional user ID
            limit: Maximum number of searches to return

        Returns:
            List of recent search data
        """
        # In a real implementation, this would query a database
        # For this example, we'll return a sample
        return [
            {
                "id": "1",
                "query": "leather",
                "entity_types": ["material"],
                "search_time": (datetime.now().isoformat()),
            },
            {
                "id": "2",
                "query": "wallet project",
                "entity_types": ["project"],
                "search_time": (datetime.now().isoformat()),
            },
            {
                "id": "3",
                "query": "hardware buckle",
                "entity_types": ["material"],
                "search_time": (datetime.now().isoformat()),
            },
        ]
