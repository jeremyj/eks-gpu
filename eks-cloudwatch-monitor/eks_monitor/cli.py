"""CLI entry point for EKS CloudWatch Monitor."""

import argparse
import sys

from .cloudwatch_client import CloudWatchClient
from .metrics import collect_node_metrics, collect_pod_metrics, collect_workload_metrics
from .reports import generate_report
from .reports.json_report import print_summary


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="eks-monitor",
        description="Analyze EKS cluster resource utilization via CloudWatch Container Insights",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze cluster metrics")

    # Required arguments
    analyze_parser.add_argument(
        "--cluster-name",
        required=True,
        help="EKS cluster name",
    )

    # Time range
    analyze_parser.add_argument(
        "--hours",
        type=int,
        default=168,
        help="Hours of data to analyze (default: 168 = 7 days)",
    )
    analyze_parser.add_argument(
        "--period",
        type=int,
        default=3600,
        help="Aggregation period in seconds (default: 3600 = 1 hour)",
    )

    # Filters
    analyze_parser.add_argument(
        "--namespace",
        action="append",
        dest="namespaces",
        help="Filter to specific namespace(s), can be specified multiple times",
    )
    analyze_parser.add_argument(
        "--exclude-gpu",
        action="store_true",
        help="Exclude GPU nodegroups from analysis",
    )
    analyze_parser.add_argument(
        "--nodegroup",
        help="Filter to specific nodegroup",
    )

    # AWS
    analyze_parser.add_argument(
        "--profile",
        help="AWS profile name (or use IAM role)",
    )
    analyze_parser.add_argument(
        "--region",
        default="eu-west-1",
        help="AWS region (default: eu-west-1)",
    )

    # Output
    analyze_parser.add_argument(
        "--output-dir",
        default="./reports",
        help="Directory for JSON output (default: ./reports)",
    )
    analyze_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    return parser.parse_args(args)


def cmd_analyze(args: argparse.Namespace) -> int:
    """Run the analyze command."""
    if not args.quiet:
        print(f"Analyzing cluster: {args.cluster_name}")
        print(f"Region: {args.region}")
        print(f"Time range: {args.hours} hours")
        print(f"Period: {args.period} seconds")

    # Initialize client
    client = CloudWatchClient(
        cluster_name=args.cluster_name,
        region=args.region,
        profile=args.profile,
    )

    # Get time range
    start_time, end_time = client.get_time_range(args.hours)

    if not args.quiet:
        print(f"\nCollecting node metrics...")

    # Collect node metrics
    node_metrics, node_summary = collect_node_metrics(
        client=client,
        start_time=start_time,
        end_time=end_time,
        period=args.period,
        nodegroup_filter=args.nodegroup,
        exclude_gpu=args.exclude_gpu,
        quiet=args.quiet,
    )

    if not args.quiet:
        print("Collecting workload metrics...")

    # Collect workload metrics
    workload_metrics = collect_workload_metrics(
        client=client,
        start_time=start_time,
        end_time=end_time,
        period=args.period,
        namespace_filter=args.namespaces,
        quiet=args.quiet,
    )

    if not args.quiet:
        print("Collecting pod metrics...")

    # Collect pod metrics
    pod_metrics, total_pods = collect_pod_metrics(
        client=client,
        start_time=start_time,
        end_time=end_time,
        period=args.period,
        namespace_filter=args.namespaces,
        quiet=args.quiet,
    )

    # Generate report
    report_path = generate_report(
        cluster_name=args.cluster_name,
        region=args.region,
        start_time=start_time,
        end_time=end_time,
        hours=args.hours,
        node_metrics=node_metrics,
        node_summary=node_summary,
        workload_metrics=workload_metrics,
        pod_metrics=pod_metrics,
        total_pods=total_pods,
        output_dir=args.output_dir,
        quiet=args.quiet,
    )

    # Print summary
    summary = {
        **node_summary,
        "total_pods": total_pods,
    }
    print_summary(summary, quiet=args.quiet)

    return 0


def main(args: list[str] | None = None) -> int:
    """Main entry point."""
    parsed_args = parse_args(args)

    if parsed_args.command == "analyze":
        return cmd_analyze(parsed_args)

    return 1


if __name__ == "__main__":
    sys.exit(main())
