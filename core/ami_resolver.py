"""
AMI resolver that combines GitHub client and HTML parser to find AMI information.
"""

from typing import List, Optional, Tuple, Dict
from core.github_client import GitHubReleaseClient, GitHubAPIError
from core.html_parser import EKSReleaseHTMLParser, ReleaseParsingError
from models.ami_types import AMIType, Architecture, AMITypeManager


class AMIResolutionError(Exception):
    """Exception raised for AMI resolution errors."""
    pass


class EKSAMIResolver:
    """High-level resolver for EKS AMI information."""
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the AMI resolver.
        
        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        self.github_client = GitHubReleaseClient(verbose=verbose)
        self.html_parser = EKSReleaseHTMLParser(verbose=verbose)
        self.ami_manager = AMITypeManager()
    
    def log(self, message: str):
        """Print verbose logging messages."""
        if self.verbose:
            print(f"[AMI-RESOLVER-DEBUG] {message}")
    
    def find_kmod_nvidia_version(self, k8s_version: str, ami_type: AMIType) -> Optional[Tuple[str, str, str]]:
        """
        Find the first kmod-nvidia-latest-dkms version for the specified Kubernetes version and AMI type.
        
        Args:
            k8s_version: Kubernetes version (e.g., "1.32")
            ami_type: AMI type to search for
        
        Returns:
            Tuple of (release_tag, release_date, kmod_version) or None if not found
        
        Raises:
            AMIResolutionError: If resolution fails
        """
        try:
            releases = self.github_client.get_releases()
        except GitHubAPIError as e:
            raise AMIResolutionError(f"Failed to fetch releases: {e}")
        
        for release in releases:
            release_tag = release.get('tag_name', '')
            release_date = release.get('published_at', '')
            body = release.get('body', '')
            
            self.log(f"Processing release: {release_tag}")
            
            try:
                # Parse the release body
                k8s_sections = self.html_parser.parse_release_body(body, release_tag)
            except ReleaseParsingError as e:
                self.log(f"Failed to parse {release_tag}: {e}")
                continue
            
            # Look for the specified Kubernetes version
            for version, packages in k8s_sections.items():
                if version == k8s_version:
                    # Try different package key formats
                    kmod_version = None
                    
                    # Try with AMI type suffix
                    key_with_type = f"kmod-nvidia-latest-dkms_{ami_type.value}"
                    if key_with_type in packages:
                        kmod_version = packages[key_with_type]
                    # Try without suffix (backward compatibility)
                    elif "kmod-nvidia-latest-dkms" in packages:
                        kmod_version = packages["kmod-nvidia-latest-dkms"]
                    
                    if kmod_version:
                        return (release_tag, release_date, kmod_version)
        
        return None
    
    def find_latest_release_for_k8s(self, k8s_version: str, ami_type: AMIType) -> Optional[Tuple[str, str, str]]:
        """
        Find the latest (most recent) release for the specified Kubernetes version and AMI type.
        
        Args:
            k8s_version: Kubernetes version (e.g., "1.32")
            ami_type: AMI type to search for
        
        Returns:
            Tuple of (release_tag, release_date, kmod_version) or None if not found
        
        Raises:
            AMIResolutionError: If resolution fails
        """
        try:
            releases = self.github_client.get_releases()
        except GitHubAPIError as e:
            raise AMIResolutionError(f"Failed to fetch releases: {e}")
        
        # Releases are typically ordered by date (newest first)
        for release in releases:
            release_tag = release.get('tag_name', '')
            release_date = release.get('published_at', '')
            body = release.get('body', '')
            
            self.log(f"Processing release: {release_tag}")
            
            try:
                # Parse the release body
                k8s_sections = self.html_parser.parse_release_body(body, release_tag)
            except ReleaseParsingError as e:
                self.log(f"Failed to parse {release_tag}: {e}")
                continue
            
            # Look for the specified Kubernetes version
            for version, packages in k8s_sections.items():
                if version == k8s_version:
                    # Try different package key formats
                    kmod_version = "Not found"
                    
                    # Try with AMI type suffix
                    key_with_type = f"kmod-nvidia-latest-dkms_{ami_type.value}"
                    if key_with_type in packages:
                        kmod_version = packages[key_with_type]
                    # Try without suffix (backward compatibility)
                    elif "kmod-nvidia-latest-dkms" in packages:
                        kmod_version = packages["kmod-nvidia-latest-dkms"]
                    
                    return (release_tag, release_date, kmod_version)
        
        return None
    
    def find_releases_by_driver_version(self, driver_version: str, fuzzy: bool = False, 
                                       k8s_version: Optional[str] = None, 
                                       ami_types: List[AMIType] = None,
                                       architecture: Architecture = Architecture.X86_64) -> List[Tuple[str, str, str, str, str]]:
        """
        Find releases that contain the specified driver version.
        
        Args:
            driver_version: The driver version to search for (e.g., "550.127.08")
            fuzzy: Whether to use fuzzy matching
            k8s_version: Optional Kubernetes version filter
            ami_types: List of AMI types to search (default: arch-specific types)
            architecture: Target architecture
            
        Returns:
            List of tuples: (release_tag, release_date, k8s_version, kmod_version, ami_type)
        
        Raises:
            AMIResolutionError: If resolution fails
        """
        if ami_types is None:
            ami_types = self.ami_manager.get_ami_types_for_architecture(architecture)
            
        try:
            releases = self.github_client.get_releases()
        except GitHubAPIError as e:
            raise AMIResolutionError(f"Failed to fetch releases: {e}")
        
        matches = []
        
        for release in releases:
            release_tag = release.get('tag_name', '')
            release_date = release.get('published_at', '')
            body = release.get('body', '')
            
            self.log(f"Processing release: {release_tag}")
            
            try:
                # Parse the release body
                k8s_sections = self.html_parser.parse_release_body(body, release_tag)
            except ReleaseParsingError as e:
                self.log(f"Failed to parse {release_tag}: {e}")
                continue
            
            # Check each Kubernetes version in this release
            for k8s_ver, packages in k8s_sections.items():
                # Filter by Kubernetes version if specified
                if k8s_version and k8s_ver != k8s_version:
                    continue
                
                # Check each AMI type
                for ami_type in ami_types:
                    key_with_type = f"kmod-nvidia-latest-dkms_{ami_type.value}"
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
                            matches.append((release_tag, release_date, k8s_ver, kmod_version, ami_type.value))
                            self.log(f"Found match: {release_tag} K8s {k8s_ver} {ami_type.value} {kmod_version}")
        
        return matches
    
    def list_available_k8s_versions(self, limit: int = 20) -> List[str]:
        """
        List all available Kubernetes versions from recent releases.
        
        Args:
            limit: Number of recent releases to check
        
        Returns:
            Sorted list of Kubernetes versions
        
        Raises:
            AMIResolutionError: If resolution fails
        """
        try:
            releases = self.github_client.get_releases(limit=limit)
        except GitHubAPIError as e:
            raise AMIResolutionError(f"Failed to fetch releases: {e}")
        
        k8s_versions = set()
        
        for release in releases:
            release_tag = release.get('tag_name', '')
            body = release.get('body', '')
            
            if not body:
                continue
            
            try:
                k8s_sections = self.html_parser.parse_release_body(body, release_tag)
                k8s_versions.update(k8s_sections.keys())
            except ReleaseParsingError as e:
                self.log(f"Failed to parse {release_tag}: {e}")
                continue
        
        return sorted(k8s_versions, key=lambda x: [int(i) for i in x.split('.')])
    
    def debug_release(self, release_tag: str) -> Dict:
        """
        Debug a specific release to see its structure and extracted data.
        
        Args:
            release_tag: Release tag to debug (e.g., "v20241121")
        
        Returns:
            Debug information dictionary
        
        Raises:
            AMIResolutionError: If resolution fails
        """
        try:
            release = self.github_client.get_release_by_tag(release_tag)
        except GitHubAPIError as e:
            raise AMIResolutionError(f"Failed to fetch release {release_tag}: {e}")
        
        if not release:
            raise AMIResolutionError(f"Release {release_tag} not found")
        
        debug_info = {
            'release_info': self.github_client.get_release_info(release),
            'validation': self.github_client.validate_release_structure(release),
            'k8s_sections': {},
            'parsing_errors': []
        }
        
        body = release.get('body', '')
        if body:
            try:
                k8s_sections = self.html_parser.parse_release_body(body, release_tag)
                debug_info['k8s_sections'] = k8s_sections
                
                # Validate each section
                for k8s_version, packages in k8s_sections.items():
                    is_valid, issues = self.html_parser.validate_package_data(packages)
                    if not is_valid:
                        debug_info['parsing_errors'].extend([f"K8s {k8s_version}: {issue}" for issue in issues])
                
                # Extract driver versions
                for k8s_version, packages in k8s_sections.items():
                    driver_versions = self.html_parser.extract_driver_versions(packages)
                    debug_info['k8s_sections'][k8s_version]['driver_versions'] = driver_versions
                    
            except ReleaseParsingError as e:
                debug_info['parsing_errors'].append(str(e))
        
        return debug_info
    
    def get_ami_compatibility_matrix(self) -> Dict[str, Dict]:
        """
        Get the compatibility matrix for all AMI types.
        
        Returns:
            Dictionary with compatibility information for all AMI types
        """
        matrix = {}
        
        for ami_type in AMIType:
            compatibility = self.ami_manager.get_compatibility_info(ami_type)
            matrix[ami_type.value] = {
                'architecture': compatibility.architecture.value,
                'kubernetes_versions': compatibility.kubernetes_versions,
                'is_deprecated': compatibility.is_deprecated,
                'deprecation_date': compatibility.deprecation_date,
                'replacement_ami_type': compatibility.replacement_ami_type.value if compatibility.replacement_ami_type else None
            }
        
        return matrix