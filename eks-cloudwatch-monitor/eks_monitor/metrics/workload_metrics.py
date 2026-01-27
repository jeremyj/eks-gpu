"""Workload-level metrics collection (aggregated by deployment/statefulset)."""

import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from ..cloudwatch_client import CloudWatchClient


def extract_workload_name(pod_name: str) -> str:
    """
    Extract workload name from pod name.

    Handles common patterns:
    - deployment-abc123-xyz45 -> deployment
    - statefulset-0 -> statefulset
    - job-abc123 -> job
    """
    # StatefulSet pattern (ends with -N where N is a number)
    if re.match(r".*-\d+$", pod_name):
        return re.sub(r"-\d+$", "", pod_name)

    # Deployment/ReplicaSet pattern (ends with -hash-hash)
    match = re.match(r"^(.+)-[a-z0-9]+-[a-z0-9]+$", pod_name)
    if match:
        return match.group(1)

    # Job pattern (ends with -hash)
    match = re.match(r"^(.+)-[a-z0-9]+$", pod_name)
    if match:
        return match.group(1)

    return pod_name


def collect_workload_metrics(
    client: CloudWatchClient,
    start_time: datetime,
    end_time: datetime,
    period: int,
    namespace_filter: list[str] | None = None,
    quiet: bool = False,
) -> list[dict[str, Any]]:
    """
    Collect workload-level metrics by aggregating pod metrics.

    Returns:
        List of workload metrics dictionaries
    """
    # Discover pods from CloudWatch metrics - get full dimensions
    cluster_dims = [{"Name": "ClusterName", "Value": client.cluster_name}]
    pod_dimensions = client.list_metric_dimensions("pod_cpu_utilization", cluster_dims)

    # Group pods by workload, storing their full dimensions
    # Only include dimension sets with FullPodName (skip aggregated metrics)
    workloads: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "pods": {},  # Use dict keyed by FullPodName to deduplicate
            "namespace": None,
        }
    )

    # Extract pod info from dimensions
    for dims in pod_dimensions:
        pod_name = None
        full_pod_name = None
        namespace = None

        for dim in dims:
            if dim["Name"] == "PodName":
                pod_name = dim["Value"]
            elif dim["Name"] == "FullPodName":
                full_pod_name = dim["Value"]
            elif dim["Name"] == "Namespace":
                namespace = dim["Value"]

        # Skip aggregated metrics (no FullPodName) and incomplete data
        if not pod_name or not namespace or not full_pod_name:
            continue

        # Apply namespace filter
        if namespace_filter and namespace not in namespace_filter:
            continue

        # Use FullPodName for workload extraction (has hash suffixes)
        workload_name = extract_workload_name(full_pod_name)
        key = f"{namespace}/{workload_name}"

        workloads[key]["namespace"] = namespace
        # Deduplicate by FullPodName
        workloads[key]["pods"][full_pod_name] = {"name": pod_name, "dimensions": dims}

    if not quiet:
        print(f"Found {len(workloads)} workloads")

    # Collect metrics for each workload by querying its pods
    workload_metrics = []

    for workload_key, workload_data in sorted(workloads.items()):
        namespace = workload_data["namespace"]
        workload_name = workload_key.split("/", 1)[1]

        cpu_avgs = []
        cpu_maxs = []
        memory_avgs = []
        memory_maxs = []
        memory_mb_avgs = []
        memory_mb_maxs = []
        network_rx_avgs = []
        network_tx_avgs = []

        for full_pod_name, pod_info in workload_data["pods"].items():
            pod_name = pod_info["name"]
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
            if cpu_stats.get("avg") is not None:
                cpu_avgs.append(cpu_stats["avg"])
            if cpu_stats.get("max") is not None:
                cpu_maxs.append(cpu_stats["max"])

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
            if memory_stats.get("avg") is not None:
                memory_avgs.append(memory_stats["avg"])
            if memory_stats.get("max") is not None:
                memory_maxs.append(memory_stats["max"])

            # Memory working set (bytes) - for actual MB values
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
                    memory_mb_avgs.append(mem_ws_stats["avg"] / (1024 * 1024))  # bytes to MB
                if mem_ws_stats.get("max") is not None:
                    memory_mb_maxs.append(mem_ws_stats["max"] / (1024 * 1024))

            # Network RX - get specific dimensions
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
                if rx_stats.get("avg") is not None:
                    network_rx_avgs.append(rx_stats["avg"])  # already bytes/sec

            # Network TX - get specific dimensions
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
                if tx_stats.get("avg") is not None:
                    network_tx_avgs.append(tx_stats["avg"])  # already bytes/sec

        # Aggregate workload metrics
        workload_metric = {
            "name": workload_name,
            "namespace": namespace,
            "pods": len(workload_data["pods"]),
            "cpu": {
                "avg": round(sum(cpu_avgs) / len(cpu_avgs), 2) if cpu_avgs else 0,
                "max": round(max(cpu_maxs), 2) if cpu_maxs else 0,
                "unit": "percent",
            },
            "memory": {
                "avg_pct": round(sum(memory_avgs) / len(memory_avgs), 2) if memory_avgs else 0,
                "max_pct": round(max(memory_maxs), 2) if memory_maxs else 0,
                "avg_mb": round(sum(memory_mb_avgs) / len(memory_mb_avgs), 0)
                if memory_mb_avgs
                else 0,
                "max_mb": round(max(memory_mb_maxs), 0) if memory_mb_maxs else 0,
            },
            "network": {
                "rx_avg": round(sum(network_rx_avgs)) if network_rx_avgs else 0,
                "tx_avg": round(sum(network_tx_avgs)) if network_tx_avgs else 0,
                "unit": "bytes/sec",
            },
        }
        workload_metrics.append(workload_metric)

    return workload_metrics
