"""
Template Command for EKS NVIDIA Tools CLI

This command provides template operations using the Phase 3 utilities.
"""

import argparse
import json
import os
from typing import Dict, Any, Optional

# Import Phase 3 utilities
from utils.template_utils import TemplateGenerator, TemplateValidator, TemplateError
from models.nodegroup_config import NodeGroupConfig
from models.ami_types import Architecture

from ..shared.arguments import add_architecture_args, add_output_args, add_aws_args
from ..shared.output import OutputFormatter
from ..shared.validation import (
    validate_architecture, validate_aws_region, validate_aws_profile, ValidationError
)
from ..shared.progress import progress, print_step


class TemplateCommand:
    """Template operations using Phase 3 utilities."""
    
    def register_parser(self, subparsers) -> None:
        """Register the template subcommand parser."""
        parser = subparsers.add_parser(
            'template',
            help='Generate and validate nodegroup templates',
            description='Manage EKS nodegroup templates with generation and validation capabilities.'
        )
        
        # Operation selection
        operation_group = parser.add_argument_group('Operations')
        operation_group.add_argument(
            '--generate',
            action='store_true',
            help='Generate a new nodegroup template'
        )
        operation_group.add_argument(
            '--validate',
            help='Validate an existing template file'
        )
        
        # Generation options
        generation_group = parser.add_argument_group('Generation Options')
        generation_group.add_argument(
            '--cluster-name',
            help='EKS cluster name for template'
        )
        generation_group.add_argument(
            '--nodegroup-name',
            help='Nodegroup name for template'
        )
        add_architecture_args(generation_group)
        
        # Instance configuration
        instance_group = parser.add_argument_group('Instance Configuration')
        instance_group.add_argument(
            '--instance-types',
            nargs='+',
            help='EC2 instance types'
        )
        instance_group.add_argument(
            '--capacity-type',
            choices=['ON_DEMAND', 'SPOT'],
            default='ON_DEMAND',
            help='Capacity type (default: ON_DEMAND)'
        )
        instance_group.add_argument(
            '--disk-size',
            type=int,
            default=50,
            help='Disk size in GB (default: 50)'
        )
        
        # Scaling configuration
        scaling_group = parser.add_argument_group('Scaling Configuration')
        scaling_group.add_argument(
            '--min-size',
            type=int,
            default=0,
            help='Minimum number of nodes (default: 0)'
        )
        scaling_group.add_argument(
            '--max-size',
            type=int,
            default=10,
            help='Maximum number of nodes (default: 10)'
        )
        scaling_group.add_argument(
            '--desired-size',
            type=int,
            default=1,
            help='Desired number of nodes (default: 1)'
        )
        
        # AWS options (for consistency across commands)
        aws_group = parser.add_argument_group('AWS Options')
        add_aws_args(aws_group)
        
        # Output options
        output_group = parser.add_argument_group('Output Options')
        output_group.add_argument(
            '--output-file', '-o',
            help='Output file for generated/merged template'
        )
        add_output_args(output_group)
        
        parser.set_defaults(func=self.execute)
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute the template command."""
        try:
            # Initialize formatter
            formatter = OutputFormatter(args.output, args.quiet)
            
            # Validate AWS arguments
            try:
                validate_aws_profile(args.profile)
                validate_aws_region(args.region)
            except ValidationError as e:
                formatter.print_status(str(e), 'error')
                return 1
            
            # Validate architecture
            try:
                architecture = validate_architecture(args.architecture)
            except ValidationError as e:
                formatter.print_status(str(e), 'error')
                return 1
            
            # Determine operation
            if args.generate:
                return self._generate_template(args, architecture, formatter)
            elif args.validate:
                return self._validate_template(args, formatter)
            else:
                formatter.print_status(
                    "No operation specified. Use --generate or --validate",
                    'error'
                )
                return 1
                
        except Exception as e:
            if args.verbose:
                import traceback
                traceback.print_exc()
            else:
                print(f"Error: {e}")
            return 1
    
    def _generate_template(self, args: argparse.Namespace, architecture: str,
                          formatter: OutputFormatter) -> int:
        """Generate a new nodegroup template."""
        try:
            # Create template generator
            generator = TemplateGenerator()
            
            # Determine architecture enum
            arch_enum = Architecture.from_string(architecture)
            
            # Build nodegroup configuration
            with progress("Building nodegroup configuration", not args.quiet):
                from models.nodegroup_config import ScalingConfig
                
                scaling_config = ScalingConfig(
                    min_size=args.min_size,
                    max_size=args.max_size,
                    desired_size=args.desired_size
                )
                
                config = NodeGroupConfig(
                    cluster_name=args.cluster_name or "your-cluster-name",
                    nodegroup_name=args.nodegroup_name or f"gpu-workers-{architecture}",
                    node_role="arn:aws:iam::YOUR_ACCOUNT_ID:role/EKSNodeInstanceRole",
                    subnets=["subnet-YOUR_SUBNET_1", "subnet-YOUR_SUBNET_2"],
                    instance_types=args.instance_types or self._get_default_instances(architecture),
                    ami_type=self._get_default_ami_type(architecture),
                    capacity_type=args.capacity_type,
                    disk_size=args.disk_size,
                    scaling_config=scaling_config
                )
                
                # Set GPU defaults for the architecture
                config.set_gpu_defaults(arch_enum)
            
            # Generate basic template
            with progress("Generating template", not args.quiet):
                template = {
                    "clusterName": config.cluster_name,
                    "nodegroupName": config.nodegroup_name,
                    "nodeRole": config.node_role,
                    "subnets": config.subnets,
                    "instanceTypes": config.instance_types,
                    "amiType": config.ami_type,
                    "capacityType": config.capacity_type,
                    "diskSize": config.disk_size,
                    "scalingConfig": config.scaling_config.to_dict(),
                    "updateConfig": {"maxUnavailable": 1},
                    "labels": config.labels,
                    "taints": [],
                    "tags": config.tags
                }
            
            # Output template
            output_file = args.output_file or f"nodegroup-{architecture}.json"
            
            with progress(f"Writing template to {output_file}", not args.quiet):
                with open(output_file, 'w') as f:
                    json.dump(template, f, indent=2)
            
            formatter.print_template_results({
                'name': args.nodegroup_name or f"gpu-workers-{architecture}",
                'type': 'basic',
                'architecture': architecture,
                'nodegroup': template
            })
            
            formatter.print_status(f"Template generated: {output_file}", 'success')
            
            # Show configuration summary
            if not args.quiet:
                arch_display = architecture.upper() if architecture == "arm64" else "x86_64"
                formatter.print_status(f"Configuration for {arch_display}:", 'info')
                formatter.print_status(f"  • Instance types: {config.instance_types}", 'info')
                formatter.print_status(f"  • Capacity type: {config.capacity_type}", 'info')
                formatter.print_status(f"  • Scaling: {config.scaling_config.min_size}-{config.scaling_config.max_size} nodes", 'info')
            
            return 0
            
        except TemplateError as e:
            formatter.print_status(f"Template generation failed: {e}", 'error')
            return 1
        except Exception as e:
            formatter.print_status(f"Unexpected error: {e}", 'error')
            return 1
    
    def _validate_template(self, args: argparse.Namespace,
                          formatter: OutputFormatter) -> int:
        """Validate an existing template file."""
        try:
            # Check if file exists
            if not os.path.exists(args.validate):
                formatter.print_status(f"Template file not found: {args.validate}", 'error')
                return 1
            
            # Load template
            with progress(f"Loading template {args.validate}", not args.quiet):
                with open(args.validate, 'r') as f:
                    template = json.load(f)
            
            # Validate template
            with progress("Validating template structure", not args.quiet):
                is_valid, errors = TemplateValidator.validate_template(template)
            
            if is_valid:
                formatter.print_status("Template validation passed", 'success')
                
                # Show template summary
                if not args.quiet:
                    formatter.print_template_results({
                        'name': template.get('nodegroupName', 'Unknown'),
                        'type': 'existing',
                        'architecture': self._detect_architecture(template),
                        'nodegroup': template
                    })
                
                return 0
            else:
                formatter.print_status("Template validation failed", 'error')
                for error in errors:
                    formatter.print_status(f"  • {error}", 'error')
                return 1
                
        except json.JSONDecodeError as e:
            formatter.print_status(f"Invalid JSON in template file: {e}", 'error')
            return 1
        except Exception as e:
            formatter.print_status(f"Validation error: {e}", 'error')
            return 1
    
    
    def _get_default_instances(self, architecture: str) -> list:
        """Get default instance types for architecture."""
        if architecture == "arm64":
            return ["g5g.xlarge"]
        else:
            return ["g4dn.xlarge"]
    
    def _get_default_ami_type(self, architecture: str) -> str:
        """Get default AMI type for architecture."""
        if architecture == "arm64":
            return "AL2023_ARM_64_NVIDIA"
        else:
            return "AL2023_x86_64_NVIDIA"
    
    def _detect_architecture(self, template: Dict[str, Any]) -> str:
        """Detect architecture from template."""
        # Check AMI type
        ami_type = template.get('amiType', '')
        if 'ARM' in ami_type or 'arm64' in ami_type.lower():
            return 'arm64'
        
        # Check instance types
        instance_types = template.get('instanceTypes', [])
        if instance_types:
            # Check if any instance type is ARM64
            arm64_prefixes = ['g5g.', 'c6g.', 'm6g.', 'r6g.', 't4g.']
            for instance_type in instance_types:
                if any(instance_type.startswith(prefix) for prefix in arm64_prefixes):
                    return 'arm64'
        
        # Check labels
        labels = template.get('labels', {})
        arch_label = labels.get('kubernetes.io/arch', '')
        if arch_label == 'arm64':
            return 'arm64'
        
        # Default to x86_64
        return 'x86_64'