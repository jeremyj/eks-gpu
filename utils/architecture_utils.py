"""
Architecture-specific utilities and mappings.
"""

from typing import Dict, List, Optional, Set, Tuple
from models.ami_types import Architecture, AMIType
from dataclasses import dataclass


@dataclass
class ArchitectureInfo:
    """Information about a specific architecture."""
    architecture: Architecture
    display_name: str
    common_aliases: List[str]
    default_gpu_instances: List[str]
    default_cpu_instances: List[str]
    package_suffix: str
    nvidia_repo_path: str
    supported_ami_types: List[AMIType]
    
    @property
    def is_arm_based(self) -> bool:
        """Check if this is an ARM-based architecture."""
        return self.architecture == Architecture.ARM64
    
    @property
    def is_x86_based(self) -> bool:
        """Check if this is an x86-based architecture."""
        return self.architecture in [Architecture.X86_64, Architecture.AMD64]


class ArchitectureManager:
    """Manager for architecture-specific operations and mappings."""
    
    def __init__(self):
        self._arch_info = self._build_architecture_info()
    
    def _build_architecture_info(self) -> Dict[Architecture, ArchitectureInfo]:
        """Build comprehensive architecture information."""
        return {
            Architecture.X86_64: ArchitectureInfo(
                architecture=Architecture.X86_64,
                display_name="x86_64",
                common_aliases=["amd64", "x86_64", "intel"],
                default_gpu_instances=["g4dn.xlarge", "g4dn.2xlarge", "g5.xlarge", "g5.2xlarge"],
                default_cpu_instances=["m5.large", "m5.xlarge", "c5.large", "c5.xlarge"],
                package_suffix="amd64",
                nvidia_repo_path="x86_64",
                supported_ami_types=[AMIType.AL2023_X86_64_NVIDIA, AMIType.AL2_X86_64_GPU]
            ),
            Architecture.ARM64: ArchitectureInfo(
                architecture=Architecture.ARM64,
                display_name="ARM64",
                common_aliases=["arm64", "aarch64", "graviton"],
                default_gpu_instances=["g5g.xlarge", "g5g.2xlarge", "g5g.4xlarge"],
                default_cpu_instances=["m6g.large", "m6g.xlarge", "c6g.large", "c6g.xlarge"],
                package_suffix="arm64",
                nvidia_repo_path="sbsa",  # Server Base System Architecture
                supported_ami_types=[AMIType.AL2023_ARM_64_NVIDIA]
            )
        }
    
    def get_architecture_info(self, architecture: Architecture) -> ArchitectureInfo:
        """Get comprehensive information about an architecture."""
        return self._arch_info.get(architecture)
    
    def normalize_architecture_string(self, arch_string: str) -> str:
        """
        Normalize architecture string to canonical form.
        
        Args:
            arch_string: Architecture string (various formats)
            
        Returns:
            Normalized architecture string
        """
        try:
            arch = Architecture.from_string(arch_string)
            return arch.normalized_name
        except ValueError:
            return arch_string.lower()
    
    def detect_architecture_from_instance_type(self, instance_type: str) -> Optional[Architecture]:
        """
        Detect architecture from EC2 instance type.
        
        Args:
            instance_type: EC2 instance type (e.g., "g5g.xlarge")
            
        Returns:
            Detected architecture or None if unknown
        """
        # ARM64/Graviton instance patterns
        arm64_patterns = [
            "g5g.",    # Graviton GPU instances
            "c6g.", "c6gd.", "c6gn.",  # Graviton compute
            "m6g.", "m6gd.",           # Graviton general purpose
            "r6g.", "r6gd.",           # Graviton memory optimized
            "t4g.",                    # Graviton burstable
            "x2gd.",                   # Graviton memory optimized
            "im4gn.", "is4gen.",       # Graviton storage optimized
        ]
        
        instance_lower = instance_type.lower()
        
        # Check for ARM64 patterns
        for pattern in arm64_patterns:
            if instance_lower.startswith(pattern):
                return Architecture.ARM64
        
        # Default to x86_64 for known EC2 patterns
        if "." in instance_type and len(instance_type.split(".")) == 2:
            return Architecture.X86_64
        
        return None
    
    def validate_instance_types_for_architecture(self, instance_types: List[str], 
                                               architecture: Architecture) -> Tuple[bool, List[str]]:
        """
        Validate that instance types are compatible with architecture.
        
        Args:
            instance_types: List of EC2 instance types
            architecture: Target architecture
            
        Returns:
            Tuple of (all_compatible, list_of_issues)
        """
        issues = []
        
        for instance_type in instance_types:
            detected_arch = self.detect_architecture_from_instance_type(instance_type)
            
            if detected_arch and detected_arch != architecture:
                arch_name = detected_arch.display_name
                target_name = architecture.display_name
                issues.append(f"Instance type {instance_type} is {arch_name} but target architecture is {target_name}")
        
        return len(issues) == 0, issues
    
    def get_recommended_gpu_instances(self, architecture: Architecture, 
                                    performance_tier: str = "standard") -> List[str]:
        """
        Get recommended GPU instance types for architecture.
        
        Args:
            architecture: Target architecture
            performance_tier: "basic", "standard", "high", "extreme"
            
        Returns:
            List of recommended instance types
        """
        arch_info = self.get_architecture_info(architecture)
        if not arch_info:
            return []
        
        if architecture == Architecture.ARM64:
            tiers = {
                "basic": ["g5g.xlarge"],
                "standard": ["g5g.xlarge", "g5g.2xlarge"],
                "high": ["g5g.2xlarge", "g5g.4xlarge"],
                "extreme": ["g5g.4xlarge", "g5g.8xlarge", "g5g.16xlarge"]
            }
        else:  # x86_64
            tiers = {
                "basic": ["g4dn.xlarge"],
                "standard": ["g4dn.xlarge", "g5.xlarge"],
                "high": ["g5.xlarge", "g5.2xlarge", "g4dn.2xlarge"],
                "extreme": ["g5.4xlarge", "g5.8xlarge", "g5.12xlarge", "p3.2xlarge"]
            }
        
        return tiers.get(performance_tier, tiers["standard"])
    
    def get_nvidia_repository_config(self, architecture: Architecture, 
                                   ubuntu_version: str = "ubuntu2204") -> Dict[str, str]:
        """
        Get NVIDIA repository configuration for architecture.
        
        Args:
            architecture: Target architecture
            ubuntu_version: Ubuntu version (e.g., "ubuntu2204")
            
        Returns:
            Dictionary with repository configuration
        """
        arch_info = self.get_architecture_info(architecture)
        if not arch_info:
            return {}
        
        return {
            "base_url": f"https://developer.download.nvidia.com/compute/cuda/repos/{ubuntu_version}/{arch_info.nvidia_repo_path}/",
            "repo_path": arch_info.nvidia_repo_path,
            "package_suffix": arch_info.package_suffix,
            "architecture": architecture.value,
            "ubuntu_version": ubuntu_version
        }
    
    def get_container_platform_string(self, architecture: Architecture) -> str:
        """
        Get Docker/container platform string for architecture.
        
        Args:
            architecture: Target architecture
            
        Returns:
            Platform string for container builds
        """
        if architecture == Architecture.ARM64:
            return "linux/arm64"
        else:
            return "linux/amd64"
    
    def get_architecture_labels(self, architecture: Architecture) -> Dict[str, str]:
        """
        Get Kubernetes labels for architecture.
        
        Args:
            architecture: Target architecture
            
        Returns:
            Dictionary of Kubernetes labels
        """
        arch_info = self.get_architecture_info(architecture)
        if not arch_info:
            return {}
        
        labels = {
            "kubernetes.io/arch": arch_info.package_suffix,
            "node.kubernetes.io/instance-type": "gpu"
        }
        
        if architecture == Architecture.ARM64:
            labels.update({
                "eks.amazonaws.com/compute-type": "graviton",
                "hardware.aws/graviton": "true"
            })
        
        return labels
    
    def get_cross_architecture_compatibility(self) -> Dict[str, List[str]]:
        """
        Get compatibility matrix for cross-architecture scenarios.
        
        Returns:
            Dictionary mapping scenarios to compatible architectures
        """
        return {
            "multi_arch_clusters": ["x86_64", "arm64"],
            "container_registries": ["x86_64", "arm64"],
            "shared_storage": ["x86_64", "arm64"],
            "networking": ["x86_64", "arm64"],
            "nvidia_drivers": ["x86_64", "arm64"],  # Both support NVIDIA
            "kubernetes_versions": ["x86_64", "arm64"]
        }
    
    def analyze_mixed_architecture_deployment(self, configurations: List[Dict]) -> Dict:
        """
        Analyze a mixed-architecture deployment configuration.
        
        Args:
            configurations: List of nodegroup configurations
            
        Returns:
            Analysis results with recommendations
        """
        architectures_used = set()
        instance_types_by_arch = {}
        issues = []
        recommendations = []
        
        for config in configurations:
            # Extract architecture from instance types or explicit config
            arch_str = config.get("architecture", "x86_64")
            try:
                arch = Architecture.from_string(arch_str)
                architectures_used.add(arch)
                
                # Analyze instance types
                instance_types = config.get("instance_types", [])
                for instance_type in instance_types:
                    detected_arch = self.detect_architecture_from_instance_type(instance_type)
                    if detected_arch:
                        if detected_arch not in instance_types_by_arch:
                            instance_types_by_arch[detected_arch] = []
                        instance_types_by_arch[detected_arch].append(instance_type)
                        
                        # Check for mismatches
                        if detected_arch != arch:
                            issues.append(
                                f"Instance type {instance_type} ({detected_arch.value}) "
                                f"doesn't match declared architecture {arch.value}"
                            )
            
            except ValueError as e:
                issues.append(f"Invalid architecture in configuration: {e}")
        
        # Generate recommendations
        if len(architectures_used) > 1:
            recommendations.append("Multi-architecture deployment detected")
            recommendations.append("Ensure container images support all target architectures")
            recommendations.append("Use multi-arch container registries")
            recommendations.append("Test application scheduling across architectures")
        
        if Architecture.ARM64 in architectures_used:
            recommendations.append("ARM64 instances detected - verify NVIDIA driver compatibility")
            recommendations.append("Consider cost savings with Graviton instances")
        
        return {
            "architectures_used": [arch.value for arch in architectures_used],
            "instance_types_by_architecture": {
                arch.value: types for arch, types in instance_types_by_arch.items()
            },
            "is_multi_architecture": len(architectures_used) > 1,
            "issues": issues,
            "recommendations": recommendations
        }


class InstanceTypeAnalyzer:
    """Analyzer for EC2 instance type characteristics."""
    
    # GPU instance families
    GPU_FAMILIES = {
        "g4dn": {"architecture": "x86_64", "gpu": "T4", "generation": "current"},
        "g5": {"architecture": "x86_64", "gpu": "A10G", "generation": "current"},
        "g5g": {"architecture": "arm64", "gpu": "T4G", "generation": "current"},
        "p3": {"architecture": "x86_64", "gpu": "V100", "generation": "previous"},
        "p4": {"architecture": "x86_64", "gpu": "A100", "generation": "current"},
        "g3": {"architecture": "x86_64", "gpu": "M60", "generation": "legacy"},
        "g2": {"architecture": "x86_64", "gpu": "GRID K520", "generation": "legacy"}
    }
    
    @classmethod
    def analyze_instance_type(cls, instance_type: str) -> Dict:
        """
        Analyze an EC2 instance type for GPU and architecture characteristics.
        
        Args:
            instance_type: EC2 instance type (e.g., "g5g.xlarge")
            
        Returns:
            Dictionary with analysis results
        """
        if "." not in instance_type:
            return {"error": "Invalid instance type format"}
        
        family, size = instance_type.split(".", 1)
        
        # Check if it's a known GPU family
        gpu_info = cls.GPU_FAMILIES.get(family)
        
        # Detect architecture
        arch_manager = ArchitectureManager()
        detected_arch = arch_manager.detect_architecture_from_instance_type(instance_type)
        
        return {
            "instance_type": instance_type,
            "family": family,
            "size": size,
            "is_gpu_instance": gpu_info is not None,
            "gpu_info": gpu_info,
            "architecture": detected_arch.value if detected_arch else "unknown",
            "is_graviton": detected_arch == Architecture.ARM64 if detected_arch else False,
            "is_current_generation": gpu_info.get("generation") == "current" if gpu_info else None
        }
    
    @classmethod
    def recommend_alternatives(cls, instance_type: str, target_architecture: Architecture = None) -> List[str]:
        """
        Recommend alternative instance types.
        
        Args:
            instance_type: Current instance type
            target_architecture: Target architecture for alternatives
            
        Returns:
            List of recommended alternative instance types
        """
        analysis = cls.analyze_instance_type(instance_type)
        
        if not analysis.get("is_gpu_instance"):
            return []
        
        alternatives = []
        current_family = analysis["family"]
        
        # Architecture-specific recommendations
        if target_architecture == Architecture.ARM64:
            if current_family in ["g4dn", "g5"]:
                alternatives.extend(["g5g.xlarge", "g5g.2xlarge"])
        elif target_architecture == Architecture.X86_64:
            if current_family == "g5g":
                alternatives.extend(["g5.xlarge", "g5.2xlarge", "g4dn.xlarge"])
        
        # Performance-based recommendations
        if current_family == "g4dn":
            alternatives.extend(["g5.xlarge", "g5.2xlarge"])  # Newer generation
        elif current_family == "g3":
            alternatives.extend(["g4dn.xlarge", "g5.xlarge"])  # Much newer
        
        return list(set(alternatives))  # Remove duplicates


# Convenience functions for backward compatibility
def get_ami_types_for_architecture(architecture: str) -> List[str]:
    """
    Legacy function: Get AMI types for architecture string.
    
    Args:
        architecture: Architecture string
        
    Returns:
        List of AMI type strings
    """
    try:
        arch = Architecture.from_string(architecture)
        manager = ArchitectureManager()
        arch_info = manager.get_architecture_info(arch)
        if arch_info:
            return [ami_type.value for ami_type in arch_info.supported_ami_types]
        return []
    except ValueError:
        return []


def get_nvidia_repo_path(architecture: str) -> str:
    """
    Legacy function: Get NVIDIA repository path for architecture.
    
    Args:
        architecture: Architecture string
        
    Returns:
        NVIDIA repository path
    """
    try:
        arch = Architecture.from_string(architecture)
        manager = ArchitectureManager()
        arch_info = manager.get_architecture_info(arch)
        return arch_info.nvidia_repo_path if arch_info else "x86_64"
    except ValueError:
        return "x86_64"


def get_package_suffix(architecture: str) -> str:
    """
    Legacy function: Get package suffix for architecture.
    
    Args:
        architecture: Architecture string
        
    Returns:
        Package suffix (amd64 or arm64)
    """
    try:
        arch = Architecture.from_string(architecture)
        manager = ArchitectureManager()
        arch_info = manager.get_architecture_info(arch)
        return arch_info.package_suffix if arch_info else "amd64"
    except ValueError:
        return "amd64"


def normalize_architecture(architecture: str) -> str:
    """
    Legacy function: Normalize architecture string.
    
    Args:
        architecture: Architecture string in various formats
        
    Returns:
        Normalized architecture string
    """
    manager = ArchitectureManager()
    return manager.normalize_architecture_string(architecture)