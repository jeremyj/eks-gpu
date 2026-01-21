"""
Inspect Command for EKS NVIDIA Tools CLI

This command queries EKS nodegroups and reports their NVIDIA driver versions.
"""

import argparse
import json
from typing import List, Optional

import yaml
from tabulate import tabulate

from core.eks_client import EKSClient, EKSClientError, NodegroupInfo
from core.ami_resolver import EKSAMIResolver, AMIResolutionError
from models.ami_types import AMIType

from ..shared.arguments import add_aws_args, add_cluster_args, add_output_args
from ..shared.output import OutputFormatter
from ..shared.validation import validate_cluster_name, ValidationError
from ..shared.progress import progress, print_step


class InspectCommand:
    """Nodegroup driver inspection subcommand."""

    def register_parser(self, subparsers) -> None:
        """Register the inspect subcommand parser."""
        parser = subparsers.add_parser(
            'inspect',
            help='Inspect EKS nodegroups and report NVIDIA driver versions',
            description='Query EKS nodegroups and report their NVIDIA driver versions based on the AMI release version.'
        )

        # Cluster options
        cluster_group = parser.add_argument_group('Cluster Options')
        cluster_group.add_argument(
            '--cluster-name',
            required=True,
            help='EKS cluster name (required)'
        )
        cluster_group.add_argument(
            '--nodegroup-name',
            help='Specific nodegroup to inspect (default: all GPU nodegroups)'
        )
        cluster_group.add_argument(
            '--all-nodegroups',
            action='store_true',
            help='Include non-GPU nodegroups in inspection'
        )

        # AWS options
        aws_group = parser.add_argument_group('AWS Options')
        add_aws_args(aws_group)

        # Output options
        output_group = parser.add_argument_group('Output Options')
        add_output_args(output_group)

        parser.set_defaults(func=self.execute)

    def execute(self, args: argparse.Namespace) -> int:
        """Execute the inspect command."""
        try:
            # Validate inputs
            try:
                validate_cluster_name(args.cluster_name)
            except ValidationError as e:
                print(f"✗ {e}")
                return 1

            formatter = OutputFormatter(args.output, args.quiet)

            # Initialize clients
            try:
                eks_client = EKSClient(
                    profile=args.profile,
                    region=args.region,
                    verbose=args.verbose
                )
            except EKSClientError as e:
                formatter.print_status(str(e), 'error')
                return 1

            ami_resolver = EKSAMIResolver(verbose=args.verbose)

            # Validate cluster access
            if not args.quiet:
                formatter.print_status(
                    f"Inspecting cluster '{args.cluster_name}'", 'info'
                )

            with progress(f"Validating cluster access", not args.quiet):
                is_valid, message = eks_client.validate_cluster_access(args.cluster_name)
                if not is_valid:
                    formatter.print_status(message, 'error')
                    return 1

            # Get nodegroups
            with progress("Fetching nodegroups", not args.quiet):
                if args.nodegroup_name:
                    # Single nodegroup
                    try:
                        nodegroups = [eks_client.get_nodegroup_info(
                            args.cluster_name, args.nodegroup_name
                        )]
                    except EKSClientError as e:
                        formatter.print_status(str(e), 'error')
                        return 1
                elif args.all_nodegroups:
                    # All nodegroups
                    nodegroup_names = eks_client.list_nodegroups(args.cluster_name)
                    nodegroups = [
                        eks_client.get_nodegroup_info(args.cluster_name, name)
                        for name in nodegroup_names
                    ]
                else:
                    # GPU nodegroups only
                    nodegroups = eks_client.get_gpu_nodegroups(args.cluster_name)

            if not nodegroups:
                formatter.print_status("No nodegroups found", 'warning')
                return 0

            # Resolve driver versions
            results = []
            with progress("Resolving driver versions", not args.quiet):
                for ng in nodegroups:
                    driver_version = self._get_driver_version(
                        ng, ami_resolver, args.verbose
                    )
                    results.append({
                        'nodegroup': ng.nodegroup_name,
                        'release_version': ng.release_version or 'N/A',
                        'driver_version': driver_version or 'N/A',
                        'ami_type': ng.ami_type,
                        'status': ng.status,
                        'is_gpu': ng.is_gpu_nodegroup
                    })

            # Output results
            self._output_results(results, args.output, formatter)

            return 0

        except Exception as e:
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
            else:
                print(f"✗ Error: {e}")
            return 1

    def _get_driver_version(
        self,
        ng: NodegroupInfo,
        ami_resolver: EKSAMIResolver,
        verbose: bool
    ) -> Optional[str]:
        """Get driver version for a nodegroup."""
        if not ng.release_version:
            return None

        if not ng.is_gpu_nodegroup:
            return None

        try:
            ami_type = AMIType(ng.ami_type)
        except ValueError:
            if verbose:
                print(f"[DEBUG] Unknown AMI type: {ng.ami_type}")
            return None

        try:
            return ami_resolver.get_driver_for_release_version(
                ng.release_version, ami_type
            )
        except AMIResolutionError as e:
            if verbose:
                print(f"[DEBUG] Failed to resolve driver for {ng.nodegroup_name}: {e}")
            return None

    def _output_results(
        self,
        results: List[dict],
        output_format: str,
        formatter: OutputFormatter
    ) -> None:
        """Output results in the requested format."""
        if output_format == 'json':
            print(json.dumps(results, indent=2))

        elif output_format == 'yaml':
            print(yaml.dump(results, default_flow_style=False, sort_keys=False))

        else:  # table
            rows = []
            for r in results:
                # Add GPU indicator for --all-nodegroups output
                nodegroup_name = r['nodegroup']
                if not r['is_gpu']:
                    nodegroup_name = f"{nodegroup_name} (non-GPU)"

                rows.append([
                    nodegroup_name,
                    r['release_version'],
                    r['driver_version'],
                    r['ami_type']
                ])

            headers = ['Nodegroup', 'Release Version', 'Driver Version', 'AMI Type']
            print(tabulate(rows, headers=headers, tablefmt='grid'))
