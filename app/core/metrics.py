# File: app/core/metrics.py

from typing import Dict, Any, List, Optional, Callable, Union, TypeVar
import time
import threading
import logging
import functools
import statistics
import json
import os
from datetime import datetime, timedelta
import uuid

# Type for decorated functions
F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    "enabled": True,
    "log_metrics": True,
    "export_interval_seconds": 60,
    "retention_days": 7,
    "sample_rate": 1.0,  # 100% sampling by default
    "export_backends": ["log"],  # Default to logging backend only
}


class Metric:
    """Base class for all metrics."""

    def __init__(
        self, name: str, description: str = "", tags: Optional[Dict[str, str]] = None
    ):
        """
        Initialize a metric.

        Args:
            name: Name of the metric
            description: Optional description
            tags: Optional tags for categorization
        """
        self.name = name
        self.description = description
        self.tags = tags or {}
        self.created_at = datetime.now()
        self.last_updated = self.created_at

    def get_value(self) -> Any:
        """Get current value of the metric."""
        raise NotImplementedError("Subclasses must implement get_value()")

    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "type": self.__class__.__name__,
            "value": self.get_value(),
            "timestamp": datetime.now().isoformat(),
        }


class Counter(Metric):
    """
    Counter metric that only increases.

    Used for counting events, operations, errors, etc.
    """

    def __init__(
        self, name: str, description: str = "", tags: Optional[Dict[str, str]] = None
    ):
        """Initialize a counter with a zero value."""
        super().__init__(name, description, tags)
        self._value = 0

    def increment(self, value: int = 1) -> None:
        """
        Increment the counter.

        Args:
            value: Amount to increment (default: 1)
        """
        self._value += value
        self.last_updated = datetime.now()

    def get_value(self) -> int:
        """Get current counter value."""
        return self._value


class Gauge(Metric):
    """
    Gauge metric that can go up and down.

    Used for values that can increase and decrease, like memory usage,
    queue sizes, active connections, etc.
    """

    def __init__(
        self, name: str, description: str = "", tags: Optional[Dict[str, str]] = None
    ):
        """Initialize a gauge with a zero value."""
        super().__init__(name, description, tags)
        self._value = 0

    def set(self, value: float) -> None:
        """
        Set the gauge to a specific value.

        Args:
            value: New value
        """
        self._value = value
        self.last_updated = datetime.now()

    def increment(self, value: float = 1) -> None:
        """
        Increment the gauge.

        Args:
            value: Amount to increment (default: 1)
        """
        self._value += value
        self.last_updated = datetime.now()

    def decrement(self, value: float = 1) -> None:
        """
        Decrement the gauge.

        Args:
            value: Amount to decrement (default: 1)
        """
        self._value -= value
        self.last_updated = datetime.now()

    def get_value(self) -> float:
        """Get current gauge value."""
        return self._value


class Histogram(Metric):
    """
    Histogram metric that tracks value distributions.

    Used for measuring distributions of values like response times,
    request sizes, etc.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        tags: Optional[Dict[str, str]] = None,
        buckets: Optional[List[float]] = None,
    ):
        """
        Initialize a histogram.

        Args:
            name: Name of the metric
            description: Optional description
            tags: Optional tags for categorization
            buckets: Optional bucket boundaries for distribution
        """
        super().__init__(name, description, tags)
        self._values = []
        self._buckets = buckets or [
            0.005,
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1,
            2.5,
            5,
            10,
        ]
        self._count = 0
        self._sum = 0
        self._min = None
        self._max = None

    def observe(self, value: float) -> None:
        """
        Record a new observation.

        Args:
            value: Value to record
        """
        self._values.append(value)
        self._count += 1
        self._sum += value

        if self._min is None or value < self._min:
            self._min = value

        if self._max is None or value > self._max:
            self._max = value

        # Limit the number of stored values to avoid memory issues
        if len(self._values) > 1000:
            self._values = self._values[-1000:]

        self.last_updated = datetime.now()

    def get_value(self) -> Dict[str, Any]:
        """Get histogram statistics."""
        if not self._values:
            return {
                "count": 0,
                "sum": 0,
                "min": None,
                "max": None,
                "mean": None,
                "median": None,
                "p90": None,
                "p95": None,
                "p99": None,
                "buckets": {str(b): 0 for b in self._buckets},
            }

        # Calculate percentiles
        sorted_values = sorted(self._values)
        p90_idx = int(len(sorted_values) * 0.9)
        p95_idx = int(len(sorted_values) * 0.95)
        p99_idx = int(len(sorted_values) * 0.99)

        # Calculate bucket counts
        buckets = {}
        for bucket in self._buckets:
            buckets[str(bucket)] = sum(1 for v in self._values if v <= bucket)

        return {
            "count": self._count,
            "sum": self._sum,
            "min": self._min,
            "max": self._max,
            "mean": statistics.mean(self._values) if self._values else None,
            "median": statistics.median(self._values) if self._values else None,
            "p90": (
                sorted_values[p90_idx]
                if p90_idx < len(sorted_values)
                else sorted_values[-1]
            ),
            "p95": (
                sorted_values[p95_idx]
                if p95_idx < len(sorted_values)
                else sorted_values[-1]
            ),
            "p99": (
                sorted_values[p99_idx]
                if p99_idx < len(sorted_values)
                else sorted_values[-1]
            ),
            "buckets": buckets,
        }


class Timer(Histogram):
    """
    Timer metric for measuring durations.

    Special case of Histogram optimized for timing operations.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        tags: Optional[Dict[str, str]] = None,
        buckets: Optional[List[float]] = None,
    ):
        """Initialize a timer with appropriate bucket defaults for seconds."""
        # Default buckets for time measurements in seconds
        default_buckets = [
            0.001,
            0.005,
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1,
            2.5,
            5,
            10,
            30,
        ]
        super().__init__(name, description, tags, buckets or default_buckets)

    @contextlib.contextmanager
    def time(self):
        """Context manager for timing a block of code."""
        start_time = time.time()
        try:
            yield
        finally:
            end_time = time.time()
            duration = end_time - start_time
            self.observe(duration)

    def time_function(self, func: Callable) -> Callable:
        """
        Decorator for timing a function.

        Args:
            func: Function to time

        Returns:
            Decorated function
        """

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self.time():
                return func(*args, **kwargs)

        return wrapper


class MetricsRegistry:
    """
    Registry for managing metrics.

    Provides a centralized registry for creating and accessing metrics.
    """

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "MetricsRegistry":
        """Get singleton instance of metrics registry."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self):
        """Initialize metrics registry."""
        self._metrics: Dict[str, Metric] = {}
        self._config = DEFAULT_CONFIG.copy()
        self._exporters = []
        self._export_thread = None
        self._stop_event = threading.Event()

        # Initialize exporters based on config
        self._init_exporters()

        # Start export thread if enabled
        if self._config["enabled"]:
            self._start_export_thread()

    def _init_exporters(self) -> None:
        """Initialize metric exporters based on configuration."""
        backends = self._config.get("export_backends", ["log"])

        for backend in backends:
            if backend == "log":
                from app.core.metrics_exporters import LogExporter

                self._exporters.append(LogExporter())
            elif backend == "prometheus" and "prometheus" in self._config:
                from app.core.metrics_exporters import PrometheusExporter

                self._exporters.append(PrometheusExporter(self._config["prometheus"]))
            elif backend == "statsd" and "statsd" in self._config:
                from app.core.metrics_exporters import StatsDExporter

                self._exporters.append(StatsDExporter(self._config["statsd"]))
            elif backend == "file" and "file" in self._config:
                from app.core.metrics_exporters import FileExporter

                self._exporters.append(FileExporter(self._config["file"]))

    def _start_export_thread(self) -> None:
        """Start background thread for exporting metrics."""
        if not self._exporters:
            return

        def export_loop():
            interval = self._config["export_interval_seconds"]
            while not self._stop_event.wait(interval):
                try:
                    self.export_metrics()
                except Exception as e:
                    logger.error(f"Error exporting metrics: {str(e)}", exc_info=True)

        self._export_thread = threading.Thread(
            target=export_loop, name="metrics-export", daemon=True
        )
        self._export_thread.start()

    def configure(self, config: Dict[str, Any]) -> None:
        """
        Update metrics configuration.

        Args:
            config: New configuration dictionary
        """
        self._config.update(config)

        # Reinitialize exporters if configuration changed
        self._exporters = []
        self._init_exporters()

        # Restart export thread if needed
        if self._export_thread and self._export_thread.is_alive():
            self._stop_event.set()
            self._export_thread.join(timeout=5)
            self._stop_event.clear()

        if self._config["enabled"]:
            self._start_export_thread()

    def shutdown(self) -> None:
        """Shutdown metrics registry and stop background threads."""
        if self._export_thread and self._export_thread.is_alive():
            self._stop_event.set()
            self._export_thread.join(timeout=5)

        # Final export
        self.export_metrics()

        # Shutdown exporters
        for exporter in self._exporters:
            if hasattr(exporter, "shutdown"):
                exporter.shutdown()

    def register(self, metric: Metric) -> Metric:
        """
        Register a metric.

        Args:
            metric: Metric instance

        Returns:
            Registered metric
        """
        if not self._config["enabled"]:
            return metric

        metric_id = f"{metric.name}:{','.join(f'{k}={v}' for k, v in sorted(metric.tags.items()))}"
        self._metrics[metric_id] = metric
        return metric

    def counter(
        self, name: str, description: str = "", tags: Optional[Dict[str, str]] = None
    ) -> Counter:
        """
        Create and register a counter.

        Args:
            name: Metric name
            description: Optional description
            tags: Optional tags

        Returns:
            Counter instance
        """
        return self.register(Counter(name, description, tags))

    def gauge(
        self, name: str, description: str = "", tags: Optional[Dict[str, str]] = None
    ) -> Gauge:
        """
        Create and register a gauge.

        Args:
            name: Metric name
            description: Optional description
            tags: Optional tags

        Returns:
            Gauge instance
        """
        return self.register(Gauge(name, description, tags))

    def histogram(
        self,
        name: str,
        description: str = "",
        tags: Optional[Dict[str, str]] = None,
        buckets: Optional[List[float]] = None,
    ) -> Histogram:
        """
        Create and register a histogram.

        Args:
            name: Metric name
            description: Optional description
            tags: Optional tags
            buckets: Optional bucket boundaries

        Returns:
            Histogram instance
        """
        return self.register(Histogram(name, description, tags, buckets))

    def timer(
        self,
        name: str,
        description: str = "",
        tags: Optional[Dict[str, str]] = None,
        buckets: Optional[List[float]] = None,
    ) -> Timer:
        """
        Create and register a timer.

        Args:
            name: Metric name
            description: Optional description
            tags: Optional tags
            buckets: Optional bucket boundaries

        Returns:
            Timer instance
        """
        return self.register(Timer(name, description, tags, buckets))

    def get_metric(
        self, name: str, tags: Optional[Dict[str, str]] = None
    ) -> Optional[Metric]:
        """
        Get a registered metric by name and tags.

        Args:
            name: Metric name
            tags: Optional tags

        Returns:
            Metric if found, None otherwise
        """
        tags = tags or {}
        metric_id = f"{name}:{','.join(f'{k}={v}' for k, v in sorted(tags.items()))}"
        return self._metrics.get(metric_id)

    def get_all_metrics(self) -> List[Metric]:
        """Get all registered metrics."""
        return list(self._metrics.values())

    def export_metrics(self) -> None:
        """Export metrics using all registered exporters."""
        if not self._config["enabled"] or not self._exporters:
            return

        metrics = self.get_all_metrics()
        for exporter in self._exporters:
            try:
                exporter.export(metrics)
            except Exception as e:
                logger.error(
                    f"Error exporting metrics with {exporter.__class__.__name__}: {str(e)}",
                    exc_info=True,
                )

    def clear_metrics(self) -> None:
        """Clear all registered metrics (primarily for testing)."""
        self._metrics.clear()


# Convenience functions for working with metrics


def get_registry() -> MetricsRegistry:
    """Get the global metrics registry instance."""
    return MetricsRegistry.get_instance()


def configure(config: Dict[str, Any]) -> None:
    """
    Configure the metrics system.

    Args:
        config: Configuration dictionary
    """
    get_registry().configure(config)


def counter(
    name: str, description: str = "", tags: Optional[Dict[str, str]] = None
) -> Counter:
    """
    Create and register a counter.

    Args:
        name: Counter name
        description: Optional description
        tags: Optional tags

    Returns:
        Counter instance
    """
    return get_registry().counter(name, description, tags)


def gauge(
    name: str, description: str = "", tags: Optional[Dict[str, str]] = None
) -> Gauge:
    """
    Create and register a gauge.

    Args:
        name: Gauge name
        description: Optional description
        tags: Optional tags

    Returns:
        Gauge instance
    """
    return get_registry().gauge(name, description, tags)


def histogram(
    name: str,
    description: str = "",
    tags: Optional[Dict[str, str]] = None,
    buckets: Optional[List[float]] = None,
) -> Histogram:
    """
    Create and register a histogram.

    Args:
        name: Histogram name
        description: Optional description
        tags: Optional tags
        buckets: Optional bucket boundaries

    Returns:
        Histogram instance
    """
    return get_registry().histogram(name, description, tags, buckets)


def timer(
    name: str,
    description: str = "",
    tags: Optional[Dict[str, str]] = None,
    buckets: Optional[List[float]] = None,
) -> Timer:
    """
    Create and register a timer.

    Args:
        name: Timer name
        description: Optional description
        tags: Optional tags
        buckets: Optional bucket boundaries

    Returns:
        Timer instance
    """
    return get_registry().timer(name, description, tags, buckets)


# Decorators for easy metric creation and use


def record_execution_time(name: Union[str, Callable]) -> Union[Callable[[F], F], F]:
    """
    Decorator to record execution time of a function.

    Can be used in two ways:

    1. With parameters:
       @record_execution_time("my_function")
       def my_function(): ...

    2. Without parameters:
       @record_execution_time
       def my_function(): ...

    Args:
        name: Name for the timer or the function to decorate

    Returns:
        Decorated function
    """
    if callable(name):
        # Used without parameters
        func = name
        timer_name = f"function.{func.__module__}.{func.__name__}"
        timer_instance = timer(
            timer_name,
            f"Execution time of {func.__name__}",
            {"function": func.__name__, "module": func.__module__},
        )
        return timer_instance.time_function(func)
    else:
        # Used with parameters
        def decorator(func: F) -> F:
            timer_instance = timer(
                name,
                f"Execution time of {func.__name__}",
                {"function": func.__name__, "module": func.__module__},
            )
            return timer_instance.time_function(func)

        return decorator


def count_calls(name: Union[str, Callable]) -> Union[Callable[[F], F], F]:
    """
    Decorator to count calls to a function.

    Can be used in two ways:

    1. With parameters:
       @count_calls("my_function")
       def my_function(): ...

    2. Without parameters:
       @count_calls
       def my_function(): ...

    Args:
        name: Name for the counter or the function to decorate

    Returns:
        Decorated function
    """
    if callable(name):
        # Used without parameters
        func = name
        counter_name = f"calls.{func.__module__}.{func.__name__}"
        counter_instance = counter(
            counter_name,
            f"Call count of {func.__name__}",
            {"function": func.__name__, "module": func.__module__},
        )

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            counter_instance.increment()
            return func(*args, **kwargs)

        return wrapper
    else:
        # Used with parameters
        def decorator(func: F) -> F:
            counter_instance = counter(
                name,
                f"Call count of {func.__name__}",
                {"function": func.__name__, "module": func.__module__},
            )

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                counter_instance.increment()
                return func(*args, **kwargs)

            return wrapper

        return decorator


def track_errors(name: Union[str, Callable]) -> Union[Callable[[F], F], F]:
    """
    Decorator to track errors in a function.

    Can be used in two ways:

    1. With parameters:
       @track_errors("my_function")
       def my_function(): ...

    2. Without parameters:
       @track_errors
       def my_function(): ...

    Args:
        name: Name for the counter or the function to decorate

    Returns:
        Decorated function
    """
    if callable(name):
        # Used without parameters
        func = name
        error_counter_name = f"errors.{func.__module__}.{func.__name__}"
        error_counter = counter(
            error_counter_name,
            f"Error count of {func.__name__}",
            {"function": func.__name__, "module": func.__module__},
        )

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_counter.increment()
                # Re-raise the exception to maintain original behavior
                raise

        return wrapper
    else:
        # Used with parameters
        def decorator(func: F) -> F:
            error_counter = counter(
                name,
                f"Error count of {func.__name__}",
                {"function": func.__name__, "module": func.__module__},
            )

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_counter.increment()
                    # Re-raise the exception to maintain original behavior
                    raise

            return wrapper

        return decorator


# Initialize global metrics
STARTUP_TIME = time.time()
PROCESS_START_TIME = gauge("process.start_time", "Process start time (epoch seconds)")
PROCESS_START_TIME.set(STARTUP_TIME)

# Application metrics (to be updated by other components)
ACTIVE_REQUESTS = gauge("hidesync.active_requests", "Number of active HTTP requests")
REQUEST_LATENCY = histogram("hidesync.request_latency", "Request latency in seconds")
DB_QUERY_LATENCY = histogram(
    "hidesync.db_query_latency", "Database query latency in seconds"
)
ERROR_COUNT = counter("hidesync.errors", "Number of application errors")
