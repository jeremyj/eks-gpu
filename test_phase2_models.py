#!/usr/bin/env python3
"""
Test script for Phase 2 models: DriverAlignment and NodeGroupConfig
"""

import sys
import json
import tempfile
import os
from typing import Dict, Any

# Add the parent directory to Python path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from models.driver_alignment import DriverAlignment, AlignmentRequest
    from models.nodegroup_config import (
        NodeGroupConfig, NodeGroupConfigBuilder, ScalingConfig, 
        UpdateConfig, RemoteAccess, Taint
    )
    from models.ami_types import Architecture, AMIType
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure all Phase 1 and Phase 2 modules are in the correct directories:")
    print("  models/driver_alignment.py")
    print("  models/nodegroup_config.py") 
    print("  models/ami_types.py")
    sys.exit(1)


class TestResults:
    """Track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def test_pass(self, test_name: str):
        print(f"✅ {test_name}")
        self.passed += 1
    
    def test_fail(self, test_name: str, error: str):
        print(f"❌ {test_name}: {error}")
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"FAILED TESTS:")
            for error in self.errors:
                print(f"  • {error}")
        print(f"{'='*60}")
        return self.failed == 0


def test_driver_alignment_basic():
    """Test basic DriverAlignment functionality."""
    results = TestResults()
    
    try:
        # Test basic creation
        alignment = DriverAlignment(
            strategy="ami-first",
            k8s_version="1.32",
            architecture=Architecture.X86_64,
            ami_release_version="20250403",
            ami_driver_version="570.148.08-1.amzn2023",
            container_driver_version="570.148.08",
            formatted_driver_version="570_570.148.08-1.ubuntu2204",
            deb_urls=[
                "https://example.com/libnvidia-compute-570_570.148.08-1.ubuntu2204_amd64.deb",
                "# NOT FOUND: missing-package_570.148.08_amd64.deb"
            ],
            nodegroup_config={
                "ami_type": "AL2023_x86_64_NVIDIA",
                "architecture": "x86_64"
            }
        )
        results.test_pass("DriverAlignment creation")
        
        # Test properties
        if alignment.architecture_display == "x86_64":
            results.test_pass("architecture_display property")
        else:
            results.test_fail("architecture_display property", f"Expected 'x86_64', got '{alignment.architecture_display}'")
        
        if alignment.is_ami_first_strategy:
            results.test_pass("is_ami_first_strategy property")
        else:
            results.test_fail("is_ami_first_strategy property", "Should be True for ami-first strategy")
        
        if not alignment.is_container_first_strategy:
            results.test_pass("is_container_first_strategy property")
        else:
            results.test_fail("is_container_first_strategy property", "Should be False for ami-first strategy")
        
        # Test package analysis
        available_packages = alignment.get_container_packages()
        if len(available_packages) == 1 and available_packages[0]['package_name'] == 'libnvidia-compute-570':
            results.test_pass("get_container_packages")
        else:
            results.test_fail("get_container_packages", f"Expected 1 package, got {len(available_packages)}")
        
        missing_packages = alignment.get_missing_packages()
        if len(missing_packages) == 1:
            results.test_pass("get_missing_packages")
        else:
            results.test_fail("get_missing_packages", f"Expected 1 missing package, got {len(missing_packages)}")
        
        # Test validation
        is_valid, issues = alignment.validate()
        if is_valid:
            results.test_pass("DriverAlignment validation")
        else:
            results.test_fail("DriverAlignment validation", f"Validation failed: {issues}")
        
        # Test serialization
        alignment_dict = alignment.to_dict()
        if isinstance(alignment_dict, dict) and 'strategy' in alignment_dict:
            results.test_pass("to_dict serialization")
        else:
            results.test_fail("to_dict serialization", "Failed to create dictionary representation")
        
        # Test deserialization
        reconstructed = DriverAlignment.from_dict(alignment_dict)
        if reconstructed.strategy == alignment.strategy and reconstructed.k8s_version == alignment.k8s_version:
            results.test_pass("from_dict deserialization")
        else:
            results.test_fail("from_dict deserialization", "Reconstructed object doesn't match original")
        
    except Exception as e:
        results.test_fail("DriverAlignment basic tests", str(e))
    
    return results


def test_alignment_request():
    """Test AlignmentRequest functionality."""
    results = TestResults()
    
    try:
        # Test valid request
        request = AlignmentRequest(
            strategy="container-first",
            cluster_name="test-cluster",
            k8s_version="1.32",
            architecture="arm64",
            current_driver_version="570.148.08"
        )
        results.test_pass("AlignmentRequest creation")
        
        # Test validation
        is_valid, issues = request.validate()
        if is_valid:
            results.test_pass("AlignmentRequest validation")
        else:
            results.test_fail("AlignmentRequest validation", f"Validation failed: {issues}")
        
        # Test architecture normalization
        if request.architecture == "arm64":  # Should remain arm64
            results.test_pass("Architecture normalization (arm64)")
        else:
            results.test_fail("Architecture normalization", f"Expected 'arm64', got '{request.architecture}'")
        
        # Test AMD64 normalization
        request_amd64 = AlignmentRequest(
            strategy="ami-first",
            cluster_name="test",
            architecture="amd64"  # Should become x86_64
        )
        if request_amd64.architecture == "x86_64":
            results.test_pass("Architecture normalization (amd64 -> x86_64)")
        else:
            results.test_fail("Architecture normalization", f"Expected 'x86_64', got '{request_amd64.architecture}'")
        
        # Test architecture enum conversion
        arch_enum = request.get_architecture_enum()
        if arch_enum == Architecture.ARM64:
            results.test_pass("get_architecture_enum")
        else:
            results.test_fail("get_architecture_enum", f"Expected ARM64, got {arch_enum}")
        
        # Test invalid request
        invalid_request = AlignmentRequest(
            strategy="invalid-strategy",
            current_driver_version="570.148.08"
            # Missing required fields
        )
        is_valid, issues = invalid_request.validate()
        if not is_valid and len(issues) > 0:
            results.test_pass("AlignmentRequest invalid validation")
        else:
            results.test_fail("AlignmentRequest invalid validation", "Should have validation errors")
        
    except Exception as e:
        results.test_fail("AlignmentRequest tests", str(e))
    
    return results


def test_nodegroup_config_basic():
    """Test basic NodeGroupConfig functionality."""
    results = TestResults()
    
    try:
        # Test basic creation
        config = NodeGroupConfig(
            cluster_name="test-cluster",
            nodegroup_name="test-nodegroup",
            node_role="arn:aws:iam::123456789012:role/EKSNodeRole",
            subnets=["subnet-12345", "subnet-67890"]
        )
        results.test_pass("NodeGroupConfig creation")
        
        # Test validation
        is_valid, issues = config.validate()
        if is_valid:
            results.test_pass("NodeGroupConfig basic validation")
        else:
            results.test_fail("NodeGroupConfig basic validation", f"Validation failed: {issues}")
        
        # Test GPU defaults
        config.set_gpu_defaults(Architecture.ARM64)
        if "g5g.xlarge" in config.instance_types and config.labels.get("kubernetes.io/arch") == "arm64":
            results.test_pass("set_gpu_defaults ARM64")
        else:
            results.test_fail("set_gpu_defaults ARM64", f"Instance types: {config.instance_types}, arch label: {config.labels.get('kubernetes.io/arch')}")
        
        # Test AMI configuration
        config.set_ami_configuration(AMIType.AL2023_ARM_64_NVIDIA, "1.32", "20250403")
        if config.ami_type == "AL2023_ARM_64_NVIDIA" and config.version == "1.32":
            results.test_pass("set_ami_configuration")
        else:
            results.test_fail("set_ami_configuration", f"AMI type: {config.ami_type}, version: {config.version}")
        
        # Test AWS CLI format conversion
        aws_format = config.to_aws_cli_format()
        required_fields = ["clusterName", "nodegroupName", "nodeRole", "subnets"]
        if all(field in aws_format for field in required_fields):
            results.test_pass("to_aws_cli_format")
        else:
            missing = [f for f in required_fields if f not in aws_format]
            results.test_fail("to_aws_cli_format", f"Missing fields: {missing}")
        
        # Test JSON serialization
        json_str = config.to_json()
        if isinstance(json_str, str) and "clusterName" in json_str:
            results.test_pass("to_json serialization")
        else:
            results.test_fail("to_json serialization", "Failed to create JSON string")
        
    except Exception as e:
        results.test_fail("NodeGroupConfig basic tests", str(e))
    
    return results


def test_nodegroup_config_builder():
    """Test NodeGroupConfigBuilder functionality."""
    results = TestResults()
    
    try:
        # Test builder pattern
        config = (NodeGroupConfigBuilder()
                 .cluster_name("test-cluster")
                 .nodegroup_name("gpu-workers")
                 .node_role("arn:aws:iam::123456789012:role/EKSNodeRole")
                 .subnets(["subnet-12345", "subnet-67890"])
                 .gpu_config(Architecture.X86_64)
                 .ami_config(AMIType.AL2023_X86_64_NVIDIA, "1.32", "20250403")
                 .scaling(1, 5, 2)
                 .instance_types(["g5.xlarge"])
                 .capacity_type("SPOT")
                 .labels({"environment": "test"})
                 .tags({"project": "ml"})
                 .build())
        
        results.test_pass("NodeGroupConfigBuilder creation")
        
        # Validate built configuration
        is_valid, issues = config.validate()
        if is_valid:
            results.test_pass("NodeGroupConfigBuilder validation")
        else:
            results.test_fail("NodeGroupConfigBuilder validation", f"Validation failed: {issues}")
        
        # Check specific configurations
        if (config.cluster_name == "test-cluster" and 
            config.scaling_config.desired_size == 2 and 
            config.capacity_type == "SPOT" and 
            config.labels.get("environment") == "test"):
            results.test_pass("NodeGroupConfigBuilder configuration")
        else:
            results.test_fail("NodeGroupConfigBuilder configuration", "Configuration not applied correctly")
        
    except Exception as e:
        results.test_fail("NodeGroupConfigBuilder tests", str(e))
    
    return results


def test_nodegroup_config_template_operations():
    """Test template loading and merging."""
    results = TestResults()
    
    try:
        # Create a temporary template file
        template_data = {
            "clusterName": "template-cluster",
            "nodegroupName": "template-nodegroup",
            "nodeRole": "arn:aws:iam::123456789012:role/EKSNodeRole",
            "subnets": ["subnet-12345"],
            "instanceTypes": ["m5.large"],
            "labels": {"template": "true"},
            "scalingConfig": {"minSize": 0, "maxSize": 5, "desiredSize": 1}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(template_data, f)
            template_file = f.name
        
        try:
            # Test loading from template
            config = NodeGroupConfig.from_template_file(template_file)
            if config.cluster_name == "template-cluster":
                results.test_pass("from_template_file")
            else:
                results.test_fail("from_template_file", f"Expected 'template-cluster', got '{config.cluster_name}'")
            
            # Test merging overrides
            overrides = {
                "instanceTypes": ["g5.xlarge"],
                "labels": {"environment": "prod"},
                "scalingConfig": {"desiredSize": 3}
            }
            
            merged_config = config.merge_overrides(overrides)
            
            # Check that overrides were applied correctly
            if (merged_config.instance_types == ["g5.xlarge"] and 
                merged_config.labels.get("environment") == "prod" and 
                merged_config.labels.get("template") == "true" and  # Original label preserved
                merged_config.scaling_config.desired_size == 3):
                results.test_pass("merge_overrides")
            else:
                results.test_fail("merge_overrides", "Overrides not applied correctly")
            
        finally:
            # Clean up temporary file
            os.unlink(template_file)
        
    except Exception as e:
        results.test_fail("Template operations tests", str(e))
    
    return results


def test_nested_config_objects():
    """Test nested configuration objects."""
    results = TestResults()
    
    try:
        # Test ScalingConfig
        scaling = ScalingConfig(min_size=1, max_size=10, desired_size=5)
        is_valid, issues = scaling.validate()
        if is_valid:
            results.test_pass("ScalingConfig validation")
        else:
            results.test_fail("ScalingConfig validation", f"Issues: {issues}")
        
        # Test invalid ScalingConfig
        invalid_scaling = ScalingConfig(min_size=5, max_size=2, desired_size=3)
        is_valid, issues = invalid_scaling.validate()
        if not is_valid:
            results.test_pass("ScalingConfig invalid validation")
        else:
            results.test_fail("ScalingConfig invalid validation", "Should have validation errors")
        
        # Test UpdateConfig
        update = UpdateConfig(max_unavailable=2)
        update_dict = update.to_dict()
        if update_dict.get("maxUnavailable") == 2:
            results.test_pass("UpdateConfig")
        else:
            results.test_fail("UpdateConfig", f"Expected maxUnavailable=2, got {update_dict}")
        
        # Test Taint
        taint = Taint(key="nvidia.com/gpu", value="true", effect="NO_SCHEDULE")
        is_valid, issues = taint.validate()
        if is_valid:
            results.test_pass("Taint validation")
        else:
            results.test_fail("Taint validation", f"Issues: {issues}")
        
        taint_dict = taint.to_dict()
        if taint_dict.get("key") == "nvidia.com/gpu" and taint_dict.get("effect") == "NO_SCHEDULE":
            results.test_pass("Taint to_dict")
        else:
            results.test_fail("Taint to_dict", f"Taint dict: {taint_dict}")
        
    except Exception as e:
        results.test_fail("Nested config objects tests", str(e))
    
    return results


def main():
    """Run all Phase 2 tests."""
    print("🧪 TESTING PHASE 2 MODELS")
    print("=" * 60)
    
    all_results = TestResults()
    
    # Run all test suites
    test_suites = [
        ("DriverAlignment Basic", test_driver_alignment_basic),
        ("AlignmentRequest", test_alignment_request),
        ("NodeGroupConfig Basic", test_nodegroup_config_basic),
        ("NodeGroupConfigBuilder", test_nodegroup_config_builder),
        ("Template Operations", test_nodegroup_config_template_operations),
        ("Nested Config Objects", test_nested_config_objects)
    ]
    
    for suite_name, test_func in test_suites:
        print(f"\n📋 {suite_name}:")
        suite_results = test_func()
        all_results.passed += suite_results.passed
        all_results.failed += suite_results.failed
        all_results.errors.extend(suite_results.errors)
    
    # Print summary
    success = all_results.summary()
    
    if success:
        print("🎉 All Phase 2 tests passed!")
        return 0
    else:
        print("💥 Some Phase 2 tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())