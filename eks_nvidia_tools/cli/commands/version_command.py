"""
Version Command for EKS NVIDIA Tools CLI

This command provides version information for the EKS NVIDIA Tools.
"""

import argparse
import sys
from typing import Dict, Any

from ..shared.output import OutputFormatter


class VersionCommand:
    """Version information command."""
    
    def register_parser(self, subparsers) -> None:
        """Register the version subcommand parser."""
        parser = subparsers.add_parser(
            'version',
            help='Show version information',
            description='Display version information for EKS NVIDIA Tools and its components.'
        )
        
        parser.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='Show detailed version information'
        )
        
        parser.add_argument(
            '--output', '-o',
            choices=['table', 'json', 'yaml'],
            default='table',
            help='Output format (default: table)'
        )
        
        parser.set_defaults(func=self.execute)
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute the version command."""
        try:
            formatter = OutputFormatter(args.output, False)  # Never quiet for version
            
            # Get version information
            version_info = self._get_version_info(args.verbose)
            
            if args.output == 'table':
                self._print_version_table(version_info, args.verbose)
            else:
                formatter.print_template_results(version_info)
            
            return 0
            
        except Exception as e:
            print(f"Error getting version information: {e}")
            return 1
    
    def _get_version_info(self, verbose: bool = False) -> Dict[str, Any]:
        """Get version information for all components."""
        try:
            # Import here to avoid circular imports
            from eks_nvidia_tools import __version__, __author__
        except ImportError:
            __version__ = "development"
            __author__ = "Jeremy J. Rossi"
        
        version_info = {
            "eks_nvidia_tools": {
                "version": __version__,
                "author": __author__
            }
        }
        
        if verbose:
            # Add Python version
            version_info["python"] = {
                "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "implementation": sys.implementation.name
            }
            
            # Add component versions
            version_info["components"] = self._get_component_versions()
        
        return version_info
    
    def _get_component_versions(self) -> Dict[str, str]:
        """Get versions of key components."""
        components = {}
        
        # Try to get versions of key dependencies
        try:
            import requests
            components["requests"] = requests.__version__
        except (ImportError, AttributeError):
            components["requests"] = "not available"
        
        try:
            import yaml
            components["pyyaml"] = yaml.__version__
        except (ImportError, AttributeError):
            components["pyyaml"] = "not available"
        
        try:
            import tabulate
            components["tabulate"] = tabulate.__version__
        except (ImportError, AttributeError):
            components["tabulate"] = "not available"
        
        # Check for AWS CLI availability
        try:
            import subprocess
            result = subprocess.run(['aws', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Parse AWS CLI version from output like "aws-cli/2.x.x Python/3.x.x"
                aws_version = result.stdout.split()[0].split('/')[1] if result.stdout else "unknown"
                components["aws_cli"] = aws_version
            else:
                components["aws_cli"] = "not available"
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            components["aws_cli"] = "not available"
        
        return components
    
    def _print_version_table(self, version_info: Dict[str, Any], verbose: bool) -> None:
        """Print version information in table format."""
        print(f"EKS NVIDIA Tools v{version_info['eks_nvidia_tools']['version']}")
        print(f"By {version_info['eks_nvidia_tools']['author']}")
        
        if verbose:
            print(f"\nPython {version_info['python']['version']} ({version_info['python']['implementation']})")
            
            print("\nComponent Versions:")
            components = version_info['components']
            for name, version in components.items():
                status = "✓" if version != "not available" else "✗"
                print(f"  {status} {name}: {version}")
            
            print("\nArchitecture Support:")
            print("  ✓ x86_64 (Intel/AMD)")
            print("  ✓ arm64 (Graviton)")
            
            print("\nSupported AMI Types:")
            print("  ✓ AL2023_x86_64_NVIDIA")
            print("  ✓ AL2023_ARM_64_NVIDIA") 
            print("  ✓ AL2_x86_64_GPU (deprecated)")
            
            print("\nSupported Strategies:")
            print("  ✓ ami-first: Use latest AMI, update containers")
            print("  ✓ container-first: Find compatible AMI for existing drivers")
            
            print("\nTemplate Features:")
            print("  ✓ Basic GPU nodegroup templates")
            print("  ✓ Multi-architecture support (x86_64, ARM64)")
            print("  ✓ Configurable instance types and scaling")
            print("  ✓ custom: Custom configurations")