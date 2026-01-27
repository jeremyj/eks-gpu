"""CloudWatch API wrapper for Container Insights metrics."""

from datetime import datetime, timedelta, timezone
from typing import Any

import boto3


class CloudWatchClient:
    """Client for querying CloudWatch Container Insights metrics."""

    NAMESPACE = "ContainerInsights"

    def __init__(self, cluster_name: str, region: str, profile: str | None = None):
        self.cluster_name = cluster_name
        self.region = region

        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile

        session = boto3.Session(**session_kwargs)
        self.cloudwatch = session.client("cloudwatch")
        self.eks = session.client("eks")

    def get_time_range(self, hours: int) -> tuple[datetime, datetime]:
        """Get start and end times for the query."""
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)
        return start_time, end_time

    def get_metric_statistics(
        self,
        metric_name: str,
        dimensions: list[dict],
        start_time: datetime,
        end_time: datetime,
        period: int,
        statistics: list[str],
    ) -> dict[str, float | None]:
        """Get metric statistics from CloudWatch, auto-chunking if needed."""
        max_datapoints = 1440
        total_seconds = (end_time - start_time).total_seconds()
        expected_datapoints = total_seconds / period

        # If within limit, single query
        if expected_datapoints <= max_datapoints:
            return self._query_metric_statistics(
                metric_name, dimensions, start_time, end_time, period, statistics
            )

        # Chunk the time range
        chunk_seconds = max_datapoints * period
        all_datapoints = []
        current_start = start_time

        while current_start < end_time:
            current_end = min(current_start + timedelta(seconds=chunk_seconds), end_time)
            response = self.cloudwatch.get_metric_statistics(
                Namespace=self.NAMESPACE,
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=current_start,
                EndTime=current_end,
                Period=period,
                Statistics=statistics,
            )
            all_datapoints.extend(response.get("Datapoints", []))
            current_start = current_end

        if not all_datapoints:
            return {stat.lower(): None for stat in statistics}

        result = {}
        for stat in statistics:
            values = [dp[stat] for dp in all_datapoints if stat in dp]
            if not values:
                result[stat.lower()] = None
            elif stat == "Average":
                result["avg"] = sum(values) / len(values)
            elif stat == "Maximum":
                result["max"] = max(values)
            elif stat == "Minimum":
                result["min"] = min(values)
            elif stat == "Sum":
                result["sum"] = sum(values)

        return result

    def _query_metric_statistics(
        self,
        metric_name: str,
        dimensions: list[dict],
        start_time: datetime,
        end_time: datetime,
        period: int,
        statistics: list[str],
    ) -> dict[str, float | None]:
        """Single query for metric statistics."""
        response = self.cloudwatch.get_metric_statistics(
            Namespace=self.NAMESPACE,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=statistics,
        )

        datapoints = response.get("Datapoints", [])
        if not datapoints:
            return {stat.lower(): None for stat in statistics}

        result = {}
        for stat in statistics:
            values = [dp[stat] for dp in datapoints if stat in dp]
            if not values:
                result[stat.lower()] = None
            elif stat == "Average":
                result["avg"] = sum(values) / len(values)
            elif stat == "Maximum":
                result["max"] = max(values)
            elif stat == "Minimum":
                result["min"] = min(values)
            elif stat == "Sum":
                result["sum"] = sum(values)

        return result

    def get_metric_data_batch(
        self,
        queries: list[dict],
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, dict[str, float | None]]:
        """
        Get multiple metrics in a single API call using GetMetricData.

        Args:
            queries: List of dicts with 'id', 'metric_name', 'dimensions', 'stat'

        Returns:
            Dict mapping query id to stats dict
        """
        metric_data_queries = []
        for q in queries:
            metric_data_queries.append({
                "Id": q["id"],
                "MetricStat": {
                    "Metric": {
                        "Namespace": self.NAMESPACE,
                        "MetricName": q["metric_name"],
                        "Dimensions": q["dimensions"],
                    },
                    "Period": q.get("period", 3600),
                    "Stat": q["stat"],
                },
                "ReturnData": True,
            })

        results = {}
        # GetMetricData has a limit of 500 queries per call
        batch_size = 500
        for i in range(0, len(metric_data_queries), batch_size):
            batch = metric_data_queries[i : i + batch_size]
            response = self.cloudwatch.get_metric_data(
                MetricDataQueries=batch,
                StartTime=start_time,
                EndTime=end_time,
            )

            for result in response.get("MetricDataResults", []):
                query_id = result["Id"]
                values = result.get("Values", [])
                stat = query_id.rsplit("_", 1)[-1]  # Extract stat from id like "m1_avg"

                if query_id not in results:
                    results[query_id] = {}

                if not values:
                    results[query_id] = None
                elif stat == "avg":
                    results[query_id] = sum(values) / len(values)
                elif stat == "max":
                    results[query_id] = max(values)
                elif stat == "min":
                    results[query_id] = min(values)
                else:
                    results[query_id] = sum(values) / len(values)

        return results

    def list_metric_dimensions(
        self, metric_name: str, dimension_filters: list[dict] | None = None
    ) -> list[list[dict]]:
        """List all dimension combinations for a metric."""
        params = {
            "Namespace": self.NAMESPACE,
            "MetricName": metric_name,
        }

        if dimension_filters:
            params["Dimensions"] = dimension_filters

        paginator = self.cloudwatch.get_paginator("list_metrics")
        dimensions_list = []

        for page in paginator.paginate(**params):
            for metric in page.get("Metrics", []):
                dimensions_list.append(metric.get("Dimensions", []))

        return dimensions_list

    def get_cluster_dimensions(self) -> list[dict]:
        """Get base dimensions for cluster-level queries."""
        return [{"Name": "ClusterName", "Value": self.cluster_name}]

    def get_node_dimensions(self, node_name: str) -> list[dict]:
        """Get dimensions for node-level queries."""
        return [
            {"Name": "ClusterName", "Value": self.cluster_name},
            {"Name": "NodeName", "Value": node_name},
        ]

    def get_pod_dimensions(self, namespace: str, pod_name: str) -> list[dict]:
        """Get dimensions for pod-level queries."""
        return [
            {"Name": "ClusterName", "Value": self.cluster_name},
            {"Name": "Namespace", "Value": namespace},
            {"Name": "PodName", "Value": pod_name},
        ]

    def get_nodegroups(self) -> list[dict[str, Any]]:
        """Get all nodegroups for the cluster."""
        nodegroups = []
        paginator = self.eks.get_paginator("list_nodegroups")

        for page in paginator.paginate(clusterName=self.cluster_name):
            for ng_name in page.get("nodegroups", []):
                ng_info = self.eks.describe_nodegroup(
                    clusterName=self.cluster_name, nodegroupName=ng_name
                )
                nodegroups.append(ng_info.get("nodegroup", {}))

        return nodegroups

    def describe_cluster(self) -> dict[str, Any]:
        """Get cluster information."""
        response = self.eks.describe_cluster(name=self.cluster_name)
        return response.get("cluster", {})
