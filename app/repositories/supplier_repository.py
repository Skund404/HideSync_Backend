# File: app/repositories/supplier_repository.py

from typing import List, Optional, Dict, Any, Generator
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, text
import logging

from app.db.models.supplier import Supplier
from app.db.models.enums import SupplierStatus
from app.repositories.base_repository import BaseRepository
from app.core.exceptions import DatabaseException

logger = logging.getLogger(__name__)


class SupplierRepository(BaseRepository[Supplier]):
    """
    Repository for Supplier entity operations with memory-efficient implementations.
    """

    def __init__(self, session: Session, encryption_service=None):
        """Initialize the repository with session and optional encryption service."""
        super().__init__(session, encryption_service)
        self.model = Supplier

    # Replace the list method in app/repositories/supplier_repository.py

    def list(self, **filters) -> List[Supplier]:
        """
        List suppliers with optional filtering using the proven diagnostics approach.

        Args:
            **filters: Optional filters including:
                - name: Filter by supplier name
                - status: Filter by supplier status
                - category: Filter by supplier category
                - skip: Number of records to skip (pagination)
                - limit: Page size (pagination)

        Returns:
            List[Supplier]: List of suppliers matching the criteria

        Raises:
            DatabaseException: If a database error occurs
        """
        try:
            # Extract pagination parameters
            skip = filters.get("skip", 0)
            limit = filters.get("limit", 100)

            # Use the exact approach from the working diagnostics script
            try:
                from app.db.session import EncryptionManager, use_sqlcipher
                from app.core.config import settings
                import os

                if not use_sqlcipher:
                    logger.warning("SQLCipher not enabled, using standard SQLAlchemy approach")
                    return self._list_with_sqlalchemy(skip, limit, filters)

                # Get the database path
                db_path = os.path.abspath(settings.DATABASE_PATH)
                logger.info(f"Using database path: {db_path}")

                # Get SQLCipher module from EncryptionManager
                sqlcipher = EncryptionManager.get_sqlcipher_module()

                # Connect exactly like in the diagnostics script
                conn = sqlcipher.connect(db_path)
                cursor = conn.cursor()

                # Configure encryption using EXACTLY the same approach as diagnostics
                key_pragma_value = EncryptionManager.format_key_for_pragma()
                logger.debug(f"Using key format: {key_pragma_value}")

                cursor.execute(f"PRAGMA key = {key_pragma_value};")
                cursor.execute("PRAGMA cipher_page_size = 4096;")
                cursor.execute("PRAGMA kdf_iter = 256000;")
                cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
                cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")

                # Verify table exists (diagnostic step)
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='suppliers';")
                if not cursor.fetchone():
                    logger.error("Table 'suppliers' not found in database")
                    raise DatabaseException(
                        message="Table 'suppliers' not found in database",
                        entity_type="Supplier"
                    )

                # Build query with parameterized values for safety
                sql = "SELECT * FROM suppliers WHERE 1=1"
                params = []

                # Add filter conditions
                if "name" in filters and filters["name"]:
                    sql += " AND name = ?"
                    params.append(filters["name"])

                if "status" in filters and filters["status"]:
                    sql += " AND status = ?"
                    params.append(str(filters["status"]))

                if "category" in filters and filters["category"]:
                    sql += " AND category = ?"
                    params.append(filters["category"])

                # Add pagination
                sql += " LIMIT ? OFFSET ?"
                params.append(limit)
                params.append(skip)

                logger.info(f"Executing query: {sql} with params: {params}")

                # Execute the query
                cursor.execute(sql, params)

                # Get column names and fetch results
                column_names = [column[0] for column in cursor.description]
                rows = cursor.fetchall()

                # Convert to model instances
                entities = []
                for row in rows:
                    supplier = Supplier()
                    for i, column in enumerate(column_names):
                        if hasattr(supplier, column):
                            setattr(supplier, column, row[i])
                    entities.append(supplier)

                conn.close()
                logger.info(f"Successfully retrieved {len(entities)} suppliers")

                # Process any sensitive fields
                return [self._decrypt_sensitive_fields(entity) for entity in entities]

            except ImportError as e:
                logger.error(f"Import error: {e}")
                return self._list_with_sqlalchemy(skip, limit, filters)

        except Exception as e:
            logger.error(f"Error in supplier list: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise DatabaseException(
                message=f"Error retrieving suppliers: {str(e)}",
                entity_type="Supplier"
            )

    def _list_with_sqlalchemy(self, skip: int, limit: int, filters: Dict[str, Any]) -> List[Supplier]:
        """SQLAlchemy fallback implementation."""
        try:
            # Start building the query
            query = self.session.query(self.model)

            # Apply specific filters if present
            if "name" in filters and filters["name"]:
                query = query.filter(self.model.name == filters["name"])

            if "status" in filters and filters["status"]:
                query = query.filter(self.model.status == filters["status"])

            if "category" in filters and filters["category"]:
                query = query.filter(self.model.category == filters["category"])

            # Apply pagination at database level
            entities = query.offset(skip).limit(limit).all()
            return [self._decrypt_sensitive_fields(entity) for entity in entities]

        except Exception as e:
            logger.error(f"Error in SQLAlchemy list method: {e}")
            raise DatabaseException(
                message=f"Error retrieving suppliers with SQLAlchemy: {str(e)}",
                entity_type="Supplier"
            )

    # Add this method to the SupplierRepository class

    # Replace the count method in your SupplierRepository

    def count(self, **filters) -> int:
        """
        Count total number of suppliers matching the given filters.

        Args:
            **filters: Optional filters to apply

        Returns:
            int: Total count of suppliers
        """
        try:
            # Use the direct SQL approach which we know works with SQLCipher
            from app.db.session import EncryptionManager
            from app.core.config import settings
            import os

            # Get database path and encryption key
            db_path = os.path.abspath(settings.DATABASE_PATH)

            try:
                # Get SQLCipher module and connect
                sqlcipher = EncryptionManager.get_sqlcipher_module()
                conn = sqlcipher.connect(db_path)
                cursor = conn.cursor()

                # Configure encryption
                key = EncryptionManager.get_key()
                cursor.execute(f"PRAGMA key = \"x'{key}'\";")
                cursor.execute("PRAGMA cipher_page_size = 4096;")
                cursor.execute("PRAGMA kdf_iter = 256000;")
                cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
                cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
                cursor.execute("PRAGMA foreign_keys = ON;")

                # Simple direct count query
                sql = "SELECT COUNT(*) FROM suppliers"

                # Execute and get count
                cursor.execute(sql)
                result = cursor.fetchone()
                count = result[0] if result else 0

                # Clean up
                cursor.close()
                conn.close()

                return count

            except ImportError:
                # Fallback to a less efficient method if SQLCipher isn't available
                logger.warning("SQLCipher not available, using fallback count method")
                all_suppliers = self.list(**filters)
                return len(all_suppliers)

        except Exception as e:
            logger.error(f"Error in supplier count: {e}")
            import traceback
            logger.error(traceback.format_exc())
            from app.core.exceptions import DatabaseException
            raise DatabaseException(
                message=f"Error counting suppliers: {str(e)}",
                entity_type="Supplier"
            )

    def stream_all(self, batch_size=50, **filters) -> Generator[Supplier, None, None]:
        """
        Stream all suppliers in memory-efficient batches.

        Use this method when you need to process a large number of suppliers
        without loading all of them into memory at once.

        Args:
            batch_size: Number of records to fetch per batch
            **filters: Optional filters (same as list method)

        Yields:
            Supplier instances, one at a time
        """
        offset = 0
        while True:
            batch = self.list(skip=offset, limit=batch_size, **filters)
            if not batch:
                break

            for supplier in batch:
                yield supplier

            offset += batch_size

    def count(self, **filters) -> int:
        """
        Count suppliers with the given filters.

        This uses a COUNT query which is memory-efficient even for large tables.

        Args:
            **filters: Optional filters (same as list method)

        Returns:
            int: Number of suppliers matching the criteria
        """
        try:
            # Avoid the SQLAlchemy boolean evaluation issue by using direct SQL for SQLCipher
            try:
                from app.db.session import EncryptionManager, use_sqlcipher
                from app.core.config import settings
                import os

                # Get database path
                db_path = os.path.abspath(settings.DATABASE_PATH)

                if use_sqlcipher:
                    # Direct SQL approach for SQLCipher
                    sqlcipher = EncryptionManager.get_sqlcipher_module()
                    conn = sqlcipher.connect(db_path)
                    cursor = conn.cursor()

                    # Configure encryption
                    key = EncryptionManager.get_key()
                    cursor.execute(f"PRAGMA key = \"x'{key}'\";")
                    cursor.execute("PRAGMA cipher_page_size = 4096;")
                    cursor.execute("PRAGMA kdf_iter = 256000;")
                    cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512;")
                    cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")

                    # Build query with WHERE clauses based on filters
                    sql = "SELECT COUNT(*) FROM suppliers WHERE 1=1"
                    params = []

                    if "name" in filters and filters["name"]:
                        sql += " AND name = ?"
                        params.append(filters["name"])

                    if "status" in filters and filters["status"]:
                        sql += " AND status = ?"
                        params.append(str(filters["status"]))

                    if "category" in filters and filters["category"]:
                        sql += " AND category = ?"
                        params.append(filters["category"])

                    # Execute the query
                    cursor.execute(sql, params)
                    result = cursor.fetchone()
                    count = result[0] if result else 0

                    # Clean up
                    cursor.close()
                    conn.close()

                    return count
                else:
                    # Standard SQLAlchemy approach
                    from sqlalchemy import func, select, text

                    # Build the query properly with select() construct
                    count_query = select(func.count()).select_from(self.model)

                    # Apply filters
                    if "name" in filters and filters["name"]:
                        count_query = count_query.where(self.model.name == filters["name"])

                    if "status" in filters and filters["status"]:
                        count_query = count_query.where(self.model.status == filters["status"])

                    if "category" in filters and filters["category"]:
                        count_query = count_query.where(self.model.category == filters["category"])

                    # Execute and return result
                    result = self.session.execute(count_query).scalar()
                    return result or 0

            except ImportError:
                # Safe fallback if imports fail
                logger.warning("Import error in count method, using fallback counting")
                suppliers = self.list(**filters)
                return len(suppliers)

        except Exception as e:
            logger.error(f"Error in supplier count: {e}")
            import traceback
            logger.error(traceback.format_exc())

            # Final fallback - do a basic count with list()
            try:
                suppliers = self.list(**filters)
                return len(suppliers)
            except Exception as fallback_error:
                logger.error(f"Fallback count failed: {fallback_error}")
                from app.core.exceptions import DatabaseException
                raise DatabaseException(
                    message=f"Error counting suppliers: {str(e)}",
                    entity_type="Supplier"
                )

    def search_suppliers(self, query_str: str, skip: int = 0, limit: int = 100) -> List[Supplier]:
        """
        Search for suppliers by name, contact, or email.

        Args:
            query_str: The search query string
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return

        Returns:
            List of matching suppliers
        """
        try:
            search_query = self.session.query(self.model).filter(
                or_(
                    self.model.name.ilike(f"%{query_str}%"),
                    self.model.contact_name.ilike(f"%{query_str}%"),
                    self.model.email.ilike(f"%{query_str}%")
                )
            )

            # Apply pagination at database level
            entities = search_query.offset(skip).limit(limit).all()
            return [self._decrypt_sensitive_fields(entity) for entity in entities]

        except MemoryError as e:
            logger.error(f"Memory error in supplier search: {e}")
            # Construct a direct SQL search with pagination
            return self._search_suppliers_direct_sql(query_str, skip, limit)
        except Exception as e:
            logger.error(f"Error in supplier search: {e}")
            raise DatabaseException(
                message=f"Error searching suppliers: {str(e)}",
                entity_type="Supplier"
            )

    def _search_suppliers_direct_sql(self, query_str: str, skip: int, limit: int) -> List[Supplier]:
        """Fallback search implementation using direct SQL."""
        try:
            # Build a simple search SQL query with pagination
            sql = """
            SELECT * FROM suppliers 
            WHERE name LIKE :query OR contact_name LIKE :query OR email LIKE :query
            LIMIT :limit OFFSET :skip
            """
            params = {
                "query": f"%{query_str}%",
                "limit": limit,
                "skip": skip
            }

            # Execute the query
            result = self.session.execute(text(sql), params)

            # Convert to model instances
            entities = []
            for row in result:
                supplier = Supplier()
                for key, value in row._mapping.items():
                    if hasattr(supplier, key):
                        setattr(supplier, key, value)
                entities.append(supplier)

            return [self._decrypt_sensitive_fields(entity) for entity in entities]

        except Exception as e:
            logger.error(f"Error in direct SQL supplier search: {e}")
            raise DatabaseException(
                message=f"Error searching suppliers with direct SQL: {str(e)}",
                entity_type="Supplier",
                query=sql
            )