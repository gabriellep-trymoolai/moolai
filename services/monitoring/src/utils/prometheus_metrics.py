"""Prometheus metrics exporters for system performance monitoring."""

from prometheus_client import (
    Counter, Histogram, Gauge, Info, 
    CollectorRegistry, REGISTRY, generate_latest
)
from typing import Dict, Any, Optional
import time
from datetime import datetime


class SystemPerformancePrometheusExporter:
    """Prometheus metrics exporter for system performance data."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or REGISTRY
        self._init_metrics()
    
    def _init_metrics(self):
        """Initialize Prometheus metrics."""
        
        # CPU Metrics
        self.cpu_usage_percent = Gauge(
            'system_cpu_usage_percent',
            'Current CPU usage percentage',
            ['user_id', 'organization_id'],
            registry=self.registry
        )
        
        self.cpu_load_average = Gauge(
            'system_cpu_load_average',
            'CPU load average',
            ['user_id', 'organization_id', 'period'],  # period: 1min, 5min, 15min
            registry=self.registry
        )
        
        self.cpu_cores_used = Gauge(
            'system_cpu_cores_used',
            'Number of CPU cores currently utilized',
            ['user_id', 'organization_id'],
            registry=self.registry
        )
        
        # Memory Metrics
        self.memory_usage_bytes = Gauge(
            'system_memory_usage_bytes',
            'Current memory usage in bytes',
            ['user_id', 'organization_id', 'type'],  # type: used, available, total
            registry=self.registry
        )
        
        self.memory_usage_percent = Gauge(
            'system_memory_usage_percent',
            'Current memory usage percentage',
            ['user_id', 'organization_id'],
            registry=self.registry
        )
        
        self.swap_usage_bytes = Gauge(
            'system_swap_usage_bytes',
            'Current swap usage in bytes',
            ['user_id', 'organization_id'],
            registry=self.registry
        )
        
        self.swap_usage_percent = Gauge(
            'system_swap_usage_percent',
            'Current swap usage percentage',
            ['user_id', 'organization_id'],
            registry=self.registry
        )
        
        # Storage Metrics
        self.storage_usage_bytes = Gauge(
            'system_storage_usage_bytes',
            'Current storage usage in bytes',
            ['user_id', 'organization_id', 'type'],  # type: used, available, total
            registry=self.registry
        )
        
        self.storage_usage_percent = Gauge(
            'system_storage_usage_percent',
            'Current storage usage percentage',
            ['user_id', 'organization_id'],
            registry=self.registry
        )
        
        self.disk_io_bytes_per_second = Gauge(
            'system_disk_io_bytes_per_second',
            'Disk I/O throughput in bytes per second',
            ['user_id', 'organization_id', 'direction'],  # direction: read, write
            registry=self.registry
        )
        
        self.disk_iops = Gauge(
            'system_disk_iops',
            'Disk I/O operations per second',
            ['user_id', 'organization_id', 'direction'],  # direction: read, write
            registry=self.registry
        )
        
        # Network Metrics
        self.network_throughput_bytes_per_second = Gauge(
            'system_network_throughput_bytes_per_second',
            'Network throughput in bytes per second',
            ['user_id', 'organization_id', 'direction'],  # direction: in, out
            registry=self.registry
        )
        
        self.network_connections_total = Gauge(
            'system_network_connections_total',
            'Total number of active network connections',
            ['user_id', 'organization_id'],
            registry=self.registry
        )
        
        # Latency Metrics
        self.api_latency_seconds = Histogram(
            'system_api_latency_seconds',
            'API response latency in seconds',
            ['user_id', 'organization_id', 'endpoint'],
            registry=self.registry
        )
        
        self.database_latency_seconds = Histogram(
            'system_database_latency_seconds',
            'Database query latency in seconds',
            ['user_id', 'organization_id', 'operation'],
            registry=self.registry
        )
        
        self.redis_latency_seconds = Histogram(
            'system_redis_latency_seconds',
            'Redis operation latency in seconds',
            ['user_id', 'organization_id', 'operation'],
            registry=self.registry
        )
        
        self.system_latency_seconds = Histogram(
            'system_overall_latency_seconds',
            'Overall system response latency in seconds',
            ['user_id', 'organization_id'],
            registry=self.registry
        )
        
        # Container/Service Metrics
        self.container_count = Gauge(
            'system_container_count',
            'Number of running containers',
            ['user_id', 'organization_id'],
            registry=self.registry
        )
        
        self.service_count = Gauge(
            'system_service_count',
            'Number of running services',
            ['user_id', 'organization_id'],
            registry=self.registry
        )
        
        self.container_restarts_total = Counter(
            'system_container_restarts_total',
            'Total number of container restarts',
            ['user_id', 'organization_id', 'container_name'],
            registry=self.registry
        )
        
        # Process Metrics
        self.process_count = Gauge(
            'system_process_count',
            'Total number of running processes',
            ['user_id', 'organization_id'],
            registry=self.registry
        )
        
        self.thread_count = Gauge(
            'system_thread_count',
            'Total number of threads',
            ['user_id', 'organization_id'],
            registry=self.registry
        )
        
        self.file_descriptors_count = Gauge(
            'system_file_descriptors_count',
            'Number of open file descriptors',
            ['user_id', 'organization_id'],
            registry=self.registry
        )
        
        # Orchestrator Version Info
        self.orchestrator_version_info = Info(
            'system_orchestrator_version',
            'Information about orchestrator component versions',
            ['organization_id', 'component_name'],
            registry=self.registry
        )
        
        # Collection Metrics
        self.metrics_collection_duration_seconds = Histogram(
            'system_metrics_collection_duration_seconds',
            'Time taken to collect system metrics',
            ['user_id', 'organization_id', 'collector'],
            registry=self.registry
        )
        
        self.metrics_collection_total = Counter(
            'system_metrics_collection_total',
            'Total number of metrics collections',
            ['user_id', 'organization_id', 'status'],  # status: success, error
            registry=self.registry
        )
    
    def update_metrics_from_data(self, metrics_data: Dict[str, Any]):
        """Update Prometheus metrics from collected system data."""
        try:
            user_id = str(metrics_data.get('user_id', 'unknown'))
            org_id = str(metrics_data.get('organization_id', 'unknown'))
            
            # CPU Metrics
            if metrics_data.get('cpu_usage_percent') is not None:
                self.cpu_usage_percent.labels(user_id=user_id, organization_id=org_id).set(
                    metrics_data['cpu_usage_percent']
                )
            
            for period, value in [
                ('1min', metrics_data.get('cpu_load_1min')),
                ('5min', metrics_data.get('cpu_load_5min')),
                ('15min', metrics_data.get('cpu_load_15min'))
            ]:
                if value is not None:
                    self.cpu_load_average.labels(
                        user_id=user_id, organization_id=org_id, period=period
                    ).set(value)
            
            if metrics_data.get('cpu_cores_used') is not None:
                self.cpu_cores_used.labels(user_id=user_id, organization_id=org_id).set(
                    metrics_data['cpu_cores_used']
                )
            
            # Memory Metrics
            if metrics_data.get('memory_usage_mb') is not None:
                memory_bytes = metrics_data['memory_usage_mb'] * 1024 * 1024
                self.memory_usage_bytes.labels(
                    user_id=user_id, organization_id=org_id, type='used'
                ).set(memory_bytes)
            
            if metrics_data.get('memory_available_mb') is not None:
                available_bytes = metrics_data['memory_available_mb'] * 1024 * 1024
                self.memory_usage_bytes.labels(
                    user_id=user_id, organization_id=org_id, type='available'
                ).set(available_bytes)
            
            if metrics_data.get('memory_total_mb') is not None:
                total_bytes = metrics_data['memory_total_mb'] * 1024 * 1024
                self.memory_usage_bytes.labels(
                    user_id=user_id, organization_id=org_id, type='total'
                ).set(total_bytes)
            
            if metrics_data.get('memory_percent') is not None:
                self.memory_usage_percent.labels(user_id=user_id, organization_id=org_id).set(
                    metrics_data['memory_percent']
                )
            
            # Swap Metrics
            if metrics_data.get('swap_usage_mb') is not None:
                swap_bytes = metrics_data['swap_usage_mb'] * 1024 * 1024
                self.swap_usage_bytes.labels(user_id=user_id, organization_id=org_id).set(swap_bytes)
            
            if metrics_data.get('swap_percent') is not None:
                self.swap_usage_percent.labels(user_id=user_id, organization_id=org_id).set(
                    metrics_data['swap_percent']
                )
            
            # Storage Metrics
            if metrics_data.get('storage_usage_gb') is not None:
                storage_bytes = metrics_data['storage_usage_gb'] * 1024 * 1024 * 1024
                self.storage_usage_bytes.labels(
                    user_id=user_id, organization_id=org_id, type='used'
                ).set(storage_bytes)
            
            if metrics_data.get('storage_available_gb') is not None:
                available_bytes = metrics_data['storage_available_gb'] * 1024 * 1024 * 1024
                self.storage_usage_bytes.labels(
                    user_id=user_id, organization_id=org_id, type='available'
                ).set(available_bytes)
            
            if metrics_data.get('storage_total_gb') is not None:
                total_bytes = metrics_data['storage_total_gb'] * 1024 * 1024 * 1024
                self.storage_usage_bytes.labels(
                    user_id=user_id, organization_id=org_id, type='total'
                ).set(total_bytes)
            
            if metrics_data.get('storage_percent') is not None:
                self.storage_usage_percent.labels(user_id=user_id, organization_id=org_id).set(
                    metrics_data['storage_percent']
                )
            
            # Disk I/O Metrics
            if metrics_data.get('disk_read_mb_s') is not None:
                read_bytes_per_sec = metrics_data['disk_read_mb_s'] * 1024 * 1024
                self.disk_io_bytes_per_second.labels(
                    user_id=user_id, organization_id=org_id, direction='read'
                ).set(read_bytes_per_sec)
            
            if metrics_data.get('disk_write_mb_s') is not None:
                write_bytes_per_sec = metrics_data['disk_write_mb_s'] * 1024 * 1024
                self.disk_io_bytes_per_second.labels(
                    user_id=user_id, organization_id=org_id, direction='write'
                ).set(write_bytes_per_sec)
            
            if metrics_data.get('iops_read') is not None:
                self.disk_iops.labels(
                    user_id=user_id, organization_id=org_id, direction='read'
                ).set(metrics_data['iops_read'])
            
            if metrics_data.get('iops_write') is not None:
                self.disk_iops.labels(
                    user_id=user_id, organization_id=org_id, direction='write'
                ).set(metrics_data['iops_write'])
            
            # Network Metrics
            if metrics_data.get('network_in_mb_s') is not None:
                in_bytes_per_sec = metrics_data['network_in_mb_s'] * 1024 * 1024
                self.network_throughput_bytes_per_second.labels(
                    user_id=user_id, organization_id=org_id, direction='in'
                ).set(in_bytes_per_sec)
            
            if metrics_data.get('network_out_mb_s') is not None:
                out_bytes_per_sec = metrics_data['network_out_mb_s'] * 1024 * 1024
                self.network_throughput_bytes_per_second.labels(
                    user_id=user_id, organization_id=org_id, direction='out'
                ).set(out_bytes_per_sec)
            
            if metrics_data.get('network_connections') is not None:
                self.network_connections_total.labels(user_id=user_id, organization_id=org_id).set(
                    metrics_data['network_connections']
                )
            
            # Latency Metrics (convert from ms to seconds)
            latency_metrics = [
                ('api_latency_ms', self.api_latency_seconds, 'api'),
                ('db_latency_ms', self.database_latency_seconds, 'query'),
                ('redis_latency_ms', self.redis_latency_seconds, 'operation'),
                ('system_latency_ms', self.system_latency_seconds, None)
            ]
            
            for metric_key, histogram, operation in latency_metrics:
                if metrics_data.get(metric_key) is not None:
                    latency_seconds = metrics_data[metric_key] / 1000.0
                    if operation:
                        histogram.labels(
                            user_id=user_id, organization_id=org_id, 
                            endpoint=operation if metric_key == 'api_latency_ms' else operation
                        ).observe(latency_seconds)
                    else:
                        histogram.labels(user_id=user_id, organization_id=org_id).observe(latency_seconds)
            
            # Container/Service Metrics
            if metrics_data.get('container_count') is not None:
                self.container_count.labels(user_id=user_id, organization_id=org_id).set(
                    metrics_data['container_count']
                )
            
            if metrics_data.get('service_count') is not None:
                self.service_count.labels(user_id=user_id, organization_id=org_id).set(
                    metrics_data['service_count']
                )
            
            # Process Metrics
            if metrics_data.get('process_count') is not None:
                self.process_count.labels(user_id=user_id, organization_id=org_id).set(
                    metrics_data['process_count']
                )
            
            if metrics_data.get('thread_count') is not None:
                self.thread_count.labels(user_id=user_id, organization_id=org_id).set(
                    metrics_data['thread_count']
                )
            
            if metrics_data.get('file_descriptors') is not None:
                self.file_descriptors_count.labels(user_id=user_id, organization_id=org_id).set(
                    metrics_data['file_descriptors']
                )
            
            # Collection Metrics
            if metrics_data.get('collection_duration_ms') is not None:
                duration_seconds = metrics_data['collection_duration_ms'] / 1000.0
                collector = metrics_data.get('collected_by', 'unknown')
                self.metrics_collection_duration_seconds.labels(
                    user_id=user_id, organization_id=org_id, collector=collector
                ).observe(duration_seconds)
            
            # Increment collection counter
            self.metrics_collection_total.labels(
                user_id=user_id, organization_id=org_id, status='success'
            ).inc()
            
        except Exception as e:
            print(f"Error updating Prometheus metrics: {e}")
            # Increment error counter
            try:
                user_id = str(metrics_data.get('user_id', 'unknown'))
                org_id = str(metrics_data.get('organization_id', 'unknown'))
                self.metrics_collection_total.labels(
                    user_id=user_id, organization_id=org_id, status='error'
                ).inc()
            except:
                pass
    
    def update_version_info(self, organization_id: str, component_name: str, version_data: Dict[str, str]):
        """Update orchestrator version information."""
        try:
            self.orchestrator_version_info.labels(
                organization_id=str(organization_id),
                component_name=component_name
            ).info(version_data)
        except Exception as e:
            print(f"Error updating version info: {e}")
    
    def get_metrics_text(self) -> str:
        """Get metrics in Prometheus text format."""
        return generate_latest(self.registry).decode('utf-8')


class SystemPerformanceMetricsCollector:
    """Prometheus collector that integrates with system metrics service."""
    
    def __init__(self, system_metrics_service, redis_client=None):
        self.system_metrics_service = system_metrics_service
        self.redis_client = redis_client
        self.exporter = SystemPerformancePrometheusExporter()
    
    async def collect_and_export_metrics(self, user_id: str, organization_id: str):
        """Collect system metrics and export to Prometheus."""
        try:
            # Collect metrics using the service
            import uuid
            user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            org_uuid = uuid.UUID(organization_id) if isinstance(organization_id, str) else organization_id
            
            metrics_data = await self.system_metrics_service.collector.collect_system_metrics(
                user_id=user_uuid,
                organization_id=org_uuid
            )
            
            # Export to Prometheus
            self.exporter.update_metrics_from_data(metrics_data)
            
            return metrics_data
            
        except Exception as e:
            print(f"Error collecting and exporting metrics: {e}")
            return None
    
    def get_prometheus_metrics(self) -> str:
        """Get Prometheus metrics text format."""
        return self.exporter.get_metrics_text()


# Global exporter instance
global_prometheus_exporter = SystemPerformancePrometheusExporter()