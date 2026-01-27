"""JSON report generation."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def generate_report(
    cluster_name: str,
    region: str,
    start_time: datetime,
    end_time: datetime,
    hours: int,
    node_metrics: list[dict],
    node_summary: dict,
    workload_metrics: list[dict],
    pod_metrics: list[dict],
    total_pods: int,
    output_dir: str,
    quiet: bool = False,
) -> str:
    """
    Generate JSON report and write to file.

    Returns:
        Path to the generated report file
    """
    report = {
        "cluster": cluster_name,
        "region": region,
        "time_range": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "hours": hours,
        },
        "summary": {
            "total_nodes": node_summary.get("total_nodes", 0),
            "total_pods": total_pods,
            "cpu_avg_pct": node_summary.get("cpu_avg_pct", 0),
            "cpu_max_pct": node_summary.get("cpu_max_pct", 0),
            "memory_avg_pct": node_summary.get("memory_avg_pct", 0),
            "memory_max_pct": node_summary.get("memory_max_pct", 0),
            "network_avg_bytes_sec": node_summary.get("network_avg_bytes_sec", 0),
        },
        "nodes": node_metrics,
        "workloads": workload_metrics,
        "pods": pod_metrics,
    }

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"eks-report-{cluster_name}-{timestamp}.json"
    filepath = output_path / filename

    # Write report
    with open(filepath, "w") as f:
        json.dump(report, f, indent=2, default=str)

    if not quiet:
        print(f"Report written to: {filepath}")

    return str(filepath)


def print_summary(summary: dict[str, Any], quiet: bool = False) -> None:
    """Print a summary of the metrics to stdout."""
    if quiet:
        return

    print("\n=== Cluster Summary ===")
    print(f"Total nodes: {summary.get('total_nodes', 0)}")
    print(f"Total pods: {summary.get('total_pods', 0)}")
    print(f"CPU: {summary.get('cpu_avg_pct', 0):.1f}% avg, {summary.get('cpu_max_pct', 0):.1f}% max")
    print(
        f"Memory: {summary.get('memory_avg_pct', 0):.1f}% avg, "
        f"{summary.get('memory_max_pct', 0):.1f}% max"
    )
    print(f"Network: {summary.get('network_avg_bytes_sec', 0):,.0f} bytes/sec avg")
