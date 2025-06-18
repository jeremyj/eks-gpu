"""
Parse Command for EKS NVIDIA Tools CLI

This command provides AMI parsing functionality using the refactored core modules.
"""

import argparse
from typing import Optional, List, Tuple, Any

# Import the new modular components
from core.ami_resolver import EKSAMIResolver, AMIResolutionError
from models.ami_types import AMIType, Architecture, AMITypeManager

from ..shared.arguments import (
    add_architecture_args, add_kubernetes_args, add_driver_args, add_output_args
)
from ..shared.output import OutputFormatter
from ..shared.validation import (
    validate_k8s_version, validate_architecture, validate_driver_version, ValidationError
)
from ..shared.progress import progress, print_step


class ParseCommand:
    """AMI parsing subcommands using the refactored core modules."""
    
    def register_parser(self, subparsers) -> None:
        """Register the parse subcommand parser."""
        parser = subparsers.add_parser(
            'parse',
            help='Parse EKS AMI releases and find NVIDIA driver versions',
            description='Parse EKS AMI releases to find NVIDIA driver versions for specific Kubernetes versions and architectures.'
        )
        
        # Add argument groups
        search_group = parser.add_argument_group('Search Options')
        add_kubernetes_args(search_group)
        add_driver_args(search_group)
        
        search_group.add_argument(
            '--fuzzy', '-f',
            action='store_true',
            help='Use fuzzy matching for driver version search'
        )
        search_group.add_argument(
            '--latest',
            action='store_true',
            help='Find the latest release for the specified K8s version'
        )
        search_group.add_argument(
            '--list-versions', '-l',
            action='store_true',
            help='List available Kubernetes versions'
        )
        
        # AMI and architecture options
        ami_group = parser.add_argument_group('AMI Options')
        ami_group.add_argument(
            '--ami-type',
            choices=['AL2023_x86_64_NVIDIA', 'AL2_x86_64_GPU', 'AL2023_ARM_64_NVIDIA', 'both'],
            default='both',
            help='AMI type to search (default: both for architecture)'
        )
        add_architecture_args(ami_group)
        
        # Output options
        output_group = parser.add_argument_group('Output Options')
        add_output_args(output_group)
        
        # Debug options
        debug_group = parser.add_argument_group('Debug Options')
        debug_group.add_argument(
            '--debug-release',
            help='Debug a specific release (e.g., v20241121)'
        )
        
        parser.set_defaults(func=self.execute)
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute the parse command."""
        try:
            # Initialize components
            resolver = EKSAMIResolver(verbose=args.verbose)
            ami_manager = AMITypeManager()
            formatter = OutputFormatter(args.output, args.quiet)
            
            # Handle debug command
            if args.debug_release:
                return self._debug_release(resolver, args.debug_release, formatter)
            
            # Handle list versions command
            if args.list_versions:
                return self._list_versions(resolver, formatter)
            
            # Validate and normalize architecture
            try:
                architecture = validate_architecture(args.architecture)
            except ValidationError as e:
                formatter.print_status(str(e), 'error')
                return 1
            
            # Determine AMI types to search
            ami_type_strings = self._get_ami_types(
                args.ami_type, architecture, ami_manager, formatter
            )
            if not ami_type_strings:
                return 1
            
            # Handle driver version search
            if args.driver_version:
                return self._search_by_driver_version(
                    resolver, args, ami_type_strings, architecture, formatter
                )
            
            # Handle Kubernetes version search
            if args.k8s_version:
                return self._search_by_k8s_version(
                    resolver, args, ami_type_strings, formatter
                )
            
            # No search criteria provided
            formatter.print_status(
                "Please specify either --k8s-version or --driver-version", 'error'
            )
            formatter.print_status(
                "Use --list-versions to see available Kubernetes versions", 'info'
            )
            return 1
            
        except Exception as e:
            if args.verbose:
                import traceback
                traceback.print_exc()
            else:
                print(f"Error: {e}")
            return 1
    
    def _debug_release(self, resolver: EKSAMIResolver, release_tag: str, 
                      formatter: OutputFormatter) -> int:
        """Debug a specific release."""
        try:
            with progress(f"Debugging release {release_tag}", not formatter.quiet):
                debug_info = resolver.debug_release(release_tag)
            
            print(f"Release: {release_tag}")
            release_info = debug_info['release_info']
            print(f"Draft: {release_info['draft']}")
            print(f"Prerelease: {release_info['prerelease']}")
            print(f"Published: {release_info['published_at']}")
            print("=" * 80)
            
            body = release_info['body']
            if body:
                print("Body preview (first 500 chars):")
                print(body[:500])
                print("=" * 80)
                
                k8s_sections = debug_info['k8s_sections']
                print(f"Found {len(k8s_sections)} Kubernetes sections:")
                
                for k8s_version, section_data in k8s_sections.items():
                    packages = {k: v for k, v in section_data.items() if k != 'driver_versions'}
                    print(f"  K8s {k8s_version}: {len(packages)} packages")
                    
                    # Show NVIDIA packages
                    for pkg, version in packages.items():
                        if 'nvidia' in pkg.lower():
                            print(f"    {pkg}: {version}")
                    
                    # Show driver versions summary
                    if 'driver_versions' in section_data:
                        driver_versions = section_data['driver_versions']
                        if driver_versions:
                            print(f"    Driver versions: {driver_versions}")
                    print()
                
                # Show any parsing errors
                if debug_info['parsing_errors']:
                    print("Parsing errors:")
                    for error in debug_info['parsing_errors']:
                        print(f"  - {error}")
            else:
                print("No body content found")
            
            return 0
            
        except AMIResolutionError as e:
            formatter.print_status(f"Error debugging release {release_tag}: {e}", 'error')
            return 1
    
    def _list_versions(self, resolver: EKSAMIResolver, formatter: OutputFormatter) -> int:
        """List available Kubernetes versions."""
        try:
            with progress("Fetching available Kubernetes versions", not formatter.quiet):
                versions = resolver.list_available_k8s_versions()
            
            if not versions:
                formatter.print_status("No Kubernetes versions found", 'warning')
                return 1
            
            formatter.print_status("Available Kubernetes versions:", 'info')
            for version in versions:
                print(f"  - {version}")
            
            return 0
            
        except AMIResolutionError as e:
            formatter.print_status(f"Error listing versions: {e}", 'error')
            return 1
    
    def _get_ami_types(self, ami_type_arg: str, architecture: str, 
                      ami_manager: AMITypeManager, formatter: OutputFormatter) -> Optional[List[str]]:
        """Get AMI types to search based on arguments."""
        try:
            arch = Architecture.from_string(architecture)
            
            if ami_type_arg == 'both':
                ami_types = ami_manager.get_ami_types_for_architecture(arch)
                return [ami_type.value for ami_type in ami_types]
            else:
                # Validate AMI type matches architecture
                compatible_types = ami_manager.get_ami_types_for_architecture(arch)
                compatible_strings = [ami_type.value for ami_type in compatible_types]
                
                if ami_type_arg not in compatible_strings:
                    formatter.print_status(
                        f"AMI type {ami_type_arg} may not be compatible with architecture {architecture}",
                        'warning'
                    )
                    formatter.print_status(
                        f"Compatible AMI types for {architecture}: {', '.join(compatible_strings)}",
                        'info'
                    )
                
                return [ami_type_arg]
                
        except ValueError as e:
            formatter.print_status(str(e), 'error')
            return None
    
    def _search_by_driver_version(self, resolver: EKSAMIResolver, args: argparse.Namespace,
                                 ami_type_strings: List[str], architecture: str,
                                 formatter: OutputFormatter) -> int:
        """Search for releases by driver version."""
        try:
            # Validate driver version if provided
            if args.driver_version:
                validate_driver_version(args.driver_version)
        except ValidationError as e:
            formatter.print_status(str(e), 'error')
            return 1
        
        # Validate K8s version if provided as filter
        k8s_version = None
        if args.k8s_version:
            try:
                k8s_version = validate_k8s_version(args.k8s_version)
            except ValidationError as e:
                formatter.print_status(str(e), 'error')
                return 1
        
        filter_text = f" for Kubernetes {k8s_version}" if k8s_version else ""
        arch_text = f" ({architecture})" if architecture != "x86_64" else ""
        
        formatter.print_status(
            f"Searching for releases with driver version: {args.driver_version}{filter_text}{arch_text}",
            'info'
        )
        if args.fuzzy:
            formatter.print_status("Using fuzzy matching", 'info')
        
        try:
            with progress("Searching releases", not formatter.quiet):
                matches = resolver.find_releases_by_driver_version(
                    args.driver_version, args.fuzzy, k8s_version, 
                    [AMIType(ami_type) for ami_type in ami_type_strings],
                    Architecture.from_string(architecture)
                )
            
            if matches:
                formatter.print_status(f"Found {len(matches)} matching release(s):", 'success')
                
                # Convert matches to the expected format for output
                results = []
                for release_tag, release_date, k8s_ver, kmod_version, ami_type in matches:
                    results.append((release_tag, kmod_version, release_date))
                
                formatter.print_ami_results(results)
            else:
                formatter.print_status(
                    f"No releases found with driver version: {args.driver_version}{filter_text}{arch_text}",
                    'warning'
                )
                
                if architecture == "arm64":
                    formatter.print_status(
                        "ARM64 AMIs may have different driver availability than x86_64",
                        'info'
                    )
                    formatter.print_status(
                        "Try searching x86_64: --architecture x86_64",
                        'info'
                    )
            
            return 0
            
        except AMIResolutionError as e:
            formatter.print_status(f"Search failed: {e}", 'error')
            return 1
    
    def _search_by_k8s_version(self, resolver: EKSAMIResolver, args: argparse.Namespace,
                              ami_type_strings: List[str], formatter: OutputFormatter) -> int:
        """Search for releases by Kubernetes version."""
        try:
            k8s_version = validate_k8s_version(args.k8s_version)
        except ValidationError as e:
            formatter.print_status(str(e), 'error')
            return 1
        
        results = []
        
        # Search each AMI type
        for i, ami_type_str in enumerate(ami_type_strings):
            print_step(i + 1, len(ami_type_strings), 
                      f"Searching {ami_type_str}", not formatter.quiet)
            
            try:
                ami_type = AMIType(ami_type_str)
                arch_name = ami_type.architecture.display_name
                
                with progress(f"Searching {ami_type_str}", not formatter.quiet) as p:
                    if args.latest:
                        p.update(f"Finding latest release for K8s {k8s_version}")
                        result = resolver.find_latest_release_for_k8s(k8s_version, ami_type)
                    else:
                        p.update(f"Finding first driver version for K8s {k8s_version}")
                        result = resolver.find_kmod_nvidia_version(k8s_version, ami_type)
                
                if result:
                    release_tag, release_date, kmod_version = result
                    results.append((release_tag, kmod_version, release_date))
                    
                    if not formatter.quiet:
                        print(f"  ✓ {ami_type_str} ({arch_name}): {kmod_version}")
                else:
                    if not formatter.quiet:
                        search_type = "latest release" if args.latest else "driver version"
                        print(f"  ✗ {ami_type_str} ({arch_name}): No {search_type} found")
                        
            except ValueError as e:
                formatter.print_status(f"Error with AMI type {ami_type_str}: {e}", 'error')
                continue
        
        if results:
            formatter.print_ami_results(results)
            return 0
        else:
            search_type = "latest releases" if args.latest else "driver versions"
            formatter.print_status(
                f"No {search_type} found for Kubernetes {k8s_version}",
                'warning'
            )
            return 1