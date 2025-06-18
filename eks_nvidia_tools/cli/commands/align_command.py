"""
Align Command for EKS NVIDIA Tools CLI

This command provides driver alignment functionality using the refactored models.
"""

import argparse
import os
import sys
from typing import Optional, Dict, Any

# Import the existing alignment classes
from eks_nvidia_alignment import DriverAlignmentOrchestrator, DriverAlignment

from ..shared.arguments import (
    add_architecture_args, add_kubernetes_args, add_output_args, 
    add_aws_args, add_cluster_args
)
from ..shared.output import OutputFormatter
from ..shared.validation import (
    validate_k8s_version, validate_architecture, validate_cluster_name,
    validate_driver_version, ValidationError
)
from ..shared.progress import progress, print_step, print_separator


class AlignCommand:
    """Driver alignment subcommands using the refactored models."""
    
    def register_parser(self, subparsers) -> None:
        """Register the align subcommand parser."""
        parser = subparsers.add_parser(
            'align',
            help='Align NVIDIA drivers between EKS AMIs and container images',
            description='Align NVIDIA drivers between EKS nodegroup AMIs and container images using two strategies: ami-first or container-first.'
        )
        
        # Strategy selection
        strategy_group = parser.add_argument_group('Strategy Options')
        strategy_group.add_argument(
            '--strategy',
            choices=['ami-first', 'container-first'],
            required=True,
            help='Alignment strategy: ami-first (use latest AMI) or container-first (find compatible AMI)'
        )
        
        # Cluster and version options
        target_group = parser.add_argument_group('Target Options')
        add_cluster_args(target_group)
        add_kubernetes_args(target_group)
        add_architecture_args(target_group)
        
        # Container-first specific options
        container_group = parser.add_argument_group('Container-First Options')
        container_group.add_argument(
            '--current-driver-version',
            help='Current container driver version (required for container-first strategy)'
        )
        
        # Nodegroup configuration
        nodegroup_group = parser.add_argument_group('Nodegroup Configuration')
        nodegroup_group.add_argument(
            '--nodegroup-name',
            help='EKS nodegroup name (overrides template)'
        )
        nodegroup_group.add_argument(
            '--template',
            help='Path to nodegroup template JSON file (default: nodegroup_template.json)'
        )
        
        # Template overrides
        override_group = parser.add_argument_group('Template Overrides')
        override_group.add_argument(
            '--instance-types',
            nargs='+',
            help='EC2 instance types for nodegroup (overrides template)'
        )
        override_group.add_argument(
            '--subnet-ids',
            nargs='+',
            help='Subnet IDs for nodegroup (overrides template)'
        )
        override_group.add_argument(
            '--node-role-arn',
            help='IAM role ARN for nodegroup (overrides template)'
        )
        override_group.add_argument(
            '--capacity-type',
            choices=['ON_DEMAND', 'SPOT'],
            help='Capacity type (overrides template)'
        )
        override_group.add_argument(
            '--disk-size',
            type=int,
            help='Disk size in GB (overrides template)'
        )
        override_group.add_argument(
            '--min-size',
            type=int,
            help='Minimum number of nodes (overrides template)'
        )
        override_group.add_argument(
            '--max-size',
            type=int,
            help='Maximum number of nodes (overrides template)'
        )
        override_group.add_argument(
            '--desired-size',
            type=int,
            help='Desired number of nodes (overrides template)'
        )
        
        # AWS configuration
        aws_group = parser.add_argument_group('AWS Options')
        add_aws_args(aws_group)
        aws_group.add_argument(
            '--ubuntu-version',
            default='ubuntu2204',
            help='Ubuntu version for driver resolution (default: ubuntu2204)'
        )
        
        # Execution options
        execution_group = parser.add_argument_group('Execution Options')
        execution_group.add_argument(
            '--plan-only',
            action='store_true',
            help='Only show the alignment plan without executing'
        )
        execution_group.add_argument(
            '--output-file', '-o',
            help='Output file for nodegroup configuration'
        )
        execution_group.add_argument(
            '--generate-template',
            action='store_true',
            help='Generate a sample nodegroup_template.json file and exit'
        )
        
        # Output options
        output_group = parser.add_argument_group('Output Options')
        add_output_args(output_group)
        
        parser.set_defaults(func=self.execute)
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute the align command."""
        try:
            # Initialize formatter
            formatter = OutputFormatter(args.output, args.quiet)
            
            # Validate and normalize architecture
            try:
                architecture = validate_architecture(args.architecture)
            except ValidationError as e:
                formatter.print_status(str(e), 'error')
                return 1
            
            # Handle template generation
            if args.generate_template:
                return self._generate_template(args, architecture, formatter)
            
            # Validate required arguments
            validation_result = self._validate_arguments(args, formatter)
            if validation_result != 0:
                return validation_result
            
            # Build configuration
            config = {
                'aws_profile': args.profile,
                'aws_region': args.region,
                'ubuntu_version': args.ubuntu_version,
                'architecture': architecture,
                'debug': args.verbose,
            }
            
            # Build template overrides
            template_overrides = self._build_template_overrides(args)
            
            # Initialize orchestrator
            orchestrator = DriverAlignmentOrchestrator(config)
            
            # Execute alignment strategy
            print_separator(f"Driver Alignment - {args.strategy.title()} Strategy", not args.quiet)
            
            if args.strategy == 'ami-first':
                alignment = self._execute_ami_first(
                    orchestrator, args, architecture, formatter
                )
            else:
                alignment = self._execute_container_first(
                    orchestrator, args, architecture, formatter
                )
            
            if alignment is None:
                return 1
            
            # Show alignment results
            formatter.print_alignment_results(alignment)
            
            # Execute if not plan-only
            if not args.plan_only:
                return self._execute_alignment(
                    orchestrator, alignment, args, architecture, 
                    template_overrides, formatter
                )
            else:
                formatter.print_status("Plan-only mode: No changes were made", 'info')
            
            return 0
            
        except Exception as e:
            if args.verbose:
                import traceback
                traceback.print_exc()
            else:
                print(f"Error: {e}")
            return 1
    
    def _validate_arguments(self, args: argparse.Namespace, 
                          formatter: OutputFormatter) -> int:
        """Validate command arguments."""
        # Validate Kubernetes version if provided
        if args.k8s_version:
            try:
                validate_k8s_version(args.k8s_version)
            except ValidationError as e:
                formatter.print_status(str(e), 'error')
                return 1
        
        # Validate cluster name if provided
        if args.cluster_name:
            try:
                validate_cluster_name(args.cluster_name)
            except ValidationError as e:
                formatter.print_status(str(e), 'error')
                return 1
        
        # Either cluster-name OR k8s-version must be provided
        if not args.cluster_name and not args.k8s_version:
            formatter.print_status(
                "Either --cluster-name (for auto-detection) or --k8s-version (manual) is required",
                'error'
            )
            return 1
        
        # Validate strategy-specific arguments
        if args.strategy == 'container-first':
            if not args.current_driver_version:
                formatter.print_status(
                    "--current-driver-version is required for container-first strategy",
                    'error'
                )
                return 1
            
            try:
                validate_driver_version(args.current_driver_version)
            except ValidationError as e:
                formatter.print_status(str(e), 'error')
                return 1
        
        # Validate template requirements
        template_will_provide = (
            (args.template and os.path.exists(args.template)) or
            os.path.exists("nodegroup_template.json")
        )
        
        if not template_will_provide:
            required_params = {
                'nodegroup_name': args.nodegroup_name,
                'node_role_arn': args.node_role_arn,
                'subnet_ids': args.subnet_ids
            }
            
            missing_required = []
            for param_name, param_value in required_params.items():
                if not param_value:
                    cli_arg = f"--{param_name.replace('_', '-')}"
                    missing_required.append(cli_arg)
            
            if missing_required:
                formatter.print_status(
                    "No template file found and missing required arguments:",
                    'error'
                )
                for field in missing_required:
                    formatter.print_status(f"  {field}", 'error')
                formatter.print_status(
                    "Either generate a template with 'eks-nvidia-tools align --generate-template' or provide required arguments",
                    'info'
                )
                return 1
        
        return 0
    
    def _generate_template(self, args: argparse.Namespace, architecture: str,
                         formatter: OutputFormatter) -> int:
        """Generate a sample nodegroup template."""
        template_filename = "nodegroup_template.json"
        
        # Check if file already exists
        if os.path.exists(template_filename):
            formatter.print_status(f"{template_filename} already exists", 'error')
            formatter.print_status(
                "Remove the existing file first if you want to regenerate it",
                'info'
            )
            return 1
        
        # Architecture-specific defaults
        if architecture == "arm64":
            default_instances = ["g5g.xlarge"]
            default_ami_type = "AL2023_ARM_64_NVIDIA"
            default_arch_label = "arm64"
        else:
            default_instances = ["g4dn.xlarge"]
            default_ami_type = "AL2023_x86_64_NVIDIA"
            default_arch_label = "amd64"
        
        sample_template = {
            # Required parameters
            "clusterName": args.cluster_name or "",
            "nodegroupName": args.nodegroup_name or f"gpu-workers-{architecture}",
            "nodeRole": args.node_role_arn or "arn:aws:iam::YOUR_ACCOUNT_ID:role/EKSNodeInstanceRole",
            "subnets": args.subnet_ids or [
                "subnet-YOUR_SUBNET_1",
                "subnet-YOUR_SUBNET_2"
            ],
            
            # Instance configuration
            "instanceTypes": args.instance_types or default_instances,
            "amiType": default_ami_type,
            "capacityType": args.capacity_type or "ON_DEMAND",
            "diskSize": args.disk_size or 50,
            
            # Scaling configuration
            "scalingConfig": {
                "minSize": args.min_size if args.min_size is not None else 0,
                "maxSize": args.max_size if args.max_size is not None else 10,
                "desiredSize": args.desired_size if args.desired_size is not None else 1
            },
            
            # Update configuration
            "updateConfig": {
                "maxUnavailable": 1
            },
            
            # Labels for node scheduling
            "labels": {
                "node-type": "gpu-worker",
                "nvidia.com/gpu": "true",
                "kubernetes.io/arch": default_arch_label,
                "environment": "production"
            },
            
            # Taints for node scheduling (optional)
            "taints": [],
            
            # Resource tags
            "tags": {
                "Environment": "production",
                "Project": "ml-workloads",
                "Architecture": architecture,
                "ManagedBy": "eks-nvidia-tools"
            }
        }
        
        try:
            import json
            with open(template_filename, 'w') as f:
                json.dump(sample_template, f, indent=2)
            
            arch_display = architecture.upper() if architecture == "arm64" else "x86_64"
            formatter.print_status(f"Generated {arch_display} template: {template_filename}", 'success')
            
            formatter.print_status("Required fields (must be edited):", 'info')
            if not args.cluster_name:
                formatter.print_status("  • clusterName: Specify your EKS cluster name", 'info')
            if not args.node_role_arn:
                formatter.print_status("  • nodeRole: Replace YOUR_ACCOUNT_ID with your AWS account ID", 'info')
            if not args.subnet_ids:
                formatter.print_status("  • subnets: Replace with your actual subnet IDs", 'info')
            
            formatter.print_status(f"Template configured for {arch_display} architecture:", 'info')
            formatter.print_status(f"  • instanceTypes: {default_instances}", 'info')
            formatter.print_status(f"  • amiType: {default_ami_type}", 'info')
            formatter.print_status(f"  • kubernetes.io/arch: {default_arch_label}", 'info')
            
            return 0
            
        except Exception as e:
            formatter.print_status(f"Error creating template file: {e}", 'error')
            return 1
    
    def _build_template_overrides(self, args: argparse.Namespace) -> Dict[str, Any]:
        """Build template overrides from command line arguments."""
        template_overrides = {}
        
        # Add nodegroup-specific overrides
        if args.nodegroup_name:
            template_overrides["nodegroupName"] = args.nodegroup_name
        if args.instance_types:
            template_overrides["instanceTypes"] = args.instance_types
        if args.subnet_ids:
            template_overrides["subnets"] = args.subnet_ids
        if args.node_role_arn:
            template_overrides["nodeRole"] = args.node_role_arn
        if args.capacity_type:
            template_overrides["capacityType"] = args.capacity_type
        if args.disk_size:
            template_overrides["diskSize"] = args.disk_size
        
        # Add scaling configuration if any scaling parameters provided
        scaling_config = {}
        if args.min_size is not None:
            scaling_config["minSize"] = args.min_size
        if args.max_size is not None:
            scaling_config["maxSize"] = args.max_size
        if args.desired_size is not None:
            scaling_config["desiredSize"] = args.desired_size
        
        if scaling_config:
            template_overrides["scalingConfig"] = scaling_config
        
        return template_overrides
    
    def _execute_ami_first(self, orchestrator: DriverAlignmentOrchestrator,
                          args: argparse.Namespace, architecture: str,
                          formatter: OutputFormatter) -> Optional[DriverAlignment]:
        """Execute ami-first strategy."""
        with progress("Finding latest AMI for Kubernetes version", not args.quiet):
            alignment = orchestrator.align_drivers_ami_first(
                k8s_version=args.k8s_version,
                architecture=architecture,
                cluster_name=args.cluster_name
            )
        
        formatter.print_status("AMI-first strategy completed", 'success')
        return alignment
    
    def _execute_container_first(self, orchestrator: DriverAlignmentOrchestrator,
                                args: argparse.Namespace, architecture: str,
                                formatter: OutputFormatter) -> Optional[DriverAlignment]:
        """Execute container-first strategy."""
        with progress("Finding compatible AMI for driver version", not args.quiet):
            alignment = orchestrator.align_drivers_container_first(
                current_driver_version=args.current_driver_version,
                architecture=architecture,
                k8s_version=args.k8s_version,
                cluster_name=args.cluster_name
            )
        
        if alignment is None:
            formatter.print_status(
                "Container-first strategy failed: Please specify an exact driver version",
                'error'
            )
            return None
        
        formatter.print_status("Container-first strategy completed", 'success')
        return alignment
    
    def _execute_alignment(self, orchestrator: DriverAlignmentOrchestrator,
                          alignment: DriverAlignment, args: argparse.Namespace,
                          architecture: str, template_overrides: Dict[str, Any],
                          formatter: OutputFormatter) -> int:
        """Execute the alignment plan."""
        print_separator("Executing Alignment", not args.quiet)
        
        # Use nodegroup name from args, or fallback to architecture-specific default
        arch_suffix = f"-{architecture}" if architecture == "arm64" else ""
        nodegroup_name = args.nodegroup_name or f"gpu-workers{arch_suffix}"
        
        try:
            with progress("Generating nodegroup configuration", not args.quiet):
                results = orchestrator.execute_alignment(
                    alignment=alignment,
                    cluster_name=args.cluster_name or "YOUR-CLUSTER-NAME",
                    nodegroup_name=nodegroup_name,
                    template_path=args.template,
                    template_overrides=template_overrides,
                    output_file=args.output_file
                )
            
            arch_display = architecture.upper() if architecture == "arm64" else "x86_64"
            formatter.print_status(f"{arch_display} configuration generation completed!", 'success')
            formatter.print_status(
                "Use the generated configuration to create your nodegroup when ready",
                'info'
            )
            
            return 0
            
        except Exception as e:
            formatter.print_status(f"Alignment execution failed: {e}", 'error')
            return 1