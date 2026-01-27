"""Pod-level metrics collection."""

from datetime import datetime
from typing import Any

from ..cloudwatch_client import CloudWatchClient
from .workload_metrics import extract_workload_name


def collect_pod_metrics(
    client: CloudWatchClient,
    start_time: datetime,
    end_time: datetime,
    period: int,
    namespace_filter: list[str] | None = None,
    quiet: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    """
    Collect individual pod-level metrics.

    Returns:
        Tuple of (pod_metrics_list, total_pod_count)
    """
    # Discover pods from CloudWatch metrics - get full dimensions
    cluster_dims = [{"Name": "ClusterName", "Value": client.cluster_name}]
    pod_dimensions = client.list_metric_dimensions("pod_cpu_utilization", cluster_dims)

    # Extract unique pods with their dimensions
    # Only include dimension sets with FullPodName (skip aggregated metrics)
    # Use dict keyed by FullPodName to deduplicate
    pods_dict: dict[str, dict] = {}
    for dims in pod_dimensions:
        pod_info = {
            "name": None,
            "full_name": None,
            "namespace": None,
            "node": None,
            "dimensions": dims,
        }
        for dim in dims:
            if dim["Name"] == "PodName":
                pod_info["name"] = dim["Value"]
            elif dim["Name"] == "FullPodName":
                pod_info["full_name"] = dim["Value"]
            elif dim["Name"] == "Namespace":
                pod_info["namespace"] = dim["Value"]
            elif dim["Name"] == "NodeName":
                pod_info["node"] = dim["Value"]

        # Skip aggregated metrics (no FullPodName) and incomplete data
        if not pod_info["name"] or not pod_info["namespace"] or not pod_info["full_name"]:
            continue

        # Apply namespace filter
        if namespace_filter and pod_info["namespace"] not in namespace_filter:
            continue

        # Deduplicate by FullPodName
        pods_dict[pod_info["full_name"]] = pod_info

    pods = list(pods_dict.values())

    if not quiet:
        print(f"Found {len(pods)} pods")

    # Collect metrics for each pod
    pod_metrics = []

    for pod_info in sorted(pods, key=lambda x: (x["namespace"], x["name"])):
        pod_name = pod_info["name"]
        namespace = pod_info["namespace"]
        dims = pod_info["dimensions"]

        # CPU utilization - use exact dimensions from list_metrics
        cpu_stats = client.get_metric_statistics(
            "pod_cpu_utilization",
            dims,
            start_time,
            end_time,
            period,
            ["Average", "Maximum"],
        )

        # Memory utilization (percent) - get specific dimensions for this metric
        memory_dims_list = client.list_metric_dimensions(
            "pod_memory_utilization",
            [
                {"Name": "ClusterName", "Value": client.cluster_name},
                {"Name": "Namespace", "Value": namespace},
                {"Name": "PodName", "Value": pod_name},
            ],
        )
        memory_dims = memory_dims_list[0] if memory_dims_list else dims

        memory_stats = client.get_metric_statistics(
            "pod_memory_utilization",
            memory_dims,
            start_time,
            end_time,
            period,
            ["Average", "Maximum"],
        )

        # Memory working set (bytes) - for actual MB values
        memory_mb_avg = 0
        memory_mb_max = 0
        mem_ws_dims_list = client.list_metric_dimensions(
            "pod_memory_working_set",
            [
                {"Name": "ClusterName", "Value": client.cluster_name},
                {"Name": "Namespace", "Value": namespace},
                {"Name": "PodName", "Value": pod_name},
            ],
        )
        if mem_ws_dims_list:
            mem_ws_stats = client.get_metric_statistics(
                "pod_memory_working_set",
                mem_ws_dims_list[0],
                start_time,
                end_time,
                period,
                ["Average", "Maximum"],
            )
            if mem_ws_stats.get("avg") is not None:
                memory_mb_avg = round(mem_ws_stats["avg"] / (1024 * 1024), 0)
            if mem_ws_stats.get("max") is not None:
                memory_mb_max = round(mem_ws_stats["max"] / (1024 * 1024), 0)

        # Network RX - get specific dimensions
        rx_avg = 0
        rx_dims_list = client.list_metric_dimensions(
            "pod_network_rx_bytes",
            [
                {"Name": "ClusterName", "Value": client.cluster_name},
                {"Name": "Namespace", "Value": namespace},
                {"Name": "PodName", "Value": pod_name},
            ],
        )
        if rx_dims_list:
            rx_stats = client.get_metric_statistics(
                "pod_network_rx_bytes",
                rx_dims_list[0],
                start_time,
                end_time,
                period,
                ["Average"],
            )
            rx_avg = round(rx_stats.get("avg") or 0)  # already bytes/sec

        # Network TX - get specific dimensions
        tx_avg = 0
        tx_dims_list = client.list_metric_dimensions(
            "pod_network_tx_bytes",
            [
                {"Name": "ClusterName", "Value": client.cluster_name},
                {"Name": "Namespace", "Value": namespace},
                {"Name": "PodName", "Value": pod_name},
            ],
        )
        if tx_dims_list:
            tx_stats = client.get_metric_statistics(
                "pod_network_tx_bytes",
                tx_dims_list[0],
                start_time,
                end_time,
                period,
                ["Average"],
            )
            tx_avg = round(tx_stats.get("avg") or 0)  # already bytes/sec

        pod_metric = {
            "name": pod_info["full_name"],
            "namespace": namespace,
            "workload": extract_workload_name(pod_info["full_name"]),
            "node": pod_info["node"],
            "cpu": {
                "avg": round(cpu_stats.get("avg") or 0, 2),
                "max": round(cpu_stats.get("max") or 0, 2),
                "unit": "percent",
            },
            "memory": {
                "avg_pct": round(memory_stats.get("avg") or 0, 2),
                "max_pct": round(memory_stats.get("max") or 0, 2),
                "avg_mb": memory_mb_avg,
                "max_mb": memory_mb_max,
            },
            "network": {
                "rx_avg": rx_avg,
                "tx_avg": tx_avg,
                "unit": "bytes/sec",
            },
        }
        pod_metrics.append(pod_metric)

    return pod_metrics, len(pods)
