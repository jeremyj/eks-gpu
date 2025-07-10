"""
NodeGroup configuration models and utilities.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from models.ami_types import AMIType, Architecture
import json


@dataclass
class ScalingConfig:
    """NodeGroup scaling configuration."""
    min_size: int = 0
    max_size: int = 10
    desired_size: int = 1
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to AWS CLI format."""
        return {
            "minSize": self.min_size,
            "maxSize": self.max_size,
            "desiredSize": self.desired_size
        }
    
    def validate(self) -> tuple[bool, List[str]]:
        """Validate scaling configuration."""
        issues = []
        
        if self.min_size < 0:
            issues.append("min_size cannot be negative")
        
        if self.max_size < 1:
            issues.append("max_size must be at least 1")
        
        if self.desired_size < 0:
            issues.append("desired_size cannot be negative")
        
        if self.min_size > self.max_size:
            issues.append("min_size cannot be greater than max_size")
        
        if self.desired_size < self.min_size:
            issues.append("desired_size cannot be less than min_size")
        
        if self.desired_size > self.max_size:
            issues.append("desired_size cannot be greater than max_size")
        
        return len(issues) == 0, issues


@dataclass
class UpdateConfig:
    """NodeGroup update configuration."""
    max_unavailable: Optional[int] = 1
    max_unavailable_percentage: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to AWS CLI format."""
        config = {}
        if self.max_unavailable is not None:
            config["maxUnavailable"] = self.max_unavailable
        if self.max_unavailable_percentage is not None:
            config["maxUnavailablePercentage"] = self.max_unavailable_percentage
        return config
    
    def validate(self) -> tuple[bool, List[str]]:
        """Validate update configuration."""
        issues = []
        
        if self.max_unavailable is not None and self.max_unavailable < 1:
            issues.append("max_unavailable must be at least 1")
        
        if self.max_unavailable_percentage is not None:
            if self.max_unavailable_percentage < 1 or self.max_unavailable_percentage > 100:
                issues.append("max_unavailable_percentage must be between 1 and 100")
        
        if self.max_unavailable is not None and self.max_unavailable_percentage is not None:
            issues.append("Cannot specify both max_unavailable and max_unavailable_percentage")
        
        return len(issues) == 0, issues


@dataclass
class RemoteAccess:
    """NodeGroup remote access configuration."""
    ec2_ssh_key: Optional[str] = None
    source_security_groups: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to AWS CLI format."""
        config = {}
        if self.ec2_ssh_key:
            config["ec2SshKey"] = self.ec2_ssh_key
        if self.source_security_groups:
            config["sourceSecurityGroups"] = self.source_security_groups
        return config


@dataclass
class Taint:
    """Kubernetes taint for nodegroup."""
    key: str
    value: Optional[str] = None
    effect: str = "NO_SCHEDULE"  # NO_SCHEDULE, NO_EXECUTE, PREFER_NO_SCHEDULE
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to AWS CLI format."""
        taint = {
            "key": self.key,
            "effect": self.effect
        }
        if self.value:
            taint["value"] = self.value
        return taint
    
    def validate(self) -> tuple[bool, List[str]]:
        """Validate taint configuration."""
        issues = []
        
        if not self.key:
            issues.append("Taint key is required")
        
        valid_effects = ["NO_SCHEDULE", "NO_EXECUTE", "PREFER_NO_SCHEDULE"]
        if self.effect not in valid_effects:
            issues.append(f"Invalid taint effect: {self.effect}. Must be one of {valid_effects}")
        
        return len(issues) == 0, issues


@dataclass
class NodeGroupConfig:
    """
    Complete EKS NodeGroup configuration.
    
    This class represents all the configuration needed to create an EKS nodegroup,
    with validation and conversion to AWS CLI format.
    """
    cluster_name: str
    nodegroup_name: str
    node_role: str
    subnets: List[str]
    
    # AMI and instance configuration
    ami_type: Optional[str] = None
    instance_types: List[str] = field(default_factory=lambda: ["m5.large"])
    capacity_type: str = "ON_DEMAND"  # ON_DEMAND or SPOT
    disk_size: int = 20
    
    # Kubernetes configuration
    version: Optional[str] = None
    release_version: Optional[str] = None
    
    # Scaling and update configuration
    scaling_config: ScalingConfig = field(default_factory=ScalingConfig)
    update_config: UpdateConfig = field(default_factory=UpdateConfig)
    
    # Network and access
    remote_access: RemoteAccess = field(default_factory=RemoteAccess)
    
    # Labeling and scheduling
    labels: Dict[str, str] = field(default_factory=dict)
    taints: List[Taint] = field(default_factory=list)
    
    # Resource tags
    tags: Dict[str, str] = field(default_factory=dict)
    
    def set_gpu_defaults(self, architecture: Architecture):
        """Set GPU-specific defaults for the nodegroup."""
        # Set default GPU instance types based on architecture
        if architecture == Architecture.ARM64:
            self.instance_types = ["g5g.xlarge"]
            self.labels["kubernetes.io/arch"] = "arm64"
        else:
            self.instance_types = ["g4dn.xlarge"]
            self.labels["kubernetes.io/arch"] = "amd64"
        
        # Set GPU-specific labels
        self.labels.update({
            "node-type": "gpu-worker",
            "nvidia.com/gpu": "true"
        })
        
        # Set GPU-specific tags
        self.tags.update({
            "NodeType": "GPU",
            "ManagedBy": "eks-nvidia-alignment-tool"
        })
        
        # Increase disk size for GPU instances
        if self.disk_size == 20:  # Only if still default
            self.disk_size = 50
    
    def set_ami_configuration(self, ami_type: AMIType, k8s_version: str, release_version: str):
        """Set AMI-related configuration."""
        self.ami_type = ami_type.value
        self.version = k8s_version
        self.release_version = f"{k8s_version}-{release_version}"
    
    def validate(self) -> tuple[bool, List[str]]:
        """
        Validate the complete nodegroup configuration.
        
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Check required fields
        if not self.cluster_name:
            issues.append("cluster_name is required")
        
        if not self.nodegroup_name:
            issues.append("nodegroup_name is required")
        
        if not self.node_role:
            issues.append("node_role is required")
        
        if not self.subnets:
            issues.append("subnets list is required")
        elif len(self.subnets) < 1:
            issues.append("At least one subnet is required")
        
        # Validate instance configuration
        if not self.instance_types:
            issues.append("instance_types list is required")
        
        if self.capacity_type not in ["ON_DEMAND", "SPOT"]:
            issues.append("capacity_type must be ON_DEMAND or SPOT")
        
        if self.disk_size < 1:
            issues.append("disk_size must be at least 1 GB")
        
        # Validate nested configurations
        scaling_valid, scaling_issues = self.scaling_config.validate()
        if not scaling_valid:
            issues.extend([f"Scaling config: {issue}" for issue in scaling_issues])
        
        update_valid, update_issues = self.update_config.validate()
        if not update_valid:
            issues.extend([f"Update config: {issue}" for issue in update_issues])
        
        # Validate taints
        for i, taint in enumerate(self.taints):
            taint_valid, taint_issues = taint.validate()
            if not taint_valid:
                issues.extend([f"Taint {i}: {issue}" for issue in taint_issues])
        
        # Validate AWS resource ARN format
        if self.node_role and not self.node_role.startswith("arn:aws:iam::"):
            issues.append("node_role should be a valid IAM role ARN")
        
        # Validate subnet format
        for subnet in self.subnets:
            if not subnet.startswith("subnet-"):
                issues.append(f"Invalid subnet format: {subnet}")
        
        return len(issues) == 0, issues
    
    def to_aws_cli_format(self) -> Dict[str, Any]:
        """
        Convert to AWS CLI create-nodegroup format.
        
        Returns:
            Dictionary in AWS CLI JSON input format
        """
        config = {
            "clusterName": self.cluster_name,
            "nodegroupName": self.nodegroup_name,
            "instanceTypes": self.instance_types,
            "nodeRole": self.node_role,
            "subnets": self.subnets,
            "capacityType": self.capacity_type,
            "scalingConfig": self.scaling_config.to_dict(),
            "labels": self.labels
        }
        
        # Add optional fields if they have values
        if self.ami_type:
            config["amiType"] = self.ami_type
        
        if self.version:
            config["version"] = self.version
        
        if self.release_version:
            config["releaseVersion"] = self.release_version
        
        if self.disk_size != 20:  # Only include if not default
            config["diskSize"] = self.disk_size
        
        # Add update config if not default
        update_config_dict = self.update_config.to_dict()
        if update_config_dict:
            config["updateConfig"] = update_config_dict
        
        # Add remote access if configured
        remote_access_dict = self.remote_access.to_dict()
        if remote_access_dict:
            config["remoteAccess"] = remote_access_dict
        
        # Add taints if any
        if self.taints:
            config["taints"] = [taint.to_dict() for taint in self.taints]
        
        # Add tags if any
        if self.tags:
            config["tags"] = self.tags
        
        return config
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string in AWS CLI format."""
        return json.dumps(self.to_aws_cli_format(), indent=indent)
    
    def save_to_file(self, filename: str, indent: int = 2):
        """Save configuration to JSON file."""
        with open(filename, 'w') as f:
            json.dump(self.to_aws_cli_format(), f, indent=indent)
    
    @classmethod
    def from_template_file(cls, template_path: str) -> 'NodeGroupConfig':
        """
        Load configuration from a JSON template file.
        
        Args:
            template_path: Path to JSON template file
            
        Returns:
            NodeGroupConfig instance
        """
        with open(template_path, 'r') as f:
            data = json.load(f)
        
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NodeGroupConfig':
        """
        Create NodeGroupConfig from dictionary.
        
        Args:
            data: Dictionary containing configuration data
            
        Returns:
            NodeGroupConfig instance
        """
        # Extract scaling config
        scaling_data = data.get('scalingConfig', {})
        scaling_config = ScalingConfig(
            min_size=scaling_data.get('minSize', 0),
            max_size=scaling_data.get('maxSize', 10),
            desired_size=scaling_data.get('desiredSize', 1)
        )
        
        # Extract update config
        update_data = data.get('updateConfig', {})
        update_config = UpdateConfig(
            max_unavailable=update_data.get('maxUnavailable'),
            max_unavailable_percentage=update_data.get('maxUnavailablePercentage')
        )
        
        # Extract remote access config
        remote_data = data.get('remoteAccess', {})
        remote_access = RemoteAccess(
            ec2_ssh_key=remote_data.get('ec2SshKey'),
            source_security_groups=remote_data.get('sourceSecurityGroups', [])
        )
        
        # Extract taints
        taints_data = data.get('taints', [])
        taints = [
            Taint(
                key=taint['key'],
                value=taint.get('value'),
                effect=taint.get('effect', 'NO_SCHEDULE')
            )
            for taint in taints_data
        ]
        
        return cls(
            cluster_name=data['clusterName'],
            nodegroup_name=data['nodegroupName'],
            node_role=data['nodeRole'],
            subnets=data['subnets'],
            ami_type=data.get('amiType'),
            instance_types=data.get('instanceTypes', ['m5.large']),
            capacity_type=data.get('capacityType', 'ON_DEMAND'),
            disk_size=data.get('diskSize', 20),
            version=data.get('version'),
            release_version=data.get('releaseVersion'),
            scaling_config=scaling_config,
            update_config=update_config,
            remote_access=remote_access,
            labels=data.get('labels', {}),
            taints=taints,
            tags=data.get('tags', {})
        )
    
    def merge_overrides(self, overrides: Dict[str, Any]) -> 'NodeGroupConfig':
        """
        Create a new NodeGroupConfig with overrides applied.
        
        Args:
            overrides: Dictionary of values to override
            
        Returns:
            New NodeGroupConfig instance with overrides applied
        """
        # Convert current config to dict
        current_data = self.to_aws_cli_format()
        
        # Apply overrides
        for key, value in overrides.items():
            if key == "labels" and key in current_data and isinstance(current_data[key], dict) and isinstance(value, dict):
                # Merge labels instead of replacing
                current_data[key].update(value)
            elif key == "scalingConfig" and isinstance(value, dict):
                # Merge scaling config
                if "scalingConfig" not in current_data:
                    current_data["scalingConfig"] = {}
                current_data["scalingConfig"].update(value)
            else:
                current_data[key] = value
        
        # Create new instance from merged data
        return self.from_dict(current_data)


class NodeGroupConfigBuilder:
    """Builder class for creating NodeGroup configurations."""
    
    def __init__(self):
        self.config = NodeGroupConfig(
            cluster_name="",
            nodegroup_name="",
            node_role="",
            subnets=[]
        )
    
    def cluster_name(self, name: str) -> 'NodeGroupConfigBuilder':
        """Set cluster name."""
        self.config.cluster_name = name
        return self
    
    def nodegroup_name(self, name: str) -> 'NodeGroupConfigBuilder':
        """Set nodegroup name."""
        self.config.nodegroup_name = name
        return self
    
    def node_role(self, role_arn: str) -> 'NodeGroupConfigBuilder':
        """Set node IAM role ARN."""
        self.config.node_role = role_arn
        return self
    
    def subnets(self, subnet_ids: List[str]) -> 'NodeGroupConfigBuilder':
        """Set subnet IDs."""
        self.config.subnets = subnet_ids
        return self
    
    def gpu_config(self, architecture: Architecture) -> 'NodeGroupConfigBuilder':
        """Configure for GPU instances."""
        self.config.set_gpu_defaults(architecture)
        return self
    
    def ami_config(self, ami_type: AMIType, k8s_version: str, release_version: str) -> 'NodeGroupConfigBuilder':
        """Set AMI configuration."""
        self.config.set_ami_configuration(ami_type, k8s_version, release_version)
        return self
    
    def scaling(self, min_size: int, max_size: int, desired_size: int) -> 'NodeGroupConfigBuilder':
        """Set scaling configuration."""
        self.config.scaling_config = ScalingConfig(min_size, max_size, desired_size)
        return self
    
    def instance_types(self, types: List[str]) -> 'NodeGroupConfigBuilder':
        """Set instance types."""
        self.config.instance_types = types
        return self
    
    def capacity_type(self, capacity: str) -> 'NodeGroupConfigBuilder':
        """Set capacity type (ON_DEMAND or SPOT)."""
        self.config.capacity_type = capacity
        return self
    
    def labels(self, labels: Dict[str, str]) -> 'NodeGroupConfigBuilder':
        """Set or update labels."""
        self.config.labels.update(labels)
        return self
    
    def tags(self, tags: Dict[str, str]) -> 'NodeGroupConfigBuilder':
        """Set or update tags."""
        self.config.tags.update(tags)
        return self
    
    def build(self) -> NodeGroupConfig:
        """Build the final configuration."""
        return self.config