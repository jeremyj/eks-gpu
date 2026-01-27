"""Node-level metrics collection and aggregation."""

from datetime import datetime
from typing import Any

from ..cloudwatch_client import CloudWatchClient


def collect_node_metrics(
    client: CloudWatchClient,
    start_time: datetime,
    end_time: datetime,
    period: int,
    nodegroup_filter: str | None = None,
    exclude_gpu: bool = False,
    quiet: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Collect node-level metrics from CloudWatch Container Insights.

    Returns:
        Tuple of (node_metrics_list, summary_dict)
    """
    # Get nodegroups to map nodes
    nodegroups = client.get_nodegroups()
    gpu_nodegroups = set()
    instance_to_nodegroup = {}

    for ng in nodegroups:
        ng_name = ng.get("nodegroupName", "")

        # Check if GPU nodegroup (has GPU instance types)
        instance_types = ng.get("instanceTypes", [])
        is_gpu = any(
            t.startswith(("p2.", "p3.", "p4.", "p5.", "g3.", "g4.", "g5.", "g6."))
            for t in instance_types
        )
        if is_gpu:
            gpu_nodegroups.add(ng_name)

    # Discover nodes from CloudWatch metrics - get full dimensions
    cluster_dims = [{"Name": "ClusterName", "Value": client.cluster_name}]
    node_dimensions_list = client.list_metric_dimensions("node_cpu_utilization", cluster_dims)

    # Build node info from dimensions
    nodes = {}
    for dims in node_dimensions_list:
        node_name = None
        instance_id = None
        for dim in dims:
            if dim["Name"] == "NodeName":
                node_name = dim["Value"]
            elif dim["Name"] == "InstanceId":
                instance_id = dim["Value"]
        if node_name:
            nodes[node_name] = {"instance_id": instance_id, "dimensions": dims}

    if not quiet:
        print(f"Found {len(nodes)} nodes")

    # Collect metrics for each node
    node_metrics = []
    all_cpu_avg = []
    all_cpu_max = []
    all_memory_avg = []
    all_memory_max = []
    all_network_avg = []

    for node_name, node_info in sorted(nodes.items()):
        # Use the exact dimensions from list_metrics
        dims = node_info["dimensions"]
        instance_id = node_info["instance_id"]

        # Try to match nodegroup via instance (would need EC2 API, skip for now)
        node_nodegroup = None

        # Apply filters
        if nodegroup_filter and node_nodegroup != nodegroup_filter:
            continue
        if exclude_gpu and node_nodegroup in gpu_nodegroups:
            continue

        # CPU utilization
        cpu_stats = client.get_metric_statistics(
            "node_cpu_utilization",
            dims,
            start_time,
            end_time,
            period,
            ["Average", "Maximum", "Minimum"],
        )

        # Memory utilization - need to get memory dimensions
        memory_dims_list = client.list_metric_dimensions(
            "node_memory_utilization",
            [
                {"Name": "ClusterName", "Value": client.cluster_name},
                {"Name": "NodeName", "Value": node_name},
            ],
        )
        memory_dims = memory_dims_list[0] if memory_dims_list else dims

        memory_stats = client.get_metric_statistics(
            "node_memory_utilization",
            memory_dims,
            start_time,
            end_time,
            period,
            ["Average", "Maximum", "Minimum"],
        )

        # Network total bytes
        network_dims_list = client.list_metric_dimensions(
            "node_network_total_bytes",
            [
                {"Name": "ClusterName", "Value": client.cluster_name},
                {"Name": "NodeName", "Value": node_name},
            ],
        )
        network_dims = network_dims_list[0] if network_dims_list else dims

        network_stats = client.get_metric_statistics(
            "node_network_total_bytes",
            network_dims,
            start_time,
            end_time,
            period,
            ["Average", "Maximum"],
        )

        # Pod count
        pod_dims_list = client.list_metric_dimensions(
            "node_number_of_running_pods",
            [
                {"Name": "ClusterName", "Value": client.cluster_name},
                {"Name": "NodeName", "Value": node_name},
            ],
        )
        pod_dims = pod_dims_list[0] if pod_dims_list else dims

        pod_stats = client.get_metric_statistics(
            "node_number_of_running_pods",
            pod_dims,
            start_time,
            end_time,
            period,
            ["Average"],
        )

        node_data = {
            "name": node_name,
            "instance_id": instance_id,
            "nodegroup": node_nodegroup,
            "cpu": {
                "avg": round(cpu_stats.get("avg") or 0, 2),
                "max": round(cpu_stats.get("max") or 0, 2),
                "min": round(cpu_stats.get("min") or 0, 2),
            },
            "memory": {
                "avg": round(memory_stats.get("avg") or 0, 2),
                "max": round(memory_stats.get("max") or 0, 2),
                "min": round(memory_stats.get("min") or 0, 2),
            },
            "network_bytes_sec": {
                "avg": round(network_stats.get("avg") or 0, 0),  # already bytes/sec
                "max": round(network_stats.get("max") or 0, 0),
            },
            "pod_count": {"avg": round(pod_stats.get("avg") or 0, 1)},
        }
        node_metrics.append(node_data)

        # Aggregate for summary
        if cpu_stats.get("avg") is not None:
            all_cpu_avg.append(cpu_stats["avg"])
        if cpu_stats.get("max") is not None:
            all_cpu_max.append(cpu_stats["max"])
        if memory_stats.get("avg") is not None:
            all_memory_avg.append(memory_stats["avg"])
        if memory_stats.get("max") is not None:
            all_memory_max.append(memory_stats["max"])
        if network_stats.get("avg") is not None:
            all_network_avg.append(network_stats["avg"])  # already bytes/sec

    # Calculate summary
    summary = {
        "total_nodes": len(node_metrics),
        "cpu_avg_pct": round(sum(all_cpu_avg) / len(all_cpu_avg), 1) if all_cpu_avg else 0,
        "cpu_max_pct": round(max(all_cpu_max), 1) if all_cpu_max else 0,
        "memory_avg_pct": round(sum(all_memory_avg) / len(all_memory_avg), 1)
        if all_memory_avg
        else 0,
        "memory_max_pct": round(max(all_memory_max), 1) if all_memory_max else 0,
        "network_avg_bytes_sec": round(sum(all_network_avg)) if all_network_avg else 0,
    }

    return node_metrics, summary
