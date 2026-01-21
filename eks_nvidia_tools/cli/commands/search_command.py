"""
Search Command for EKS NVIDIA Tools CLI

This command searches the NVIDIA CUDA repository for driver packages.
"""

import argparse
import json
import re
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import yaml
from tabulate import tabulate

from ..shared.output import OutputFormatter
from ..shared.validation import (
    validate_driver_version, validate_architecture, validate_os_version,
    ValidationError
)
from ..shared.progress import progress


@dataclass
class PackageInfo:
    """Information about a found package."""
    name: str
    version: str
    arch: str
    url: str


class SearchCommand:
    """NVIDIA CUDA repository search subcommand."""

    # Package types to search for
    PACKAGE_TYPES = {
        'compute': 'libnvidia-compute',
        'encode': 'libnvidia-encode',
        'decode': 'libnvidia-decode',
    }

    # Architecture mappings
    ARCH_MAPPINGS = {
        'x86_64': {'path': 'x86_64', 'suffix': 'amd64'},
        'arm64': {'path': 'sbsa', 'suffix': 'arm64'},
    }

    NVIDIA_REPO_BASE = 'https://developer.download.nvidia.com/compute/cuda/repos'

    def register_parser(self, subparsers) -> None:
        """Register the search subcommand parser."""
        parser = subparsers.add_parser(
            'search',
            help='Search NVIDIA CUDA repository for driver packages',
            description='Search the NVIDIA CUDA repository for driver packages (libnvidia-compute, libnvidia-encode, libnvidia-decode).',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Search for all packages with driver major version
  eks-nvidia-tools search --driver-version 570

  # Search for specific driver version
  eks-nvidia-tools search --driver-version 570.124.06

  # Search specific package type
  eks-nvidia-tools search --driver-version 570 --package-type compute
  eks-nvidia-tools search --driver-version 570 --package-type encode

  # ARM64 architecture
  eks-nvidia-tools search --driver-version 570 --architecture arm64

  # Different OS versions
  eks-nvidia-tools search --driver-version 570 --os-version ubuntu2404
  eks-nvidia-tools search --driver-version 570 --os-version debian12

  # JSON output
  eks-nvidia-tools search --driver-version 570 --output json
"""
        )

        # Required arguments
        required_group = parser.add_argument_group('Required Options')
        required_group.add_argument(
            '--driver-version', '-d',
            required=True,
            help='NVIDIA driver version (e.g., 570, 560.35, 570.124.06)'
        )

        # Optional arguments
        optional_group = parser.add_argument_group('Optional Options')
        optional_group.add_argument(
            '--package-type', '-p',
            choices=['compute', 'encode', 'decode', 'all'],
            default='all',
            help='Package type to search for (default: all)'
        )
        optional_group.add_argument(
            '--architecture', '--arch',
            default='x86_64',
            help='Architecture: x86_64 or arm64 (default: x86_64)'
        )
        optional_group.add_argument(
            '--os-version', '-o',
            default='ubuntu2204',
            help='OS version string (default: ubuntu2204). Format: {distro}{version} e.g., ubuntu2204, debian12, rhel9'
        )

        # Output options
        output_group = parser.add_argument_group('Output Options')
        output_group.add_argument(
            '--output',
            choices=['table', 'json', 'yaml'],
            default='table',
            help='Output format (default: table)'
        )
        output_group.add_argument(
            '--quiet', '-q',
            action='store_true',
            help='Suppress progress output'
        )

        parser.set_defaults(func=self.execute)

    def execute(self, args: argparse.Namespace) -> int:
        """Execute the search command."""
        try:
            # Validate inputs
            try:
                driver_version = validate_driver_version(args.driver_version)
                architecture = validate_architecture(args.architecture)
                os_version = validate_os_version(args.os_version)
            except ValidationError as e:
                print(f"✗ {e}")
                return 1

            formatter = OutputFormatter(args.output, args.quiet)

            # Determine which packages to search for
            if args.package_type == 'all':
                package_types = list(self.PACKAGE_TYPES.keys())
            else:
                package_types = [args.package_type]

            # Get architecture mapping
            arch_map = self.ARCH_MAPPINGS[architecture]

            # Build repository URL
            repo_url = f"{self.NVIDIA_REPO_BASE}/{os_version}/{arch_map['path']}/"

            if not args.quiet:
                formatter.print_status(
                    f"Searching NVIDIA repository for driver {driver_version}", 'info'
                )
                formatter.print_status(f"Repository: {repo_url}", 'info')

            # Fetch repository listing
            try:
                with progress("Fetching repository listing", not args.quiet):
                    html_content = self._fetch_repo_listing(repo_url)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    formatter.print_status(
                        f"OS version '{os_version}' not found in NVIDIA repository", 'error'
                    )
                    formatter.print_status(
                        "Available OS versions can be found at: https://developer.download.nvidia.com/compute/cuda/repos/",
                        'info'
                    )
                else:
                    formatter.print_status(
                        f"HTTP error fetching repository: {e.code} {e.reason}", 'error'
                    )
                return 1
            except urllib.error.URLError as e:
                formatter.print_status(f"Network error: {e.reason}", 'error')
                return 1

            # Search for packages
            packages = []
            for pkg_type in package_types:
                pkg_name = self.PACKAGE_TYPES[pkg_type]
                found = self._search_packages(
                    html_content, pkg_name, driver_version,
                    arch_map['suffix'], repo_url
                )
                packages.extend(found)

            if not packages:
                formatter.print_status(
                    f"No packages found for driver version {driver_version}", 'warning'
                )
                return 0

            # Output results
            self._output_results(packages, args.output, formatter)

            return 0

        except Exception as e:
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
            else:
                print(f"✗ Error: {e}")
            return 1

    def _fetch_repo_listing(self, url: str) -> str:
        """Fetch the HTML listing from the NVIDIA repository."""
        request = urllib.request.Request(
            url,
            headers={'User-Agent': 'eks-nvidia-tools/1.0'}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode('utf-8')

    def _search_packages(
        self,
        html_content: str,
        pkg_name: str,
        driver_version: str,
        arch_suffix: str,
        repo_url: str
    ) -> List[PackageInfo]:
        """Search HTML content for matching packages."""
        packages = []
        seen = set()

        # If driver_version is just major version (e.g., 570),
        # search for any packages with that major version
        if '.' not in driver_version:
            # Pattern for major-only search: pkg-MAJOR_X.Y.Z-suffix_arch.deb
            # Version format: X.Y.Z-Nubuntu... (stops before underscore)
            pattern = rf'{re.escape(pkg_name)}-{re.escape(driver_version)}_(\d+\.\d+\.\d+-[0-9a-z.]+)_{re.escape(arch_suffix)}\.deb'
            matches = re.findall(pattern, html_content)

            for version in matches:
                key = (pkg_name, driver_version, version)
                if key not in seen:
                    seen.add(key)
                    filename = f"{pkg_name}-{driver_version}_{version}_{arch_suffix}.deb"
                    packages.append(PackageInfo(
                        name=f"{pkg_name}-{driver_version}",
                        version=version,
                        arch=arch_suffix,
                        url=f"{repo_url}{filename}"
                    ))
        else:
            # Exact version search: pkg-MAJOR_VERSION-suffix_arch.deb
            driver_major = driver_version.split('.')[0]
            pattern = rf'{re.escape(pkg_name)}-{re.escape(driver_major)}_({re.escape(driver_version)}-[0-9a-z.]+)_{re.escape(arch_suffix)}\.deb'
            matches = re.findall(pattern, html_content)

            for version in matches:
                key = (pkg_name, driver_major, version)
                if key not in seen:
                    seen.add(key)
                    filename = f"{pkg_name}-{driver_major}_{version}_{arch_suffix}.deb"
                    packages.append(PackageInfo(
                        name=f"{pkg_name}-{driver_major}",
                        version=version,
                        arch=arch_suffix,
                        url=f"{repo_url}{filename}"
                    ))

        return packages

    def _output_results(
        self,
        packages: List[PackageInfo],
        output_format: str,
        formatter: OutputFormatter
    ) -> None:
        """Output results in the requested format."""
        if output_format == 'json':
            data = [
                {
                    'package': p.name,
                    'version': p.version,
                    'arch': p.arch,
                    'url': p.url
                }
                for p in packages
            ]
            print(json.dumps(data, indent=2))

        elif output_format == 'yaml':
            data = [
                {
                    'package': p.name,
                    'version': p.version,
                    'arch': p.arch,
                    'url': p.url
                }
                for p in packages
            ]
            print(yaml.dump(data, default_flow_style=False, sort_keys=False))

        else:  # table
            rows = [
                [p.name, p.version, p.arch, p.url]
                for p in packages
            ]
            headers = ['Package', 'Version', 'Arch', 'URL']
            print(tabulate(rows, headers=headers, tablefmt='grid'))
