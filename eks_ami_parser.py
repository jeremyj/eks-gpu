#!/usr/bin/env python3
"""
EKS AMI Release Parser

This script parses the Amazon EKS AMI releases from GitHub API to find
the kmod-nvidia-latest-dkms version for AL2023_x86_64_NVIDIA AMI type
based on a specified Kubernetes version.
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
        
        # Look for the AL2023 package table
        for i, table in enumerate(tables):
            headers = [th.get_text().strip() for th in table.find_all('th')]
            self.log(f"Table {i} headers: {headers}")
            
            # Check if this is the AL2023 package table
            if 'AL2023_x86_64_NVIDIA' in headers:
                self.log(f"Found AL2023 package table in K8s {k8s_version}")
                return self._parse_package_table(table, headers, k8s_version)
        
        return {}

    def _find_packages_after_header(self, header, k8s_version: str) -> Dict:
        """Find package tables after a Kubernetes version header."""
        # Find all tables after this header
        current = header.find_next_sibling()
        while current:
            if current.name == 'table':
                headers = [th.get_text().strip() for th in current.find_all('th')]
                if 'AL2023_x86_64_NVIDIA' in headers:
                    self.log(f"Found AL2023 package table after header for K8s {k8s_version}")
                    return self._parse_package_table(current, headers, k8s_version)
            elif current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                # Stop if we hit another header
                break
            current = current.find_next_sibling()
        
        return {}

    def _parse_package_table(self, table, headers: List[str], k8s_version: str) -> Dict:
        """Parse a package table to extract package versions."""
        packages = {}
        
        # Find the column index for AL2023_x86_64_NVIDIA
        nvidia_col_idx = None
        for i, header in enumerate(headers):
            if header == 'AL2023_x86_64_NVIDIA':
                nvidia_col_idx = i
                break
        
        if nvidia_col_idx is None:
            self.log(f"Could not find AL2023_x86_64_NVIDIA column in K8s {k8s_version}")
            return packages
        
        self.log(f"AL2023_x86_64_NVIDIA column index: {nvidia_col_idx}")
        
        # Parse each row
        rows = table.find_all('tr')[1:]  # Skip header row
        self.log(f"Processing {len(rows)} rows")
        
        for row_idx, row in enumerate(rows):
            cells = row.find_all(['td', 'th'])
            if len(cells) == 0:
                continue
                
            package_name = cells[0].get_text().strip()
            
            # Handle colspan attributes
            nvidia_cell = None
            current_col = 0
            
            for cell in cells[1:]:  # Skip first column (package name)
                colspan = int(cell.get('colspan', 1))
                if current_col <= nvidia_col_idx - 1 < current_col + colspan:
                    nvidia_cell = cell
                    break
                current_col += colspan
            
            if nvidia_cell:
                version = nvidia_cell.get_text().strip()
                self.log(f"Row {row_idx}: {package_name} = {version}")
                if version and version != '—' and version != '-':
                    packages[package_name] = version
        
        self.log(f"Extracted {len(packages)} packages for K8s {k8s_version}")
        return packages

    def find_kmod_nvidia_version(self, k8s_version: str) -> Optional[Tuple[str, str, str]]:
        """Find the first kmod-nvidia-latest-dkms version for the specified Kubernetes version."""
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
                    kmod_version = packages.get('kmod-nvidia-latest-dkms')
                    if kmod_version:
                        return (release_tag, release_date, kmod_version)
        
        return None

    def find_latest_release_for_k8s(self, k8s_version: str) -> Optional[Tuple[str, str, str]]:
        """Find the latest (most recent) release for the specified Kubernetes version."""
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
                    kmod_version = packages.get('kmod-nvidia-latest-dkms', 'Not found')
                    return (release_tag, release_date, kmod_version)
        
        return None

    def find_releases_by_driver_version(self, driver_version: str, fuzzy: bool = False, k8s_version: Optional[str] = None) -> List[Tuple[str, str, str, str]]:
        """Find releases that contain the specified driver version, optionally filtered by Kubernetes version."""
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
                    
                kmod_version = packages.get('kmod-nvidia-latest-dkms')
                if kmod_version:
                    # Check for exact or fuzzy match
                    if fuzzy:
                        if driver_version.lower() in kmod_version.lower():
                            matches.append((release_tag, release_date, k8s_ver, kmod_version))
                    else:
                        if driver_version in kmod_version:
                            matches.append((release_tag, release_date, k8s_ver, kmod_version))
        
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
                            print(f"    {pkg}: {version}")
                        print()
                else:
                    print("No body content found")
                return
        
        print(f"Release {release_tag} not found")


def main():
    parser = argparse.ArgumentParser(
        description='Find kmod-nvidia-latest-dkms version for AL2023_x86_64_NVIDIA AMI type'
    )
    parser.add_argument(
        '--k8s-version', '-k',
        help='Kubernetes version (e.g., 1.32, 1.31)'
    )
    parser.add_argument(
        '--driver-version', '-d',
        help='Driver version to search for (e.g., 570.124.06)'
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
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--debug-release',
        help='Debug a specific release (e.g., v20250403)'
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
    
    # Search by driver version (with optional K8s version filter)
    if args.driver_version:
        filter_text = f" for Kubernetes {args.k8s_version}" if args.k8s_version else ""
        print(f"Searching for releases with kmod-nvidia-latest-dkms version: {args.driver_version}{filter_text}")
        if args.fuzzy:
            print("(Using fuzzy matching)")
        print("=" * 80)
        
        matches = eks_parser.find_releases_by_driver_version(args.driver_version, args.fuzzy, args.k8s_version)
        
        if matches:
            print(f"Found {len(matches)} matching release(s):")
            print()
            for release_tag, release_date, k8s_version, kmod_version in matches:
                print(f"Release: {release_tag}")
                print(f"Date: {release_date}")
                print(f"Kubernetes version: {k8s_version}")
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
    
    if args.latest:
        print(f"Finding latest release for Kubernetes {args.k8s_version}")
        print("=" * 80)
        
        result = eks_parser.find_latest_release_for_k8s(args.k8s_version)
        
        if result:
            release_tag, release_date, kmod_version = result
            print(f"Latest release: {release_tag}")
            print(f"Release date: {release_date}")
            print(f"kmod-nvidia-latest-dkms version: {kmod_version}")
        else:
            print(f"No releases found for Kubernetes {args.k8s_version}")
    else:
        print(f"Searching for first kmod-nvidia-latest-dkms version for Kubernetes {args.k8s_version}")
        print("=" * 80)
        
        result = eks_parser.find_kmod_nvidia_version(args.k8s_version)
        
        if result:
            release_tag, release_date, kmod_version = result
            print(f"Found in release: {release_tag}")
            print(f"Release date: {release_date}")
            print(f"kmod-nvidia-latest-dkms version: {kmod_version}")
        else:
            print(f"No kmod-nvidia-latest-dkms version found for Kubernetes {args.k8s_version}")
    
    # Show available versions if search failed
    if not args.driver_version and (not result if 'result' in locals() else True):
        print("\nAvailable Kubernetes versions:")
        versions = eks_parser.list_available_k8s_versions()
        for version in versions:
            print(f"  - {version}")


if __name__ == "__main__":
    main()
