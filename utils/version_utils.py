"""
Version parsing and comparison utilities - FIXED VERSION
"""

import re
from typing import List, Optional, Tuple, Union
from dataclasses import dataclass


@dataclass
class VersionInfo:
    """Structured version information."""
    major: int
    minor: int
    patch: int
    suffix: str = ""
    original: str = ""
    
    def __str__(self) -> str:
        """String representation of version - PRESERVES LEADING ZEROS."""
        # Extract original patch format from original string if available
        if self.original:
            # Try to preserve original formatting
            major_minor_match = re.search(rf"^{self.major}\.{self.minor}\.(\d+)", self.original)
            if major_minor_match:
                original_patch = major_minor_match.group(1)
                base = f"{self.major}.{self.minor}.{original_patch}"
            else:
                base = f"{self.major}.{self.minor}.{self.patch:02d}" if self.patch < 10 else f"{self.major}.{self.minor}.{self.patch}"
        else:
            # Default formatting - preserve leading zeros for patch versions
            base = f"{self.major}.{self.minor}.{self.patch:02d}" if self.patch < 10 else f"{self.major}.{self.minor}.{self.patch}"
        
        return f"{base}{self.suffix}" if self.suffix else base
    
    def __eq__(self, other) -> bool:
        """Check version equality."""
        if not isinstance(other, VersionInfo):
            return False
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)
    
    def __lt__(self, other) -> bool:
        """Check if this version is less than another."""
        if not isinstance(other, VersionInfo):
            return NotImplemented
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
    
    def __le__(self, other) -> bool:
        """Check if this version is less than or equal to another."""
        return self == other or self < other
    
    def __gt__(self, other) -> bool:
        """Check if this version is greater than another."""
        if not isinstance(other, VersionInfo):
            return NotImplemented
        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)
    
    def __ge__(self, other) -> bool:
        """Check if this version is greater than or equal to another."""
        return self == other or self > other
    
    @property
    def is_patch_version(self) -> bool:
        """Check if this is a patch-level version (x.y.z)."""
        return self.patch > 0
    
    @property
    def base_version(self) -> str:
        """Get base version without suffix (x.y.z) - PRESERVES FORMATTING."""
        # Use the same logic as __str__ but without suffix
        if self.original:
            major_minor_match = re.search(rf"^{self.major}\.{self.minor}\.(\d+)", self.original)
            if major_minor_match:
                original_patch = major_minor_match.group(1)
                return f"{self.major}.{self.minor}.{original_patch}"
        
        # Default formatting with leading zeros preserved
        return f"{self.major}.{self.minor}.{self.patch:02d}" if self.patch < 10 else f"{self.major}.{self.minor}.{self.patch}"
    
    @property
    def minor_version(self) -> str:
        """Get minor version (x.y)."""
        return f"{self.major}.{self.minor}"


class VersionParser:
    """Parser for various version string formats."""
    
    # Common version patterns
    PATTERNS = [
        # Standard semantic versioning: 1.32.0, 570.148.08
        r"^(\d+)\.(\d+)\.(\d+)(.*)$",
        # Minor version only: 1.32
        r"^(\d+)\.(\d+)()(.*)$",
        # Major version only: 570
        r"^(\d+)()()(.*)$"
    ]
    
    # NVIDIA driver specific patterns
    NVIDIA_PATTERNS = [
        # 570.148.08-1.amzn2023, 560.35.05-1.ubuntu2204
        r"(\d+\.\d+\.\d+)[-.](\d+)\.([a-z0-9]+)",
        # 570.148.08-1.el7
        r"(\d+\.\d+\.\d+)[-.](\d+)\.([a-z0-9]+)",
        # Basic: 570.148.08
        r"(\d+\.\d+\.\d+)",
    ]
    
    @classmethod
    def parse_version(cls, version_string: str) -> Optional[VersionInfo]:
        """
        Parse a version string into structured version information.
        
        Args:
            version_string: Version string to parse
            
        Returns:
            VersionInfo object or None if parsing fails
        """
        if not version_string:
            return None
        
        version_string = version_string.strip()
        
        for pattern in cls.PATTERNS:
            match = re.match(pattern, version_string)
            if match:
                major_str, minor_str, patch_str, suffix = match.groups()
                
                try:
                    major = int(major_str) if major_str else 0
                    minor = int(minor_str) if minor_str else 0
                    patch = int(patch_str) if patch_str else 0
                    suffix = suffix.strip() if suffix else ""
                    
                    return VersionInfo(
                        major=major,
                        minor=minor,
                        patch=patch,
                        suffix=suffix,
                        original=version_string
                    )
                except ValueError:
                    continue
        
        return None
    
    @classmethod
    def parse_driver_version(cls, driver_string: str) -> Optional[VersionInfo]:
        """
        Parse NVIDIA driver version string with various suffixes.
        
        Args:
            driver_string: Driver version string (e.g., "570.148.08-1.amzn2023")
            
        Returns:
            VersionInfo object with clean version or None if parsing fails
        """
        if not driver_string:
            return None
        
        # Try NVIDIA-specific patterns first
        for pattern in cls.NVIDIA_PATTERNS:
            match = re.search(pattern, driver_string)
            if match:
                base_version = match.group(1)
                return cls.parse_version(base_version)
        
        # Fall back to general parsing
        return cls.parse_version(driver_string)
    
    @classmethod
    def extract_clean_version(cls, version_string: str) -> Optional[str]:
        """
        Extract clean version number from a version string.
        
        Args:
            version_string: Version string with potential suffixes
            
        Returns:
            Clean version string (e.g., "570.148.08") or None
        """
        version_info = cls.parse_version(version_string)
        return version_info.base_version if version_info else None
    
    @classmethod
    def extract_driver_version(cls, driver_string: str) -> Optional[str]:
        """
        Extract clean driver version from driver string.
        
        Args:
            driver_string: Driver string (e.g., "570.148.08-1.amzn2023")
            
        Returns:
            Clean driver version (e.g., "570.148.08") or None
        """
        version_info = cls.parse_driver_version(driver_string)
        return version_info.base_version if version_info else None


class VersionComparator:
    """Utilities for comparing versions."""
    
    @staticmethod
    def compare_versions(v1: str, v2: str) -> int:
        """
        Compare two version strings.
        
        Args:
            v1: First version string
            v2: Second version string
            
        Returns:
            -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
        """
        version1 = VersionParser.parse_version(v1)
        version2 = VersionParser.parse_version(v2)
        
        if not version1 or not version2:
            # Fall back to string comparison if parsing fails
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1
            else:
                return 0
        
        if version1 < version2:
            return -1
        elif version1 > version2:
            return 1
        else:
            return 0
    
    @staticmethod
    def sort_versions(versions: List[str], reverse: bool = False) -> List[str]:
        """
        Sort a list of version strings.
        
        Args:
            versions: List of version strings to sort
            reverse: Sort in descending order if True
            
        Returns:
            Sorted list of version strings
        """
        def version_key(v: str) -> Tuple[int, int, int]:
            """Generate sort key for version string."""
            version_info = VersionParser.parse_version(v)
            if version_info:
                return (version_info.major, version_info.minor, version_info.patch)
            else:
                # Fallback for unparseable versions
                return (0, 0, 0)
        
        return sorted(versions, key=version_key, reverse=reverse)
    
    @staticmethod
    def is_version_compatible(version: str, min_version: str, max_version: str = None) -> bool:
        """
        Check if a version falls within a compatible range.
        
        Args:
            version: Version to check
            min_version: Minimum compatible version
            max_version: Maximum compatible version (optional)
            
        Returns:
            True if version is compatible
        """
        parsed_version = VersionParser.parse_version(version)
        parsed_min = VersionParser.parse_version(min_version)
        
        if not parsed_version or not parsed_min:
            return False
        
        if parsed_version < parsed_min:
            return False
        
        if max_version:
            parsed_max = VersionParser.parse_version(max_version)
            if parsed_max and parsed_version > parsed_max:
                return False
        
        return True
    
    @staticmethod
    def find_latest_version(versions: List[str]) -> Optional[str]:
        """
        Find the latest version from a list of version strings.
        
        Args:
            versions: List of version strings
            
        Returns:
            Latest version string or None if list is empty
        """
        if not versions:
            return None
        
        sorted_versions = VersionComparator.sort_versions(versions, reverse=True)
        return sorted_versions[0]
    
    @staticmethod
    def find_versions_in_range(versions: List[str], min_version: str, max_version: str = None) -> List[str]:
        """
        Find all versions within a specified range.
        
        Args:
            versions: List of version strings to filter
            min_version: Minimum version (inclusive)
            max_version: Maximum version (inclusive, optional)
            
        Returns:
            List of versions within the range, sorted
        """
        compatible_versions = [
            v for v in versions 
            if VersionComparator.is_version_compatible(v, min_version, max_version)
        ]
        
        return VersionComparator.sort_versions(compatible_versions)


class KubernetesVersionUtils:
    """Kubernetes-specific version utilities."""
    
    # Kubernetes version support matrix
    SUPPORTED_VERSIONS = ["1.28", "1.29", "1.30", "1.31", "1.32", "1.33"]
    EOL_VERSIONS = ["1.26", "1.27"]
    
    @classmethod
    def is_supported_k8s_version(cls, version: str) -> bool:
        """Check if Kubernetes version is currently supported."""
        return version in cls.SUPPORTED_VERSIONS
    
    @classmethod
    def is_eol_k8s_version(cls, version: str) -> bool:
        """Check if Kubernetes version is end-of-life."""
        return version in cls.EOL_VERSIONS
    
    @classmethod
    def get_latest_k8s_version(cls) -> str:
        """Get the latest supported Kubernetes version."""
        return cls.SUPPORTED_VERSIONS[-1]
    
    @classmethod
    def get_previous_k8s_version(cls, current_version: str) -> Optional[str]:
        """Get the previous Kubernetes version."""
        try:
            current_index = cls.SUPPORTED_VERSIONS.index(current_version)
            if current_index > 0:
                return cls.SUPPORTED_VERSIONS[current_index - 1]
        except ValueError:
            pass
        return None
    
    @classmethod
    def get_next_k8s_version(cls, current_version: str) -> Optional[str]:
        """Get the next Kubernetes version."""
        try:
            current_index = cls.SUPPORTED_VERSIONS.index(current_version)
            if current_index < len(cls.SUPPORTED_VERSIONS) - 1:
                return cls.SUPPORTED_VERSIONS[current_index + 1]
        except ValueError:
            pass
        return None
    
    @classmethod
    def validate_k8s_version(cls, version: str) -> Tuple[bool, str]:
        """
        Validate Kubernetes version and provide guidance.
        
        Args:
            version: Kubernetes version to validate
            
        Returns:
            Tuple of (is_valid, message)
        """
        if not version:
            return False, "Kubernetes version is required"
        
        if cls.is_supported_k8s_version(version):
            return True, f"Kubernetes {version} is supported"
        
        if cls.is_eol_k8s_version(version):
            latest = cls.get_latest_k8s_version()
            return False, f"Kubernetes {version} is end-of-life. Consider upgrading to {latest}"
        
        # Check if it's a valid format but unknown version
        parsed = VersionParser.parse_version(version)
        if parsed and parsed.major == 1:
            latest = cls.get_latest_k8s_version()
            if version > latest:
                return False, f"Kubernetes {version} is not yet supported. Latest supported is {latest}"
            else:
                return False, f"Kubernetes {version} is not supported. Supported versions: {', '.join(cls.SUPPORTED_VERSIONS)}"
        
        return False, f"Invalid Kubernetes version format: {version}"


# Convenience functions for backward compatibility
def parse_driver_version(version_string: str) -> Optional[str]:
    """
    Legacy function: Extract clean version number from driver version string.
    
    Args:
        version_string: Driver version string
        
    Returns:
        Clean version string or None
    """
    return VersionParser.extract_driver_version(version_string)


def compare_versions(v1: str, v2: str) -> int:
    """
    Legacy function: Compare two version strings.
    
    Args:
        v1: First version string
        v2: Second version string
        
    Returns:
        -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
    """
    return VersionComparator.compare_versions(v1, v2)


def sort_versions(versions: List[str], reverse: bool = False) -> List[str]:
    """
    Legacy function: Sort version strings.
    
    Args:
        versions: List of version strings
        reverse: Sort in descending order if True
        
    Returns:
        Sorted list of version strings
    """
    return VersionComparator.sort_versions(versions, reverse)