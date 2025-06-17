#!/usr/bin/env python3
"""
Enhanced EKS AMI Release Parser

Fixed version that properly handles both AL2 and AL2023 AMI types
and improves driver version matching for container-first strategy.
"""

import requests
import re
import sys
import argparse
from bs4 import BeautifulSoup
from typing import Optional, Dict, List, Tuple
import json


class EKSAMIParser:
    def __init__(self, verbose: bool = False):
        self.api_url = "https://api.github.com/repos/awslabs/amazon-eks-ami/releases"
        self.session = requests.Session()
        self.verbose = verbose
        # Add headers to avoid rate limiting
        self.session.headers.update({
            'User-Agent': 'EKS-AMI-Parser/1.0',
            'Accept': 'application/vnd.github.v3+json'
        })

    def log(self, message: str):
        """Print verbose logging messages."""
        if self.verbose:
            print(f"[DEBUG] {message}")

    def get_releases(self, limit: int = 50) -> List[Dict]:
        """Fetch releases from the GitHub API."""
        try:
            params = {'per_page': limit}
            response = self.session.get(self.api_url, params=params)
            response.raise_for_status()
            releases = response.json()
            self.log(f"Fetched {len(releases)} releases")
            return releases
        except requests.exceptions.RequestException as e:
            print(f"Error fetching releases: {e}")
            sys.exit(1)

    def parse_release_body(self, body: str, release_tag: str) -> Dict:
        """Parse the release body HTML to extract package information."""
        if not body:
            self.log(f"Empty body for release {release_tag}")
            return {}
        
        self.log(f"Parsing release body for {release_tag}")
        soup = BeautifulSoup(body, 'html.parser')
        
        # Find all Kubernetes version sections
        k8s_sections = {}
        
        # Method 1: Look for <summary> tags with Kubernetes versions
        for summary in soup.find_all('summary'):
            if summary.find('b'):
                b_tag = summary.find('b')
                version_text = b_tag.get_text().strip()
                self.log(f"Found summary with text: {version_text}")
                
                # Extract version number (e.g., "1.32" from "Kubernetes 1.32")
                version_match = re.search(r'Kubernetes\s+([\d.]+)', version_text)
                if version_match:
                    k8s_version = version_match.group(1)
                    self.log(f"Found Kubernetes version: {k8s_version}")
                    
                    # Find the parent details element
                    details = summary.find_parent('details')
                    if details:
                        packages = self._parse_k8s_section(details, k8s_version)
                        if packages:
                            k8s_sections[k8s_version] = packages
        
        # Method 2: Look for headers with Kubernetes versions (fallback)
        if not k8s_sections:
            headers = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            for header in headers:
                header_text = header.get_text().strip()
                version_match = re.search(r'Kubernetes\s+([\d.]+)', header_text)
                if version_match:
                    k8s_version = version_match.group(1)
                    self.log(f"Found Kubernetes version in header: {k8s_version}")
                    
                    # Find tables after this header
                    packages = self._find_packages_after_header(header, k8s_version)
                    if packages:
                        k8s_sections[k8s_version] = packages
        
        self.log(f"Found {len(k8s_sections)} Kubernetes sections")
        return k8s_sections

    def _parse_k8s_section(self, details_element, k8s_version: str) -> Dict:
        """Parse a Kubernetes version section to extract package tables."""
        tables = details_element.find_all('table')
        self.log(f"Found {len(tables)} tables in K8s {k8s_version} section")
        
        # Initialize packages dict
        packages = {}
        
        # Look for tables with NVIDIA GPU AMI columns
        for i, table in enumerate(tables):
            headers = [th.get_text().strip() for th in table.find_all('th')]
            self.log(f"Table {i} headers: {headers}")
            
            # Check for both AL2023 and AL2 GPU AMI types
            gpu_columns = {}
            for idx, header in enumerate(headers):
                if header in ['AL2023_x86_64_NVIDIA', 'AL2_x86_64_GPU']:
                    gpu_columns[header] = idx
                    self.log(f"Found GPU column: {header} at index {idx}")
            
            if gpu_columns:
                table_packages = self._parse_package_table(table, headers, k8s_version, gpu_columns)
                packages.update(table_packages)
        
        return packages

    def _find_packages_after_header(self, header, k8s_version: str) -> Dict:
        """Find package tables after a Kubernetes version header."""
        packages = {}
        
        # Find all tables after this header
        current = header.find_next_sibling()
        while current:
            if current.name == 'table':
                headers = [th.get_text().strip() for th in current.find_all('th')]
                
                # Check for GPU columns
                gpu_columns = {}
                for idx, h in enumerate(headers):
                    if h in ['AL2023_x86_64_NVIDIA', 'AL2_x86_64_GPU']:
                        gpu_columns[h] = idx
                
                if gpu_columns:
                    self.log(f"Found GPU table after header for K8s {k8s_version}")
                    table_packages = self._parse_package_table(current, headers, k8s_version, gpu_columns)
                    packages.update(table_packages)
                    
            elif current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                # Stop if we hit another header
                break
            current = current.find_next_sibling()
        
        return packages

    def _parse_package_table(self, table, headers: List[str], k8s_version: str, gpu_columns: Dict[str, int]) -> Dict:
        """Parse a package table to extract package versions from GPU columns."""
        packages = {}
        
        # Parse each row
        rows = table.find_all('tr')[1:]  # Skip header row
        self.log(f"Processing {len(rows)} rows for GPU columns: {list(gpu_columns.keys())}")
        self.log(f"Headers: {headers}")
        
        for row_idx, row in enumerate(rows):
            cells = row.find_all(['td', 'th'])
            if len(cells) == 0:
                continue
                
            package_name = cells[0].get_text().strip()
            self.log(f"Row {row_idx}: Processing package '{package_name}' with {len(cells)} cells")
            
            # Debug: show all cell values and their colspan
            cell_info = []
            for i, cell in enumerate(cells):
                colspan = int(cell.get('colspan', 1))
                value = cell.get_text().strip()
                cell_info.append(f"[{i}]:{value}(span:{colspan})")
            self.log(f"  Cell details: {' '.join(cell_info)}")
            
            # Check each GPU column type
            for column_name, target_col_idx in gpu_columns.items():
                self.log(f"  Looking for column {column_name} at logical index {target_col_idx}")
                
                # Map logical column index to actual cell index considering colspan
                current_logical_col = 0
                cell_value = None
                
                for cell_idx, cell in enumerate(cells):
                    colspan = int(cell.get('colspan', 1))
                    self.log(f"    Cell {cell_idx}: logical_cols {current_logical_col}-{current_logical_col + colspan - 1}")
                    
                    # Check if target column falls within this cell's span
                    if current_logical_col <= target_col_idx < current_logical_col + colspan:
                        cell_value = cell.get_text().strip()
                        self.log(f"    ✅ FOUND in cell {cell_idx}: '{cell_value}'")
                        break
                    
                    current_logical_col += colspan
                
                if cell_value and cell_value not in ['—', '-', '']:
                    # Store with AMI type prefix to distinguish between AL2 and AL2023
                    key = f"{package_name}_{column_name}"
                    packages[key] = cell_value
                    self.log(f"  ✅ STORED: {key} = {cell_value}")
                    
                    # Also store without prefix for backward compatibility
                    if package_name == 'kmod-nvidia-latest-dkms':
                        packages[package_name] = cell_value
                        self.log(f"  ✅ STORED (compat): {package_name} = {cell_value}")
                else:
                    self.log(f"  ❌ NOT FOUND or empty value for column {column_name}")
        
        self.log(f"Extracted {len(packages)} packages for K8s {k8s_version}")
        return packages

    def find_kmod_nvidia_version(self, k8s_version: str, ami_type: str = "AL2023_x86_64_NVIDIA") -> Optional[Tuple[str, str, str]]:
        """Find the first kmod-nvidia-latest-dkms version for the specified Kubernetes version and AMI type."""
        releases = self.get_releases()
        
        for release in releases:
            if release.get('draft', False) or release.get('prerelease', False):
                continue
                
            release_tag = release.get('tag_name', '')
            release_date = release.get('published_at', '')
            body = release.get('body', '')
            
            self.log(f"Processing release: {release_tag}")
            
            # Parse the release body
            k8s_sections = self.parse_release_body(body, release_tag)
            
            # Look for the specified Kubernetes version
            for version, packages in k8s_sections.items():
                if version == k8s_version:
                    # Try different package key formats
                    kmod_version = None
                    
                    # Try with AMI type suffix
                    key_with_type = f"kmod-nvidia-latest-dkms_{ami_type}"
                    if key_with_type in packages:
                        kmod_version = packages[key_with_type]
                    # Try without suffix (backward compatibility)
                    elif "kmod-nvidia-latest-dkms" in packages:
                        kmod_version = packages["kmod-nvidia-latest-dkms"]
                    
                    if kmod_version:
                        return (release_tag, release_date, kmod_version)
        
        return None

    def find_latest_release_for_k8s(self, k8s_version: str, ami_type: str = "AL2023_x86_64_NVIDIA") -> Optional[Tuple[str, str, str]]:
        """Find the latest (most recent) release for the specified Kubernetes version and AMI type."""
        releases = self.get_releases()
        
        # Releases are typically ordered by date (newest first)
        for release in releases:
            if release.get('draft', False) or release.get('prerelease', False):
                continue
                
            release_tag = release.get('tag_name', '')
            release_date = release.get('published_at', '')
            body = release.get('body', '')
            
            self.log(f"Processing release: {release_tag}")
            
            # Parse the release body
            k8s_sections = self.parse_release_body(body, release_tag)
            
            # Look for the specified Kubernetes version
            for version, packages in k8s_sections.items():
                if version == k8s_version:
                    # Try different package key formats
                    kmod_version = "Not found"
                    
                    # Try with AMI type suffix
                    key_with_type = f"kmod-nvidia-latest-dkms_{ami_type}"
                    if key_with_type in packages:
                        kmod_version = packages[key_with_type]
                    # Try without suffix (backward compatibility)
                    elif "kmod-nvidia-latest-dkms" in packages:
                        kmod_version = packages["kmod-nvidia-latest-dkms"]
                    
                    return (release_tag, release_date, kmod_version)
        
        return None

    def find_releases_by_driver_version(self, driver_version: str, fuzzy: bool = False, 
                                       k8s_version: Optional[str] = None, 
                                       ami_types: List[str] = None) -> List[Tuple[str, str, str, str, str]]:
        """
        Find releases that contain the specified driver version.
        
        Args:
            driver_version: The driver version to search for (e.g., "550.127.08")
            fuzzy: Whether to use fuzzy matching
            k8s_version: Optional Kubernetes version filter
            ami_types: List of AMI types to search (default: both AL2023 and AL2)
            
        Returns:
            List of tuples: (release_tag, release_date, k8s_version, kmod_version, ami_type)
        """
        if ami_types is None:
            ami_types = ["AL2023_x86_64_NVIDIA", "AL2_x86_64_GPU"]
            
        releases = self.get_releases()
        matches = []
        
        for release in releases:
            if release.get('draft', False) or release.get('prerelease', False):
                continue
                
            release_tag = release.get('tag_name', '')
            release_date = release.get('published_at', '')
            body = release.get('body', '')
            
            self.log(f"Processing release: {release_tag}")
            
            # Parse the release body
            k8s_sections = self.parse_release_body(body, release_tag)
            
            # Check each Kubernetes version in this release
            for k8s_ver, packages in k8s_sections.items():
                # Filter by Kubernetes version if specified
                if k8s_version and k8s_ver != k8s_version:
                    continue
                
                # Check each AMI type
                for ami_type in ami_types:
                    key_with_type = f"kmod-nvidia-latest-dkms_{ami_type}"
                    kmod_version = packages.get(key_with_type)
                    
                    # Also check without suffix for backward compatibility
                    if not kmod_version:
                        kmod_version = packages.get("kmod-nvidia-latest-dkms")
                    
                    if kmod_version:
                        # Check for exact or fuzzy match
                        version_matched = False
                        if fuzzy:
                            if driver_version.lower() in kmod_version.lower():
                                version_matched = True
                        else:
                            if driver_version in kmod_version:
                                version_matched = True
                        
                        if version_matched:
                            matches.append((release_tag, release_date, k8s_ver, kmod_version, ami_type))
                            self.log(f"Found match: {release_tag} K8s {k8s_ver} {ami_type} {kmod_version}")
        
        return matches

    def list_available_k8s_versions(self) -> List[str]:
        """List all available Kubernetes versions from recent releases."""
        releases = self.get_releases(limit=20)  # Check last 20 releases
        k8s_versions = set()
        
        for release in releases:
            if release.get('draft', False) or release.get('prerelease', False):
                continue
                
            release_tag = release.get('tag_name', '')
            body = release.get('body', '')
            
            if not body:
                continue
            
            k8s_sections = self.parse_release_body(body, release_tag)
            k8s_versions.update(k8s_sections.keys())
        
        return sorted(k8s_versions, key=lambda x: [int(i) for i in x.split('.')])

    def debug_release(self, release_tag: str):
        """Debug a specific release to see its structure."""
        releases = self.get_releases()
        
        for release in releases:
            if release.get('tag_name', '') == release_tag:
                print(f"Release: {release_tag}")
                print(f"Draft: {release.get('draft', False)}")
                print(f"Prerelease: {release.get('prerelease', False)}")
                print(f"Published: {release.get('published_at', '')}")
                print("=" * 80)
                
                body = release.get('body', '')
                if body:
                    print("Body preview (first 500 chars):")
                    print(body[:500])
                    print("=" * 80)
                    
                    k8s_sections = self.parse_release_body(body, release_tag)
                    print(f"Found {len(k8s_sections)} Kubernetes sections:")
                    for k8s_version, packages in k8s_sections.items():
                        print(f"  K8s {k8s_version}: {len(packages)} packages")
                        for pkg, version in packages.items():
                            if 'nvidia' in pkg.lower():
                                print(f"    {pkg}: {version}")
                        print()
                else:
                    print("No body content found")
                return
        
        print(f"Release {release_tag} not found")


def main():
    parser = argparse.ArgumentParser(
        description='Find kmod-nvidia-latest-dkms version for EKS AMI types'
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
        choices=['AL2023_x86_64_NVIDIA', 'AL2_x86_64_GPU', 'both'],
        default='both',
        help='AMI type to search (default: both)'
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
    
    eks_parser = EKSAMIParser(verbose=args.verbose)
    
    if args.debug_release:
        eks_parser.debug_release(args.debug_release)
        return
    
    if args.list_versions:
        print("Available Kubernetes versions:")
        versions = eks_parser.list_available_k8s_versions()
        for version in versions:
            print(f"  - {version}")
        return
    
    # Determine AMI types to search
    if args.ami_type == 'both':
        ami_types = ['AL2023_x86_64_NVIDIA', 'AL2_x86_64_GPU']
    else:
        ami_types = [args.ami_type]
    
    # Search by driver version (with optional K8s version filter)
    if args.driver_version:
        filter_text = f" for Kubernetes {args.k8s_version}" if args.k8s_version else ""
        print(f"Searching for releases with kmod-nvidia-latest-dkms version: {args.driver_version}{filter_text}")
        if args.fuzzy:
            print("(Using fuzzy matching)")
        print("=" * 80)
        
        matches = eks_parser.find_releases_by_driver_version(
            args.driver_version, args.fuzzy, args.k8s_version, ami_types
        )
        
        if matches:
            print(f"Found {len(matches)} matching release(s):")
            print()
            for release_tag, release_date, k8s_version, kmod_version, ami_type in matches:
                print(f"Release: {release_tag}")
                print(f"Date: {release_date}")
                print(f"Kubernetes version: {k8s_version}")
                print(f"AMI type: {ami_type}")
                print(f"kmod-nvidia-latest-dkms: {kmod_version}")
                print("-" * 40)
        else:
            filter_text = f" for Kubernetes {args.k8s_version}" if args.k8s_version else ""
            print(f"No releases found with driver version: {args.driver_version}{filter_text}")
        return
    
    # Search by Kubernetes version
    if not args.k8s_version:
        print("Error: Please specify either --k8s-version or --driver-version")
        print("Use --list-versions to see available Kubernetes versions")
        print("Use --debug-release <tag> to debug a specific release")
        parser.print_help()
        return
    
    # Try both AMI types for K8s version search
    for ami_type in ami_types:
        print(f"\n--- Searching {ami_type} ---")
        
        if args.latest:
            print(f"Finding latest release for Kubernetes {args.k8s_version}")
            print("=" * 80)
            
            result = eks_parser.find_latest_release_for_k8s(args.k8s_version, ami_type)
            
            if result:
                release_tag, release_date, kmod_version = result
                print(f"Latest release: {release_tag}")
                print(f"Release date: {release_date}")
                print(f"AMI type: {ami_type}")
                print(f"kmod-nvidia-latest-dkms version: {kmod_version}")
            else:
                print(f"No releases found for Kubernetes {args.k8s_version} with {ami_type}")
        else:
            print(f"Searching for first kmod-nvidia-latest-dkms version for Kubernetes {args.k8s_version}")
            print("=" * 80)
            
            result = eks_parser.find_kmod_nvidia_version(args.k8s_version, ami_type)
            
            if result:
                release_tag, release_date, kmod_version = result
                print(f"Found in release: {release_tag}")
                print(f"Release date: {release_date}")
                print(f"AMI type: {ami_type}")
                print(f"kmod-nvidia-latest-dkms version: {kmod_version}")
            else:
                print(f"No kmod-nvidia-latest-dkms version found for Kubernetes {args.k8s_version} with {ami_type}")


if __name__ == "__main__":
    main()
