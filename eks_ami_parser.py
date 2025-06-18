#!/usr/bin/env python3
"""
Enhanced EKS AMI Release Parser - Refactored Version

This is the refactored version using the new modular architecture.
The original eks_ami_parser.py functionality is preserved while using
the new core modules for better maintainability.
"""

import argparse
import sys
from typing import Optional

# Import the new modular components
from core.ami_resolver import EKSAMIResolver, AMIResolutionError
from models.ami_types import AMIType, Architecture, AMITypeManager


class EKSAMIParserCLI:
    """Command-line interface for the EKS AMI parser using the new modular architecture."""
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the CLI with the new resolver.
        
        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        self.resolver = EKSAMIResolver(verbose=verbose)
        self.ami_manager = AMITypeManager()
    
    def find_kmod_nvidia_version(self, k8s_version: str, ami_type_str: str = "AL2023_x86_64_NVIDIA") -> Optional[tuple]:
        """Find the first kmod-nvidia-latest-dkms version for the specified Kubernetes version and AMI type."""
        try:
            ami_type = AMIType(ami_type_str)
            return self.resolver.find_kmod_nvidia_version(k8s_version, ami_type)
        except (ValueError, AMIResolutionError) as e:
            if self.verbose:
                print(f"Error: {e}")
            return None
    
    def find_latest_release_for_k8s(self, k8s_version: str, ami_type_str: str = "AL2023_x86_64_NVIDIA") -> Optional[tuple]:
        """Find the latest (most recent) release for the specified Kubernetes version and AMI type."""
        try:
            ami_type = AMIType(ami_type_str)
            return self.resolver.find_latest_release_for_k8s(k8s_version, ami_type)
        except (ValueError, AMIResolutionError) as e:
            if self.verbose:
                print(f"Error: {e}")
            return None
    
    def find_releases_by_driver_version(self, driver_version: str, fuzzy: bool = False, 
                                       k8s_version: Optional[str] = None, 
                                       ami_types: list = None,
                                       architecture: str = "x86_64") -> list:
        """Find releases that contain the specified driver version."""
        try:
            arch = Architecture.from_string(architecture)
            
            # Convert AMI type strings to AMIType objects
            ami_type_objects = None
            if ami_types:
                ami_type_objects = [AMIType(ami_type) for ami_type in ami_types]
            
            return self.resolver.find_releases_by_driver_version(
                driver_version, fuzzy, k8s_version, ami_type_objects, arch
            )
        except (ValueError, AMIResolutionError) as e:
            if self.verbose:
                print(f"Error: {e}")
            return []
    
    def list_available_k8s_versions(self) -> list:
        """List all available Kubernetes versions from recent releases."""
        try:
            return self.resolver.list_available_k8s_versions()
        except AMIResolutionError as e:
            if self.verbose:
                print(f"Error: {e}")
            return []
    
    def debug_release(self, release_tag: str):
        """Debug a specific release to see its structure."""
        try:
            debug_info = self.resolver.debug_release(release_tag)
            
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
                
        except AMIResolutionError as e:
            print(f"Error debugging release {release_tag}: {e}")


def main():
    """Main function preserving the original CLI interface."""
    parser = argparse.ArgumentParser(
        description='Find kmod-nvidia-latest-dkms version for EKS AMI types across architectures (Refactored)'
    )
    parser.add_argument(
        '--k8s-version', '-k',
        help='Kubernetes version (e.g., 1.32, 1.31)'
    )
    parser.add_argument(
        '--driver-version', '-d',
        help='Driver version to search for (e.g., 550.127.08)'
    )
    parser.add_argument(
        '--fuzzy', '-f',
        action='store_true',
        help='Use fuzzy matching for driver version search'
    )
    parser.add_argument(
        '--latest',
        action='store_true',
        help='Find the latest release for the specified K8s version'
    )
    parser.add_argument(
        '--list-versions', '-l',
        action='store_true',
        help='List available Kubernetes versions'
    )
    parser.add_argument(
        '--ami-type',
        choices=['AL2023_x86_64_NVIDIA', 'AL2_x86_64_GPU', 'AL2023_ARM_64_NVIDIA', 'both'],
        default='both',
        help='AMI type to search (default: both for x86_64)'
    )
    parser.add_argument(
        '--architecture', '--arch',
        choices=['x86_64', 'amd64', 'arm64'],
        default='x86_64',
        help='Target architecture (default: x86_64)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--debug-release',
        help='Debug a specific release (e.g., v20241121)'
    )
    
    args = parser.parse_args()
    
    # Initialize the CLI with the new architecture
    cli = EKSAMIParserCLI(verbose=args.verbose)
    ami_manager = AMITypeManager()
    
    if args.debug_release:
        cli.debug_release(args.debug_release)
        return
    
    if args.list_versions:
        print("Available Kubernetes versions:")
        versions = cli.list_available_k8s_versions()
        for version in versions:
            print(f"  - {version}")
        return
    
    # Normalize architecture
    architecture = args.architecture
    if architecture == "amd64":
        architecture = "x86_64"
    
    # Determine AMI types to search based on architecture
    if args.ami_type == 'both':
        ami_types = ami_manager.get_ami_types_for_architecture(Architecture.from_string(architecture))
        ami_type_strings = [ami_type.value for ami_type in ami_types]
    else:
        ami_type_strings = [args.ami_type]
        
        # Validate AMI type matches architecture
        try:
            arch = Architecture.from_string(architecture)
            compatible_types = ami_manager.get_ami_types_for_architecture(arch)
            compatible_strings = [ami_type.value for ami_type in compatible_types]
            
            if args.ami_type not in compatible_strings:
                print(f"⚠️  Warning: AMI type {args.ami_type} may not be compatible with architecture {architecture}")
                print(f"   Compatible AMI types for {architecture}: {', '.join(compatible_strings)}")
        except ValueError as e:
            print(f"Error: {e}")
            return
    
    # Search by driver version (with optional K8s version filter)
    if args.driver_version:
        filter_text = f" for Kubernetes {args.k8s_version}" if args.k8s_version else ""
        arch_text = f" ({architecture})" if architecture != "x86_64" else ""
        print(f"Searching for releases with kmod-nvidia-latest-dkms version: {args.driver_version}{filter_text}{arch_text}")
        if args.fuzzy:
            print("(Using fuzzy matching)")
        print("=" * 80)
        
        matches = cli.find_releases_by_driver_version(
            args.driver_version, args.fuzzy, args.k8s_version, ami_type_strings, architecture
        )
        
        if matches:
            print(f"Found {len(matches)} matching release(s):")
            print()
            for release_tag, release_date, k8s_version, kmod_version, ami_type in matches:
                print(f"Release: {release_tag}")
                print(f"Date: {release_date}")
                print(f"Kubernetes version: {k8s_version}")
                print(f"AMI type: {ami_type}")
                print(f"Architecture: {'ARM64' if 'ARM' in ami_type else 'x86_64'}")
                print(f"kmod-nvidia-latest-dkms: {kmod_version}")
                print("-" * 40)
        else:
            filter_text = f" for Kubernetes {args.k8s_version}" if args.k8s_version else ""
            arch_text = f" on {architecture}" if architecture != "x86_64" else ""
            print(f"No releases found with driver version: {args.driver_version}{filter_text}{arch_text}")
            
            if architecture == "arm64":
                print(f"\n💡 ARM64 AMIs may have different driver availability than x86_64")
                print(f"   Try searching x86_64 to see if the driver exists: --architecture x86_64")
        return
    
    # Search by Kubernetes version
    if not args.k8s_version:
        print("Error: Please specify either --k8s-version or --driver-version")
        print("Use --list-versions to see available Kubernetes versions")
        print("Use --debug-release <tag> to debug a specific release")
        parser.print_help()
        return
    
    # Try all specified AMI types for K8s version search
    for ami_type_str in ami_type_strings:
        try:
            ami_type = AMIType(ami_type_str)
            arch_name = ami_type.architecture.display_name
            print(f"\n--- Searching {ami_type_str} ({arch_name}) ---")
            
            if args.latest:
                print(f"Finding latest release for Kubernetes {args.k8s_version}")
                print("=" * 80)
                
                result = cli.find_latest_release_for_k8s(args.k8s_version, ami_type_str)
                
                if result:
                    release_tag, release_date, kmod_version = result
                    print(f"Latest release: {release_tag}")
                    print(f"Release date: {release_date}")
                    print(f"AMI type: {ami_type_str}")
                    print(f"Architecture: {arch_name}")
                    print(f"kmod-nvidia-latest-dkms version: {kmod_version}")
                else:
                    print(f"No releases found for Kubernetes {args.k8s_version} with {ami_type_str}")
            else:
                print(f"Searching for first kmod-nvidia-latest-dkms version for Kubernetes {args.k8s_version}")
                print("=" * 80)
                
                result = cli.find_kmod_nvidia_version(args.k8s_version, ami_type_str)
                
                if result:
                    release_tag, release_date, kmod_version = result
                    print(f"Found in release: {release_tag}")
                    print(f"Release date: {release_date}")
                    print(f"AMI type: {ami_type_str}")
                    print(f"Architecture: {arch_name}")
                    print(f"kmod-nvidia-latest-dkms version: {kmod_version}")
                else:
                    print(f"No kmod-nvidia-latest-dkms version found for Kubernetes {args.k8s_version} with {ami_type_str}")
        
        except ValueError as e:
            print(f"Error with AMI type {ami_type_str}: {e}")


if __name__ == "__main__":
    main()