"""
Align Command for EKS NVIDIA Tools CLI

This command provides driver alignment functionality using the refactored models.
"""

import argparse
import os
import sys
from typing import Optional, Dict, Any, List

# Import the existing alignment classes
from eks_nvidia_alignment import DriverAlignmentOrchestrator
from models.driver_alignment import DriverAlignment
from core.eks_client import EKSClient, EKSClientError, NodegroupInfo
from core.ami_resolver import EKSAMIResolver
from models.ami_types import AMIType, AMITypeManager

from ..shared.arguments import (
    add_architecture_args, add_kubernetes_args, add_output_args, 
    add_aws_args, add_cluster_args
)
from utils.path_utils import get_template_path, get_output_path, find_template_file
from ..shared.output import OutputFormatter
from ..shared.validation import (
    validate_k8s_version, validate_architecture, validate_cluster_name,
    validate_driver_version, validate_aws_region, validate_aws_profile, ValidationError
)
from ..shared.progress import progress, print_step, print_separator


class AlignCommand:
    """Driver alignment subcommands using the refactored models."""
    
    def register_parser(self, subparsers) -> None:
        """Register the align subcommand parser."""
        parser = subparsers.add_parser(
            'align',
            help='Align NVIDIA drivers between EKS AMIs and container images',
            description='Align NVIDIA drivers between EKS nodegroup AMIs and container images using ami-first or container-first strategies. Use --extract-from-cluster to apply strategies to existing nodegroups.'
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
        target_group.add_argument(
            '--extract-from-cluster',
            help='Extract nodegroup configurations from existing cluster and apply strategy to each'
        )
        
        # Container-first specific options
        container_group = parser.add_argument_group('Container-First Options')
        container_group.add_argument(
            '--current-driver-version',
            help='Current container driver version (required for container-first strategy)'
        )
        
        # Extraction mode options
        extract_group = parser.add_argument_group('Extraction Mode Options')
        extract_group.add_argument(
            '--extract-nodegroups',
            nargs='+',
            help='Specific nodegroup names to extract (defaults to all GPU nodegroups)'
        )
        extract_group.add_argument(
            '--target-cluster',
            help='Target cluster name for generated nodegroup configurations (defaults to source cluster)'
        )
        extract_group.add_argument(
            '--new-nodegroup-suffix',
            default=None,
            help='Suffix to add to generated nodegroup names (default: timestamp in format -YYYY-MM-DDTHH-MM-SS)'
        )
        
        # Nodegroup configuration
        nodegroup_group = parser.add_argument_group('Nodegroup Configuration')
        nodegroup_group.add_argument(
            '--nodegroup-name',
            help='EKS nodegroup name (overrides template)'
        )
        nodegroup_group.add_argument(
            '--template',
            help='Path to nodegroup template JSON file (default: templates/nodegroup_template.json)'
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
            help='Generate a sample nodegroup template file and exit'
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
            
            # Check if we're in extraction mode
            if args.extract_from_cluster:
                return self._execute_extraction_mode(args, architecture, formatter)
            
            # Execute alignment strategy (non-extraction mode)
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
        # Validate AWS arguments
        try:
            validate_aws_profile(args.profile)
            validate_aws_region(args.region)
        except ValidationError as e:
            formatter.print_status(str(e), 'error')
            return 1
        
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
        
        # Validate extraction mode
        if args.extract_from_cluster:
            # Validate extract-from-cluster name
            try:
                validate_cluster_name(args.extract_from_cluster)
            except ValidationError as e:
                formatter.print_status(str(e), 'error')
                return 1
            
            # Validate target cluster if provided
            if args.target_cluster:
                try:
                    validate_cluster_name(args.target_cluster)
                except ValidationError as e:
                    formatter.print_status(str(e), 'error')
                    return 1
        else:
            # Non-extraction mode: Either cluster-name OR k8s-version must be provided
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
        
        # Validate template requirements (only for non-extraction mode)
        if not args.extract_from_cluster:
            template_will_provide = (
                (args.template and os.path.exists(args.template)) or
                find_template_file() is not None
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
        template_filename = get_template_path()
        
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
                "Project": "gpu-cluster",
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
    
    # Old extract-and-recreate method removed - functionality moved to extraction mode

    def _execute_extraction_mode(self, args: argparse.Namespace, architecture: str,
                                formatter: OutputFormatter) -> int:
        """Execute extraction mode with the chosen strategy."""
        try:
            # Initialize EKS client and orchestrator
            eks_client = EKSClient(
                profile=args.profile,
                region=args.region,
                verbose=args.verbose
            )
            
            # Store region for later use (will be used when generating JSON)
            cluster_region = args.region
            
            config = {
                'aws_profile': args.profile,
                'aws_region': args.region,
                'ubuntu_version': args.ubuntu_version,
                'architecture': architecture,
                'debug': args.verbose,
            }
            orchestrator = DriverAlignmentOrchestrator(config)
            
            source_cluster = args.extract_from_cluster
            target_cluster = args.target_cluster or source_cluster
            
            # Generate timestamp suffix if none provided
            if args.new_nodegroup_suffix is None:
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
                nodegroup_suffix = f'-{timestamp}'
            else:
                nodegroup_suffix = args.new_nodegroup_suffix
            
            print_separator(f"Extraction Mode - {args.strategy.title()} Strategy", not args.quiet)
            
            print_step(1, 4, f"Validating cluster access", not args.quiet)
            
            # Validate source cluster access
            with progress(f"Validating access to cluster '{source_cluster}'", not args.quiet):
                is_valid, message = eks_client.validate_cluster_access(source_cluster)
                if not is_valid:
                    formatter.print_status(message, 'error')
                    return 1
                formatter.print_status(message, 'success')
            
            print_step(2, 4, "Extracting nodegroup configurations", not args.quiet)
            
            # Extract nodegroup configurations
            with progress("Extracting nodegroup configurations", not args.quiet):
                nodegroups = eks_client.extract_nodegroup_configurations(
                    source_cluster, args.extract_nodegroups
                )
            
            if not nodegroups:
                formatter.print_status("No GPU nodegroups found to extract", 'warning')
                return 1
            
            formatter.print_status(f"Extracted {len(nodegroups)} nodegroup configuration(s)", 'success')
            
            # Show extracted nodegroups
            self._display_extracted_nodegroups(nodegroups, formatter)
            
            print_step(3, 4, f"Applying {args.strategy} strategy to each nodegroup", not args.quiet)
            
            # Apply strategy to each extracted nodegroup
            all_alignments = []
            failed_alignments = []
            
            for i, ng in enumerate(nodegroups):
                print(f"\nProcessing nodegroup {i+1}/{len(nodegroups)}: {ng.nodegroup_name}")
                
                try:
                    if args.strategy == 'ami-first':
                        alignment = self._apply_ami_first_to_nodegroup(
                            orchestrator, ng, args, architecture, nodegroup_suffix, target_cluster, formatter
                        )
                    else:  # container-first
                        alignment = self._apply_container_first_to_nodegroup(
                            orchestrator, ng, args, architecture, nodegroup_suffix, target_cluster, formatter
                        )
                    
                    if alignment:
                        all_alignments.append((ng, alignment))
                    else:
                        failed_alignments.append(ng.nodegroup_name)
                        
                except Exception as e:
                    formatter.print_status(f"Failed to process {ng.nodegroup_name}: {e}", 'error')
                    failed_alignments.append(ng.nodegroup_name)
            
            print_step(4, 4, "Generating aligned configurations", not args.quiet)
            
            # Save all alignments to file
            if all_alignments:
                # Generate separate JSON file for each nodegroup using original name + new timestamp
                saved_files = []
                for ng, alignment in all_alignments:
                    # Use the new nodegroup name (which already includes the timestamp) as the filename
                    new_nodegroup_name = alignment.nodegroup_config['nodegroupName']
                    # Extract just the new timestamp part for the filename
                    if args.output_file:
                        output_file = args.output_file
                    else:
                        # Use the new nodegroup name directly as filename (it already has the correct timestamp)
                        output_file = get_output_path(f"{new_nodegroup_name}.json")
                    
                    json_file = self._save_nodegroup_config(ng, alignment, output_file, formatter, args.profile, cluster_region)
                    if json_file:
                        saved_files.append((json_file, ng, alignment))
                
                # Display next steps
                if saved_files:
                    self._display_extraction_next_steps(saved_files, formatter)
            
            # Summary
            formatter.print_status(f"Successfully processed {len(all_alignments)} nodegroup(s)", 'success')
            if failed_alignments:
                formatter.print_status(f"Failed to process {len(failed_alignments)} nodegroup(s): {', '.join(failed_alignments)}", 'error')
            
            return 0 if not failed_alignments else 1
            
        except Exception as e:
            formatter.print_status(f"Extraction mode failed: {e}", 'error')
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1
    
    def _apply_ami_first_to_nodegroup(self, orchestrator, ng: NodegroupInfo, 
                                     args: argparse.Namespace, architecture: str,
                                     nodegroup_suffix: str, target_cluster: str,
                                     formatter: OutputFormatter):
        """Apply ami-first strategy to a single extracted nodegroup."""
        try:
            # Get cluster info to determine K8s version if not provided
            if args.k8s_version:
                k8s_version = args.k8s_version
            else:
                # Extract K8s version from the cluster
                k8s_version = ng.version or "1.32"  # fallback
            
            # Execute ami-first alignment
            alignment = orchestrator.align_drivers_ami_first(
                k8s_version=k8s_version,
                architecture=architecture,
                cluster_name=None  # We're not using cluster auto-detection
            )
            
            if alignment:
                # Update the alignment with extracted nodegroup info
                alignment.nodegroup_config = self._merge_extracted_config(
                    ng, alignment.nodegroup_config, nodegroup_suffix, target_cluster
                )
                
            return alignment
            
        except Exception as e:
            formatter.print_status(f"Failed ami-first for {ng.nodegroup_name}: {e}", 'error')
            return None
    
    def _apply_container_first_to_nodegroup(self, orchestrator, ng: NodegroupInfo,
                                           args: argparse.Namespace, architecture: str,
                                           nodegroup_suffix: str, target_cluster: str,
                                           formatter: OutputFormatter):
        """Apply container-first strategy to a single extracted nodegroup."""
        try:
            # Get cluster info to determine K8s version if not provided
            if args.k8s_version:
                k8s_version = args.k8s_version
            else:
                # Extract K8s version from the cluster
                k8s_version = ng.version or "1.32"  # fallback
            
            # Execute container-first alignment
            alignment = orchestrator.align_drivers_container_first(
                current_driver_version=args.current_driver_version,
                architecture=architecture,
                k8s_version=k8s_version,
                cluster_name=None  # We're not using cluster auto-detection
            )
            
            if alignment:
                # Update the alignment with extracted nodegroup info
                alignment.nodegroup_config = self._merge_extracted_config(
                    ng, alignment.nodegroup_config, nodegroup_suffix, target_cluster
                )
            
            return alignment
            
        except Exception as e:
            formatter.print_status(f"Failed container-first for {ng.nodegroup_name}: {e}", 'error')
            return None
    
    def _merge_extracted_config(self, ng: NodegroupInfo, alignment_config: Dict[str, Any],
                               nodegroup_suffix: str, target_cluster: str) -> Dict[str, Any]:
        """Merge extracted nodegroup configuration with alignment results."""
        # Start with the extracted nodegroup template
        merged_config = ng.to_template_dict()
        
        # Get base nodegroup name without any existing timestamp suffix
        import re
        base_name = ng.nodegroup_name
        # Remove any existing timestamp pattern (YYYY-MM-DDTHH-MM-SS)
        base_name = re.sub(r'-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}$', '', base_name)
        
        # Update with alignment-specific settings
        merged_config['clusterName'] = target_cluster
        merged_config['nodegroupName'] = f"{base_name}{nodegroup_suffix}"
        
        # Override with alignment config (AMI type, etc.)
        if 'ami_type' in alignment_config:
            merged_config['amiType'] = alignment_config['ami_type']
        if 'architecture' in alignment_config:
            merged_config['architecture'] = alignment_config['architecture']
        
        return merged_config
    
    def _save_nodegroup_config(self, ng: NodegroupInfo, alignment: DriverAlignment, 
                              output_file: str, formatter: OutputFormatter,
                              aws_profile: str = None, aws_region: str = None) -> Optional[str]:
        """Save single nodegroup configuration to AWS CLI compatible JSON file."""
        try:
            import json
            
            # AWS CLI compatible configuration
            aws_config = alignment.nodegroup_config.copy()
            
            # Get the actual AMI release version from AWS SSM/EC2
            try:
                # Initialize EKS client to get actual release version
                eks_client = EKSClient(
                    profile=aws_profile,
                    region=aws_region,
                    verbose=False
                )
                
                actual_release_version, ami_id = eks_client.get_actual_ami_release_version(
                    alignment.k8s_version, 
                    aws_config.get("amiType")
                )
                
                formatter.print_status(f"Using actual AMI release version: {actual_release_version}", 'info')
                
            except Exception as e:
                formatter.print_status(f"Warning: Could not get actual AMI release version: {e}", 'warning')
                formatter.print_status(f"Using alignment release version: {alignment.release_tag}", 'info')
                actual_release_version = alignment.release_tag
            
            # AWS CLI compatible configuration with proper release version
            aws_cli_config = {
                "clusterName": aws_config.get("clusterName"),
                "nodegroupName": aws_config.get("nodegroupName"),
                "scalingConfig": aws_config.get("scalingConfig", {}),
                "instanceTypes": aws_config.get("instanceTypes", []),
                "amiType": aws_config.get("amiType"),
                "releaseVersion": actual_release_version,  # Actual AWS EKS release version
                "nodeRole": aws_config.get("nodeRole"),
                "subnets": aws_config.get("subnets", []),
                "capacityType": aws_config.get("capacityType", "ON_DEMAND"),
                "diskSize": aws_config.get("diskSize", 50),
                "labels": aws_config.get("labels", {}),
                "taints": aws_config.get("taints", []),
                "tags": aws_config.get("tags", {})
            }
            
            # Add optional fields if present, but filter out invalid fields
            if aws_config.get("updateConfig"):
                # Filter updateConfig to only include valid fields for nodegroup creation
                update_config = aws_config["updateConfig"].copy()
                # Remove updateStrategy as it's not valid for create-nodegroup
                update_config.pop("updateStrategy", None)
                if update_config:  # Only add if there are still valid fields
                    aws_cli_config["updateConfig"] = update_config
            if aws_config.get("launchTemplate"):
                # Filter launchTemplate to only include valid fields for nodegroup creation
                launch_template = aws_config["launchTemplate"].copy()
                # Remove read-only fields that might be present in describe responses
                launch_template.pop("name", None)  # name is read-only
                launch_template.pop("version", None)  # version might need to be specified differently
                if launch_template:
                    aws_cli_config["launchTemplate"] = launch_template
                    
            if aws_config.get("remoteAccess"):
                aws_cli_config["remoteAccess"] = aws_config["remoteAccess"]
            
            # Save single nodegroup configuration
            with open(output_file, 'w') as f:
                json.dump(aws_cli_config, f, indent=2)
            
            formatter.print_status(f"Configuration saved to: {output_file}", 'success')
            return output_file
            
        except Exception as e:
            formatter.print_status(f"Warning: Failed to save {output_file}: {e}", 'warning')
            return None
    
    def _display_extraction_next_steps(self, saved_files: List[tuple], formatter: OutputFormatter) -> None:
        """Display next steps for extraction results."""
        formatter.print_status("Generated Files:", 'info')
        for json_file, ng, alignment in saved_files:
            print(f"  📄 {json_file}")
        print()
        
        formatter.print_status("Next Steps:", 'info')
        print("1. Review and modify configurations if needed:")
        for json_file, ng, alignment in saved_files:
            config = alignment.nodegroup_config
            release_version = alignment.release_tag
            ami_type = config.get('amiType', 'N/A')
            print(f"   • {json_file}")
            print(f"     - Release: {release_version} | AMI Type: {ami_type}")
            print(f"     - Original: {ng.nodegroup_name} → New: {config['nodegroupName']}")
        print()
        
        print("2. Create nodegroups using AWS CLI:")
        for json_file, ng, alignment in saved_files:
            config = alignment.nodegroup_config
            new_name = config['nodegroupName']
            cluster_name = config['clusterName']
            
            print(f"   # Create {new_name}")
            print(f"   aws eks create-nodegroup --cli-input-json file://{json_file}")
            print()
        
        print("3. To modify driver versions or releases:")
        print("   • Edit the JSON files to change:")
        print("     - releaseVersion: Change AMI release (e.g., '1.31-20250519' → '1.31-20250403')")
        print("     - amiType: Change AMI type (AL2023_x86_64_NVIDIA, AL2_x86_64_GPU, etc.)")
        print("   • Re-run alignment with --current-driver-version for different strategy")
        print("   • Note: Invalid fields for nodegroup creation are automatically filtered out")
        print()
        
        print("4. After verifying new nodegroups work correctly:")
        print("   • Drain and delete original nodegroups manually")
        print("   • Update applications to use new nodegroups if needed")
        print()
        
        formatter.print_status("⚠ This tool generates configurations only - you must create nodegroups manually", 'warning')
    
    def _display_extracted_nodegroups(self, nodegroups: List[NodegroupInfo], 
                                     formatter: OutputFormatter) -> None:
        """Display extracted nodegroup information."""
        formatter.print_status("Extracted GPU Nodegroups:", 'info')
        
        for ng in nodegroups:
            status_icon = "⚠" if ng.ami_type == 'AL2_x86_64_GPU' else "✓"
            arch_display = ng.architecture.upper() if ng.architecture == "arm64" else "x86_64"
            
            print(f"  {status_icon} {ng.nodegroup_name}")
            print(f"    AMI Type: {ng.ami_type}")
            print(f"    Architecture: {arch_display}")
            print(f"    Instance Types: {', '.join(ng.instance_types)}")
            print(f"    Status: {ng.status}")
            
            if ng.ami_type == 'AL2_x86_64_GPU':
                print(f"    ⚠ Warning: Uses deprecated AL2 AMI (EOL: 2024-11-26)")
            print()
    
    
    def _save_aligned_configurations(self, aligned_configs: List[tuple], 
                                   output_file: str, formatter: OutputFormatter) -> None:
        """Save aligned configurations to file."""
        try:
            import json
            configurations = [config for _, config in aligned_configs]
            
            with open(output_file, 'w') as f:
                json.dump(configurations, f, indent=2)
            
            formatter.print_status(f"Aligned configurations saved to: {output_file}", 'info')
            
        except Exception as e:
            formatter.print_status(f"Warning: Failed to save configurations: {e}", 'warning')
    
    def _display_next_steps(self, validated_configs: List[tuple], 
                           output_file: str, formatter: OutputFormatter) -> None:
        """Display next steps for using the generated configurations."""
        formatter.print_status("Next Steps:", 'info')
        
        print(f"1. Review the generated configurations in: {output_file}")
        print("2. Create nodegroups using AWS CLI or Console:")
        print()
        
        for original_ng, aligned_config in validated_configs:
            new_name = aligned_config['nodegroupName']
            cluster_name = aligned_config['clusterName']
            
            print(f"   # Create {new_name}")
            print(f"   aws eks create-nodegroup \\")
            print(f"     --cluster-name {cluster_name} \\")
            print(f"     --nodegroup-name {new_name} \\")
            print(f"     --node-role {aligned_config['nodeRole']} \\")
            print(f"     --subnets {' '.join(aligned_config['subnets'])} \\")
            print(f"     --instance-types {' '.join(aligned_config['instanceTypes'])} \\")
            print(f"     --ami-type {aligned_config['amiType']} \\")
            print(f"     --capacity-type {aligned_config['capacityType']} \\")
            print(f"     --disk-size {aligned_config['diskSize']} \\")
            print(f"     --scaling-config minSize={aligned_config['scalingConfig']['minSize']},maxSize={aligned_config['scalingConfig']['maxSize']},desiredSize={aligned_config['scalingConfig']['desiredSize']}")
            
            if aligned_config.get('labels'):
                labels_str = ','.join([f"{k}={v}" for k, v in aligned_config['labels'].items()])
                print(f"     --labels {labels_str} \\")
            
            print()
        
        print("3. After verifying the new nodegroups work correctly:")
        print("   - Drain and delete the original nodegroups manually")
        print("   - Update your applications to use the new nodegroups if needed")
        print()
        print("⚠ This tool only generates configurations - you must create the nodegroups manually")