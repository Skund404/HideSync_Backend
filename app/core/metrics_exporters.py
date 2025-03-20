# File: app/core/metrics_exporters.py

from typing import Dict, Any, List, Optional, Protocol, runtime_checkable
import logging
import json
import os
import time
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)


# Define protocol for metrics
@runtime_checkable
class MetricProtocol(Protocol):
    """Protocol defining required methods for metrics."""

    @property
    def name(self) -> str:
        """Get metric name."""
        ...

    @property
    def description(self) -> str:
        """Get metric description."""
        ...

    @property
    def tags(self) -> Dict[str, str]:
        """Get metric tags."""
        ...

    def get_value(self) -> Any:
        """Get current value of the metric."""
        ...

    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary."""
        ...


@runtime_checkable
class MetricsExporter(Protocol):
    """Protocol defining required methods for metric exporters."""

    def export(self, metrics: List[MetricProtocol]) -> None:
        """
        Export metrics to destination.

        Args:
            metrics: List of metrics to export
        """
        ...

    def shutdown(self) -> None:
        """Shutdown the exporter and release resources."""
        ...


class LogExporter:
    """
    Exporter that logs metrics to the application log.

    Simple exporter for development and debugging.
    """

    def __init__(self, log_level: int = logging.DEBUG):
        """
        Initialize log exporter.

        Args:
            log_level: Logging level to use
        """
        self.log_level = log_level
        self.metrics_logger = logging.getLogger("hidesync.metrics")

    def export(self, metrics: List[MetricProtocol]) -> None:
        """
        Export metrics to log.

        Args:
            metrics: List of metrics to export
        """
        for metric in metrics:
            self.metrics_logger.log(
                self.log_level,
                f"METRIC: {metric.name} = {metric.get_value()} {metric.tags}",
            )

    def shutdown(self) -> None:
        """No resources to release for log exporter."""
        pass


class FileExporter:
    """
    Exporter that writes metrics to files.

    Writes metrics to JSON files for later analysis.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize file exporter.

        Args:
            config: Configuration dictionary with keys:
                - directory: Directory to write metrics to
                - prefix: Prefix for metric files
                - rotate_interval: Interval in seconds to rotate files
                - max_files: Maximum number of files to keep
        """
        self.directory = config.get("directory", "metrics")
        self.prefix = config.get("prefix", "hidesync-metrics")
        self.rotate_interval = config.get("rotate_interval", 3600)  # 1 hour default
        self.max_files = config.get("max_files", 24)  # 24 files default

        # Create directory if it doesn't exist
        os.makedirs(self.directory, exist_ok=True)

        # Initialize file rotation
        self.current_file = None
        self.current_file_timestamp = 0
        self._lock = threading.Lock()

    def _get_current_file(self) -> str:
        """
        Get current file path based on rotation policy.

        Returns:
            Path to current metrics file
        """
        current_time = int(time.time())
        interval_start = current_time - (current_time % self.rotate_interval)

        if interval_start != self.current_file_timestamp:
            # Time to rotate
            self.current_file_timestamp = interval_start
            timestamp = datetime.fromtimestamp(interval_start).strftime("%Y%m%d-%H%M%S")
            self.current_file = os.path.join(
                self.directory, f"{self.prefix}-{timestamp}.json"
            )

            # Clean up old files
            self._cleanup_old_files()

        return self.current_file

    def _cleanup_old_files(self) -> None:
        """Clean up old metrics files based on max_files setting."""
        try:
            files = [
                os.path.join(self.directory, f)
                for f in os.listdir(self.directory)
                if f.startswith(self.prefix) and f.endswith(".json")
            ]

            # Sort by modification time (oldest first)
            files.sort(key=lambda f: os.path.getmtime(f))

            # Delete oldest files if we have too many
            if len(files) > self.max_files:
                for old_file in files[: -self.max_files]:
                    os.remove(old_file)
                    logger.debug(f"Deleted old metrics file: {old_file}")
        except Exception as e:
            logger.warning(f"Error cleaning up old metrics files: {str(e)}")

    def export(self, metrics: List[MetricProtocol]) -> None:
        """
        Export metrics to file.

        Args:
            metrics: List of metrics to export
        """
        if not metrics:
            return

        with self._lock:
            file_path = self._get_current_file()

            # Convert metrics to dictionaries
            metric_dicts = [metric.to_dict() for metric in metrics]

            try:
                # Create or append to file
                export_data = {
                    "timestamp": datetime.now().isoformat(),
                    "metrics": metric_dicts,
                }

                with open(file_path, "a") as f:
                    f.write(json.dumps(export_data) + "\n")
            except Exception as e:
                logger.error(
                    f"Error exporting metrics to file {file_path}: {str(e)}",
                    exc_info=True,
                )

    def shutdown(self) -> None:
        """No specific resources to release for file exporter."""
        pass


class PrometheusExporter:
    """
    Exporter for Prometheus monitoring system.

    Exports metrics in Prometheus format via HTTP endpoint.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Prometheus exporter.

        Args:
            config: Configuration dictionary with keys:
                - port: Port for Prometheus HTTP server
                - endpoint: HTTP endpoint path
        """
        self.port = config.get("port", 8000)
        self.endpoint = config.get("endpoint", "/metrics")
        self.app_name = config.get("app_name", "hidesync")

        # Store latest metrics text
        self.metrics_text = ""
        self._lock = threading.Lock()

        # We would typically start a HTTP server here, but for simplicity
        # we'll just store the metrics text and assume it's integrated
        # with the main application server
        logger.info(
            f"Prometheus metrics available at http://localhost:{self.port}{self.endpoint}"
        )

    def export(self, metrics: List[MetricProtocol]) -> None:
        """
        Export metrics in Prometheus format.

        Args:
            metrics: List of metrics to export
        """
        with self._lock:
            lines = []

            for metric in metrics:
                metric_name = f"{self.app_name}_{metric.name.replace('.', '_')}"

                # Add metric help text
                lines.append(f"# HELP {metric_name} {metric.description}")

                # Add metric type based on class
                metric_type = self._get_prometheus_type(metric)
                lines.append(f"# TYPE {metric_name} {metric_type}")

                # Add metric value(s)
                if metric_type == "histogram":
                    # For histograms, we need to add separate lines for sum, count, and buckets
                    value = metric.get_value()

                    # Add sum
                    labels = self._format_labels(metric.tags)
                    lines.append(f"{metric_name}_sum{labels} {value['sum']}")

                    # Add count
                    lines.append(f"{metric_name}_count{labels} {value['count']}")

                    # Add buckets
                    for bucket, count in value["buckets"].items():
                        bucket_labels = labels[:-1] + f',le="{bucket}"{labels[-1:]}'
                        lines.append(f"{metric_name}_bucket{bucket_labels} {count}")
                else:
                    # For counters and gauges, add a single line
                    value = metric.get_value()
                    if isinstance(value, (int, float)):
                        labels = self._format_labels(metric.tags)
                        lines.append(f"{metric_name}{labels} {value}")

            self.metrics_text = "\n".join(lines) + "\n"

    def _get_prometheus_type(self, metric: MetricProtocol) -> str:
        """
        Get Prometheus metric type based on metric class.

        Args:
            metric: Metric instance

        Returns:
            Prometheus metric type (counter, gauge, histogram, summary)
        """
        class_name = metric.__class__.__name__.lower()

        if class_name == "counter":
            return "counter"
        elif class_name == "gauge":
            return "gauge"
        elif class_name in ("histogram", "timer"):
            return "histogram"
        else:
            return "untyped"

    def _format_labels(self, tags: Dict[str, str]) -> str:
        """
        Format tags as Prometheus labels.

        Args:
            tags: Dictionary of tags

        Returns:
            Formatted labels string
        """
        if not tags:
            return ""

        labels = ",".join([f'{k}="{v}"' for k, v in sorted(tags.items())])
        return f"{{{labels}}}"

    def get_metrics_text(self) -> str:
        """
        Get metrics text in Prometheus format.

        Returns:
            Metrics text
        """
        with self._lock:
            return self.metrics_text

    def shutdown(self) -> None:
        """Shutdown HTTP server if running."""
        # We would typically stop the HTTP server here
        pass


class StatsDExporter:
    """
    Exporter for StatsD monitoring system.

    Exports metrics to a StatsD server via UDP.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize StatsD exporter.

        Args:
            config: Configuration dictionary with keys:
                - host: StatsD server host
                - port: StatsD server port
                - prefix: Prefix for metric names
        """
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 8125)
        self.prefix = config.get("prefix", "hidesync")

        # We would normally initialize a StatsD client here
        # For simplicity, we'll just log the metrics
        logger.info(f"StatsD metrics will be sent to {self.host}:{self.port}")

    def export(self, metrics: List[MetricProtocol]) -> None:
        """
        Export metrics to StatsD.

        Args:
            metrics: List of metrics to export
        """
        for metric in metrics:
            metric_name = f"{self.prefix}.{metric.name}"
            value = metric.get_value()

            if isinstance(value, (int, float)):
                logger.debug(f"StatsD: {metric_name}:{value}|g")
            elif isinstance(value, dict) and "count" in value and "sum" in value:
                # For histograms, send count and sum
                logger.debug(f"StatsD: {metric_name}.count:{value['count']}|c")
                logger.debug(f"StatsD: {metric_name}.sum:{value['sum']}|g")

                # For timing metrics, also send the timing in ms
                if "mean" in value and value["mean"] is not None:
                    logger.debug(f"StatsD: {metric_name}:{value['mean'] * 1000}|ms")

    def shutdown(self) -> None:
        """Close StatsD client if needed."""
        pass
