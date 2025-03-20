# File: app/core/db_metrics.py

from typing import Dict, Any, Optional
import time
import functools
import sqlalchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
import logging

from app.core.metrics import counter, histogram, timer, gauge, DB_QUERY_LATENCY

logger = logging.getLogger(__name__)

# Database metrics
db_queries = counter("db.queries.total", "Total database queries")
db_queries_by_type = {}  # Type-specific counters
db_query_timer = timer("db.queries.duration", "Database query duration in seconds")
db_errors = counter("db.errors", "Database error count")
db_connections = gauge("db.connections.active", "Active database connections")
db_connections_max = gauge("db.connections.max", "Maximum database connections")
db_pool_size = gauge("db.pool.size", "Database connection pool size")
db_pool_overflow = gauge("db.pool.overflow", "Database connection pool overflow count")
db_pool_timeout = counter("db.pool.timeout", "Database connection pool timeout count")
db_transaction_count = counter("db.transactions.total", "Total database transactions")
db_transaction_commit = counter(
    "db.transactions.commits", "Database transaction commits"
)
db_transaction_rollback = counter(
    "db.transactions.rollbacks", "Database transaction rollbacks"
)
db_deadlocks = counter("db.deadlocks", "Database deadlock count")

# Connection states
connection_states = {
    "idle": gauge("db.connections.idle", "Idle database connections"),
    "active": gauge("db.connections.active", "Active database connections"),
    "checked_out": gauge(
        "db.connections.checked_out", "Checked out database connections"
    ),
    "checked_in": gauge("db.connections.checked_in", "Checked in database connections"),
}


def setup_metrics_events(engine: Engine) -> None:
    """
    Set up SQLAlchemy event handlers for metrics collection.

    Args:
        engine: SQLAlchemy engine
    """
    # Update pool size metrics
    _update_pool_metrics(engine)

    # Register event handlers
    _register_connection_events(engine)
    _register_execution_events(engine)
    _register_transaction_events(engine)


def _update_pool_metrics(engine: Engine) -> None:
    """
    Update database pool metrics.

    Args:
        engine: SQLAlchemy engine
    """
    try:
        pool = engine.pool
        db_pool_size.set(pool.size())
        db_connections_max.set(pool._max_overflow + pool._pool_size)
    except Exception:
        logger.exception("Error updating pool metrics")


def _register_connection_events(engine: Engine) -> None:
    """
    Register event handlers for connection events.

    Args:
        engine: SQLAlchemy engine
    """

    @event.listens_for(engine, "connect")
    def on_connect(dbapi_connection, connection_record):
        """Handle connection creation."""
        db_connections.increment()
        connection_states["idle"].increment()

    @event.listens_for(engine, "checkout")
    def on_checkout(dbapi_connection, connection_record, connection_proxy):
        """Handle connection checkout from pool."""
        connection_states["idle"].decrement()
        connection_states["checked_out"].increment()
        connection_states["active"].increment()

    @event.listens_for(engine, "checkin")
    def on_checkin(dbapi_connection, connection_record):
        """Handle connection checkin to pool."""
        connection_states["active"].decrement()
        connection_states["checked_out"].decrement()
        connection_states["checked_in"].increment()
        connection_states["idle"].increment()

    @event.listens_for(engine, "close")
    def on_close(dbapi_connection, connection_record):
        """Handle connection close."""
        db_connections.decrement()
        connection_states["idle"].decrement()

    @event.listens_for(engine.pool, "overflow")
    def on_overflow(conn_proxy):
        """Handle pool overflow."""
        db_pool_overflow.increment()

    @event.listens_for(engine.pool, "timeout")
    def on_timeout(conn_proxy):
        """Handle pool timeout."""
        db_pool_timeout.increment()


def _register_execution_events(engine: Engine) -> None:
    """
    Register event handlers for query execution events.

    Args:
        engine: SQLAlchemy engine
    """

    @event.listens_for(engine, "before_execute")
    def before_execute(conn, clauseelement, multiparams, params, execution_options):
        """Record query start time."""
        conn.info.setdefault("query_start_time", {})
        conn.info["query_start_time"][id(clauseelement)] = time.time()

    @event.listens_for(engine, "after_execute")
    def after_execute(conn, clauseelement, multiparams, params, result):
        """Record query metrics."""
        start_time = conn.info.get("query_start_time", {}).pop(id(clauseelement), None)
        if start_time is not None:
            duration = time.time() - start_time
            DB_QUERY_LATENCY.observe(duration)
            db_query_timer.observe(duration)

            # Increment queries counter
            db_queries.increment()

            # Determine query type
            query_type = _get_query_type(clauseelement)
            if query_type not in db_queries_by_type:
                db_queries_by_type[query_type] = counter(
                    f"db.queries.{query_type}", f"Database {query_type} queries"
                )
            db_queries_by_type[query_type].increment()

    @event.listens_for(engine, "handle_error")
    def handle_error(exception_context):
        """Record query errors."""
        db_errors.increment()

        # Check for deadlocks
        error = exception_context.original_exception
        if isinstance(error, sqlalchemy.exc.OperationalError):
            if "deadlock" in str(error).lower():
                db_deadlocks.increment()


def _register_transaction_events(engine: Engine) -> None:
    """
    Register event handlers for transaction events.

    Args:
        engine: SQLAlchemy engine
    """

    @event.listens_for(engine, "begin")
    def on_begin(conn):
        """Handle transaction begin."""
        db_transaction_count.increment()

    @event.listens_for(engine, "commit")
    def on_commit(conn):
        """Handle transaction commit."""
        db_transaction_commit.increment()

    @event.listens_for(engine, "rollback")
    def on_rollback(conn):
        """Handle transaction rollback."""
        db_transaction_rollback.increment()


def _get_query_type(clauseelement) -> str:
    """
    Determine query type from clause element.

    Args:
        clauseelement: SQLAlchemy clause element

    Returns:
        Query type string
    """
    # Get statement type based on class name
    stmt_type = type(clauseelement).__name__.lower()

    if hasattr(clauseelement, "type") and hasattr(
        clauseelement.type, "_get_select_raw_columns"
    ):
        return "select"
    elif "insert" in stmt_type:
        return "insert"
    elif "update" in stmt_type:
        return "update"
    elif "delete" in stmt_type:
        return "delete"
    elif "create" in stmt_type:
        return "create"
    elif "drop" in stmt_type:
        return "drop"
    elif "execute" in stmt_type:
        return "execute"
    elif "text" in stmt_type:
        # Try to guess type from SQL text
        sql_text = str(clauseelement).lower()
        for stmt_key in ["select", "insert", "update", "delete", "create", "drop"]:
            if sql_text.startswith(stmt_key):
                return stmt_key
        return "text"
    else:
        return "other"


def track_session_metrics(session: Session) -> None:
    """
    Set up metrics tracking for a SQLAlchemy session.

    Args:
        session: SQLAlchemy session
    """
    # We would track session-specific metrics here
    # For now, we'll just ensure engine metrics are set up
    if session.bind:
        setup_metrics_events(session.bind)


def with_db_metrics(func):
    """
    Decorator to track database metrics for a function.

    Args:
        func: Function to decorate

    Returns:
        Decorated function
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Track function call metrics
        timer_name = f"db.function.{func.__module__}.{func.__name__}"
        function_timer = timer(
            timer_name,
            f"Execution time of database function {func.__name__}",
            {"function": func.__name__, "module": func.__module__},
        )

        with function_timer.time():
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Track error metrics
                error_counter = counter(
                    f"db.function.errors.{func.__module__}.{func.__name__}",
                    f"Error count of database function {func.__name__}",
                    {"function": func.__name__, "module": func.__module__},
                )
                error_counter.increment()
                raise

    return wrapper
