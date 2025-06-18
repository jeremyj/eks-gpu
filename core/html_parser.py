"""
HTML parser for extracting package information from EKS AMI release notes.
"""

import re
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Set
from models.ami_types import AMIType, AMITypeManager


class ReleaseParsingError(Exception):
    """Exception raised for errors during release parsing."""
    pass


class EKSReleaseHTMLParser:
    """Parser for EKS AMI release HTML content."""
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the HTML parser.
        
        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        self.ami_manager = AMITypeManager()
    
    def log(self, message: str):
        """Print verbose logging messages."""
        if self.verbose:
            print(f"[HTML-PARSER-DEBUG] {message}")
    
    def parse_release_body(self, body: str, release_tag: str) -> Dict[str, Dict[str, str]]:
        """
        Parse the release body HTML to extract package information.
        
        Args:
            body: HTML content of the release body
            release_tag: Release tag for logging purposes
        
        Returns:
            Dictionary mapping Kubernetes versions to package dictionaries
            Format: {k8s_version: {package_key: package_version}}
        
        Raises:
            ReleaseParsingError: If parsing fails
        """
        if not body:
            self.log(f"Empty body for release {release_tag}")
            return {}
        
        self.log(f"Parsing release body for {release_tag}")
        
        try:
            soup = BeautifulSoup(body, 'html.parser')
        except Exception as e:
            raise ReleaseParsingError(f"Failed to parse HTML for {release_tag}: {e}")
        
        # Find all Kubernetes version sections
        k8s_sections = {}
        
        # Method 1: Look for <summary> tags with Kubernetes versions (collapsible sections)
        k8s_sections.update(self._parse_summary_sections(soup))
        
        # Method 2: Look for headers with Kubernetes versions (fallback)
        if not k8s_sections:
            k8s_sections.update(self._parse_header_sections(soup))
        
        self.log(f"Found {len(k8s_sections)} Kubernetes sections in {release_tag}")
        return k8s_sections
    
    def _parse_summary_sections(self, soup: BeautifulSoup) -> Dict[str, Dict[str, str]]:
        """Parse collapsible <summary> sections for Kubernetes versions."""
        k8s_sections = {}
        
        for summary in soup.find_all('summary'):
            if summary.find('b'):
                b_tag = summary.find('b')
                version_text = b_tag.get_text().strip()
                self.log(f"Found summary with text: {version_text}")
                
                # Extract version number (e.g., "1.32" from "Kubernetes 1.32")
                k8s_version = self._extract_k8s_version(version_text)
                if k8s_version:
                    self.log(f"Found Kubernetes version: {k8s_version}")
                    
                    # Find the parent details element
                    details = summary.find_parent('details')
                    if details:
                        packages = self._parse_k8s_section(details, k8s_version)
                        if packages:
                            k8s_sections[k8s_version] = packages
        
        return k8s_sections
    
    def _parse_header_sections(self, soup: BeautifulSoup) -> Dict[str, Dict[str, str]]:
        """Parse header sections for Kubernetes versions (fallback method)."""
        k8s_sections = {}
        
        headers = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for header in headers:
            header_text = header.get_text().strip()
            k8s_version = self._extract_k8s_version(header_text)
            if k8s_version:
                self.log(f"Found Kubernetes version in header: {k8s_version}")
                
                # Find tables after this header
                packages = self._find_packages_after_header(header, k8s_version)
                if packages:
                    k8s_sections[k8s_version] = packages
        
        return k8s_sections
    
    def _extract_k8s_version(self, text: str) -> Optional[str]:
        """Extract Kubernetes version from text."""
        version_match = re.search(r'Kubernetes\s+([\d.]+)', text, re.IGNORECASE)
        return version_match.group(1) if version_match else None
    
    def _parse_k8s_section(self, details_element, k8s_version: str) -> Dict[str, str]:
        """Parse a Kubernetes version section to extract package tables."""
        tables = details_element.find_all('table')
        self.log(f"Found {len(tables)} tables in K8s {k8s_version} section")
        
        packages = {}
        
        # Look for tables with NVIDIA GPU AMI columns
        for i, table in enumerate(tables):
            headers = [th.get_text().strip() for th in table.find_all('th')]
            self.log(f"Table {i} headers: {headers}")
            
            # Find GPU columns
            gpu_columns = self._identify_gpu_columns(headers)
            
            if gpu_columns:
                table_packages = self._parse_package_table(table, headers, k8s_version, gpu_columns)
                packages.update(table_packages)
        
        return packages
    
    def _find_packages_after_header(self, header, k8s_version: str) -> Dict[str, str]:
        """Find package tables after a Kubernetes version header."""
        packages = {}
        
        # Find all tables after this header
        current = header.find_next_sibling()
        while current:
            if current.name == 'table':
                headers = [th.get_text().strip() for th in current.find_all('th')]
                
                # Check for GPU columns
                gpu_columns = self._identify_gpu_columns(headers)
                
                if gpu_columns:
                    self.log(f"Found GPU table after header for K8s {k8s_version}")
                    table_packages = self._parse_package_table(current, headers, k8s_version, gpu_columns)
                    packages.update(table_packages)
                    
            elif current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                # Stop if we hit another header
                break
            current = current.find_next_sibling()
        
        return packages
    
    def _identify_gpu_columns(self, headers: List[str]) -> Dict[str, int]:
        """Identify GPU-related columns in table headers."""
        gpu_columns = {}
        gpu_ami_types = self.ami_manager.get_all_gpu_ami_types()
        
        for idx, header in enumerate(headers):
            # Check if header matches any GPU AMI type
            for ami_type in gpu_ami_types:
                if header == ami_type.value:
                    gpu_columns[header] = idx
                    self.log(f"Found GPU column: {header} at index {idx}")
                    break
        
        return gpu_columns
    
    def _parse_package_table(self, table, headers: List[str], k8s_version: str, 
                           gpu_columns: Dict[str, int]) -> Dict[str, str]:
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
            if self.verbose:
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
                cell_value = self._extract_cell_value(cells, target_col_idx)
                
                if cell_value and cell_value not in ['—', '-', '']:
                    # Store with AMI type prefix to distinguish between AL2, AL2023, and architectures
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
    
    def _extract_cell_value(self, cells: List, target_col_idx: int) -> Optional[str]:
        """
        Extract cell value considering colspan attributes.
        
        Args:
            cells: List of table cells
            target_col_idx: Target logical column index
        
        Returns:
            Cell value or None if not found
        """
        current_logical_col = 0
        
        for cell_idx, cell in enumerate(cells):
            colspan = int(cell.get('colspan', 1))
            self.log(f"    Cell {cell_idx}: logical_cols {current_logical_col}-{current_logical_col + colspan - 1}")
            
            # Check if target column falls within this cell's span
            if current_logical_col <= target_col_idx < current_logical_col + colspan:
                cell_value = cell.get_text().strip()
                self.log(f"    ✅ FOUND in cell {cell_idx}: '{cell_value}'")
                return cell_value
            
            current_logical_col += colspan
        
        return None
    
    def get_available_k8s_versions(self, release_bodies: List[tuple[str, str]]) -> Set[str]:
        """
        Extract all available Kubernetes versions from multiple release bodies.
        
        Args:
            release_bodies: List of (release_tag, body) tuples
        
        Returns:
            Set of Kubernetes versions found
        """
        k8s_versions = set()
        
        for release_tag, body in release_bodies:
            if not body:
                continue
            
            try:
                k8s_sections = self.parse_release_body(body, release_tag)
                k8s_versions.update(k8s_sections.keys())
            except ReleaseParsingError as e:
                self.log(f"Error parsing {release_tag}: {e}")
                continue
        
        return k8s_versions
    
    def validate_package_data(self, packages: Dict[str, str]) -> tuple[bool, List[str]]:
        """
        Validate extracted package data.
        
        Args:
            packages: Package dictionary to validate
        
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        if not packages:
            issues.append("No packages found")
            return False, issues
        
        # Check for NVIDIA driver packages
        nvidia_packages = [key for key in packages.keys() if 'nvidia' in key.lower()]
        if not nvidia_packages:
            issues.append("No NVIDIA packages found")
        
        # Check for version format validity
        for package_name, version in packages.items():
            if not version or version in ['—', '-', '']:
                issues.append(f"Empty version for package: {package_name}")
            elif len(version) < 3:
                issues.append(f"Suspiciously short version for {package_name}: {version}")
        
        # Check for expected kmod-nvidia package
        if 'kmod-nvidia-latest-dkms' not in packages:
            # Check if it exists with AMI type suffix
            kmod_variants = [key for key in packages.keys() if key.startswith('kmod-nvidia-latest-dkms_')]
            if not kmod_variants:
                issues.append("No kmod-nvidia-latest-dkms package found")
        
        return len(issues) == 0, issues
    
    def extract_driver_versions(self, packages: Dict[str, str]) -> Dict[str, str]:
        """
        Extract driver versions for each AMI type from package data.
        
        Args:
            packages: Package dictionary from parse_release_body
        
        Returns:
            Dictionary mapping AMI types to driver versions
        """
        driver_versions = {}
        
        # Look for kmod-nvidia packages with AMI type suffixes
        for package_key, version in packages.items():
            if package_key.startswith('kmod-nvidia-latest-dkms_'):
                # Extract AMI type from key (e.g., "kmod-nvidia-latest-dkms_AL2023_x86_64_NVIDIA")
                ami_type_str = package_key.replace('kmod-nvidia-latest-dkms_', '')
                driver_versions[ami_type_str] = version
        
        # Also check for generic kmod-nvidia package (backward compatibility)
        if 'kmod-nvidia-latest-dkms' in packages:
            driver_versions['generic'] = packages['kmod-nvidia-latest-dkms']
        
        return driver_versions