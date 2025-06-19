"""
AWS EKS Client for nodegroup management operations.
"""

import boto3
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from botocore.exceptions import ClientError, NoCredentialsError
from models.ami_types import AMIType, Architecture, AMITypeManager


@dataclass
class NodegroupInfo:
    """Information about an EKS nodegroup."""
    cluster_name: str
    nodegroup_name: str
    status: str
    ami_type: str
    instance_types: List[str]
    scaling_config: Dict[str, int]
    disk_size: int
    node_role_arn: str
    subnets: List[str]
    capacity_type: str
    version: str
    labels: Dict[str, str]
    taints: List[Dict[str, Any]]
    tags: Dict[str, str]
    launch_template: Optional[Dict[str, Any]]
    remote_access: Optional[Dict[str, Any]]
    update_config: Optional[Dict[str, Any]]
    
    @property
    def architecture(self) -> str:
        """Determine architecture from AMI type."""
        if "ARM" in self.ami_type:
            return "arm64"
        return "x86_64"
    
    @property
    def is_gpu_nodegroup(self) -> bool:
        """Check if this is a GPU-enabled nodegroup."""
        return "GPU" in self.ami_type or "NVIDIA" in self.ami_type
    
    def to_template_dict(self) -> Dict[str, Any]:
        """Convert to nodegroup template format."""
        template = {
            "clusterName": self.cluster_name,
            "nodegroupName": self.nodegroup_name,
            "nodeRole": self.node_role_arn,
            "subnets": self.subnets,
            "instanceTypes": self.instance_types,
            "amiType": self.ami_type,
            "capacityType": self.capacity_type,
            "diskSize": self.disk_size,
            "scalingConfig": self.scaling_config,
            "labels": self.labels,
            "taints": self.taints,
            "tags": self.tags
        }
        
        if self.update_config:
            template["updateConfig"] = self.update_config
        
        if self.launch_template:
            template["launchTemplate"] = self.launch_template
            
        if self.remote_access:
            template["remoteAccess"] = self.remote_access
        
        return template


class EKSClientError(Exception):
    """Exception raised for EKS client errors."""
    pass


class EKSClient:
    """AWS EKS client for nodegroup operations."""
    
    def __init__(self, profile: str = None, region: str = None, verbose: bool = False):
        """
        Initialize EKS client.
        
        Args:
            profile: AWS profile to use
            region: AWS region
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        self.ami_manager = AMITypeManager()
        
        try:
            # Create session with profile if specified
            if profile:
                session = boto3.Session(profile_name=profile)
                self.eks_client = session.client('eks', region_name=region)
                self.ec2_client = session.client('ec2', region_name=region)
            else:
                self.eks_client = boto3.client('eks', region_name=region)
                self.ec2_client = boto3.client('ec2', region_name=region)
                
        except NoCredentialsError:
            raise EKSClientError("AWS credentials not found. Please configure your credentials.")
        except Exception as e:
            raise EKSClientError(f"Failed to initialize AWS clients: {e}")
    
    def log(self, message: str):
        """Print verbose logging messages."""
        if self.verbose:
            print(f"[EKS-CLIENT] {message}")
    
    def list_clusters(self) -> List[str]:
        """
        List all EKS clusters in the region.
        
        Returns:
            List of cluster names
        """
        try:
            self.log("Listing EKS clusters")
            response = self.eks_client.list_clusters()
            return response.get('clusters', [])
        except ClientError as e:
            raise EKSClientError(f"Failed to list clusters: {e}")
    
    def get_cluster_info(self, cluster_name: str) -> Dict[str, Any]:
        """
        Get cluster information.
        
        Args:
            cluster_name: Name of the cluster
            
        Returns:
            Cluster information dictionary
        """
        try:
            self.log(f"Getting cluster info for {cluster_name}")
            response = self.eks_client.describe_cluster(name=cluster_name)
            return response['cluster']
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                raise EKSClientError(f"Cluster '{cluster_name}' not found")
            raise EKSClientError(f"Failed to get cluster info: {e}")
    
    def list_nodegroups(self, cluster_name: str) -> List[str]:
        """
        List all nodegroups in a cluster.
        
        Args:
            cluster_name: Name of the cluster
            
        Returns:
            List of nodegroup names
        """
        try:
            self.log(f"Listing nodegroups for cluster {cluster_name}")
            response = self.eks_client.list_nodegroups(clusterName=cluster_name)
            return response.get('nodegroups', [])
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                raise EKSClientError(f"Cluster '{cluster_name}' not found")
            raise EKSClientError(f"Failed to list nodegroups: {e}")
    
    def get_nodegroup_info(self, cluster_name: str, nodegroup_name: str) -> NodegroupInfo:
        """
        Get detailed nodegroup information.
        
        Args:
            cluster_name: Name of the cluster
            nodegroup_name: Name of the nodegroup
            
        Returns:
            NodegroupInfo object
        """
        try:
            self.log(f"Getting nodegroup info for {cluster_name}/{nodegroup_name}")
            response = self.eks_client.describe_nodegroup(
                clusterName=cluster_name,
                nodegroupName=nodegroup_name
            )
            
            ng = response['nodegroup']
            
            return NodegroupInfo(
                cluster_name=cluster_name,
                nodegroup_name=nodegroup_name,
                status=ng.get('status', ''),
                ami_type=ng.get('amiType', ''),
                instance_types=ng.get('instanceTypes', []),
                scaling_config=ng.get('scalingConfig', {}),
                disk_size=ng.get('diskSize', 20),
                node_role_arn=ng.get('nodeRole', ''),
                subnets=ng.get('subnets', []),
                capacity_type=ng.get('capacityType', 'ON_DEMAND'),
                version=ng.get('version', ''),
                labels=ng.get('labels', {}),
                taints=ng.get('taints', []),
                tags=ng.get('tags', {}),
                launch_template=ng.get('launchTemplate'),
                remote_access=ng.get('remoteAccess'),
                update_config=ng.get('updateConfig')
            )
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                raise EKSClientError(f"Nodegroup '{nodegroup_name}' not found in cluster '{cluster_name}'")
            raise EKSClientError(f"Failed to get nodegroup info: {e}")
    
    def get_gpu_nodegroups(self, cluster_name: str) -> List[NodegroupInfo]:
        """
        Get all GPU-enabled nodegroups in a cluster.
        
        Args:
            cluster_name: Name of the cluster
            
        Returns:
            List of GPU nodegroups
        """
        gpu_nodegroups = []
        nodegroup_names = self.list_nodegroups(cluster_name)
        
        for ng_name in nodegroup_names:
            ng_info = self.get_nodegroup_info(cluster_name, ng_name)
            if ng_info.is_gpu_nodegroup:
                gpu_nodegroups.append(ng_info)
                self.log(f"Found GPU nodegroup: {ng_name} (AMI: {ng_info.ami_type})")
        
        return gpu_nodegroups
    
    def extract_nodegroup_configurations(self, cluster_name: str, 
                                       nodegroup_names: List[str] = None) -> List[NodegroupInfo]:
        """
        Extract configurations from existing nodegroups.
        
        Args:
            cluster_name: Name of the cluster
            nodegroup_names: Specific nodegroups to extract (None for all GPU nodegroups)
            
        Returns:
            List of nodegroup configurations
        """
        if nodegroup_names:
            # Extract specific nodegroups
            configurations = []
            for ng_name in nodegroup_names:
                ng_info = self.get_nodegroup_info(cluster_name, ng_name)
                configurations.append(ng_info)
        else:
            # Extract all GPU nodegroups
            configurations = self.get_gpu_nodegroups(cluster_name)
        
        self.log(f"Extracted {len(configurations)} nodegroup configurations")
        return configurations
    
    def validate_cluster_access(self, cluster_name: str) -> Tuple[bool, str]:
        """
        Validate access to a cluster.
        
        Args:
            cluster_name: Name of the cluster to validate
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            cluster_info = self.get_cluster_info(cluster_name)
            status = cluster_info.get('status', '')
            
            if status != 'ACTIVE':
                return False, f"Cluster '{cluster_name}' is not active (status: {status})"
            
            return True, f"Cluster '{cluster_name}' is accessible and active"
            
        except EKSClientError as e:
            return False, str(e)
    
    def get_recommended_ami_type(self, current_ami_type: str, k8s_version: str) -> Tuple[str, bool]:
        """
        Get recommended AMI type for a given current AMI type and Kubernetes version.
        
        Args:
            current_ami_type: Current AMI type
            k8s_version: Kubernetes version
            
        Returns:
            Tuple of (recommended_ami_type, needs_upgrade)
        """
        try:
            current_ami = AMIType(current_ami_type)
            architecture = current_ami.architecture
            
            # Get recommended AMI type for the architecture
            recommended_ami = self.ami_manager.get_recommended_ami_type(architecture, k8s_version)
            
            # Check if current AMI is deprecated
            compatibility = self.ami_manager.get_compatibility_info(current_ami)
            needs_upgrade = compatibility.is_deprecated if compatibility else False
            
            return recommended_ami.value, needs_upgrade
            
        except ValueError:
            # Unknown AMI type, return as-is
            return current_ami_type, False
    
    def validate_nodegroup_template(self, template: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate a nodegroup template configuration (read-only).
        
        Args:
            template: Nodegroup template dictionary
            
        Returns:
            Tuple of (is_valid, message)
        """
        # Validate template without creating anything
        required_fields = ['clusterName', 'nodegroupName', 'nodeRole', 'subnets']
        missing_fields = [field for field in required_fields if field not in template]
        
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"
        
        # Validate nodegroup name follows AWS EKS naming rules
        nodegroup_name = template.get('nodegroupName', '')
        if not self._validate_nodegroup_name(nodegroup_name):
            return False, f"Invalid nodegroup name '{nodegroup_name}': must be 1-63 characters, start with letter/digit, and contain only letters, digits, hyphens, and underscores"
        
        # Validate instance types are provided
        if not template.get('instanceTypes'):
            return False, "instanceTypes field is required"
            
        # Validate AMI type is supported
        ami_type = template.get('amiType', '')
        if ami_type not in ['AL2023_x86_64_NVIDIA', 'AL2_x86_64_GPU', 'AL2023_ARM_64_NVIDIA']:
            return False, f"Unsupported AMI type: {ami_type}"
        
        return True, f"Template validation successful for nodegroup '{template['nodegroupName']}'"
    
    def _validate_nodegroup_name(self, name: str) -> bool:
        """
        Validate nodegroup name against AWS EKS naming rules.
        
        Args:
            name: Nodegroup name to validate
            
        Returns:
            True if valid, False otherwise
        """
        import re
        
        # AWS EKS nodegroup name rules:
        # - 1-63 characters
        # - Must start with letter or digit
        # - Can contain letters, digits, hyphens, and underscores
        if not name or len(name) > 63:
            return False
        
        # Regex pattern: start with letter/digit, followed by 0-62 chars of letters/digits/hyphens/underscores
        pattern = r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$'
        return bool(re.match(pattern, name))
    
