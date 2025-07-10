"""
Template loading, merging, and validation utilities - FIXED VERSION
"""

import json
import os
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
from models.nodegroup_config import NodeGroupConfig
from models.ami_types import Architecture
from .path_utils import get_template_path, get_output_path, find_template_file


class TemplateError(Exception):
    """Exception raised for template-related errors."""
    pass


class TemplateValidator:
    """Validator for nodegroup templates."""
    
    # Required fields in a valid template
    REQUIRED_FIELDS = {
        "clusterName": str,
        "nodegroupName": str,
        "nodeRole": str,
        "subnets": list
    }
    
    # Optional fields with expected types
    OPTIONAL_FIELDS = {
        "instanceTypes": list,
        "amiType": str,
        "version": str,
        "releaseVersion": str,
        "capacityType": str,
        "diskSize": int,
        "scalingConfig": dict,
        "updateConfig": dict,
        "remoteAccess": dict,
        "labels": dict,
        "taints": list,
        "tags": dict
    }
    
    @classmethod
    def validate_template(cls, template: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate a nodegroup template structure.
        
        Args:
            template: Template dictionary to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Check required fields
        for field, expected_type in cls.REQUIRED_FIELDS.items():
            if field not in template:
                issues.append(f"Missing required field: {field}")
            elif not isinstance(template[field], expected_type):
                issues.append(f"Field {field} must be of type {expected_type.__name__}")
            elif expected_type == list and len(template[field]) == 0:
                issues.append(f"Field {field} cannot be empty")
        
        # Check optional fields if present
        for field, expected_type in cls.OPTIONAL_FIELDS.items():
            if field in template and not isinstance(template[field], expected_type):
                issues.append(f"Field {field} must be of type {expected_type.__name__}")
        
        # Validate specific field contents
        issues.extend(cls._validate_field_contents(template))
        
        return len(issues) == 0, issues
    
    @classmethod
    def _validate_field_contents(cls, template: Dict[str, Any]) -> List[str]:
        """Validate specific field contents and formats."""
        issues = []
        
        # Validate node role ARN format
        node_role = template.get("nodeRole")
        if node_role and not node_role.startswith("arn:aws:iam::"):
            issues.append("nodeRole should be a valid IAM role ARN (arn:aws:iam::ACCOUNT:role/ROLE)")
        
        # Validate subnet format
        subnets = template.get("subnets", [])
        for subnet in subnets:
            if not isinstance(subnet, str) or not subnet.startswith("subnet-"):
                issues.append(f"Invalid subnet format: {subnet} (should start with 'subnet-')")
        
        # Validate capacity type
        capacity_type = template.get("capacityType")
        if capacity_type and capacity_type not in ["ON_DEMAND", "SPOT"]:
            issues.append("capacityType must be 'ON_DEMAND' or 'SPOT'")
        
        # Validate scaling config
        scaling_config = template.get("scalingConfig", {})
        if scaling_config:
            min_size = scaling_config.get("minSize", 0)
            max_size = scaling_config.get("maxSize", 0)
            desired_size = scaling_config.get("desiredSize", 0)
            
            if min_size < 0:
                issues.append("scalingConfig.minSize cannot be negative")
            if max_size < 1:
                issues.append("scalingConfig.maxSize must be at least 1")
            if desired_size < 0:
                issues.append("scalingConfig.desiredSize cannot be negative")
            if min_size > max_size:
                issues.append("scalingConfig.minSize cannot be greater than maxSize")
            if desired_size < min_size or desired_size > max_size:
                issues.append("scalingConfig.desiredSize must be between minSize and maxSize")
        
        # Validate instance types
        instance_types = template.get("instanceTypes", [])
        if instance_types:
            for instance_type in instance_types:
                if not isinstance(instance_type, str) or "." not in instance_type:
                    issues.append(f"Invalid instance type format: {instance_type}")
        
        return issues


class TemplateMerger:
    """Utility for merging template configurations."""
    
    @staticmethod
    def merge_configs(base: Dict[str, Any], overrides: Dict[str, Any], 
                     deep_merge_keys: List[str] = None) -> Dict[str, Any]:
        """
        Merge two configuration dictionaries.
        
        Args:
            base: Base configuration dictionary
            overrides: Override values to apply
            deep_merge_keys: Keys that should be deep-merged instead of replaced
            
        Returns:
            Merged configuration dictionary
        """
        if deep_merge_keys is None:
            deep_merge_keys = ["labels", "tags", "scalingConfig", "updateConfig"]
        
        result = base.copy()
        
        for key, value in overrides.items():
            if key in deep_merge_keys and key in result:
                if isinstance(result[key], dict) and isinstance(value, dict):
                    # Deep merge dictionaries
                    result[key] = {**result[key], **value}
                elif isinstance(result[key], list) and isinstance(value, list):
                    # Merge lists (extend)
                    result[key] = result[key] + value
                else:
                    # Replace if types don't match
                    result[key] = value
            else:
                # Replace value
                result[key] = value
        
        return result
    
    @staticmethod
    def apply_architecture_specific_overrides(template: Dict[str, Any], 
                                            architecture: Architecture) -> Dict[str, Any]:
        """
        Apply architecture-specific overrides to a template.
        
        Args:
            template: Base template
            architecture: Target architecture
            
        Returns:
            Template with architecture-specific modifications
        """
        from utils.architecture_utils import ArchitectureManager
        
        result = template.copy()
        arch_manager = ArchitectureManager()
        
        # Get architecture-specific information
        arch_info = arch_manager.get_architecture_info(architecture)
        if not arch_info:
            return result
        
        # Update instance types if they're generic or incompatible
        current_instances = result.get("instanceTypes", [])
        if not current_instances or any("m5.large" in inst or "t3.medium" in inst for inst in current_instances):
            # Replace with architecture-appropriate GPU instances
            result["instanceTypes"] = arch_info.default_gpu_instances[:1]  # Use first one as default
        
        # Update architecture labels
        if "labels" not in result:
            result["labels"] = {}
        
        arch_labels = arch_manager.get_architecture_labels(architecture)
        result["labels"].update(arch_labels)
        
        # Update tags
        if "tags" not in result:
            result["tags"] = {}
        
        result["tags"]["Architecture"] = architecture.value
        
        return result


class TemplateLoader:
    """Loader for various template formats and sources."""
    
    DEFAULT_TEMPLATE_PATHS = [
        "templates/nodegroup_template.json",
        "nodegroup_template.json",  # backward compatibility
        "config/nodegroup_template.json"
    ]
    
    @classmethod
    def load_template(cls, template_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load a nodegroup template from file.
        
        Args:
            template_path: Path to template file (optional, will search defaults)
            
        Returns:
            Template dictionary
            
        Raises:
            TemplateError: If template cannot be loaded or is invalid
        """
        if template_path:
            paths_to_try = [template_path]
        else:
            paths_to_try = cls.DEFAULT_TEMPLATE_PATHS
        
        for path in paths_to_try:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        template = json.load(f)
                    
                    # Validate template
                    is_valid, issues = TemplateValidator.validate_template(template)
                    if not is_valid:
                        raise TemplateError(f"Invalid template in {path}: {'; '.join(issues)}")
                    
                    return template
                
                except json.JSONDecodeError as e:
                    raise TemplateError(f"Invalid JSON in template file {path}: {e}")
                except Exception as e:
                    raise TemplateError(f"Error loading template {path}: {e}")
        
        # No template found
        if template_path:
            raise TemplateError(f"Template file not found: {template_path}")
        else:
            raise TemplateError(f"No template file found. Searched: {', '.join(cls.DEFAULT_TEMPLATE_PATHS)}")
    
    @classmethod
    def create_default_template(cls, cluster_name: str = "", architecture: Architecture = Architecture.X86_64,
                               output_path: str = "nodegroup_template.json") -> str:
        """
        Create a default template file.
        
        Args:
            cluster_name: EKS cluster name
            architecture: Target architecture
            output_path: Output file path
            
        Returns:
            Path to created template file
            
        Raises:
            TemplateError: If template creation fails
        """
        from utils.architecture_utils import ArchitectureManager
        
        arch_manager = ArchitectureManager()
        arch_info = arch_manager.get_architecture_info(architecture)
        
        if not arch_info:
            raise TemplateError(f"Unsupported architecture: {architecture}")
        
        # Create architecture-specific template
        template = {
            "clusterName": cluster_name or "YOUR-CLUSTER-NAME",
            "nodegroupName": f"gpu-workers-{architecture.value}",
            "nodeRole": "arn:aws:iam::YOUR_ACCOUNT_ID:role/EKSNodeInstanceRole",
            "subnets": [
                "subnet-YOUR_SUBNET_1",
                "subnet-YOUR_SUBNET_2"
            ],
            "instanceTypes": arch_info.default_gpu_instances[:1],
            "amiType": arch_info.supported_ami_types[0].value,
            "capacityType": "ON_DEMAND",
            "diskSize": 50,
            "scalingConfig": {
                "minSize": 0,
                "maxSize": 10,
                "desiredSize": 1
            },
            "updateConfig": {
                "maxUnavailable": 1
            },
            "remoteAccess": {},
            "labels": arch_manager.get_architecture_labels(architecture),
            "taints": [],
            "tags": {
                "Environment": "production",
                "Project": "ml-workloads",
                "Architecture": architecture.value,
                "ManagedBy": "eks-nvidia-alignment-tool"
            }
        }
        
        # Add GPU-specific labels
        template["labels"].update({
            "node-type": "gpu-worker",
            "nvidia.com/gpu": "true"
        })
        
        # FIXED: Don't try to write file if output_path is empty
        if not output_path:
            # Return template as dict instead of writing to file
            return template
        
        try:
            with open(output_path, 'w') as f:
                json.dump(template, f, indent=2)
            
            return output_path
        
        except Exception as e:
            raise TemplateError(f"Error creating template file {output_path}: {e}")
    
    @classmethod
    def validate_and_load(cls, template_path: str) -> Tuple[Dict[str, Any], List[str]]:
        """
        Load and validate a template, returning both the template and any warnings.
        
        Args:
            template_path: Path to template file
            
        Returns:
            Tuple of (template_dict, warnings_list)
            
        Raises:
            TemplateError: If template cannot be loaded or has critical errors
        """
        template = cls.load_template(template_path)
        warnings = []
        
        # Additional validation beyond basic structure
        # Check for placeholder values
        placeholder_checks = [
            ("clusterName", ["YOUR-CLUSTER-NAME", "", "CLUSTER-NAME"]),
            ("nodeRole", ["YOUR_ACCOUNT_ID", "ACCOUNT_ID"]),
            ("subnets", ["YOUR_SUBNET", "SUBNET"])
        ]
        
        for field, placeholders in placeholder_checks:
            value = template.get(field)
            if isinstance(value, str):
                for placeholder in placeholders:
                    if placeholder in value:
                        warnings.append(f"Template contains placeholder value in {field}: {value}")
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        for placeholder in placeholders:
                            if placeholder in item:
                                warnings.append(f"Template contains placeholder value in {field}: {item}")
        
        # Check for reasonable instance types
        instance_types = template.get("instanceTypes", [])
        non_gpu_instances = ["t3.micro", "t3.small", "m5.large"]
        if any(inst in non_gpu_instances for inst in instance_types):
            warnings.append("Template uses CPU instance types for GPU nodegroup")
        
        return template, warnings


class TemplateGenerator:
    """Generator for creating templates based on requirements."""
    
    @staticmethod
    def generate_for_workload(workload_type: str, architecture: Architecture = Architecture.X86_64,
                            performance_tier: str = "standard") -> Dict[str, Any]:
        """
        Generate a template optimized for specific workload types.
        
        Args:
            workload_type: "ml-training", "ml-inference", "gaming", "rendering", "general-gpu"
            architecture: Target architecture
            performance_tier: "basic", "standard", "high", "extreme"
            
        Returns:
            Generated template dictionary
        """
        from utils.architecture_utils import ArchitectureManager
        
        arch_manager = ArchitectureManager()
        
        # Base template
        base_template = {
            "clusterName": "",
            "nodegroupName": f"{workload_type}-{architecture.value}",
            "nodeRole": "",
            "subnets": [],
            "capacityType": "ON_DEMAND",
            "scalingConfig": {"minSize": 0, "maxSize": 10, "desiredSize": 1},
            "updateConfig": {"maxUnavailable": 1},
            "remoteAccess": {},
            "labels": arch_manager.get_architecture_labels(architecture),
            "taints": [],
            "tags": {"WorkloadType": workload_type, "Architecture": architecture.value}
        }
        
        # Workload-specific configurations
        workload_configs = {
            "ml-training": {
                "instanceTypes": arch_manager.get_recommended_gpu_instances(architecture, performance_tier),
                "diskSize": 100,
                "labels": {"workload": "ml-training", "spot-ok": "true"},
                "capacityType": "SPOT" if performance_tier in ["basic", "standard"] else "ON_DEMAND"
            },
            "ml-inference": {
                "instanceTypes": arch_manager.get_recommended_gpu_instances(architecture, "standard"),
                "diskSize": 50,
                "labels": {"workload": "ml-inference"},
                "scalingConfig": {"minSize": 1, "maxSize": 20, "desiredSize": 2}
            },
            "gaming": {
                "instanceTypes": arch_manager.get_recommended_gpu_instances(architecture, "high"),
                "diskSize": 200,
                "labels": {"workload": "gaming"},
                "capacityType": "ON_DEMAND"
            },
            "rendering": {
                "instanceTypes": arch_manager.get_recommended_gpu_instances(architecture, "extreme"),
                "diskSize": 500,
                "labels": {"workload": "rendering"},
                "capacityType": "ON_DEMAND"
            },
            "general-gpu": {
                "instanceTypes": arch_manager.get_recommended_gpu_instances(architecture, performance_tier),
                "diskSize": 50,
                "labels": {"workload": "general-gpu"}
            }
        }
        
        # Apply workload-specific configuration
        if workload_type in workload_configs:
            config = workload_configs[workload_type]
            merger = TemplateMerger()
            base_template = merger.merge_configs(base_template, config)
        
        return base_template
    
    @staticmethod
    def generate_multi_architecture_templates(cluster_name: str, 
                                            architectures: List[Architecture]) -> Dict[str, Dict[str, Any]]:
        """
        Generate templates for multiple architectures.
        
        Args:
            cluster_name: EKS cluster name
            architectures: List of target architectures
            
        Returns:
            Dictionary mapping architecture names to templates
        """
        templates = {}
        
        for arch in architectures:
            # FIXED: Use the updated create_default_template that returns dict when no output_path
            template = TemplateLoader.create_default_template(
                cluster_name=cluster_name,
                architecture=arch,
                output_path=""  # Returns dict instead of writing file
            )
            templates[arch.value] = template
        
        return templates


# Convenience functions
def load_template(template_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to load a template.
    
    Args:
        template_path: Optional path to template file
        
    Returns:
        Template dictionary
    """
    return TemplateLoader.load_template(template_path)


def merge_template_overrides(template: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to merge template overrides.
    
    Args:
        template: Base template
        overrides: Override values
        
    Returns:
        Merged template
    """
    return TemplateMerger.merge_configs(template, overrides)


def validate_template(template: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Convenience function to validate a template.
    
    Args:
        template: Template to validate
        
    Returns:
        Tuple of (is_valid, issues_list)
    """
    return TemplateValidator.validate_template(template)