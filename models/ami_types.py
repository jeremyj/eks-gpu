"""
AMI Type definitions and architecture mappings for EKS.
"""

from enum import Enum
from typing import List, Dict
from dataclasses import dataclass


class AMIType(Enum):
    """EKS AMI types with their exact string representations."""
    AL2023_X86_64_NVIDIA = "AL2023_x86_64_NVIDIA"
    AL2_X86_64_GPU = "AL2_x86_64_GPU"
    AL2023_ARM_64_NVIDIA = "AL2023_ARM_64_NVIDIA"

    def __str__(self) -> str:
        return self.value
    
    @property
    def is_al2023(self) -> bool:
        """Check if this AMI type is AL2023-based."""
        return "AL2023" in self.value
    
    @property
    def is_gpu_enabled(self) -> bool:
        """Check if this AMI type supports GPU instances."""
        return "NVIDIA" in self.value or "GPU" in self.value
    
    @property
    def architecture(self) -> 'Architecture':
        """Get the architecture for this AMI type."""
        if "ARM" in self.value:
            return Architecture.ARM64
        else:
            return Architecture.X86_64


class Architecture(Enum):
    """Supported CPU architectures."""
    X86_64 = "x86_64"
    ARM64 = "arm64"
    AMD64 = "amd64"  # Alias for x86_64

    def __str__(self) -> str:
        return self.value
    
    @property
    def normalized_name(self) -> str:
        """Get normalized architecture name (amd64 -> x86_64)."""
        return "x86_64" if self == Architecture.AMD64 else self.value
    
    @property
    def display_name(self) -> str:
        """Get human-readable architecture name."""
        return "ARM64" if self == Architecture.ARM64 else "x86_64"

    @classmethod
    def from_string(cls, arch_str: str) -> 'Architecture':
        """Create Architecture from string, handling common variations."""
        arch_str = arch_str.lower()
        if arch_str in ("amd64", "x86_64"):
            return cls.X86_64
        elif arch_str == "arm64":
            return cls.ARM64
        else:
            raise ValueError(f"Unsupported architecture: {arch_str}")


@dataclass
class AMICompatibility:
    """Information about AMI type compatibility and support status."""
    ami_type: AMIType
    architecture: Architecture
    kubernetes_versions: List[str]
    is_deprecated: bool = False
    deprecation_date: str = None
    replacement_ami_type: AMIType = None


class AMITypeManager:
    """Manager class for AMI type operations and compatibility checks."""
    
    # AL2 End-of-Life Information
    AL2_EOL_DATE = "2024-11-26"
    AL2_LAST_K8S_VERSION = "1.32"
    
    def __init__(self):
        self._compatibility_matrix = self._build_compatibility_matrix()
    
    def _build_compatibility_matrix(self) -> Dict[AMIType, AMICompatibility]:
        """Build the compatibility matrix for AMI types."""
        return {
            AMIType.AL2023_X86_64_NVIDIA: AMICompatibility(
                ami_type=AMIType.AL2023_X86_64_NVIDIA,
                architecture=Architecture.X86_64,
                kubernetes_versions=["1.28", "1.29", "1.30", "1.31", "1.32", "1.33"],
                is_deprecated=False
            ),
            AMIType.AL2_X86_64_GPU: AMICompatibility(
                ami_type=AMIType.AL2_X86_64_GPU,
                architecture=Architecture.X86_64,
                kubernetes_versions=["1.28", "1.29", "1.30", "1.31", "1.32"],
                is_deprecated=True,
                deprecation_date=self.AL2_EOL_DATE,
                replacement_ami_type=AMIType.AL2023_X86_64_NVIDIA
            ),
            AMIType.AL2023_ARM_64_NVIDIA: AMICompatibility(
                ami_type=AMIType.AL2023_ARM_64_NVIDIA,
                architecture=Architecture.ARM64,
                kubernetes_versions=["1.28", "1.29", "1.30", "1.31", "1.32", "1.33"],
                is_deprecated=False
            )
        }
    
    def get_ami_types_for_architecture(self, architecture: Architecture, include_deprecated: bool = True) -> List[AMIType]:
        """Get compatible AMI types for a specific architecture."""
        if architecture == Architecture.ARM64:
            types = [AMIType.AL2023_ARM_64_NVIDIA]
        else:  # x86_64 or amd64
            types = [AMIType.AL2023_X86_64_NVIDIA, AMIType.AL2_X86_64_GPU]

        if not include_deprecated:
            types = [t for t in types if not self._compatibility_matrix[t].is_deprecated]

        return types
    
    def get_recommended_ami_type(self, architecture: Architecture, k8s_version: str = None) -> AMIType:
        """Get the recommended AMI type for an architecture and K8s version."""
        if architecture == Architecture.ARM64:
            return AMIType.AL2023_ARM_64_NVIDIA
        else:
            # Always recommend AL2023 for x86_64 (AL2 is deprecated)
            return AMIType.AL2023_X86_64_NVIDIA
    
    def is_ami_type_supported(self, ami_type: AMIType, k8s_version: str) -> bool:
        """Check if an AMI type supports a specific Kubernetes version."""
        compatibility = self._compatibility_matrix.get(ami_type)
        if not compatibility:
            return False
        
        return k8s_version in compatibility.kubernetes_versions
    
    def is_al2_supported(self, k8s_version: str) -> bool:
        """Check if AL2 AMIs are still supported for the given Kubernetes version."""
        try:
            version_parts = [int(x) for x in k8s_version.split('.')]
            last_supported = [int(x) for x in self.AL2_LAST_K8S_VERSION.split('.')]
            return version_parts <= last_supported
        except (ValueError, IndexError):
            return False
    
    def get_compatibility_info(self, ami_type: AMIType) -> AMICompatibility:
        """Get detailed compatibility information for an AMI type."""
        return self._compatibility_matrix.get(ami_type)
    
    def validate_ami_compatibility(self, ami_type: AMIType, k8s_version: str) -> tuple[bool, str]:
        """
        Validate AMI type compatibility with Kubernetes version.
        
        Returns:
            Tuple of (is_valid, warning_message)
        """
        compatibility = self.get_compatibility_info(ami_type)
        if not compatibility:
            return False, f"Unknown AMI type: {ami_type}"
        
        if k8s_version not in compatibility.kubernetes_versions:
            return False, f"AMI type {ami_type} does not support Kubernetes {k8s_version}"
        
        warning = ""
        if compatibility.is_deprecated:
            warning = f"AMI type {ami_type} is deprecated (EOL: {compatibility.deprecation_date})"
            if compatibility.replacement_ami_type:
                warning += f". Consider migrating to {compatibility.replacement_ami_type}"
        
        return True, warning
    
    def get_all_gpu_ami_types(self) -> List[AMIType]:
        """Get all GPU-enabled AMI types."""
        return [ami_type for ami_type in AMIType if ami_type.is_gpu_enabled]
    
    def get_column_names_for_ami_types(self, ami_types: List[AMIType]) -> List[str]:
        """Get the column names used in GitHub release tables for given AMI types."""
        return [ami_type.value for ami_type in ami_types]


# Convenience functions for backward compatibility
def get_ami_types_for_architecture(architecture: str) -> List[str]:
    """
    Backward compatible function that returns AMI type strings.
    
    Args:
        architecture: Architecture string (x86_64, amd64, arm64)
    
    Returns:
        List of AMI type strings
    """
    arch = Architecture.from_string(architecture)
    manager = AMITypeManager()
    ami_types = manager.get_ami_types_for_architecture(arch)
    return [ami_type.value for ami_type in ami_types]


def get_recommended_ami_type(architecture: str, k8s_version: str = None) -> str:
    """
    Backward compatible function that returns recommended AMI type string.
    
    Args:
        architecture: Architecture string (x86_64, amd64, arm64)
        k8s_version: Kubernetes version (optional)
    
    Returns:
        Recommended AMI type string
    """
    arch = Architecture.from_string(architecture)
    manager = AMITypeManager()
    ami_type = manager.get_recommended_ami_type(arch, k8s_version)
    return ami_type.value